"""企业微信 Webhook 消息发送器。"""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


class WeChatSender:
    """企业微信机器人 Webhook 发送器。"""

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    def send(self, title: str, content: str) -> bool:
        """发送 Markdown 格式消息。"""
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {title}\n{content}",
            },
        }
        try:
            resp = requests.post(self._url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") != 0:
                logger.warning("微信推送返回错误: %s", data)
                return False
            return True
        except Exception as exc:
            logger.warning("微信推送失败: %s", exc)
            return False

    def test(self) -> bool:
        """发送测试消息。"""
        return self.send("测试通知", "Fund Analyzer 通知功能配置成功！")
