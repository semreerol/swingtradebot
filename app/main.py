"""
Swing Trade Bot — Main Entry Point.

Orchestrates the complete bot lifecycle:
1. Load config, initialize services.
2. Acquire Firestore lock.
3. Check for open trades or generate new signals.
4. Record run results and release lock.
"""
import sys
import uuid
import traceback
from datetime import datetime, timezone

from app.config import load_config
from app.utils.logger import setup_logger, get_logger
from app.firebase.client import FirebaseClient
from app.firebase.repositories import BotRepository
from app.firebase.lock_manager import LockManager
from app.notification.telegram import TelegramNotifier
from app.exchange.binance_market_data import fetch_klines, fetch_current_price
from app.strategies import daily_trend_4h_entry
from app.risk.risk_manager import validate_signal
from app.execution.paper_executor import create_paper_trade, check_open_trade


def main() -> None:
    """Main bot execution flow."""

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Config & Logger ──────────────────────────────────────────
    config = load_config()
    logger = setup_logger(config.log_level)
    log = get_logger("main")

    log.info(f"=== Swing Trade Bot Starting === (run: {run_id})")
    log.info(f"Environment: {config.bot_env}")

    # ── Step 2: Telegram Notifier ────────────────────────────────────────
    notifier = TelegramNotifier(
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
    )

    # ── Step 3: Firebase Client ──────────────────────────────────────────
    repo = None
    lock_manager = None

    try:
        firebase_client = FirebaseClient(config.firebase_service_account_json)
        repo = BotRepository(firebase_client.db)
        lock_manager = LockManager(firebase_client.db)
    except (ValueError, RuntimeError) as e:
        log.error(f"Firebase initialization failed: {e}")
        notifier.send_error(f"Firebase initialization failed: {e}")
        sys.exit(1)

    try:
        _run_bot(
            repo=repo,
            lock_manager=lock_manager,
            notifier=notifier,
            run_id=run_id,
            started_at=started_at,
            log=log,
        )
    except Exception as e:
        # ── Step 13: Error handling ──────────────────────────────────
        error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        log.error(f"Bot run FAILED: {error_msg}")

        # Record failed run
        try:
            repo.create_bot_run({
                "status": "failed",
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "message": str(e)[:500],
                "symbol": "N/A",
            })
        except Exception as run_err:
            log.error(f"Failed to record bot run: {run_err}")

        # Notify via Telegram
        notifier.send_error(str(e)[:1000])

        # Release lock
        if lock_manager:
            try:
                lock_manager.release()
            except Exception as lock_err:
                log.error(f"Failed to release lock on error: {lock_err}")

        sys.exit(1)


def _run_bot(
    repo: BotRepository,
    lock_manager: LockManager,
    notifier: TelegramNotifier,
    run_id: str,
    started_at: str,
    log,
) -> None:
    """Core bot logic, separated for clean error handling."""

    # ── Step 5: Read Bot Settings ────────────────────────────────────────
    settings = repo.get_bot_settings()
    symbol = settings["symbol"]
    log.info(f"Bot settings loaded. Symbol: {symbol}, Mode: {settings['mode']}")

    # ── Step 6: Check enabled flag ───────────────────────────────────────
    if not settings.get("enabled", True):
        log.info("Bot is DISABLED via bot_settings. Exiting.")
        repo.create_bot_run({
            "status": "skipped",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "message": "Bot disabled in settings.",
            "symbol": symbol,
        })
        return

    # ── Step 7: Acquire Lock ─────────────────────────────────────────────
    if not lock_manager.acquire(run_id):
        log.warning("Could not acquire lock. Another instance may be running.")
        repo.create_bot_run({
            "status": "skipped",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "message": "Could not acquire lock.",
            "symbol": symbol,
        })
        return

    try:
        # ── Step 8: Check for Open Trade ─────────────────────────────
        open_trade_result = repo.get_open_trade(symbol)

        if open_trade_result:
            # ── Step 9: Manage Existing Trade ────────────────────────
            trade_id, trade_data = open_trade_result
            log.info(f"Open trade found: {trade_id}")

            # Fetch current price
            current_price = fetch_current_price(symbol)

            # Check trade status
            close_reason, updates = check_open_trade(trade_data, current_price)

            if close_reason:
                # Trade closed
                repo.update_trade(trade_id, updates)
                repo.create_trade_event(trade_id, close_reason, {
                    "current_price": current_price,
                    "exit_price": updates.get("exit_price"),
                    "pnl": updates.get("pnl"),
                })

                # Merge for notification
                closed_trade = {**trade_data, **updates}
                notifier.send_trade_closed(closed_trade)

                log.info(f"Trade {trade_id} closed: {close_reason}")

                message = (
                    f"Trade {trade_id} closed: {close_reason}. "
                    f"PnL: {updates.get('pnl', 0):.2f}"
                )
            else:
                # Trade still open — log status check
                repo.create_trade_event(trade_id, "STATUS_CHECK", {
                    "current_price": current_price,
                })
                message = f"Open trade {trade_id} checked. Price: {current_price:.2f}"

            # After closing a trade, also look for new signals
            if close_reason:
                log.info("Trade closed. Looking for new signals...")
                _search_new_signal(
                    repo=repo,
                    notifier=notifier,
                    settings=settings,
                    log=log,
                )

        else:
            # ── Step 10: Search for New Signal ───────────────────────
            log.info("No open trade. Searching for new signal...")
            _search_new_signal(
                repo=repo,
                notifier=notifier,
                settings=settings,
                log=log,
            )
            message = "Signal search completed."

        # ── Step 11: Record Successful Run ───────────────────────────
        repo.create_bot_run({
            "status": "success",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "symbol": symbol,
        })

    finally:
        # ── Step 12: Release Lock ────────────────────────────────────
        lock_manager.release()

    log.info("=== Swing Trade Bot Finished ===")


