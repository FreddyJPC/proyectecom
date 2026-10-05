from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class NotificationMessage:
    to: str
    template_name: str = ""
    components: list = field(default_factory=list)
    language_code: str = "es_EC"


class NotificationChannel(ABC):
    @abstractmethod
    def send(self, message: NotificationMessage) -> bool: ...
