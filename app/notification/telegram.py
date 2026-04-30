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
        side = trade.get('side', 'LONG')
        emoji = "📈" if side == "LONG" else "📉"
        score = trade.get('entry_score', 0)
        grade = trade.get('entry_grade', 'N/A')
        
        text = (
            f"{emoji} <b>Paper Trade Opened</b>\n\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Symbol:</b> {trade.get('symbol', 'N/A')}\n"
            f"<b>Entry:</b> {trade.get('entry', 0):.2f}\n"
            f"<b>Stop:</b> {trade.get('stop_loss', 0):.2f}\n"
            f"<b>Target:</b> {trade.get('take_profit', 0):.2f}\n"
            f"<b>Score:</b> {score} / 100\n"
            f"<b>Grade:</b> {grade}\n"
            f"<b>Strategy:</b> {trade.get('strategy_id', 'N/A')}\n"
            f"<b>Mode:</b> {trade.get('mode', 'paper')}"
        )
        return self.send_message(text)

    def send_trade_closed(self, trade: dict[str, Any]) -> bool:
        """Send a notification for a closed paper trade."""
        status = trade.get("status", "CLOSED")
        pnl = trade.get("pnl", 0) or 0
        pnl_percent = trade.get("pnl_percent", 0) or 0
        side = trade.get("side", "LONG")

        emoji = "🟢" if pnl >= 0 else "🔴"
        status_text = {
            "CLOSED_BY_STOP": "Stop-Loss Hit",
            "CLOSED_BY_TARGET": "Take-Profit Hit",
            "CLOSED_BY_TIMEOUT": "Max Holding Time Exceeded",
        }.get(status, status)

        text = (
            f"{emoji} <b>Paper Trade Closed — {status_text}</b>\n\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Symbol:</b> {trade.get('symbol', 'N/A')}\n"
            f"<b>Entry:</b> {trade.get('entry', 0):.2f}\n"
            f"<b>Exit:</b> {trade.get('exit_price', 0):.2f}\n"
            f"<b>PnL:</b> ${pnl:.2f} ({pnl_percent:.2f}%)\n"
            f"<b>Strategy:</b> {trade.get('strategy_id', 'N/A')}\n"
            f"<b>Mode:</b> {trade.get('mode', 'paper')}"
        )
        return self.send_message(text)

    def send_scan_summary(self, symbol: str, strategy_id: str, signal: Any) -> bool:
        """Send a summary of the strategy scan."""
        metrics = signal.metrics if hasattr(signal, "metrics") else {}
        long_score = metrics.get("long_score", 0)
        short_score = metrics.get("short_score", 0)
        selected_side = metrics.get("selected_side", signal.side if signal.has_signal else "NONE")
        decision = "PAPER TRADE OPENED" if signal.has_signal else "NO TRADE"
        
        regime = metrics.get("daily_slope_regime", "N/A")
        btc_filter = metrics.get("btc_market_filter", "N/A")
        
        warnings_text = "\n".join([f"- {w}" for w in signal.warnings]) if signal.warnings else "- None"
        
        text = (
            f"📊 <b>Swing Bot Scan Summary</b>\n\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Strategy:</b> {strategy_id}\n\n"
            f"<b>Long Score:</b> {long_score} / 100\n"
            f"<b>Short Score:</b> {short_score} / 100\n"
            f"<b>Selected Side:</b> {selected_side}\n"
            f"<b>Decision:</b> {decision}\n\n"
            f"<b>Market:</b>\n"
            f"1D slope: {regime}\n"
            f"BTC filter: {btc_filter}\n\n"
            f"<b>Warnings:</b>\n{warnings_text}"
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