def _search_new_signal(
    repo: BotRepository,
    notifier: TelegramNotifier,
    settings: dict,
    log,
) -> None:
    """Search for new trading signals and create paper trades if approved."""

    symbol = settings["symbol"]
    strategy_id = settings["strategy_id"]

    # Double-check no open trade exists
    if repo.get_open_trade(symbol):
        log.info("Open trade exists. Skipping new signal search.")
        return

    # Load strategy config
    strategy_config = repo.get_strategy_config(strategy_id)
    if not strategy_config.get("enabled", True):
        log.info(f"Strategy {strategy_id} is disabled. Skipping.")
        return

    params = strategy_config.get("params", {})

    # Fetch market data
    log.info(f"Fetching market data for {symbol}...")
    candles_1d = fetch_klines(symbol, settings.get("timeframe_trend", "1d"), limit=200)
    candles_4h = fetch_klines(symbol, settings.get("timeframe_entry", "4h"), limit=200)

    # Fetch BTC market data for filter if enabled and needed
    btc_filter_enabled = params.get("btc_filter_enabled", True)
    btc_candles_1d = None
    if btc_filter_enabled and symbol != "BTCUSDT":
        log.info("Fetching BTCUSDT market data for BTC filter...")
        btc_candles_1d = fetch_klines("BTCUSDT", settings.get("timeframe_trend", "1d"), limit=200)

    # Strategy Factory
    if strategy_id == "daily_trend_4h_score_long_short_v3":
        from app.strategies.daily_trend_4h_score_long_short import DailyTrend4HScoreLongShortStrategy
        strategy = DailyTrend4HScoreLongShortStrategy()
        signal = strategy.evaluate(
            symbol=symbol,
            candles_1d=candles_1d,
            candles_4h=candles_4h,
            params=params,
            btc_candles_1d=btc_candles_1d
        )
    else:
        # Fallback to older strategy
        signal = daily_trend_4h_entry.evaluate(
            symbol=symbol,
            candles_1d=candles_1d,
            candles_4h=candles_4h,
            params=params,
        )

    # Send scan summary
    if strategy_id == "daily_trend_4h_score_long_short_v3":
        notifier.send_scan_summary(symbol, strategy_id, signal)

    if not signal.has_signal:
        log.info(f"No signal generated. Reasons: {signal.reason}")
        return

    # Validate with risk manager
    risk_result = validate_signal(
        signal=signal,
        account_balance=settings.get("account_balance", 10000),
        risk_per_trade=settings.get("risk_per_trade", 0.01),
        min_risk_reward=settings.get("min_risk_reward", 2.0),
        has_open_trade=False,
    )

    if not risk_result.approved:
        log.info(f"Signal rejected by risk manager: {risk_result.rejection_reasons}")
        return

    # Create paper trade
    account_balance = settings.get("account_balance", 10000)
    trade_data = create_paper_trade(
        signal=signal,
        risk_result=risk_result,
        max_holding_days=settings.get("max_holding_days", 14),
        account_balance=account_balance,
    )
    trade_data["entry_score"] = getattr(signal, "score", 0)
    trade_data["entry_grade"] = getattr(signal, "grade", "")
    trade_data["entry_metrics"] = getattr(signal, "metrics", {})
    trade_data["entry_warnings"] = getattr(signal, "warnings", [])

    # Save signal to Firestore
    signal_id = repo.create_signal(signal.to_dict())
    trade_data["signal_id"] = signal_id

    # Save trade to Firestore
    trade_id = repo.create_trade(trade_data)

    # Log trade event
    repo.create_trade_event(trade_id, "OPENED", {
        "signal_id": signal_id,
        "entry": signal.entry,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
    })

    # Send Telegram notification
    notifier.send_trade_opened(trade_data)

    log.info(f"Paper trade opened: {trade_id} (signal: {signal_id})")


if __name__ == "__main__":
    main()
