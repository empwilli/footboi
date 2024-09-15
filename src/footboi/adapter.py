"""Provides synchronization functions for banks."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING

from pydantic import BaseModel

import footboi.adapters

if TYPE_CHECKING:
    from footboi.common import Adapter

logger = logging.Logger(__name__)

ADAPTER: dict[str, "Adapter"] = {}
ADAPTER_CONFIG: dict[str, type[BaseModel]] = {}

adapter_modules = pkgutil.iter_modules(footboi.adapters.__path__, footboi.adapters.__name__ + ".")  # pyright: ignore
for _, name, ispkg in adapter_modules:
    if ispkg:
        continue

    try:
        module = importlib.import_module(name)
    except ImportError as e:
        logger.warning('Could not import module "%s": %s', name, e)
        continue

    if not hasattr(module, "register"):
        logger.warning("Invalid adapter module %s, no register function.", name)
        continue

    register_adapter = getattr(module, "register")

    if not callable(register_adapter):
        logger.warning("Invalid adapter module %s, no valid register function.", name)
        continue

    name, adapter_type, adapter_config = register_adapter()  # pyright: ignore

    ADAPTER[name] = adapter_type  # pyright: ignore
    ADAPTER_CONFIG[name] = adapter_config  # pyright: ignore
