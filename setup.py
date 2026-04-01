#!/usr/bin/env python3
"""
交互式配置向导 - 帮助用户配置新闻分析器
"""
import sys
import yaml
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.yaml"
EXPERTS_DIR = SCRIPT_DIR / "experts"


def print_header(text: str):
    print(f"\n{'='*50}")
    print(f"  {text}")
    print('='*50)


def print_step(step: int, total: int, text: str):
    print(f"\n[{step}/{total}] {text}")


def input_choice(prompt: str, options: list, default: int = None) -> str:
    """带选项的输入"""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    
    if default:
        print(f"  [默认: {default}]")
    
    while True:
        try:
            choice = input("\n请选择: ").strip()
            if not choice and default:
                return options[default-1]
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx-1]
        except ValueError:
            pass
        print("输入无效，请重新选择")


def input_text(prompt: str, default: str = None) -> str:
    """文本输入"""
    print(f"\n{prompt}")
    if default:
        print(f"  [默认: {default}]")
    
    value = input("请输入: ").strip()
    return value or default or ""


def input_api_key(provider: str) -> str:
    """API Key输入"""
    print(f"\n请输入 {provider} 的API Key:")
    print("  (需要在对应官网申请)")
    
    key = input("API Key: ").strip()
    return key


def select_experts() -> list:
    """选择专家"""
    print_header("选择分析专家")
    
    # 可用专家列表
    available_experts = [
        ("buffett", "巴菲特 - 价值投资", 1),
        ("musk", "马斯克 - 科技趋势", 2),
        ("wood", "木头姐 - 成长投资", 3),
        ("huang_yiping", "黄益平 - 宏观经济", 4),
        ("liu_yuhui", "刘煜辉 - 政策分析", 5),
        ("gao_shanwen", "高善文 - 宏观策略", 6),
        ("peng_wensheng", "彭文生 - 中金宏观", 7),
        ("li_daokui", "李稻葵 - 经济结构", 8),
        ("peter_lynch", "彼得林奇 - 成长投资", 9),
        ("dalio", "达利欧 - 宏观周期", 10),
    ]
    
    print("\n可用专家:")
    for key, name, num in available_experts:
        print(f"  {num}. {name}")
    
    print("\n请输入专家编号(空格分隔，如: 1 2 3 5)")
    print("  [默认: 1 2 3 4 5 巴菲特+马斯克+木头姐+黄益平+刘煜辉]")
    
    choice = input("选择: ").strip()
    
    if not choice:
        # 默认选择前5个
        return ["buffett", "musk", "wood", "huang_yiping", "liu_yuhui"]
    
    # 解析选择
    selected = []
    for idx_str in choice.split():
        try:
            idx = int(idx_str)
            if 1 <= idx <= len(available_experts):
                selected.append(available_experts[idx-1][0])
        except ValueError:
            pass
    
    return selected if selected else ["buffett", "musk", "wood", "huang_yiping", "liu_yuhui"]


def select_categories() -> dict:
    """选择新闻类别"""
    print_header("选择新闻类别")
    
    available = {
        "热点新闻": "全球重大新闻",
        "宏观": "宏观经济政策",
        "科技": "科技创新动态",
        "金融投资": "金融市场投资",
        "消费": "消费行业",
        "能源": "能源大宗商品",
        "地缘政治": "国际关系",
        "医药": "医疗健康",
        "地产": "房地产",
        "汽车": "汽车行业",
    }
    
    print("\n可用类别:")
    for key, desc in available.items():
        print(f"  {key}: {desc}")
    
    print("\n请输入类别及数量(类别:数量，逗号分隔)")
    print("  示例: 热点新闻:10,宏观:3,科技:3,金融投资:2")
    print("  [默认: 热点新闻:10,宏观:3,科技:3]")
    
    choice = input("选择: ").strip()
    
    if not choice:
        return {"热点新闻": 10, "宏观": 3, "科技": 3}
    
    # 解析
    categories = {}
    for part in choice.split(","):
        if ":" in part:
            cat, count = part.split(":")
            cat = cat.strip()
            count = count.strip()
            try:
                categories[cat] = int(count)
            except:
                pass
    
    return categories if categories else {"热点新闻": 10, "宏观": 3, "科技": 3}


