"""RAG (Retrieval-Augmented Generation) 模块 v2.0
   升级：时间权重 + 同义词扩展 + 去重
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


# ============ 同义词词典 ============
SYNONYMS = {
    # 货币/利率
    "加息": ["收紧货币政策", "提高利率", "基准利率上调", "紧缩货币"],
    "降息": ["宽松货币政策", "降低利率", "基准利率下调", "货币宽松"],
    "缩表": ["量化紧缩", "QT", "缩减资产负债表"],
    "放水": ["量化宽松", "QE", "宽松货币"],
    
    # 经济指标
    "GDP": ["国内生产总值", "经济总量"],
    "CPI": ["消费者价格指数", "通胀率"],
    "PPI": ["生产者价格指数", "工业品价格"],
    "非农": ["非农就业", "ADP就业"],
    "失业率": ["jobless rate", "unemployment"],
    
    # 市场
    "牛市": ["上涨趋势", "多头市场", "上升行情"],
    "熊市": ["下跌趋势", "空头市场", "下行行情"],
    "震荡": ["波动", "区间震荡", "横盘"],
    "崩盘": ["暴跌", "市场大跌", "金融危机"],
    
    # 人物
    "美联储": ["Fed", "美国央行", "Federal Reserve"],
    "鲍威尔": ["Powell", "美联储主席"],
    "耶伦": ["Yellen", "美国财长"],
    "巴菲特": ["Warren Buffett", "Warren"],
    "马斯克": ["Elon Musk", "Musk", "Tesla"],
    
    # 投资策略
    "价值投资": ["value investing", "基本面投资"],
    "成长投资": ["growth investing", "成长股"],
    "分散投资": ["diversification", "仓位分散", "配置"],
    "止损": ["stop loss", "割肉", "风控止损"],
}

HALF_LIFE_DAYS = 180  # 半衰期6个月


class SimpleRAG:
    """知识库检索 v2.0"""
    
    def __init__(self, knowledge_dir: str, top_k: int = 3, chunk_size: int = 500):
        self.knowledge_dir = Path(knowledge_dir)
        self.top_k = top_k
        self.chunk_size = chunk_size
        self.expert_knowledge: Dict[str, List[Dict]] = {}
    
    def load_expert_knowledge(self, expert_id: str) -> int:
        expert_dir = self.knowledge_dir / expert_id
        if not expert_dir.exists():
            return 0
        
        files_loaded = 0
        chunks = []
        
        for md_file in expert_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding='utf-8')
                text_chunks = self._chunk_text(content)
                for chunk in text_chunks:
                    if len(chunk.strip()) > 50:
                        chunks.append({
                            'file': md_file.name,
                            'content': chunk.strip()
                        })
                files_loaded += 1
            except Exception as e:
                print(f"  ! {md_file.name}: {e}")
        
        self.expert_knowledge[expert_id] = chunks
        return files_loaded
    
    def load_all_experts(self, expert_ids: List[str]) -> Dict[str, int]:
        results = {}
        for expert_id in expert_ids:
            results[expert_id] = self.load_expert_knowledge(expert_id)
        return results
    
    def _chunk_text(self, text: str) -> List[str]:
        """文本分块，带 15% 重叠防止逻辑断裂"""
        overlap_ratio = 0.15
        overlap_chars = int(self.chunk_size * overlap_ratio)
        
        chunks = []
        paragraphs = re.split(r'\n\n+', text)
        
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                    # 重叠：保留末尾部分到下一个chunk
                    current_chunk = current_chunk[-overlap_chars:] + "\n\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        if current_chunk:
            chunks.append(current_chunk)
        return chunks
    
    def _extract_keywords(self, query: str) -> List[tuple]:
        """提取关键词，返回: [(keyword, weight), ...]
        原始词权重=1.0，同义词扩展=0.3
        """
        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{2,}', query.lower())
        stopwords = {'这个', '那个', '什么', '如何', '怎么', '一个', '一些', '可能', '已经', '但是'}
        base_keywords = [w for w in words if w not in stopwords]
        
        result = []
        for word in base_keywords:
            result.append((word, 1.0))  # 原词
            if word in SYNONYMS:
                for syn in SYNONYMS[word]:
                    result.append((syn, 0.3))  # 扩展词 - 从0.5改为0.3
        
        return result
    
    def _get_base_weight(self, keywords: List[tuple]) -> float:
        """仅计算原始关键词权重之和（用于分母）"""
        return sum(w for kw, w in keywords if w >= 1.0)
    
    def _extract_date_from_filename(self, filename: str) -> Optional[datetime]:
        date_patterns = [
            r'(\d{4})-(\d{1,2})-(\d{1,2})',   # 2024-01-01
            r'(\d{4})/(\d{1,2})/(\d{1,2})',   # 2024/01/01
            r'(\d{4})(\d{2})(\d{2})',          # 20240101
            r'(\d{4})_(\d{1,2})_(\d{1,2})',  # 2024_01_01
        ]
        for pattern in date_patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    if len(match.groups()) == 3:
                        year, month, day = match.groups()
                        year = int(year)
                        # 年份范围校验，防止误抓版本号v2等
                        if 2000 <= year <= 2030:
                            return datetime(int(year), int(month), int(day))
                except:
                    pass
        return None
    
    def _time_decay_score(self, filename: str) -> float:
        date = self._extract_date_from_filename(filename)
        if not date:
            return 0.5
        days_old = max(0, (datetime.now() - date).days)
        decay = 0.5 ** (days_old / HALF_LIFE_DAYS)
        return min(1.0, max(0.1, decay))
    
    def retrieve(self, expert_id: str, query: str, top_k: int = None) -> List[Dict]:
        """检索返回带元信息的知识片段"""
        if expert_id not in self.expert_knowledge:
            return []
        if not self.expert_knowledge[expert_id]:
            return []
        
        top_k = top_k or self.top_k
        query_keywords = self._extract_keywords(query)
        
        if not query_keywords:
            return self.expert_knowledge[expert_id][:top_k]
        
        # 计算仅原始关键词权重（用于分母）
        max_base_weight = self._get_base_weight(query_keywords)
        
        # 综合得分：kw_ratio * 0.7 + time_weight * 0.3
        # kw_ratio = min(1.0, kw_score / max_base_weight)
        scored = []
        
        for chunk in self.expert_knowledge[expert_id]:
            kw_score = self._compute_weighted_kw_score(chunk['content'], query_keywords)
            kw_ratio = min(1.0, kw_score / max_base_weight) if max_base_weight > 0 else 0
            time_weight = self._time_decay_score(chunk['file'])
            final_score = (kw_ratio * 0.7) + (time_weight * 0.3)
            scored.append((final_score, kw_ratio, kw_score, time_weight, chunk))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # 去重
        results = []
        seen = set()
        for score, kw_ratio, kw_score, time_weight, chunk in scored:
            if score > 0:
                content_hash = chunk['content'][:50]
                if content_hash not in seen:
                    seen.add(content_hash)
                    results.append({
                        'content': chunk['content'],
                        'file': chunk['file'],
                        'score': round(score, 3),
                        'kw_ratio': round(kw_ratio, 3),
                        'kw_matches': kw_score,
                        'time_weight': round(time_weight, 3)
                    })
                    if len(results) >= top_k:
                        break
        return results
    
    def _compute_weighted_kw_score(self, content: str, keywords: List[tuple]) -> float:
        """计算加权关键词命中得分"""
        content_lower = content.lower()
        score = 0.0
        for kw, weight in keywords:
            if kw in content_lower:
                score += weight
        return score
    
    def get_stats(self) -> Dict[str, int]:
        return {eid: len(chunks) for eid, chunks in self.expert_knowledge.items()}


def create_rag(config: dict, base_dir: str = None) -> Optional[SimpleRAG]:
    rag_config = config.get('rag', {})
    if not rag_config.get('enabled', False):
        return None
    
    knowledge_dir = rag_config.get('knowledge_dir', 'knowledge')
    if base_dir:
        knowledge_dir = os.path.join(base_dir, knowledge_dir)
    elif not os.path.isabs(knowledge_dir):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        knowledge_dir = os.path.join(script_dir, knowledge_dir)
    
    return SimpleRAG(
        knowledge_dir=knowledge_dir,
        top_k=rag_config.get('top_k', 3),
        chunk_size=rag_config.get('chunk_size', 500)
    )