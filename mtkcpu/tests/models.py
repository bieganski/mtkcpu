from __future__ import annotations
from dataclasses import dataclass
from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.tests.exceptions import OverlappingMemoryError, EmptyMemoryError, InvalidMemoryValueError
from typing import List, Dict, Optional, Iterable, Generator
from enum import Enum, unique
from itertools import count, groupby, islice
from mtkcpu.asm.asm_dump import dump_asm
from mtkcpu.utils.common import START_ADDR
from enum import Enum, unique

from io import StringIO


def ranges(i: Iterable[int]) -> Generator[Tuple[int, int], None, None]:
    for a, b in groupby(enumerate(i), lambda pair: pair[1] - pair[0]):
        b = list(b)
        yield b[0][1], b[-1][1]


@dataclass(frozen=True)
class MemoryContents:
    memory: Dict[int, int]

    @property
    def size(self):
        return len(self.memory)

    def get_overlap(self, mem: MemoryContents) -> Generator[Tuple[int, int], None, None]:
        mem_keys = set(mem.memory.keys())
        self_keys = set(self.memory)
        return ranges(mem_keys.intersection(self_keys))

    def set(self, index: int, value: int):
        self.memory[index] = value

    def get_default(self, index: int, default: int = 0):
        if index in self.memory:
            return self.memory[index]
        return default

    def assert_equality(self, expected: MemoryContents, raise_errors: bool = True) -> bool:
        for index, value in expected.memory.items():
            if index not in self.memory:
                if not raise_errors:
                    return False
                raise EmptyMemoryError(index=index, expected=value)
            if self.memory[index] != value:
                if not raise_errors:
                    return False
                raise InvalidMemoryValueError(index=index, actual=self.memory[index], expected=value)
        return True

    def patch(
        self,
        mem: MemoryContents,
        can_overlap: bool = True,
        overlap_message_limit: int = 5,
    ) -> MemoryContents:
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
        return new_memory_contents

    @classmethod
    def empty(cls):
        return MemoryContents(memory=dict())


@dataclass(frozen=True)
class RegistryContents:
    reg: List[int]

    @classmethod
    def empty(cls, size: int = 32, value: int = 0):
        return RegistryContents(reg=[value for _ in range(size)])

    @property
    def size(self):
        return len(self.reg)


@unique
class MemState(Enum):
    FREE = 0
    BUSY_READ = 1
    BUSY_WRITE = 2
