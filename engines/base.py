from abc import ABC, abstractmethod
from collections.abc import Sequence


class Engine[InputT, OutputT](ABC):
    @abstractmethod
    def execute(self, items: Sequence[InputT]) -> OutputT: ...

