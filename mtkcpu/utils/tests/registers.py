from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional


def id_fn(i):
    return i


@dataclass(frozen=True)
class RegistryContents:
    reg: List[int]

    @classmethod
    def empty(cls, size: int = 32, value: int = 0):
        return RegistryContents(reg=[value for _ in range(size)])

    @classmethod
    def fill(cls, value: Optional[Callable[[], int]] = None, size: int = 32):
        if value is None:
            value = id_fn
        return RegistryContents(reg=[value(i) for i in range(size)])

    @property
    def size(self):
        return len(self.reg)
