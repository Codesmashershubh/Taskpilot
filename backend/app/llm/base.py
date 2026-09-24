from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_estimate: float  # USD; 0.0 on free tiers, tracked anyway for interview talking points


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def complete(self, system: str, user: str, json_mode: bool = False, max_tokens: int = 800) -> LLMResponse:
        """Run one completion. Implementations must raise on failure (caller handles retry/escalation)."""
        raise NotImplementedError
