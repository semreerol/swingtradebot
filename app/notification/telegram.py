"""
Telegram notification service.
Sends trade alerts, errors, and status updates via Telegram Bot API.
Gracefully degrades if credentials are not configured.
"""
from typing import Any, Optional

import requests

from app.utils.logger import get_logger

logger = get_logger("notification.telegram")

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
REQUEST_TIMEOUT = 15


class TelegramNotifier:
    """Sends messages to a Telegram chat via the Bot API."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        """
        Initialize the Telegram notifier.

        Args:
            bot_token: Telegram Bot API token.
            chat_id: Target chat ID for messages.
        """
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._enabled = bool(bot_token and chat_id)

        if not self._enabled:
            logger.warning(
                "Telegram notifier disabled: "
                "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing."
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a text message to the configured Telegram chat.

        Args:
            text: Message text (supports HTML formatting).
            parse_mode: Telegram parse mode (default: HTML).

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._enabled:
            logger.debug(f"Telegram disabled. Would send: {text[:100]}...")
            return False

        url = TELEGRAM_API_URL.format(token=self._bot_token)
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                logger.info("Telegram message sent successfully.")
                return True
            else:
                logger.error(
                    f"Telegram API error: {response.status_code} — {response.text}"
                )
                return False
        except requests.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_trade_opened(self, trade: dict[str, Any]) -> bool:
        """Send a notification for a newly opened paper trade."""
        text = (
            "🟢 <b>Paper Trade Opened</b>\n\n"
            f"<b>Symbol:</b> {trade.get('symbol', 'N/A')}\n"
            f"<b>Side:</b> {trade.get('side', 'N/A')}\n"
            f"<b>Entry:</b> {trade.get('entry', 0):.2f}\n"
            f"<b>Stop-Loss:</b> {trade.get('stop_loss', 0):.2f}\n"
            f"<b>Take-Profit:</b> {trade.get('take_profit', 0):.2f}\n"
            f"<b>Quantity:</b> {trade.get('quantity', 0):.8f}\n"
            f"<b>Risk Amount:</b> ${trade.get('risk_amount', 0):.2f}\n"
            f"<b>Risk/Reward:</b> {trade.get('risk_reward', 0):.2f}\n"
            f"<b>Strategy:</b> {trade.get('strategy_id', 'N/A')}\n"
            f"<b>Mode:</b> {trade.get('mode', 'paper')}"
        )
        return self.send_message(text)

    def send_trade_closed(self, trade: dict[str, Any]) -> bool:
        """Send a notification for a closed paper trade."""
        status = trade.get("status", "CLOSED")
        pnl = trade.get("pnl", 0) or 0
        pnl_percent = trade.get("pnl_percent", 0) or 0

        emoji = "🟢" if pnl >= 0 else "🔴"
        status_text = {
            "CLOSED_BY_STOP": "Stop-Loss Hit",
            "CLOSED_BY_TARGET": "Take-Profit Hit",
            "CLOSED_BY_TIMEOUT": "Max Holding Time Exceeded",
        }.get(status, status)

        text = (
            f"{emoji} <b>Paper Trade Closed — {status_text}</b>\n\n"
            f"<b>Symbol:</b> {trade.get('symbol', 'N/A')}\n"
            f"<b>Entry:</b> {trade.get('entry', 0):.2f}\n"
            f"<b>Exit:</b> {trade.get('exit_price', 0):.2f}\n"
            f"<b>PnL:</b> ${pnl:.2f} ({pnl_percent:.2f}%)\n"
            f"<b>Quantity:</b> {trade.get('quantity', 0):.8f}\n"
            f"<b>Strategy:</b> {trade.get('strategy_id', 'N/A')}\n"
            f"<b>Mode:</b> {trade.get('mode', 'paper')}"
        )
        return self.send_message(text)

    def send_error(self, error: str) -> bool:
        """Send an error notification."""
        text = f"🚨 <b>Bot Error</b>\n\n<code>{error[:3000]}</code>"
        return self.send_message(text)

    def send_status(self, text: str) -> bool:
        """Send a status update."""
        msg = f"ℹ️ <b>Bot Status</b>\n\n{text}"
        return self.send_message(msg)
