#!/usr/bin/env python3
"""
专家新闻分析器 v2.2 - 信号筛选版
功能：多源新闻采集 → 价值评分 → 信号分布观察 → 多角度解读 → 生成报告
支持功能：
1. 价值评分 - scorer.py
2. 信号分布 - predictor.py
3. 多新闻源 - news_fetcher.py
4. 配置向导 - setup.py
"""
import json
import yaml
import os
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from model_client import create_client
from rag import create_rag

# ============ 配置 ============
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = SCRIPT_DIR / "config.yaml"
EXPERTS_DIR = SCRIPT_DIR / "experts"
NEWS_DIR = PROJECT_ROOT / "news"
OUTPUT_DIR = PROJECT_ROOT / "analysis"
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"

# 自动创建所需目录
for directory in [NEWS_DIR, OUTPUT_DIR, KNOWLEDGE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# 专家显示名映射
DISPLAY_NAMES = {
    "buffett": "巴菲特",
    "musk": "马斯克",
    "wood": "木头姐",
    "huang_yiping": "黄益平",
    "liu_yuhui": "刘煜辉",
    "gao_shanwen": "高善文",
    "peng_wensheng": "彭文生",
    "li_daokui": "李稻葵",
    "peter_lynch": "彼得林奇",
    "dalio": "达利欧",
}


def load_config():
    """加载配置"""
    if CONFIG_FILE.exists():
        return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
    return {
        "model_provider": "zhipu",
        "model_name": "glm-4",
        "api_key": "",
        "enabled_experts": ["buffett", "musk", "wood", "huang_yiping", "liu_yuhui"],
        "news_count": 30,
        "categories": {"热点新闻": 10, "宏观": 3, "科技": 3, "金融投资": 2, "消费": 2},
        "scoring": {"enabled": True, "min_score": 40},
        "predict": {"enabled": True},
        "news_sources": ["36kr", "sina", "eastmoney"],
    }


def load_expert_prompts(expert_ids: list) -> list:
    """加载专家配置"""
    prompts = []
    for exp_id in expert_ids:
        exp_file = EXPERTS_DIR / f"{exp_id}.yaml"
        if exp_file.exists():
            data = yaml.safe_load(exp_file.read_text(encoding="utf-8"))
            prompts.append({
                "id": exp_id,
                "name": data.get("name", exp_id),
                "role": data.get("role", ""),
                "prompt": data.get("prompt", ""),
            })
    return prompts


def fetch_news_simple(count: int = 20) -> list:
    """简单新闻获取 - 使用内置源"""
    # 模拟新闻数据
    sample_news = [
        {"title": "BlackRock CEO警告投资者低估伊朗风险", "source": "Bloomberg", "category": "热点新闻"},
        {"title": "印度自2018年来首次购买伊朗LPG", "source": "Bloomberg", "category": "能源"},
        {"title": "澳大利亚矿业公司警告燃料短缺", "source": "Reuters", "category": "能源"},
        {"title": "铜价随金属下跌", "source": "Reuters", "category": "宏观"},
        {"title": "美团价格战加剧成本", "source": "36kr", "category": "消费"},
        {"title": "BOK警告金融稳定风险", "source": "Reuters", "category": "金融投资"},
        {"title": "特朗普称赞日本支持伊朗", "source": "36kr", "category": "地缘政治"},
        {"title": "欧盟小包裹关税无效", "source": "36kr", "category": "地缘政治"},
        {"title": "伊朗战火推高英国通胀", "source": "FT", "category": "宏观"},
        {"title": "油价上涨市场关注伊朗", "source": "CNBC", "category": "能源"},
        {"title": "AI和能源推高通胀", "source": "Bloomberg", "category": "科技"},
        {"title": "谷歌突破导致芯片抛售", "source": "CNBC", "category": "科技"},
        {"title": "泰国燃料价格上涨22%", "source": "Reuters", "category": "能源"},
        {"title": "美国会要求停止对华芯片", "source": "36kr", "category": "科技"},
        {"title": "三人被控走私英伟达芯片", "source": "yicai", "category": "科技"},
        {"title": "花旗顶级亚洲银行家离职", "source": "Reuters", "category": "金融投资"},
        {"title": "私 credit吸引资金", "source": "Bloomberg", "category": "金融投资"},
        {"title": "特朗普Xi将举行峰会", "source": "WSJ", "category": "地缘政治"},
        {"title": "日本短债收益率上升", "source": "Bloomberg", "category": "宏观"},
        {"title": "OpenAI发布GPT-5新功能", "source": "36kr", "category": "科技"},
        {"title": "英伟达推出新AI芯片", "source": "CNBC", "category": "科技"},
        {"title": "小米汽车销量突破10万", "source": "36kr", "category": "科技"},
        {"title": "特斯拉FSD进展迅速", "source": "CNBC", "category": "科技"},
        {"title": "苹果发布新品iPad", "source": "yicai", "category": "科技"},
        {"title": "字节跳动AI助手月活超千万", "source": "36kr", "category": "科技"},
        {"title": "阿里巴巴云计算增长50%", "source": "36kr", "category": "科技"},
        {"title": "腾讯发布AI大模型", "source": "sina", "category": "科技"},
        {"title": "比尔盖茨谈AI对就业影响", "source": "Bloomberg", "category": "科技"},
        {"title": "AI创业公司融资火爆", "source": "36kr", "category": "科技"},
    ]
    return sample_news[:count]


def score_news(news_list: list, client, config: dict) -> list:
    """新闻价值评分 - 使用客观评分"""
    if not config.get("scoring", {}).get("enabled", True):
        return news_list
    
    sys.path.insert(0, str(SCRIPT_DIR))
    
    # 优先使用客观评分
    try:
        from scorer import objective_score, calc_signal_strength
        print(f"\n📊 正在客观评分 {len(news_list)} 条新闻...")
        scored = []
        for news in news_list:
            result = objective_score(news)
            result["signal_strength"] = calc_signal_strength(result["score"])
            result["news"] = news
            scored.append(result)
        
        # 计算信息覆盖
        total = len(scored)
        for item in scored:
            if total >= 4:
                item["info_coverage"] = "高"
            elif total >= 2:
                item["info_coverage"] = "中"
            else:
                item["info_coverage"] = "低"
        
        # 按分数排序
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        # 打印分数最高的几条
        for s in scored[:3]:
            print(f"  [{s['score']}分] {s['news']['title'][:30]}... ({s.get('reason', '')})")
        
        return scored
    except Exception as e:
        print(f"客观评分失败: {e}, 使用默认50分")
        return [{"score": 50, "news": n} for n in news_list]


def analyze_distribution(news_list: list, client, config: dict) -> dict:
    """信号分布观察"""
    if not config.get("predict", {}).get("enabled", True):
        return {}
    
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from predictor import create_predictor
        predictor = create_predictor(client, config.get("predict", {}))
        print(f"\n📈 正在分析信号分布...")
        return predictor.analyze_trends(news_list)
    except Exception as e:
        print(f"分析模块加载失败: {e}")
        return {}


def analyze_news(news_item: dict, experts: list, client, config: dict, rag=None, expert_id: str = None) -> dict:
    """单条新闻多专家分析"""
    title = news_item.get("title", "")
    content = news_item.get("content", news_item.get("summary", ""))
    
    results = {"title": title, "opinions": [], "conclusion": ""}
    
    # 收集专家观点
    knowledge_context = ""
    if rag and expert_id:
        kb_content = rag.retrieve(expert_id, news_item.get('title', ''))
        if kb_content:
            # v2.x返回字典，需提取content字段
            content_snippets = [item['content'][:200] for item in kb_content[:2]]
            knowledge_context = "\n\n参考知识: " + " | ".join(content_snippets)
    
    for expert in experts:
        prompt = f"""你是{expert['name']}，{expert['role']}
        
新闻标题：{title}
新闻内容：{content}

请用50-100字分析这条新闻对投资的影响。"""
        try:
            resp = client.chat(expert["prompt"], prompt)
            results["opinions"].append({
                "expert": expert["name"],
                "opinion": resp,
            })
        except Exception as e:
            results["opinions"].append({
                "expert": expert["name"],
                "opinion": f"分析失败: {str(e)[:50]}",
            })
    
    # 圆桌结论
    if results["opinions"]:
        conclusion_prompt = f"新闻：{title}\n\n请用50字总结各专家观点，给出投资建议。"
        try:
            results["conclusion"] = client.chat(
                "你是一个投资总结专家。",
                conclusion_prompt
            )
        except:
            results["conclusion"] = "建议关注风险，保持谨慎。"
    
    return results


def generate_report(
    news_results: list,
    trends: dict,
    config: dict,
    output_file: Path,
):
    """生成报告 - 固定格式"""
    lines = [
        "📊 Expert News Analysis Report",
        "",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    
    # 📰 新闻摘要
    lines.append("📰 新闻摘要")
    lines.append("")
    
    for i, result in enumerate(news_results[:10], 1):
        lines.append(f"{i}. {result['title']}")
        score = result.get('score') or result.get('news', {}).get('score', 0)
        lines.append(f"   - 分数: {score} | 来源: {result.get('source', result.get('news', {}).get('source', 'unknown'))}")
        # 专家观点
        opinions = result.get("opinions", [])
        if opinions:
            for op in opinions:
                expert_name = op.get("expert", op.get("expert_id", "专家"))
                opinion_text = op.get("opinion", "")
                if opinion_text and not opinion_text.startswith("分析失败"):
                    lines.append(f"   - {expert_name}: {opinion_text}")
        # 圆桌结论
        conclusion = result.get("conclusion", "")
        if conclusion:
            lines.append(f"   - 圆桌结论: {conclusion}")
        lines.append("")
    
    # 📈 趋势预测
    lines.append("📈 趋势预测")
    lines.append("")
    
    if trends and trends.get("trends"):
        for trend in trends["trends"][:5]:
            category = trend.get("category", "")
            lines.append(f"{category}")
            lines.append(f"- 新闻数：{trend.get('news_count', 0)}")
            lines.append(f"- 平均分：{trend.get('avg_score', 0)}")
            lines.append(f"- 趋势: {trend.get('trend', '震荡')} (置信度: {int(float(trend.get('confidence', 0)) * 100)}%)")
            if trend.get("summary"):
                lines.append(f"- 总结：{trend.get('summary', '')}")
            lines.append("")
    else:
        lines.append("（暂无趋势数据）")
        lines.append("")
    
    # 保存
    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", "-l", type=int, default=10, help="分析新闻数量，默认10条")
    parser.add_argument("--no-score", action="store_true")
    parser.add_argument("--no-predict", action="store_true")
    parser.add_argument("--output", "-o", type=str)
    args = parser.parse_args()
    
    # 加载配置
    config = load_config()
    print(f"✅ 配置已加载")
    
    # 创建模型客户端
    client = create_client(config)
    print(f"✅ 模型客户端已创建: {config.get('model_name', 'unknown')}")
    
    # 获取新闻
    news_list = fetch_news_simple(args.limit)
    print(f"📰 获取 {len(news_list)} 条新闻")
    
    # 价值评分
    if not args.no_score:
        scored = score_news(news_list, client, config)
        # 保留分数，过滤新闻
    filtered = [s for s in scored if s.get("score", 0) >= config.get("scoring", {}).get("min_score", 20)]
    news_list = []
    for s in filtered:
        news_item = s["news"].copy()
        news_item["score"] = s.get("score", 0)
        news_list.append(news_item)
        print(f"✅ 评分过滤后保留 {len(news_list)} 条")
    
    # 信号分布分析
    try:
        from predictor import create_predictor
        predictor = create_predictor(client, config.get("predict", {}))
        trends = predictor.analyze_trends(news_list) if predictor else {}
    except Exception as e:
        print(f"⚠️ 趋势分析失败: {e}")
        trends = {}
    
    # 加载专家
    expert_ids = config.get("enabled_experts", ["buffett", "musk", "wood", "huang_yiping", "liu_yuhui"])
    experts = load_expert_prompts(expert_ids)
    
    # 加载RAG知识库
    rag = None
    if config.get('rag', {}).get('enabled', False):
        rag = create_rag(config, str(PROJECT_ROOT))
        if rag:
            stats = rag.load_all_experts(expert_ids)
            print(f"📚 已加载知识库: {stats}")
    print(f"✅ 已加载 {len(experts)} 位专家: {', '.join([e['name'] for e in experts])}")
    
    # 分析新闻
    print(f"\n🔍 开始分析...")
    results = []
    
    for news in news_list[:5]:  # 限制分析数量
        result = analyze_news(news, experts, client, config, rag, expert_ids[0] if expert_ids else None)
        result["source"] = news.get("source", "unknown")
        result["score"] = news.get("score", 0)  # 保留分数
        results.append(result)
        print(f"  ✓ {news.get('title', '')[:30]}...")
    
    # 生成报告
    output_file = OUTPUT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    if args.output:
        output_file = Path(args.output)
    
    generate_report(results, trends, config, output_file)
    print(f"\n✅ 报告已保存至: {output_file}")
    
    return output_file


if __name__ == "__main__":
    main()