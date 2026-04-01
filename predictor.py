#!/usr/bin/env python3
"""
趋势预测模块 - 基于历史新闻分析趋势
"""
import json
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_CONFIDENCE_THRESHOLD = 0.6


class TrendPredictor:
    """趋势预测器"""
    
    def __init__(self, model_client, config: dict = None):
        self.client = model_client
        self.config = config or {}
        self.lookback_days = self.config.get("lookback_days", DEFAULT_LOOKBACK_DAYS)
        self.confidence_threshold = self.config.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
        
        # 趋势类别配置
        self.categories = {
            "宏观观察": ["宏观", "经济", "GDP", "通胀", "利率", "美联储", "央行", "政策"],
            "科技前沿": ["科技", "AI", "芯片", "互联网", "软件", "技术", "创新"],
            "金融投资": ["投资", "股市", "股票", "基金", "债券", "资管", "私募"],
            "消费动态": ["消费", "零售", "电商", "食品", "饮料", "汽车", "地产"],
            "地缘政治": ["伊朗", "俄乌", "中美", "贸易战", "关税", "制裁", "外交"],
        }
    
    def analyze_trends(self, news_list: list) -> dict:
        """分析趋势"""
        if not news_list:
            return {"trends": [], "summary": "无新闻数据"}
        
        # 按类别分组
        category_news = self._categorize_news(news_list)
        
        # 分析每个类别
        trends = []
        for category, news in category_news.items():
            if not news:
                continue
            
            # 计算平均分数
            scores = [n.get("score", 50) for n in news]
            avg_score = sum(scores) / len(scores) if scores else 0
            
            # 提取关键词
            keywords = self._extract_keywords(news)
            
            # 生成趋势预测
            prediction = self._predict_category_trend(category, news, keywords)
            
            trends.append({
                "category": category,
                "news_count": len(news),
                "avg_score": round(avg_score, 1),
                "keywords": keywords[:5],
                "trend": prediction["trend"],
                "confidence": prediction["confidence"],
                "summary": prediction["summary"],
            })
        
        # 按置信度排序
        trends.sort(key=lambda x: x["confidence"], reverse=True)
        
        # 生成总体趋势总结
        overall_summary = self._generate_overall_summary(trends)
        
        return {
            "trends": trends,
            "summary": overall_summary,
            "analyzed_date": datetime.now().strftime("%Y-%m-%d"),
        }
    
    def _categorize_news(self, news_list: list) -> dict:
        """按类别分组新闻"""
        category_news = defaultdict(list)
        
        for news in news_list:
            title = news.get("title", "")
            content = news.get("content", news.get("summary", ""))
            text = f"{title} {content}"
            
            assigned = False
            for category, keywords in self.categories.items():
                for keyword in keywords:
                    if keyword in text:
                        category_news[category].append(news)
                        assigned = True
                        break
                if assigned:
                    break
            
            if not assigned:
                category_news["其他资讯"].append(news)
        
        return dict(category_news)
    
    def _extract_keywords(self, news_list: list) -> list:
        """提取关键词"""
        all_keywords = []
        
        for news in news_list:
            title = news.get("title", "")
            # 简单分词 - 提取英文单词和中文关键词
            import re
            words = re.findall(r'[A-Z][a-zA-Z]+|\d+[%]?|[^\s\d,，。、]+', title)
            all_keywords.extend(words[:3])
        
        # 统计频率
        from collections import Counter
        counter = Counter(all_keywords)
        return [word for word, _ in counter.most_common(10)]
    
    def _predict_category_trend(self, category: str, news_list: list, keywords: list) -> dict:
        """预测类别趋势"""
        # 构建分析提示
        top_news = news_list[:5] if len(news_list) > 5 else news_list
        news_summary = "\n".join([f"- {n.get('title', '')[:60]}" for n in top_news])
        
        prompt = f"""请分析以下新闻的趋势。

类别：{category}
近期新闻：
{news_summary}

请预测：
1. 趋势方向：上涨/下跌/震荡/不变
2. 置信度：0.0-1.0
3. 一句话总结

请按JSON格式返回：
{{
  "trend": "上涨/下跌/震荡/不变",
  "confidence": 0.0-1.0,
  "summary": "一句话总结"
}}

只返回JSON。"""
        
        try:
            response = self.client.chat("你是一个专业的市场趋势分析师。", prompt)
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        # 默认返回值
        return {
            "trend": "震荡",
            "confidence": 0.5,
            "summary": f"{category}趋势不明朗，需更多数据"
        }
    
    def _generate_overall_summary(self, trends: list) -> str:
        """生成总体趋势总结"""
        if not trends:
            return "无足够数据进行趋势分析"
        
        # 获取高置信度趋势
        high_conf = [t for t in trends if t["confidence"] >= self.confidence_threshold]
        
        if not high_conf:
            return f"整体趋势震荡，各类别趋势不明朗"
        
        # 生成总结
        summary_parts = []
        for trend in high_conf[:3]:
            summary_parts.append(
                f"{trend['category']}:{trend['trend']}(置信度:{int(trend['confidence']*100)}%)"
            )
        
        return "；".join(summary_parts)


def create_predictor(model_client, config: dict = None) -> TrendPredictor:
    """创建预测器"""
    return TrendPredictor(model_client, config)