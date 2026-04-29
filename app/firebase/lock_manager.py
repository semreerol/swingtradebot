"""
Distributed lock manager using Firestore.
Prevents concurrent bot executions.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from google.cloud.firestore import Client as FirestoreClient

from app.utils.logger import get_logger

logger = get_logger("firebase.lock_manager")

DEFAULT_LOCK_TIMEOUT_MINUTES = 30


class LockManager:
    """
    Manages a distributed lock via Firestore bot_locks/main document.

    The lock includes a timeout mechanism: if a previous run crashed
    without releasing the lock, the next run can acquire it after
    the timeout period has elapsed.
    """

    def __init__(
        self,
        db: FirestoreClient,
        timeout_minutes: int = DEFAULT_LOCK_TIMEOUT_MINUTES,
    ) -> None:
        self._db = db
        self._timeout_minutes = timeout_minutes
        self._doc_ref = self._db.collection("bot_locks").document("main")
        self._run_id: Optional[str] = None

    def acquire(self, run_id: str) -> bool:
        """
        Attempt to acquire the lock.

        Args:
            run_id: Unique identifier for this bot run.

        Returns:
            True if the lock was acquired, False otherwise.
        """
        self._run_id = run_id
        doc = self._doc_ref.get()

        if doc.exists:
            lock_data = doc.to_dict()
            if lock_data.get("locked", False):
                locked_at_str = lock_data.get("locked_at", "")
                if locked_at_str:
                    try:
                        locked_at = datetime.fromisoformat(locked_at_str)
                        if locked_at.tzinfo is None:
                            locked_at = locked_at.replace(tzinfo=timezone.utc)
                        elapsed = datetime.now(timezone.utc) - locked_at
                        timeout = timedelta(minutes=self._timeout_minutes)

                        if elapsed < timeout:
                            logger.warning(
                                f"Lock is active (run: {lock_data.get('run_id')}). "
                                f"Elapsed: {elapsed}. Timeout: {timeout}. "
                                "Skipping this run."
                            )
                            return False

                        logger.warning(
                            f"Lock expired (elapsed: {elapsed}). "
                            "Forcing lock acquisition."
                        )
                    except (ValueError, TypeError):
                        logger.warning(
                            "Could not parse locked_at timestamp. "
                            "Forcing lock acquisition."
                        )

        # Acquire the lock
        self._doc_ref.set({
            "locked": True,
            "locked_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
        })
        logger.info(f"Lock acquired for run: {run_id}")
        return True

    def release(self) -> None:
        """Release the lock."""
        try:
            self._doc_ref.set({
                "locked": False,
                "locked_at": None,
                "run_id": None,
            })
            logger.info(f"Lock released for run: {self._run_id}")
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
