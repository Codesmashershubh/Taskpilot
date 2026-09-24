from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    output: Any
    requires_approval: bool  # True = external/irreversible-facing, must go through human checkpoint
    summary: str  # one-line human-readable summary for the timeline UI


class Tool(ABC):
    name: str = "base_tool"

    @abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        raise NotImplementedError
