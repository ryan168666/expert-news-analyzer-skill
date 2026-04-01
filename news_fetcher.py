#!/usr/bin/env python3
"""
多源新闻获取器 - 支持多个新闻源
"""
import re
import json
import yaml
import requests
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# ============ 新闻源配置 ============
NEWS_SOURCES = {
    # 中文源
    "36kr": {
        "name": "36Kr",
        "url": "https://www.36kr.com/information/tech/".strip(),
        "type": "rss",
        "parser": "36kr",
    },
    "wallstreetcn": {
        "name": "华尔街见闻",
        "url": "https://api.wallstreetcn.com/articles?type=inner&client_id=pc",
        "type": "api",
    },
    "sina": {
        "name": "新浪财经",
        "url": "https://finance.sina.com.cn/info/industryindex.shtml",
        "type": "html",
        "parser": "sina",
    },
    "eastmoney": {
        "name": "东方财富",
        "url": "https://news.eastmoney.com/kjjj.html",
        "type": "html",
        "parser": "eastmoney",
    },
    "tencent": {
        "name": "腾讯新闻",
        "url": "https://news.qq.com/gn.htm",
        "type": "html",
        "parser": "tencent",
    },
    "yicai": {
        "name": "第一财经",
        "url": "https://www.yicai.com/news/",
        "type": "html",
        "parser": "yicai",
    },
    "caijing": {
        "name": "财经网",
        "url": "https://www.caijing.com.cn/",
        "type": "html",
        "parser": "caijing",
    },
    # 英文源
    "reuters": {
        "name": "Reuters",
        "url": "https://www.reutersagency.com/",
        "type": "rss",
    },
    "bloomberg": {
        "name": "Bloomberg",
        "url": "https://feeds.bloomberg.com/news/news.rss",
        "type": "rss",
    },
    "cnbc": {
        "name": "CNBC",
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "type": "rss",
    },
    "wsj": {
        "name": "WSJ",
        "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "type": "rss",
    },
    "FT": {
        "name": "Financial Times",
        "url": "https://www.ft.com/rss/home",
        "type": "rss",
    },
    
    # ========== 新增中文源 ==========
    "xueqiu": {
        "name": "雪球",
        "url": "https://xueqiu.com/hq",
        "type": "html",
    },
    "stcn": {
        "name": "证券时报",
        "url": "https://www.stcn.com/",
        "type": "html",
    },
    "ssb": {
        "name": "上海证券报",
        "url": "http://www.ssb.cn/",
        "type": "html",
    },
    "cs": {
        "name": "中国证券报",
        "url": "http://www.cs.com.cn/",
        "type": "html",
    },
    "tonghuashun": {
        "name": "同花顺",
        "url": "https://www.10jqka.com.cn/",
        "type": "html",
    },
    
    # ========== 新增英文源 ==========
    "yahoo_finance": {
        "name": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/rssindex",
        "type": "rss",
    },
    "marketwatch": {
        "name": "MarketWatch",
        "url": "https://feeds.marketwatch.com/marketwatch/topstories/",
        "type": "rss",
    },
    "seeking_alpha": {
        "name": "Seeking Alpha",
        "url": "https://seekingalpha.com/market_currents.xml",
        "type": "rss",
    },
    "zerohedge": {
        "name": "ZeroHedge",
        "url": "https://zerohedge.com/rss",
        "type": "rss",
    },
    "coindesk": {
        "name": "CoinDesk",
        "url": "https://www.coindesk.com/feed/",
        "type": "rss",
    },
    "investopedia": {
        "name": "Investopedia",
        "url": "https://www.investopedia.com/rss/",
        "type": "rss",
    },
    
    # ========== 加密货币源 ==========
    "cointelegraph": {
        "name": "CoinTelegraph",
        "url": "https://cointelegraph.com/feed",
        "type": "rss",
    },
    "cryptoslate": {
        "name": "CryptoSlate",
        "url": "https://cryptoslate.com/feed/",
        "type": "rss",
    },
}

DEFAULT_sources = ["36kr", "sina", "eastmoney", "tencent", "yicai", "caijing", "reuters", "bloomberg", "cnbc", "FT"]


