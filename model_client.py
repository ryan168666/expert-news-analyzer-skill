#!/usr/bin/env python3
"""
多模型客户端 - 支持自选大模型
"""
import os
import requests
from pathlib import Path

class ModelClient:
    """统一模型客户端接口"""
    
    def __init__(self, provider: str, model_name: str, api_key: str = None):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key or self._load_api_key()
    
    def _load_api_key(self) -> str:
        """从配置文件或环境变量加载API Key"""
        # 优先从环境变量读取
        api_key = os.environ.get("LLM_API_KEY")
        if api_key:
            return api_key
        
        # 从 api_key.txt 读取
        key_file = Path(__file__).parent / "api_key.txt"
        if key_file.exists():
            return key_file.read_text().strip()
        
        raise ValueError(f"未找到 {self.provider} 的API Key")
    
    def chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
        """通用聊天接口"""
        if self.provider == "zhipu":
            return self._chat_zhipu(system_prompt, user_prompt, max_tokens)
        elif self.provider == "openai":
            return self._chat_openai(system_prompt, user_prompt, max_tokens)
        elif self.provider == "anthropic":
            return self._chat_anthropic(system_prompt, user_prompt, max_tokens)
        elif self.provider == "ollama":
            return self._chat_ollama(system_prompt, user_prompt, max_tokens)
        else:
            raise ValueError(f"不支持的模型提供商: {self.provider}")
    
    def _chat_zhipu(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {
            "model": self.model_name or "glm-4",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens
        }
        try:
            r = requests.post(url, headers=headers, json=data, timeout=30)
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"智谱API调用失败: {str(e)[:50]}"
    
    def _chat_openai(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {
            "model": self.model_name or "gpt-4o",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens
        }
        try:
            r = requests.post(url, headers=headers, json=data, timeout=30)
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"OpenAI API调用失败: {str(e)[:50]}"
    
    def _chat_anthropic(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model_name or "claude-3-5-sonnet-20241022",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}]
        }
        try:
            r = requests.post(url, headers=headers, json=data, timeout=30)
            return r.json()["content"][0]["text"]
        except Exception as e:
            return f"Anthropic API调用失败: {str(e)[:50]}"
    
    def _chat_ollama(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        url = "http://localhost:11434/api/chat"
        headers = {"Content-Type": "application/json"}
        data = {
            "model": self.model_name or "qwen2.5:7b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "options": {"temperature": 0.7, "num_predict": max_tokens}
        }
        try:
            r = requests.post(url, headers=headers, json=data, timeout=60)
            return r.json()["message"]["content"]
        except Exception as e:
            return f"Ollama调用失败: {str(e)[:50]}"


def create_client(config: dict) -> ModelClient:
    """从配置创建模型客户端"""
    provider = config.get("model_provider", "zhipu")
    model_name = config.get("model_name", "glm-4")
    api_key = config.get("api_key", "")
    
    return ModelClient(provider, model_name, api_key if api_key else None)
