# ============================================
# 多格式/多平台输出模块
# ============================================

import json
import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
from typing import List, Dict, Optional


class MultiOutput:
    """多格式多平台输出"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.output_dir = self.config.get("output_dir", "analysis")
        os.makedirs(self.output_dir, exist_ok=True)
    
    def save_json(self, report_data: dict, filename: str = None) -> str:
        """保存JSON"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ JSON已保存: {filepath}")
        return filepath
    
    def save_markdown(self, report_data: dict, filename: str = None) -> str:
        """保存Markdown"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.md"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # 构建Markdown内容
        lines = [
            f"# 📊 Expert News Analysis Report",
            f"",
            f"**生成时间**: {report_data.get('timestamp', '')}",
            f"",
            f"---",
            f"",
            f"## 📰 新闻摘要",
            f"",
        ]
        
        for i, news in enumerate(report_data.get("news", [])):
            signal = news.get('signal_strength', '中')
            lines.append(f"### {i+1}. {news.get('title', '')}")
            lines.append(f"   - **评分**: {news.get('score', 0)}/100 | **来源**: {news.get('source', '')}")
            lines.append(f"   - **信号强度**: {signal}")
            lines.append(f"   - **多角度解读**: {news.get('conclusion', 'N/A')}")
            lines.append("")
        
        # 信号分布观察
        lines.append("---")
        lines.append("")
        lines.append("## 📊 信号分布观察")
        lines.append("")
        lines.append("说明: 该部分仅反映当前筛选结果的分布情况，不构成趋势判断或投资建议")
        lines.append("")
        
        # 免责声明
        lines.append("---")
        lines.append("")
        lines.append("⚠️ Important Notice")
        lines.append("")
        lines.append("This report is generated for informational purposes only.")
        lines.append("- It does NOT predict future outcomes")
        lines.append("- It does NOT provide investment advice")
        lines.append("- It may be incomplete or inaccurate")
        lines.append("")
        lines.append("Users should verify information independently and make their own decisions.")
        
        # 趋势预测
        if "trends" in report_data:
            lines.extend([
                f"---",
                f"",
                f"## 📈 趋势预测",
                f"",
                report_data["trends"],
                f"",
            ])
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        print(f"✅ Markdown已保存: {filepath}")
        return filepath
    
    def save_pdf(self, report_data: dict, filename: str = None) -> str:
        """保存PDF"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.units import inch
        except ImportError:
            print("⚠️ 请安装: pip install reportlab")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.pdf"
        
        filepath = os.path.join(self.output_dir, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=0.5*inch)
        styles = getSampleStyleSheet()
        story = []
        
        # 标题
        story.append(Paragraph("Expert News Analysis Report", styles['Title']))
        story.append(Spacer(1, 0.2*inch))
        
        # 时间
        story.append(Paragraph(f"Time: {report_data.get('timestamp', '')}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # 新闻列表
        for i, news in enumerate(report_data.get("news", [])[:10]):
            text = f"{i+1}. {news.get('title', '')}"
            story.append(Paragraph(text, styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
        
        doc.build(story)
        print(f"✅ PDF已保存: {filepath}")
        return filepath
    
    def send_feishu(self, message: str, webhook: str = None) -> bool:
        """发送到飞书"""
        if not webhook:
            # 尝试从环境变量获取
            webhook = os.environ.get("FEISHU_WEBHOOK")
        
        if not webhook:
            print("⚠️ 未配置飞书Webhook (环境变量 FEISHU_WEBHOOK)")
            return False
        
        try:
            payload = {"msg_type": "text", "content": {"text": message}}
            response = requests.post(webhook, json=payload, timeout=10)
            if response.status_code == 200:
                print("✅ 飞书推送成功")
                return True
            else:
                print(f"❌ 飞书失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 飞书错误: {e}")
            return False
    
    def send_telegram(self, message: str, bot_token: str = None, chat_id: str = None) -> bool:
        """发送到Telegram"""
        if not bot_token:
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not chat_id:
            chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        if not bot_token or not chat_id:
            print("⚠️ 未配置Telegram (环境变量 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message}
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                print("✅ Telegram发送成功")
                return True
            return False
        except Exception as e:
            print(f"❌ Telegram错误: {e}")
            return False
    
    def send_email(self, subject: str, body: str, smtp_config: dict = None, attachments: list = None) -> bool:
        """发送邮件"""
        if not smtp_config:
            smtp_config = self.config.get("smtp", {})
        
        if not smtp_config.get("host"):
            print("⚠️ 未配置SMTP")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = smtp_config.get("user", "")
            msg['To'] = ",".join(smtp_config.get("to", []))
            
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            for filepath in attachments or []:
                with open(filepath, 'rb') as f:
                    part = MIMEApplication(f.read())
                    part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(filepath))
                    msg.attach(part)
            
            with smtplib.SMTP_SSL(smtp_config["host"], smtp_config.get("port", 465)) as server:
                server.login(smtp_config["user"], smtp_config["password"])
                server.send_message(msg)
            
            print("✅ 邮件发送成功")
            return True
        except Exception as e:
            print(f"❌ 邮件错误: {e}")
            return False
    
    def output_all(self, report_data: dict, output_config: dict = None) -> dict:
        """输出到所有配置的渠道"""
        output_config = output_config or self.config.get("output", {})
        results = {}
        
        # 文件输出
        if output_config.get("json", True):
            results["json"] = self.save_json(report_data)
        
        if output_config.get("markdown", True):
            results["markdown"] = self.save_markdown(report_data)
        
        if output_config.get("pdf", False):
            results["pdf"] = self.save_pdf(report_data)
        
        # 消息内容 (用于推送)
        msg_content = self._build_message(report_data)
        
        # 平台推送
        if output_config.get("wechat", False):
            results["wechat"] = "Use analyzer built-in WeChat"
        
        if output_config.get("feishu", False):
            results["feishu"] = self.send_feishu(msg_content)
        
        if output_config.get("telegram", False):
            results["telegram"] = self.send_telegram(msg_content)
        
        if output_config.get("email", False):
            results["email"] = self.send_email(
                "Expert News Report",
                msg_content.replace("\\n", "<br/>")
            )
        
        return results
    
    def _build_message(self, report_data: dict) -> str:
        """构建消息内容"""
        lines = ["📊 Expert News Report", ""]
        
        for i, news in enumerate(report_data.get("news", [])[:5]):
            title = news.get("title", "")[:50]
            score = news.get("score", 0)
            lines.append(f"{i+1}. {title}... [{score}分]")
        
        return "\n".join(lines)


def create_output(config: dict = None) -> MultiOutput:
    """创建输出器"""
    return MultiOutput(config)


if __name__ == "__main__":
    # 测试
    output = create_output({"output_dir": "analysis"})
    
    test_data = {
        "timestamp": "2026-03-29 19:00:00",
        "news": [
            {"title": "Test News 1", "score": 85, "source": "Bloomberg"},
            {"title": "Test News 2", "score": 72, "source": "Reuters"},
        ]
    }
    
    output.save_json(test_data)
    output.save_markdown(test_data)
