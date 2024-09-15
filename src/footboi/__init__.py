from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from footboi.adapter import ADAPTER
from footboi.storage import Storage
from footboi.common import Transaction, Adapter
from footboi.config import Config
from footboi.webhook import notify_transactions

logger = logging.getLogger()

def _get_transactions(
    accounts: list[Adapter],
    storage: Storage,
) -> list[Transaction]:
    new_transactions: list[Transaction] = []

    for account in accounts:
        account_adapter = account.get_adapter()
        account_name = account.get_name()
        if not storage.is_account_enabled(account_adapter, account_name):
            logger.info("Skipping inactive account: %s.%s", account_adapter, account_name)
            return []

        transactions: list[Transaction]

        try:
            transactions = account.poll()
        except Exception as e:
            logging.warning(
                "Failed to poll transactions for %s %s: %s. Deactivating connection.",
                account.get_adapter(),
                account.get_name(),
                e,
            )
            storage.disable_account(account_adapter, account_name)
            continue

        new_transactions.extend(transactions)

    return new_transactions


def _get_accounts(config: Config) -> list[Adapter]:
    adapters: list[Adapter] = []

    storage = Storage(config)

    for adapter in ADAPTER.values():
        adapters.extend(adapter.get_adapters(config, storage))

    return adapters


def init(args: argparse.Namespace) -> None:
    """Perform initialization steps for the specified accounts."""
    config_path = Path()

    if args.config:
        config_path = args.config

    config = Config.from_toml_file(config_path)

    storage = Storage(config)

    accounts = _get_accounts(config)

    for account in accounts:
        account_adapter = account.get_adapter()
        account_name = account.get_name()

        if not storage.is_account_enabled(account_adapter, account_name):
            continue

        account.setup()


def fetch(args: argparse.Namespace) -> None:
    """Fetch transaction data and emit notifications."""
    config_path = Path()

    if args.config:
        config_path = args.config

    config = Config.from_toml_file(config_path)

    storage = Storage(config)

    accounts = _get_accounts(config)

    new_transactions = _get_transactions(accounts, storage)

    for transaction in new_transactions:
        if storage.exists_transaction(transaction):
            continue

        new_transactions.append(transaction)

        storage.store_transaction(transaction)

    notify_transactions(config.notification, new_transactions)


def cli() -> None:
    """Entry point for the sync service."""
    parser = argparse.ArgumentParser(
        prog="footboi",
        description="Service utility to notify on new bank transactions.",
    )

    parser.add_argument(
        "-c",
        "--config",
        required=False,
        type=Path,
        help="Path to the config file, defaults to XDG_CONFIG_DIRS/config.toml",
        default=Path(os.environ.get("XDG_CONFIG_HOME", "~/.config/footboi")) / "config.toml",
    )

    subparser = parser.add_subparsers(required=True)

    init_parser = subparser.add_parser(
        "init", help="(Re)-initialize accounts in the config. Necessary, e.g. for providers that require 2FA."
    )
    init_parser.set_defaults(func=init)

    fetch_parser = subparser.add_parser("fetch", help=("Fetch transactions."))
    fetch_parser.set_defaults(func=fetch)

    args = parser.parse_args()

    args.func(args)
