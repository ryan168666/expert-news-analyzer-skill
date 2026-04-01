#!/usr/bin/env python3
"""
新闻价值评分器 - 基于多维度AI评估
"""
import json
import yaml
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 评分维度配置
SCORING_DIMENSIONS = {
    "信息价值": 30,      # 信息的重要性和独特性
    "影响力": 25,         # 对市场/行业的影响程度
    "时效性": 20,         # 时间敏感度
    "独特性": 15,        # 独家vs普通新闻
    "可操作性": 10,       # 投资参考价值
}

DEFAULT_MIN_SCORE = 40
SIMILARITY_THRESHOLD = 0.7


class NewsScorer:
    """新闻价值评分器"""
    
    def __init__(self, model_client, config: dict = None):
        self.client = model_client
        self.config = config or {}
        self.min_score = self.config.get("min_score", DEFAULT_MIN_SCORE)
        self.enable_dedup = self.config.get("enable_dedup", True)
        self.similarity_threshold = self.config.get("similarity_threshold", SIMILARITY_THRESHOLD)
    
    def score_news(self, news_item: dict) -> dict:
        """对单条新闻进行价值评分"""
        title = news_item.get("title", "")
        content = news_item.get("content", news_item.get("summary", ""))
        
        if not title:
            return {"score": 0, "reason": "无标题", "dimensions": {}}
        
        # 构建评分提示词
        prompt = self._build_score_prompt(title, content)
        
        try:
            response = self.client.chat(
                "你是一个专业的新闻价值评估专家。", 
                prompt
            )
            result = self._parse_score_response(response)
            result["title"] = title
            result["news"] = news_item
            return result
        except Exception as e:
            return {
                "score": 50,  # 默认分数
                "reason": f"评估失败: {str(e)}",
                "dimensions": {},
                "title": title,
                "news": news_item
            }
    
    def _build_score_prompt(self, title: str, content: str) -> str:
        """构建评分提示词"""
        return f"""请对以下新闻进行0-100分的价值评估。

新闻标题：{title}
新闻内容：{content}

评估维度及权重：
- 信息价值 (30%): 信息的重要性和独特性
- 影响力 (25%): 对市场/行业的影响程度  
- 时效性 (20%): 时间敏感度
- 独特性 (15%): 独家vs普通新闻
- 可操作性 (10%): 投资参考价值

请按以下JSON格式返回评估结果：
{{
  "信息价值": 分数(0-100),
  "影响力": 分数(0-100),
  "时效性": 分数(0-100),
  "独特性": 分数(0-100),
  "可操作性": 分数(0-100),
  "总分数": 加权总分,
  "评估理由": "一句话说明"
}}

只返回JSON，不要其他内容。"""

    def _parse_score_response(self, response: str) -> dict:
        """解析评分响应"""
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                # 计算加权总分
                total = 0
                for dim, weight in SCORING_DIMENSIONS.items():
                    if dim in data:
                        total += data[dim] * weight / 100
                data["score"] = int(total)
                return data
        except:
            pass
        return {"score": 50, "reason": response[:100], "dimensions": {}}
    
    def score_batch(self, news_list: list, max_workers: int = 5) -> list:
        """批量评分"""
        scored_news = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.score_news, news): news for news in news_list}
            for future in futures:
                result = future.result()
                if result["score"] >= self.min_score:
                    scored_news.append(result)
        
        # 按分数排序
        scored_news.sort(key=lambda x: x["score"], reverse=True)
        return scored_news
    
    def deduplicate(self, news_list: list) -> list:
        """去重 - 基于标题相似度"""
        if not self.enable_dedup:
            return news_list
        
        unique_news = []
        for news in news_list:
            is_duplicate = False
            title = news.get("title", "").lower()
            
            for existing in unique_news:
                existing_title = existing.get("title", "").lower()
                # 简单相似度检查
                if self._calculate_similarity(title, existing_title) > self.similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_news.append(news)
        
        return unique_news
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        # 简单词集合相似度
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0


