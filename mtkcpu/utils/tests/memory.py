from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from itertools import groupby, islice
from typing import Dict, Generator, Iterable, Tuple

from mtkcpu.utils.tests.exceptions import (EmptyMemoryError,
                                           InvalidMemoryValueError,
                                           OverlappingMemoryError)


def ranges(i: Iterable[int]) -> Generator[Tuple[int, int], None, None]:
    for a, b in groupby(enumerate(i), lambda pair: pair[1] - pair[0]):
        b = list(b)
        yield b[0][1], b[-1][1]


@unique
class MemState(Enum):
    FREE = 0
    BUSY_READ = 1
    BUSY_WRITE = 2


@dataclass(frozen=False)
class MemoryContents:
    memory: Dict[int, int]

    @property
    def size(self):
        return len(self.memory)

    def shift_addresses(self, offset):
        self.memory = dict([(k + offset, v) for k, v in self.memory.items()])

    def get_overlap(
        self, mem: MemoryContents
    ) -> Generator[Tuple[int, int], None, None]:
        mem_keys = set(mem.memory.keys())
        self_keys = set(self.memory)
        return ranges(mem_keys.intersection(self_keys))

    def set(self, index: int, value: int):
        self.memory[index] = value

    def get_default(self, index: int, default: int = 0):
        if index in self.memory:
            return self.memory[index]
        return default

    def assert_equality(
        self, expected: MemoryContents, raise_errors: bool = True
    ) -> bool:
        for index, value in expected.memory.items():
            if index not in self.memory:
                if not raise_errors:
                    return False
                raise EmptyMemoryError(index=index, expected=value)
            if self.memory[index] != value:
                if not raise_errors:
                    return False
                raise InvalidMemoryValueError(
                    index=index, actual=self.memory[index], expected=value
                )
        return True

    def patch(
        self,
        mem: MemoryContents,
        can_overlap: bool = True,
        overlap_message_limit: int = 5,
    ) -> None:
        new_memory_contents = MemoryContents(
            memory={**self.memory, **mem.memory},
        )
        if not can_overlap:
            if mem.size + self.size != new_memory_contents.size:
                # Overlap was detected
                raise OverlappingMemoryError(
                    list(islice(self.get_overlap(mem), overlap_message_limit)),
                    overlap_message_limit,
                )
        self.memory = new_memory_contents.memory

    @classmethod
    def empty(cls):
        return MemoryContents(memory=dict())
