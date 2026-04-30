"""
Firestore repository layer.
Handles all CRUD operations for bot collections.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from google.cloud.firestore import Client as FirestoreClient

from app.utils.logger import get_logger

logger = get_logger("firebase.repositories")


# ── Default Documents ────────────────────────────────────────────────────────

DEFAULT_BOT_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "mode": "paper",
    "symbol": "BTCUSDT",
    "quote_currency": "USDT",
    "timeframe_trend": "1d",
    "timeframe_entry": "4h",
    "risk_per_trade": 0.01,
    "account_balance": 10000,
    "max_open_positions": 1,
    "max_holding_days": 14,
    "min_risk_reward": 2.0,
    "strategy_id": "daily_trend_4h_score_long_short_v3",
    "allow_long": True,
    "allow_short": True,
}

DEFAULT_STRATEGY_CONFIG: dict[str, Any] = {
    "name": "Daily Trend 4H Score Long Short",
    "version": "3.0.0",
    "enabled": True,
    "params": {
        "ema_fast": 20,
        "ema_slow": 50,
        "rsi_length": 14,
        "rsi_long_min": 45,
        "rsi_long_max": 70,
        "rsi_short_min": 30,
        "rsi_short_max": 55,
        "atr_length": 14,
        "atr_stop_multiplier": 2.0,
        "risk_reward": 2.0,
        "volume_ma_length": 20,
        "volume_ratio_min": 1.0,
        "volume_ratio_strong": 1.2,
        "breakout_lookback": 20,
        "near_breakout_tolerance_percent": 0.3,
        "slope_lookback": 5,
        "strong_positive_slope_percent": 1.0,
        "strong_negative_slope_percent": -1.0,
        "atr_percent_min": 1.0,
        "atr_percent_max": 8.0,
        "min_score_to_trade": 75,
        "btc_filter_enabled": True,
        "btc_filter_reject_opposite": True,
        "allow_long": True,
        "allow_short": True
    },
}


class BotRepository:
    """Repository for all Firestore bot collections."""

    def __init__(self, db: FirestoreClient) -> None:
        self._db = db

    # ── Bot Settings ─────────────────────────────────────────────────────

    def get_bot_settings(self) -> dict[str, Any]:
        """
        Read bot_settings/main document.
        Creates it with defaults if it doesn't exist.
        """
        doc_ref = self._db.collection("bot_settings").document("main")
        doc = doc_ref.get()

        if doc.exists:
            logger.info("Loaded bot_settings/main from Firestore.")
            return doc.to_dict()

        logger.warning("bot_settings/main not found. Creating with defaults.")
        doc_ref.set(DEFAULT_BOT_SETTINGS)
        return DEFAULT_BOT_SETTINGS.copy()

    # ── Strategy Config ──────────────────────────────────────────────────

    def get_strategy_config(self, strategy_id: str) -> dict[str, Any]:
        """
        Read strategies/{strategy_id} document.
        Creates it with defaults if it doesn't exist.
        """
        doc_ref = self._db.collection("strategies").document(strategy_id)
        doc = doc_ref.get()

        if doc.exists:
            logger.info(f"Loaded strategies/{strategy_id} from Firestore.")
            return doc.to_dict()

        logger.warning(
            f"strategies/{strategy_id} not found. Creating with defaults."
        )
        doc_ref.set(DEFAULT_STRATEGY_CONFIG)
        return DEFAULT_STRATEGY_CONFIG.copy()

    # ── Signals ──────────────────────────────────────────────────────────

    def create_signal(self, signal_data: dict[str, Any]) -> str:
        """
        Create a new signal document.

        Returns:
            The generated signal ID.
        """
        signal_id = f"signal_{uuid.uuid4().hex[:12]}"
        signal_data["created_at"] = datetime.now(timezone.utc).isoformat()

        self._db.collection("signals").document(signal_id).set(signal_data)
        logger.info(f"Created signal: {signal_id}")
        return signal_id

    # ── Trades ───────────────────────────────────────────────────────────

    def get_open_trade(self, symbol: str) -> Optional[tuple[str, dict[str, Any]]]:
        """
        Get the currently open trade for a symbol.

        Returns:
            Tuple of (trade_id, trade_data) or None.
        """
        trades_ref = self._db.collection("trades")
        from google.cloud.firestore import FieldFilter
        query = (
            trades_ref
            .where(filter=FieldFilter("symbol", "==", symbol))
            .where(filter=FieldFilter("status", "==", "OPEN"))
            .limit(1)
        )
        docs = list(query.stream())

        if docs:
            doc = docs[0]
            logger.info(f"Found open trade: {doc.id}")
            return (doc.id, doc.to_dict())

        logger.info(f"No open trade found for {symbol}.")
        return None

    def create_trade(self, trade_data: dict[str, Any]) -> str:
        """
        Create a new trade document.

        Returns:
            The generated trade ID.
        """
        trade_id = f"trade_{uuid.uuid4().hex[:12]}"
        self._db.collection("trades").document(trade_id).set(trade_data)
        logger.info(f"Created trade: {trade_id}")
        return trade_id

    def update_trade(self, trade_id: str, updates: dict[str, Any]) -> None:
        """Update fields on an existing trade document."""
        self._db.collection("trades").document(trade_id).update(updates)
        logger.info(f"Updated trade {trade_id}: {list(updates.keys())}")

    # ── Trade Events ─────────────────────────────────────────────────────

    def create_trade_event(
        self,
        trade_id: str,
        event_type: str,
        details: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Log a trade event.

        Args:
            trade_id: Related trade document ID.
            event_type: OPENED, CLOSED_BY_STOP, CLOSED_BY_TARGET,
                        CLOSED_BY_TIMEOUT, STATUS_CHECK.
            details: Additional event data.

        Returns:
            The generated event ID.
        """
        event_id = f"event_{uuid.uuid4().hex[:12]}"
        event_data = {
            "trade_id": trade_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
        self._db.collection("trade_events").document(event_id).set(event_data)
        logger.info(f"Created trade event: {event_type} for {trade_id}")
        return event_id

    # ── Bot Runs ─────────────────────────────────────────────────────────

    def create_bot_run(self, run_data: dict[str, Any]) -> str:
        """
        Log a bot run result.

        Returns:
            The generated run ID.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        self._db.collection("bot_runs").document(run_id).set(run_data)
        logger.info(f"Created bot run: {run_id} ({run_data.get('status', 'unknown')})")
        return run_id
