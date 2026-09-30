"""Model base class: the dynamics of the underlying, with its parameters."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class Model(ABC):
    """Base for all models. Subclasses are frozen dataclasses holding model parameters."""

    name: ClassVar[str]