def select_model_provider() -> tuple:
    """选择模型提供商"""
    print_header("选择LLM模型")
    
    providers = [
        ("zhipu", "智谱GLM (推荐, 国内可直接使用)"),
        ("openai", "OpenAI GPT"),
        ("anthropic", "Anthropic Claude"),
        ("ollama", "Ollama (本地模型)"),
    ]
    
    provider = input_choice("请选择模型提供商:", [p[1] for p in providers])
    
    # 提取provider key
    provider_key = providers[[p[1] for p in providers].index(provider)][0]
    
    # 获取API Key
    api_key = input_api_key(provider)
    
    # 模型名称
    model_name = ""
    if provider_key == "zhipu":
        model_name = input_text("模型名称", "glm-4")
    elif provider_key == "openai":
        model_name = input_text("模型名称", "gpt-4")
    elif provider_key == "anthropic":
        model_name = input_text("模型名称", "claude-3-opus-20240229")
    
    return provider_key, model_name, api_key


def select_push_channel() -> str:
    """选择推送渠道"""
    print_header("选择推送方式")
    
    channels = [
        ("wecom", "企业微信 (推荐)"),
        ("feishu", "飞书"),
        ("email", "邮件"),
        ("webhook", "Webhook"),
        ("file", "文件输出"),
    ]
    
    channel = input_choice("请选择推送方式:", [c[1] for c in channels])
    
    channel_key = channels[[c[1] for c in channels].index(channel)][0]
    
    if channel_key == "wecom":
        print("\n企业微信Webhook地址:")
        webhook = input("Webhook: ").strip()
        return webhook
    elif channel_key == "feishu":
        print("\n飞书Webhook地址:")
        webhook = input("Webhook: ").strip()
        return webhook
    elif channel_key == "email":
        print("\n邮件地址:")
        email = input("Email: ").strip()
        return email
    elif channel_key == "webhook":
        print("\nWebhook URL:")
        url = input("URL: ").strip()
        return url
    
    return ""


def enable_rag() -> bool:
    """RAG配置"""
    print_header("知识增强(RAG)")
    
    options = ["是", "否"]
    choice = input_choice("是否启用知识增强(RAG)?", options, 2)
    
    return choice == "是"


def generate_config(
    provider: str,
    model_name: str,
    api_key: str,
    experts: list,
    categories: dict,
    push_channel: str = "",
    rag_enabled: bool = False,
) -> dict:
    """生成配置"""
    config = {
        "model_provider": provider,
        "model_name": model_name,
        "api_key": api_key,
        "enabled_experts": experts,
        "news_count": sum(categories.values()),
        "categories": categories,
    }
    
    if push_channel:
        config["push_channel"] = push_channel
    
    if rag_enabled:
        config["rag"] = {
            "enabled": True,
            "knowledge_dir": "knowledge",
            "top_k": 3,
            "chunk_size": 500,
        }
    
    return config


def save_config(config: dict):
    """保存配置"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    
    print(f"\n✅ 配置已保存至: {CONFIG_FILE}")


def main():
    print_header("专家新闻分析器 - 配置向导")
    print("\n欢迎使用！本向导将帮助您配置新闻分析器。")
    
    # Step 1: 选择模型
    provider, model_name, api_key = select_model_provider()
    
    # Step 2: 选择专家
    experts = select_experts()
    
    # Step 3: 选择类别
    categories = select_categories()
    
    # Step 4: 选择推送渠道
    push_channel = select_push_channel()
    
    # Step 5: RAG
    rag_enabled = enable_rag()
    
    # 生成配置
    config = generate_config(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        experts=experts,
        categories=categories,
        push_channel=push_channel,
        rag_enabled=rag_enabled,
    )
    
    # 保存
    save_config(config)
    
    print_header("配置完成！")
    print("\n下一步:")
    print("  1. 运行: python scripts/analyzer_v2.2.py --limit 5")
    print("  2. 或运行: python scripts/setup.py --test 测试配置")
    print("\n如需修改配置，直接编辑 config.yaml 或重新运行本向导")


if __name__ == "__main__":
    main()