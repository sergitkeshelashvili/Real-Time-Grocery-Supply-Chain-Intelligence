from typing import Protocol

class AIProvider(Protocol):
    def explain(self, risks: list[dict]) -> list[dict]: ...