def create_scorer(model_client, config: dict = None) -> NewsScorer:
    """创建评分器"""
    return NewsScorer(model_client, config)

# ============================================
# 客观评分系统 (不依赖LLM)
# ============================================

# 投资相关关键词及权重
KEYWORDS = {
    # 宏观政策
    "美联储": 10, "降息": 10, "加息": 9, "QE": 9, "QT": 8,
    "央行": 8, "货币政策": 9, "财政": 8, "通胀": 9, "CPI": 9,
    "非农": 10, "GDP": 8, "PMI": 9, "LPR": 9, "利率": 8,
    
    # 地缘政治
    "伊朗": 9, "以色列": 9, "战争": 9, "冲突": 8, "制裁": 9,
    "中美": 9, "贸易战": 9, "关税": 8, "谈判": 7,
    
    # 公司/行业
    "财报": 8, "营收": 7, "利润": 8, "财报季": 9, "业绩": 8,
    "CEO": 7, "董事长": 7, "离职": 7, "裁员": 8,
    "收购": 8, "并购": 8, "上市": 8, "IPO": 8,
    
    # 科技趋势
    "AI": 9, "人工智能": 9, "大模型": 8, "GPT": 8, "OpenAI": 8,
    "英伟达": 9, "NVIDIA": 9, "AMD": 8, "芯片": 8, "半导体": 8,
    "特斯拉": 8, "电动车": 8, "自动驾驶": 8,
    
    # 金融投资
    "股票": 6, "基金": 7, "ETF": 7, "指数": 7,
    "比特币": 8, "BTC": 8, "加密货币": 8, "黄金": 8,
    "石油": 8, "原油": 8, "天然气": 7, "大宗商品": 7,
    
    # 市场动态
    "大涨": 9, "暴跌": 9, "涨停": 8, "跌停": 8, "熔断": 9,
    "泡沫": 8, "危机": 9, "风险": 7,
    "BlackRock": 9, "高盛": 8, "摩根": 8, "贝莱德": 9,
    
    # 中国相关
    "A股": 8, "港股": 8, "上证": 7, "创业板": 7, "科创板": 8,
    "房地产": 8, "房价": 7, "恒大": 8, "万科": 7,
}

# 新闻来源权威性权重
SOURCE_WEIGHTS = {
    "Bloomberg": 10, "Reuters": 10, "华尔街日报": 9, "FT": 9, "WSJ": 9,
    "华尔街见闻": 8, "财新": 8, "第一财经": 7,
    "36kr": 7, "TechCrunch": 8,
    "新浪财经": 7, "东方财富": 7, "同花顺": 7, "雪球": 7,
    "BBC": 7, "CNN": 7, "NYT": 8,
}

def objective_score(news_item: dict) -> dict:
    """
    客观评分：基于关键词+来源权重
    """
    title = news_item.get("title", "")
    content = news_item.get("content", "")[:300]
    source = news_item.get("source", "")
    
    # 1. 关键词分数 (0-70)
    keyword_score = 0
    found_keywords = []
    text = (title + content).lower()
    
    for keyword, weight in KEYWORDS.items():
        kw = keyword.lower()
        if kw in text:
            keyword_score += weight
            found_keywords.append(keyword)
    
    keyword_score = min(70, keyword_score)
    
    # 2. 来源权重 (0-20)
    source_score = 0
    for src, weight in SOURCE_WEIGHTS.items():
        if src.lower() in source.lower():
            source_score = weight
            break
    
    # 3. 时间分数 (0-10)
    time_score = 10
    
    # 总分
    total = keyword_score + min(20, source_score) + time_score
    total = min(100, int(total))
    
    return {
        "score": total,
        "keyword_score": keyword_score,
        "source_score": source_score,
        "found_keywords": found_keywords[:5],
        "reason": f"{', '.join(found_keywords[:3])}" if found_keywords else "无"
    }

def calc_signal_strength(score: int) -> str:
    """计算信号强度"""
    if score <= 30:
        return "低"
    elif score <= 60:
        return "中"
    else:
        return "高"

