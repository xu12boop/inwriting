import json
import re
import requests
import chromadb
from app.core.config import settings
from app.core.llm import get_llm_response

# 初始化本地持久化的 Chroma 客户端（目录可通过 CHROMA_DIR 配置，默认 ./.chroma）
client = chromadb.PersistentClient(path=settings.chroma_dir)
collection = client.get_or_create_collection(name="job_descriptions")

def get_embedding(text: str):
    """调用智谱 API 生成文本向量"""
    url = f"{settings.llm_base_url}/embeddings"
    headers = {"Authorization": f"Bearer {settings.zhipuai_api_key}"}
    payload = {"model": settings.embedding_model, "input": text}
    try:
        res = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=(settings.llm_timeout_connect, settings.llm_timeout_read),
        ).json()
        return res["data"][0]["embedding"]
    except Exception as e:
        print(f"获取向量失败: {e}")
        return None

def add_jd_to_kb(job_name: str, jd_text: str):
    """将岗位 JD 存入 Chroma（使用 upsert，重复写入同一岗位不会报错）"""
    emb = get_embedding(jd_text)
    if emb:
        collection.upsert(
            embeddings=[emb],
            documents=[jd_text],
            metadatas=[{"job_name": job_name}],
            ids=[job_name] # 用岗位名做唯一标识，防止重复
        )
        print(f"✅ 岗位 {job_name} 的 JD 已存入向量库")

def search_jd(job_name: str) -> str:
    """根据岗位名去检索最匹配的 JD"""
    emb = get_embedding(job_name)
    if not emb:
        return "暂无岗位JD信息。"
    
    results = collection.query(
        query_embeddings=[emb],
        n_results=1
    )
    if results['documents'] and len(results['documents'][0]) > 0:
        return results['documents'][0][0]
    return "暂无岗位JD信息。"


def search_jd_top_k(job_name: str, k: int = 5) -> list:
    """向量召回 Top-K 候选 JD（双路召回的第一路：语义向量）。"""
    emb = get_embedding(job_name)
    if not emb:
        return []
    k = max(1, min(k, collection.count() or 1))
    res = collection.query(query_embeddings=[emb], n_results=k)
    out = []
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        out.append({
            "job_name": (meta or {}).get("job_name", "岗位"),
            "snippet": (doc or "")[:200],
            "distance": round(float(dist), 4),
        })
    return out


def _parse_rerank_scores(raw: str) -> dict:
    """把重排结果解析成 {index: score}。

    大模型对"仅输出 JSON"的遵从度并不稳定：常见三种偏差是 ```json 围栏、
    用单引号、把数组包成 {"0": 90} 的对象。逐个兜住，避免一次格式抖动
    就把整条检索链打回向量距离（那会把"AI 应用开发"检索成"前端工程师"）。
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text[3:]
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()

    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        body = text[start : end + 1]
        try:
            data = json.loads(body)
            return {int(s["index"]): float(s["score"]) for s in data if "index" in s}
        except Exception:
            # 单引号 / 尾逗号等：退到逐条正则
            pairs = re.findall(
                r"index\D{0,4}(\d+)\D{0,8}score\D{0,4}(\d+(?:\.\d+)?)", body
            )
            if pairs:
                return {int(i): float(s) for i, s in pairs}

    # 对象形式 {"0": 90, "1": 45}
    try:
        obj = json.loads(text[text.find("{") : text.rfind("}") + 1])
        if isinstance(obj, dict):
            return {int(k): float(v) for k, v in obj.items() if str(k).isdigit()}
    except Exception:
        pass

    raise ValueError(f"无法解析重排结果: {text[:80]}")


def rerank_with_llm(query: str, candidates: list) -> list:
    """第二路召回 + 重排：用大模型对候选 JD 做相关性打分，返回按分数降序的列表。

    候选为空或模型异常时直接回退到向量距离排序（距离越小越相关）。
    """
    if not candidates:
        return []
    try:
        items = "\n".join(
            f"[{i}] {c['job_name']}: {c['snippet']}" for i, c in enumerate(candidates)
        )
        prompt = (
            f"用户目标岗位关键词：{query}\n"
            f"以下是向量召回的候选岗位 JD：\n{items}\n\n"
            '请对每个候选与用户目标的匹配度打 0-100 分，仅输出 JSON 数组，'
            '格式：[{"index": 0, "score": 90}, {"index": 1, "score": 40}]，不要任何解释。'
        )
        raw = get_llm_response([{"role": "user", "content": prompt}], temperature=0.1)
        score_map = _parse_rerank_scores(raw)
        for i, c in enumerate(candidates):
            c["rerank_score"] = score_map.get(i, 0.0)
    except Exception as e:
        print(f"重排失败，回退向量距离排序: {e}")
        for c in candidates:
            c["rerank_score"] = round((1.0 - float(c.get("distance", 1.0))) * 100, 2)
    candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    return candidates


def get_best_match_reranked(job_name: str, k: int = 5) -> dict:
    """端到端：向量召回 Top-K → 大模型重排 → 返回最佳 JD、引用片段与得分。

    返回 {'jd': str, 'citation': str, 'score': float, 'job_name': str}
    """
    cands = search_jd_top_k(job_name, k=k)
    if not cands:
        return {"jd": "暂无岗位JD信息。", "citation": "", "score": 0.0, "job_name": ""}
    ranked = rerank_with_llm(job_name, cands)
    best = ranked[0]
    return {
        "jd": best["snippet"],
        "citation": f"{best['job_name']}（匹配度 {best.get('rerank_score', 0):.0f}/100）",
        "score": best.get("rerank_score", 0.0),
        "job_name": best["job_name"],
    }