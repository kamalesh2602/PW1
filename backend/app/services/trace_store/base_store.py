from abc import ABC, abstractmethod
from app.models.trace import TraceExecution


class TraceStore(ABC):
    @abstractmethod
    def save_execution(self, execution: TraceExecution) -> None: ...

    @abstractmethod
    def get_execution(self, execution_id: str) -> TraceExecution | None: ...

    @abstractmethod
    def delete_execution(self, execution_id: str) -> bool: ...
