import requests
import chromadb
from app.core.config import settings

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