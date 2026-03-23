"""EmailSender 单元测试。"""
from unittest.mock import MagicMock, patch

from fund_analyzer.config import EmailConfig
from fund_analyzer.notification.email_sender import EmailSender


def _make_config(**overrides) -> EmailConfig:
    defaults = {
        "enabled": True,
        "smtp_host": "smtp.163.com",
        "smtp_port": 465,
        "smtp_user": "test@163.com",
        "smtp_password": "auth_code",
        "receiver": "recv@163.com",
        "send_time": "14:40",
        "use_ssl": True,
    }
    defaults.update(overrides)
    return EmailConfig(**defaults)


class TestEmailSender:
    """EmailSender 测试类。"""

    @patch("fund_analyzer.notification.email_sender.smtplib.SMTP_SSL")
    def test_send_success(self, mock_smtp_cls):
        """正常发送邮件应返回 True。"""
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        sender = EmailSender(_make_config())
        result = sender.send("测试标题", "<p>内容</p>")

        assert result is True
        mock_smtp_cls.assert_called_once_with("smtp.163.com", 465, timeout=30)
        mock_server.login.assert_called_once_with("test@163.com", "auth_code")
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("fund_analyzer.notification.email_sender.smtplib.SMTP_SSL")
    def test_send_failure(self, mock_smtp_cls):
        """SMTP 连接失败应返回 False。"""
        mock_smtp_cls.side_effect = ConnectionRefusedError("refused")

        sender = EmailSender(_make_config())
        result = sender.send("标题", "<p>内容</p>")

        assert result is False

    @patch("fund_analyzer.notification.email_sender.smtplib.SMTP")
    def test_send_without_ssl(self, mock_smtp_cls):
        """use_ssl=False 时应使用 SMTP + starttls。"""
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        sender = EmailSender(_make_config(use_ssl=False, smtp_port=25))
        result = sender.send("标题", "<p>内容</p>")

        assert result is True
        mock_smtp_cls.assert_called_once_with("smtp.163.com", 25, timeout=30)
        mock_server.starttls.assert_called_once()

    @patch("fund_analyzer.notification.email_sender.smtplib.SMTP_SSL")
    def test_send_multiple_receivers(self, mock_smtp_cls):
        """多收件人应正确分割。"""
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        sender = EmailSender(_make_config(receiver="a@b.com, c@d.com"))
        sender.send("标题", "<p>内容</p>")

        call_args = mock_server.sendmail.call_args
        receivers = call_args[0][1]
        assert receivers == ["a@b.com", "c@d.com"]

    @patch("fund_analyzer.notification.email_sender.smtplib.SMTP_SSL")
    def test_test_method(self, mock_smtp_cls):
        """test() 方法应调用 send。"""
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        sender = EmailSender(_make_config())
        result = sender.test()

        assert result is True
        mock_server.sendmail.assert_called_once()
