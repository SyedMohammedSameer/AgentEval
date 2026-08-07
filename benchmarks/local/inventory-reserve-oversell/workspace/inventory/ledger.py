from dataclasses import dataclass


class InsufficientStock(Exception):
    """Not enough available stock to satisfy the request."""


@dataclass
class Entry:
    on_hand: int
    reserved: int = 0

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved
