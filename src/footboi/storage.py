"""Persistance logic for the transaction data."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from pymongo import MongoClient

from footboi.common import Transaction, MONITOR_PERIOD_IN_DAYS
from footboi.config import Config

logger = logging.Logger(__name__)

_EXPIRY_PERIOD = MONITOR_PERIOD_IN_DAYS * 24 * 60 * 60


class Storage:
    """Storage abstraction to persist transaction data."""

    def __init__(self, config: Config) -> None:
        self.client: MongoClient[dict[str, Any]] = MongoClient(str(config.storage.mongo))

    def exists_transaction(self, transaction: Transaction) -> bool:
        """Check whether the storage already contains transaction.

        Args:
            transaction (Transaction): transaction info to look for.

        Returns:
            bool: True, if transaction already exists in the storage, False
            otherwise.

        """
        collection = self.client["footboi"]["transactions"]
        collection.create_index("inserted", expireAfterSeconds=_EXPIRY_PERIOD)

        if collection.find_one(transaction.__dict__):
            return True

        return False

    def store_transaction(self, transaction: Transaction) -> None:
        """Store a transaction.

        Args:
            endpoint (str): endpoint description as described in the config.
            account (str): account as described in the config.
            transaction (Transactio): transaction info to store.
        """
        collection = self.client["footboi"]["transactions"]
        collection.create_index("inserted", expireAfterSeconds=_EXPIRY_PERIOD)

        collection.insert_one(  # pyright: ignore
            {
                "inserted": datetime.datetime.now(datetime.timezone.utc),
                **transaction.__dict__,
            }
        )

    def is_account_enabled(self, adapter: str, name: str) -> bool:
        """Check whether the endpoint is currently enabled.

        Args:
            adapter (str): adapter used for access to an endpoint as described in the config.
            name (str): account name in the config.

        Returns:
            bool: True, if the endpoint is enabled, False if it is not initialized yet or
            it is disabled.
        """
        collection = self.client["footboi"]["info"]

        info = collection.find_one(
            {
                "adapter": adapter,
                "name": name,
            }
        )

        if info is None:
            return False

        return info.get("active", False)

    def enable_account(self, adapter: str, name: str) -> None:
        """Disable an account.

        Args:
            adapter (str): adapter used for access to an endpoint as described in the config.
            name (str): account name in the config.
        """
        collection = self.client["footboi"]["info"]

        print(f"enable account: {adapter} {name}")

        collection.update_one(
            {
                "adapter": adapter,
                "name": name,
            },
            {
                "$set": {
                    "active": True,
                }
            },
            upsert=True,
        )

    def disable_account(self, adapter: str, name: str) -> None:
        """Disable an account.

        Args:
            adapter (str): adapter used for access to an endpoint as described in the config.
            name (str): account name in the config.
        """
        collection = self.client["footboi"]["info"]

        collection.update_one(
            {
                "adapter": adapter,
                "name": name,
            },
            {
                "$set": {
                    "active": False,
                }
            },
        )

    def update_account_data(self, adapter: str, name: str, data: bytes) -> None:
        """Update auxiliary data for an account.

        Args:
            adapter (str): adapter used for access to an endpoint as described in the config.
            name (str): account name in the config.
            data (bytes): new auxiliary data.
        """
        collection = self.client["footboi"]["info"]

        collection.insert_one(  # pyright: ignore
            {
                "adapter": adapter,
                "name": name,
                "data": data,
            }
        )

    def account_data(self, adapter: str, name: str) -> bytes | None:
        """Get auxiliary data for the respective endpoint.

        Args:
            adapter (str): adapter used for access to an endpoint as described in the config.
            name (str): account name in the config.

        Returns:
            bytes | None: auxiliary data, if available.
        """
        collection = self.client["footboi"]["info"]

        result = collection.find_one(
            {
                "adapter": adapter,
                "name": name,
            }
        )

        if result is None or not result.get("active", False):
            logging.info(
                "Skipping uninitialized config: % %",
                adapter,
                name,
            )
            return None

        return result.get("data")
