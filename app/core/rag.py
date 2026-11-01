import json
import requests
import chromadb
from app.core.config import settings
from app.core.llm import get_llm_response

# 初始化本地持久化的 Chroma 客户端（数据存在 .chroma 文件夹）
client = chromadb.PersistentClient(path="./.chroma")
collection = client.get_or_create_collection(name="job_descriptions")

def get_embedding(text: str):
    """调用智谱 API 生成文本向量"""
    url = "https://open.bigmodel.cn/api/paas/v4/embeddings"
    headers = {"Authorization": f"Bearer {settings.zhipuai_api_key}"}
    payload = {"model": "embedding-3", "input": text}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10).json()
        return res["data"][0]["embedding"]
    except Exception as e:
        print(f"获取向量失败: {e}")
        return None

def add_jd_to_kb(job_name: str, jd_text: str):
    """将岗位 JD 存入 Chroma"""
    emb = get_embedding(jd_text)
    if emb:
        collection.add(
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
            "请对每个候选与用户目标的匹配度打 0-100 分，仅输出 JSON 数组，"
            "格式：[{'index':0,'score':90}, ...]，不要任何解释。"
        )
        raw = get_llm_response([{"role": "user", "content": prompt}], temperature=0.1)
        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw[7:-3].strip()
        elif raw.startswith("```"):
            raw = raw[3:-3].strip()
        scores = json.loads(raw)
        score_map = {int(s["index"]): float(s["score"]) for s in scores}
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