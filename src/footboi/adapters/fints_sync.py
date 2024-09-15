"""FINTs adapter with and without 2FA authentication."""

from __future__ import annotations

import subprocess
from datetime import date, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, Optional, Self, cast

from fints.client import FinTS3PinTanClient  # type: ignore
from fints.models import SEPAAccount  # type: ignore
from fints.utils import minimal_interactive_cli_bootstrap  # type: ignore
from mt940.models import Transaction as Mt940Transaction  # type: ignore
from pydantic import BaseModel, HttpUrl, model_validator

from footboi.common import (
    MONITOR_PERIOD_IN_DAYS,
    Transaction,
    Adapter,
)

if TYPE_CHECKING:
    from footboi.config import Config
    from footboi.storage import Storage


logger = logging.getLogger(__name__)


class Bank(BaseModel):
    bic: str
    endpoint: HttpUrl
    two_factor_auth: bool = False


class Account(BaseModel):
    bank: str
    iban: str
    login: str
    password: Optional[str] = None
    password_cmd: Optional[list[str]] = None
    account_filter: list[str] = []

    @model_validator(mode="after")
    def check_password_or_password_cmd(self) -> Self:
        if (self.password is None and self.password_cmd is None) or (
            self.password is not None and self.password_cmd is not None
        ):
            raise ValueError('either "password" or "password_cmd" must be set')

        return self

    def get_password(self) -> str:
        """Return the password.

        Adapter method to retrieve the password either from property or from
        command.

        """
        if self.password:
            return self.password

        assert self.password_cmd is not None

        proc = subprocess.run(
            self.password_cmd,
            capture_output=True,
        )

        proc.check_returncode()

        return proc.stdout.decode("utf-8")


class Fints(BaseModel):
    product_id: str
    banks: dict[str, Bank]
    accounts: dict[str, Account]

    @model_validator(mode="after")
    def check_referenced_banks_in_sources(self) -> Self:
        errors: dict[str, str] = {}

        for bank in self.accounts:
            if bank not in self.banks:
                errors[f"sources.{bank}"] = f'could not find definition for bank "{bank}"'

        if errors:
            raise ValueError(errors)

        return self


def to_transaction(name: str, mt940: Mt940Transaction) -> Transaction:
    """Transform an Mt940 transaction to the internal representation.

    Args:
        transaction: Mt940Transaction
    """

    # NOTE (empwilli 2024-09-30): mt940 doesn't provide type stubs, silence the
    # errors.
    mt940_transaction = cast(Any, mt940)

    transaction_data = mt940_transaction.data

    return Transaction(
        "fints",
        name,
        datetime(
            transaction_data["date"].year,
            transaction_data["date"].month,
            transaction_data["date"].day,
        ),
        str(transaction_data["amount"]),
        transaction_data["applicant_bin"],
        transaction_data["applicant_iban"],
        transaction_data["applicant_name"],
        transaction_data["purpose"],
        transaction_data["recipient_name"],
    )


class FintsAdapter:
    """Poll from banks supporting FINTS."""

    def __init__(
        self, name: str, storage: Storage, client: FinTS3PinTanClient, account_filter: list[str], two_factor_init: bool
    ) -> None:
        self.name = name
        self.storage = storage
        self.client = client
        self.account_filter = account_filter
        self.two_factor_init = two_factor_init

    @staticmethod
    def get_adapters(config: Config, storage: Storage) -> list[Adapter]:
        fints_config = cast(Fints, config.fints)

        adapters: list[Adapter] = []

        for name, account in fints_config.accounts.items():
            bank = fints_config.banks[account.bank]

            state = storage.account_data("fints", name)

            client = FinTS3PinTanClient(
                bank.bic,
                account.login,
                account.get_password(),
                bank.endpoint,
                product_id=fints_config.product_id,
                from_data=state,
            )

            adapters.append(
                FintsAdapter(
                    name,
                    storage,
                    client,
                    account.account_filter,
                    bank.two_factor_auth,
                )
            )

        return adapters

    def setup(self) -> None:
        # NOTE (empwilli 2024-11-12): this operation consumes the client, the
        # client must not be reused.
        if not self.two_factor_init:
            self.storage.enable_account("fints", self.name)
            return

        minimal_interactive_cli_bootstrap(self.client)

        with self.client:
            if self.client.init_tan_response:
                print("A TAN is required: ", self.client.init_tan_response.challenge)
                tan = input("Please enter TAN: ")
                self.client.send_tan(self.client.init_tan_response, tan)

        state = self.client.deconstruct(including_private=True)

        self.storage.update_account_data("fints", self.name, state)
        self.storage.enable_account("fints", self.name)

    def poll(self) -> list[Transaction]:
        transactions: list[Transaction] = []

        end_date = date.today()
        start_date = end_date - timedelta(days=MONITOR_PERIOD_IN_DAYS)

        try:
            accounts: list[SEPAAccount] = self.client.get_sepa_accounts()

            for account in accounts:
                accountnumber = cast(str, account.accountnumber)  # type: ignore

                if accountnumber in self.account_filter:
                    continue

                mt940_transactions = cast(
                    list[Mt940Transaction], self.client.get_transactions(account, start_date, end_date)
                )

                transactions.extend(
                    to_transaction(self.name, mt490_transaction) for mt490_transaction in mt940_transactions
                )

            state = self.client.deconstruct(including_private=True)
        except Exception as e:
            self.storage.disable_account("fints", self.name)
            raise ValueError(f"Failed to fetch transaction data: {e}.")

        self.storage.update_account_data("fints", self.name, state)

        return transactions

    def get_name(self) -> str:
        return self.name

    def get_adapter(self) -> str:
        return "fints"


def register() -> tuple[str, type[Adapter], type[BaseModel]]:
    return "fints", FintsAdapter, Fints
