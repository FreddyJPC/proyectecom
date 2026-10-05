from ._base import NotificationChannel, NotificationMessage


class NotificationService:
    def __init__(self, channel: NotificationChannel):
        self._channel = channel

    def send(self, message: NotificationMessage) -> bool:
        return self._channel.send(message)
