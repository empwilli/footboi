"""Common utilities of the transaction adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from footboi.config import Config
    from footboi.storage import Storage

# NOTE (empwilli 2024-10-08): We get roughly data for the last 30 days without
# 2 factor, so use this as a limit.

MONITOR_PERIOD_IN_DAYS = 31


@dataclass
class Transaction:
    adapter: str
    name: str
    date: datetime
    amount: str
    applicant_bin: str
    applicant_iban: str
    applicant_name: str
    purpose: str
    recipient_name: str


class Adapter(Protocol):
    """A type that can be used to fetch transactions."""

    @staticmethod
    def get_adapters(config: "Config", storage: "Storage") -> list[Adapter]: ...

    def setup(self) -> None: ...

    def poll(self) -> list[Transaction]: ...

    def get_name(self) -> str: ...

    def get_adapter(self) -> str: ...
