"""Functionality to send webhooks."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import logging
from typing import Any

import json

import requests

from footboi.common import Transaction
from footboi.config import Notification

logger = logging.Logger(__name__)


class _HookType(StrEnum):
    FetchFail = "fetch.failure"
    NewTransactions = "transactions.new"


@dataclass
class _Payload:
    type: _HookType
    timestamp: datetime
    data: dict[str, Any]


class _PayloadEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, _Payload):
            return {
                "type": str(o.type),
                "timestamp": str(o.timestamp),
                "data": o.data,
            }
        elif isinstance(o, datetime):
            return str(o)

        return super().default(o)  # type: ignore


def _notify(endpoints: list[str], type: _HookType, data: dict[str, Any]) -> None:
    notification = _Payload(
        type=type,
        timestamp=datetime.now(),
        data=data,
    )

    for endpoint in endpoints:
        request = requests.post(endpoint, data=json.dumps(notification, cls=_PayloadEncoder))
        if request.status_code >= 400:
            logger.warning(
                "Could not reach endpoint %s: %s.",
                endpoint,
                request.status_code,
            )


def notify_transactions(config: Notification, transactions: list[Transaction]) -> None:
    for transaction in transactions:
        _notify(
            list(map(str, config.endpoints or [])),
            _HookType.NewTransactions,
            transaction.__dict__,
        )


def notify_poll_fail(config: Notification, bank: str, account: str) -> None:
    _notify(
        list(map(str, config.endpoints or [])),
        _HookType.FetchFail,
        {
            "bank": bank,
            "account": account,
        },
    )
