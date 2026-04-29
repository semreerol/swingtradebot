"""
Configuration module.
Reads environment variables and provides a typed Config dataclass.
"""
import os
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Firebase
    firebase_service_account_json: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Bot
    bot_env: str = "development"
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.bot_env.lower() == "production"

    @property
    def has_firebase(self) -> bool:
        return bool(self.firebase_service_account_json.strip())

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token.strip() and self.telegram_chat_id.strip())

    @property
    def firebase_credentials_dict(self) -> Optional[dict]:
        """Parse the Firebase JSON string into a dict."""
        if not self.has_firebase:
            return None
        try:
            return json.loads(self.firebase_service_account_json)
        except json.JSONDecodeError:
            logging.error("Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON")
            return None


def load_config() -> Config:
    """Load configuration from environment variables."""
    # Load .env file if it exists (local development)
    load_dotenv()

    config = Config(
        firebase_service_account_json=os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", ""),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        bot_env=os.getenv("BOT_ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )

    return config
