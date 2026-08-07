from dataclasses import dataclass


@dataclass
class Policy:
    max_attempts: int = 3
    base_delay: float = 0.01
    factor: float = 2.0
    max_delay: float = 0.05

    def delay_for(self, attempt: int) -> float:
        """Delay before retry number `attempt` (0-based)."""
        return min(self.base_delay * (self.factor ** attempt), self.max_delay)