class NewsFetcher:
    """多源新闻获取器"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.sources = self.config.get("sources", DEFAULT_sources)
        self.count = self.config.get("count", 40)
        self.timeout = self.config.get("timeout", 30)
        
        # 分类关键词
        self.category_keywords = {
            "科技": ["AI", "人工智能", "芯片", "互联网", "科技", "技术", "软件", "数据", "云计算", "大模型", "GPT", "英伟达", "谷歌", "微软", "特斯拉", "机器人"],
            "宏观": ["经济", "GDP", "通胀", "利率", "美联储", "央行", "政策", "财政", "降息", "加息", "货币", "M2", "CPI", "PPI"],
            "金融投资": ["投资", "股市", "股票", "基金", "债券", "资管", "私募", "公募", "IPO", "融资", "并购"],
            "消费": ["消费", "零售", "电商", "食品", "饮料", "汽车", "地产", "家电", "手机", "茅台", "海底捞", "泡泡玛特"],
            "能源": ["石油", "天然气", "原油", "油价", "OPEC", "伊朗", "煤炭", "新能源", "锂", "电池"],
            "地缘政治": ["伊朗", "俄乌", "中美", "贸易战", "关税", "制裁", "外交", "特朗普", "普京", "联合国"],
        }
    
    def fetch_all(self, max_workers: int = 5) -> list:
        """并行获取所有源新闻"""
        all_news = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for source in self.sources:
                if source in NEWS_SOURCES:
                    future = executor.submit(self._fetch_source, source)
                    futures[future] = source
            
            for future in as_completed(futures):
                source = futures[future]
                try:
                    news_list = future.result()
                    all_news.extend(news_list)
                except Exception as e:
                    print(f"获取 {source} 失败: {e}")
        
        # 去重并返回
        return self._deduplicate(all_news)
    
    def _fetch_source(self, source: str) -> list:
        """获取单个源新闻"""
        source_config = NEWS_SOURCES.get(source, {})
        url = source_config.get("url", "")
        source_type = source_config.get("type", "html")
        
        try:
            if source_type == "rss":
                return self._fetch_rss(url, source_config.get("name", source))
            elif source_type == "api":
                return self._fetch_api(url, source_config.get("name", source))
            else:
                return self._fetch_html(url, source_config.get("name", source))
        except Exception as e:
            print(f"Error fetching {source}: {e}")
            return []
    
    def _fetch_rss(self, url: str, source_name: str) -> list:
        """获取RSS源"""
        try:
            response = requests.get(url, timeout=self.timeout)
            response.encoding = 'utf-8'
            
            # 简单解析
            items = []
            import re
            # 简单的item提取
            pattern = r'<item>(.*?)</item>'
            matches = re.findall(pattern, response.text, re.DOTALL)
            
            for match in matches[:10]:
                title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', match)
                if not title_match:
                    title_match = re.search(r'<title>(.*?)</title>', match)
                
                link_match = re.search(r'<link>(.*?)</link>', match)
                desc_match = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>', match)
                
                if title_match:
                    items.append({
                        "title": title_match.group(1).strip(),
                        "url": link_match.group(1).strip() if link_match else "",
                        "summary": desc_match.group(1).strip()[:200] if desc_match else "",
                        "source": source_name,
                    })
            
            return items
        except Exception as e:
            print(f"RSS fetch error: {e}")
            return []
    
    def _fetch_api(self, url: str, source_name: str) -> list:
        """获取API源"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=self.timeout)
            data = response.json()
            
            items = []
            for article in data.get("data", {}).get("articles", [])[:10]:
                items.append({
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "summary": article.get("summary", "")[:200],
                    "source": source_name,
                })
            
            return items
        except Exception as e:
            print(f"API fetch error: {e}")
            return []
    
    def _fetch_html(self, url: str, source_name: str) -> list:
        """获取HTML源"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            items = []
            # 尝试多种选择器
            for link in soup.find_all('a', href=True)[:20]:
                title = link.get_text().strip()
                if title and len(title) > 10:
                    items.append({
                        "title": title[:100],
                        "url": link.get('href', ''),
                        "summary": "",
                        "source": source_name,
                    })
            
            return items
        except Exception as e:
            print(f"HTML fetch error: {e}")
            return []
    
    def _deduplicate(self, news_list: list) -> list:
        """去重"""
        seen_titles = set()
        unique_news = []
        
        for news in news_list:
            # 简化标题进行比对
            key = news.get("title", "")[:30].lower()
            key = re.sub(r'[^\w\u4e00-\u9fff]', '', key)
            
            if key and key not in seen_titles:
                seen_titles.add(key)
                # 添加分类
                news["category"] = self._categorize(news.get("title", ""))
                unique_news.append(news)
        
        # 限制数量
        return unique_news[:self.count]
    
    def _categorize(self, title: str) -> str:
        """分类"""
        text = title.lower()
        
        for category, keywords in self.category_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    return category
        
        return "其他资讯"


def create_fetcher(config: dict = None) -> NewsFetcher:
    """创建新闻获取器"""
    return NewsFetcher(config)


# ============ CLI ============
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="多源新闻获取器")
    parser.add_argument("--sources", "-s", nargs="+", help="指定新闻源")
    parser.add_argument("--count", "-c", type=int, default=20, help="新闻数量")
    args = parser.parse_args()
    
    config = {
        "sources": args.sources,
        "count": args.count,
    }
    
    fetcher = create_fetcher(config)
    news = fetcher.fetch_all()
    
    print(f"获取到 {len(news)} 条新闻")
    for n in news[:10]:
        print(f"- [{n.get('source')}] {n.get('title')[:50]}")
# ============================================
# 多平台输出模块
# ============================================

import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
from datetime import datetime

# 飞书Webhook (需要配置)
FEISHU_WEBHOOK = None  # 配置你的飞书机器人Webhook

# 邮件配置
SMTP_CONFIG = {
    "host": "smtp.qq.com",
    "port": 465,
    "user": "your_email@qq.com",
    "password": "your_password",
    "to": ["recipient@example.com"]
}

def output_json(report_data: dict, output_path: str = None) -> str:
    """
    输出JSON格式
    """
    if not output_path:
        output_dir = "analysis"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{output_dir}/report_{timestamp}.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ JSON已保存: {output_path}")
    return output_path


def output_pdf(report_data: dict, output_path: str = None) -> str:
    """
    输出PDF格式 (需要安装 reportlab)
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import inch
    except ImportError:
        print("⚠️ 请安装 reportlab: pip install reportlab")
        return None
    
    if not output_path:
        output_dir = "analysis"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{output_dir}/report_{timestamp}.pdf"
    
    # 创建PDF
    doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # 标题
    title = Paragraph("Expert News Analysis Report", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 0.2*inch))
    
    # 时间
    time_text = Paragraph(f"生成时间: {report_data.get('timestamp', '')}", styles['Normal'])
    story.append(time_text)
    story.append(Spacer(1, 0.2*inch))
    
    # 摘要
    if "summary" in report_data:
        summary = Paragraph(f"<b>摘要:</b> {report_data['summary']}", styles['Normal'])
        story.append(summary)
        story.append(Spacer(1, 0.1*inch))
    
    # 新闻列表
    for i, news in enumerate(report_data.get("news", [])[:10]):
        news_text = Paragraph(
            f"{i+1}. <b>{news.get('title', '')}</b><br/>"
            f"   分数: {news.get('score', 0)} | 来源: {news.get('source', '')}",
            styles['Normal']
        )
        story.append(news_text)
        story.append(Spacer(1, 0.1*inch))
    
    # 生成PDF
    doc.build(story)
    print(f"✅ PDF已保存: {output_path}")
    return output_path


def send_feishu(message: str, webhook: str = None) -> bool:
    """
    发送到飞书
    """
    if not webhook:
        webhook = FEISHU_WEBHOOK
    
    if not webhook:
        print("⚠️ 未配置飞书Webhook")
        return False
    
    try:
        import requests
        payload = {"msg_type": "text", "content": {"text": message}}
        response = requests.post(webhook, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ 飞书推送成功")
            return True
        else:
            print(f"❌ 飞书推送失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 飞书推送错误: {e}")
        return False


def send_email(subject: str, body: str, attachments: list = None) -> bool:
    """
    发送邮件
    """
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = SMTP_CONFIG["user"]
        msg['To'] = ",".join(SMTP_CONFIG["to"])
        
        # 邮件正文
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        
        # 添加附件
        for filepath in attachments or []:
            with open(filepath, 'rb') as f:
                part = MIMEApplication(f.read())
                part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(filepath))
                msg.attach(part)
        
        # 发送邮件
        with smtplib.SMTP_SSL(SMTP_CONFIG["host"], SMTP_CONFIG["port"]) as server:
            server.login(SMTP_CONFIG["user"], SMTP_CONFIG["password"])
            server.send_message(msg)
        
        print("✅ 邮件发送成功")
        return True
    except Exception as e:
        print(f"❌ 邮件发送错误: {e}")
        return False


def send_telegram(message: str, bot_token: str = None, chat_id: str = None) -> bool:
    """
    发送到Telegram
    """
    if not bot_token or not chat_id:
        print("⚠️ 未配置Telegram")
        return False
    
    try:
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram发送成功")
            return True
        else:
            print(f"❌ Telegram发送失败")
            return False
    except Exception as e:
        print(f"❌ Telegram错误: {e}")
        return False
