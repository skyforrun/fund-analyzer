"""163邮箱 SMTP 发送器。"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fund_analyzer.config import EmailConfig

logger = logging.getLogger(__name__)


class EmailSender:
    """邮件发送器，使用 SMTP_SSL 连接 163 邮箱。"""

    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    def send(self, title: str, content: str) -> bool:
        """发送 HTML 格式邮件。

        Parameters
        ----------
        title : str
            邮件主题。
        content : str
            HTML 格式的邮件正文。

        Returns
        -------
        bool
            发送成功返回 True，失败返回 False。
        """
        cfg = self._config
        msg = MIMEMultipart("alternative")
        msg["Subject"] = title
        msg["From"] = f"Fund Analyzer <{cfg.smtp_user}>"
        msg["To"] = cfg.receiver

        msg.attach(MIMEText(content, "html", "utf-8"))

        try:
            if cfg.use_ssl:
                server = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30)
                server.starttls()

            server.login(cfg.smtp_user, cfg.smtp_password)
            receivers = [r.strip() for r in cfg.receiver.split(",")]
            server.sendmail(cfg.smtp_user, receivers, msg.as_string())
            server.quit()
            logger.info("邮件发送成功: %s -> %s", title, cfg.receiver)
            return True
        except Exception as exc:
            logger.warning("邮件发送失败: %s", exc)
            return False

    def test(self) -> bool:
        """发送测试邮件。"""
        html = """
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #2c3e50;">Fund Analyzer 测试邮件</h2>
            <p style="color: #27ae60; font-size: 16px;">邮件通知功能配置成功！</p>
        </div>
        """
        return self.send("Fund Analyzer 测试邮件", html)
