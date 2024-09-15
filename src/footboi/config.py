"""Config file parsing and processing."""

from __future__ import annotations

import re
import tomllib
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Self, Union

from pydantic import BaseModel, HttpUrl, MongoDsn, create_model, field_validator
from pydantic_settings import BaseSettings

from footboi.adapter import ADAPTER_CONFIG


class Notification(BaseModel):
    endpoints: Optional[list[HttpUrl]] = []


class Storage(BaseModel):
    mongo: MongoDsn


config_attributes = {
    "interval": (timedelta, None),
    "storage": (Storage, None),
    "notification": (Notification, None),
    **{name: (Union[config, None], None) for name, config in ADAPTER_CONFIG.items()},
}


def parse_timedelta(cls: "Config", value: str) -> timedelta:  # type: ignore
    time_units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}

    match = re.match(r"(?P<value>\d+)(?P<unit>[smhd])$", value)
    if not match:
        raise ValueError(f"Invalid time format: {value}")

    time_value = int(match.group("value"))
    time_unit = match.group("unit")

    # Create timedelta object
    kwargs = {time_units[time_unit]: time_value}
    return timedelta(**kwargs)


validators = {  # type: ignore
    "interval_validator": field_validator("interval", mode="before")(parse_timedelta)  # type: ignore
}

if TYPE_CHECKING:
    class Config(BaseModel):
        interval: timedelta
        storage: Storage
        notification: Notification

        @classmethod
        def from_toml_file(cls, config_path: Path) -> Self: ...

        def __getattr__(self, name: str) -> object: ...

else:
    Config = create_model(
        "Config",
        **config_attributes,
        __validators__=validators,  # type: ignore
        __base__=BaseSettings,
    )


def from_toml_file(cls: type[Config], config_path: Path) -> Config:  # type: ignore
    with config_path.open("rb") as config_file:
        config = tomllib.load(config_file)

    return cls(**config)  # type: ignore


setattr(Config, "from_toml_file", classmethod(from_toml_file))
