"""
Firebase Admin SDK client initialization.
Parses the service account JSON from environment and initializes Firestore.
"""
import json
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client as FirestoreClient

from app.utils.logger import get_logger

logger = get_logger("firebase.client")


class FirebaseClient:
    """Manages Firebase Admin SDK initialization and Firestore access."""

    def __init__(self, service_account_json: str) -> None:
        """
        Initialize the Firebase client.

        Args:
            service_account_json: JSON string of the Firebase service account.

        Raises:
            ValueError: If the JSON is empty or invalid.
            RuntimeError: If Firebase initialization fails.
        """
        self._db: Optional[FirestoreClient] = None

        if not service_account_json or not service_account_json.strip():
            raise ValueError(
                "FIREBASE_SERVICE_ACCOUNT_JSON is empty. "
                "Please set it in your environment or .env file."
            )

        try:
            cred_dict = json.loads(service_account_json)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON: {e}"
            ) from e

        try:
            # Avoid re-initialization if already initialized
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK initialized successfully.")
            else:
                logger.info("Firebase Admin SDK already initialized.")

            self._db = firestore.client()
            logger.info("Firestore client ready.")

        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firebase: {e}") from e

    @property
    def db(self) -> FirestoreClient:
        """Return the Firestore client instance."""
        if self._db is None:
            raise RuntimeError("Firestore client is not initialized.")
        return self._db
