from typing import List, Tuple


class OverlappingMemoryError(Exception):
    overlapping_locations: List[Tuple[int, int]]

    def __init__(self, overlapping_locations: List[Tuple[int, int]], locations_limit: int):
        self.overlapping_locations = overlapping_locations
        locations_str = ', '.join([(f"{start} to {end}" if start != end else f"{start}") for (start, end) in self.overlapping_locations])
        message = f"Memory overlap detected. Overlapping positions are: {locations_str} " \
                  f"(trimmed to first {locations_limit} results)"

        super().__init__(message)


class InvalidMemoryContentsError(Exception):
    index: int

    def __init__(self, message: str, index: int):
        super().__init__(f"Invalid memory contents at index {self.index}: {message}")
        self.index = index


class EmptyMemoryError(InvalidMemoryContentsError):
    def __init__(self, index: int, expected: int):
        super().__init__(f"memory is empty, but expected: {expected}", index)


class InvalidMemoryValueError(InvalidMemoryContentsError):
    def __init__(self, index: int, actual: int, expected: int):
        super().__init__(f"memory contains {actual}, but expected {expected}", index)