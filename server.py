#!/usr/bin/env python3
"""
FastAPI 服务器 - RAG 接口封装
用法: python server.py
"""
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yaml

# 添加 scripts 目录到路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from rag import SimpleRAG
from model_client import create_client


# ============ 全局单例 ============
rag_instance: Optional[SimpleRAG] = None
client_instance = None


def load_config() -> dict:
    """加载配置"""
    config_file = SCRIPT_DIR / "config.yaml"
    if config_file.exists():
        return yaml.safe_load(config_file.read_text(encoding="utf-8"))
    return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时加载知识库"""
    global rag_instance, client_instance
    
    config = load_config()
    
    # 加载知识库
    rag_config = config.get('rag', {})
    knowledge_dir = SCRIPT_DIR.parent / rag_config.get('knowledge_dir', 'knowledge')
    
    rag_instance = SimpleRAG(
        knowledge_dir=str(knowledge_dir),
        top_k=rag_config.get('top_k', 3),
        chunk_size=rag_config.get('chunk_size', 500)
    )
    
    # 加载所有启用的专家
    expert_ids = config.get('enabled_experts', [])
    if expert_ids:
        stats = rag_instance.load_all_experts(expert_ids)
        print(f"✅ 知识库加载完成: {stats}")
    
    # 初始化模型客户端
    try:
        client_instance = create_client(config)
        print(f"✅ 模型客户端: {config.get('model_name', 'unknown')}")
    except Exception as e:
        print(f"⚠️ 模型客户端初始化失败: {e}")
    
    yield
    
    # 清理
    rag_instance = None
    client_instance = None


# ============ FastAPI 应用 ============
app = FastAPI(
    title="Expert News Analyzer API",
    description="RAG 知识检索 + 新闻分析 API",
    version="2.2.0",
    lifespan=lifespan
)


# ============ 请求模型 ============
class RetrieveRequest(BaseModel):
    expert_id: str
    query: str
    top_k: int = 3


class AnalyzeRequest(BaseModel):
    query: str
    news_title: str
    news_content: str = ""


# ============ Endpoints ============
@app.get("/")
async def root():
    return {"message": "Expert News Analyzer API v2.2", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok", "rag_loaded": rag_instance is not None}


@app.get("/stats")
async def stats():
    """返回知识库加载状态"""
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG 未初始化")
    return {
        "experts": rag_instance.get_stats(),
        "total_chunks": sum(rag_instance.get_stats().values())
    }


@app.post("/retrieve")
async def retrieve(request: RetrieveRequest):
    """检索知识片段"""
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG 未初始化")
    
    results = rag_instance.retrieve(
        expert_id=request.expert_id,
        query=request.query,
        top_k=request.top_k
    )
    
    return {
        "expert_id": request.expert_id,
        "query": request.query,
        "results": results
    }


@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    """分析新闻"""
    if not client_instance:
        raise HTTPException(status_code=503, detail="模型客户端未初始化")
    
    # 使用 RAG 检索上下文
    knowledge_context = ""
    if rag_instance:
        for expert_id in ["buffett", "musk", "wood"]:
            kb = rag_instance.retrieve(expert_id, request.query)
            if kb:
                snippets = [item['content'][:150] for item in kb[:2]]
                knowledge_context = "\n\n参考: " + " | ".join(snippets)
                break
    
    # 构建提示
    prompt = f"""新闻标题：{request.news_title}
新闻内容：{request.news_content}

请用50-100字分析这条新闻对投资的影响。"""
    
    if knowledge_context:
        prompt += f"\n\n{knowledge_context}"
    
    try:
        response = client_instance.chat(
            "你是一个专业的投资分析师。",
            prompt
        )
        return {
            "query": request.query,
            "analysis": response,
            "knowledge_used": bool(knowledge_context)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


# ============ 主入口 ============
if __name__ == "__main__":
    import uvicorn
    print("🚀 启动 Expert News Analyzer API...")
    print("📖 文档: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)