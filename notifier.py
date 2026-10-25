from abc import ABC, abstractmethod
from threading import Thread
from time import sleep, time
from typing import Optional

import requests


class Notifier(ABC):
    """Abstraction over notification channels (dependency inversion)."""

    @abstractmethod
    def send(self, title: str, message: str) -> None:
        ...


class DesktopNotifier(Notifier):
    """Native macOS desktop notification via ``osascript`` (no third-party CLI)."""

    def send(self, title: str, message: str) -> None:
        import subprocess

        script = 'display notification "{}" with title "{}"'.format(
            _escape_applescript(message), _escape_applescript(title)
        )
        subprocess.run(["osascript", "-e", script], check=False)


class PushbulletNotifier(Notifier):
    """Sends a note through the Pushbullet REST API (no third-party CLI)."""

    PUSHES_URL = "https://api.pushbullet.com/v2/pushes"

    def __init__(self, token: str, device_iden: Optional[str] = None, session=None):
        self.token = token
        self.device_iden = device_iden
        self.session = session or requests.Session()

    def send(self, title: str, message: str) -> None:
        headers = {"Access-Token": self.token, "Content-Type": "application/json"}
        payload = {"type": "note", "title": title, "body": message}
        if self.device_iden:
            payload["device_iden"] = self.device_iden
        response = self.session.post(self.PUSHES_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()


def _escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


class NotificationThread(Thread):
    def __init__(self, desktop_notifier, pushbullet_notifiers, title, message, interval):
        super().__init__()
        self.desktop_notifier = desktop_notifier
        self.pushbullet_notifiers = pushbullet_notifiers
        self.title = title
        self.message = message
        self.interval = interval

    def run(self) -> None:
        for notifier in self.pushbullet_notifiers:
            notifier.send(self.title, self.message)
        while True:
            start = time()
            self.desktop_notifier.send(self.title, self.message)
            stop = time()
            remaining = self.interval - (stop - start)
            remaining = int(round(remaining if remaining > 0 else 0))
            sleep(remaining)


class NotificationService:
    """Starts background notifications without blocking the caller."""

    def __init__(self, desktop_notifier=None, pushbullet_notifiers=None, interval: int = 10):
        self.desktop_notifier = desktop_notifier or DesktopNotifier()
        self.pushbullet_notifiers = pushbullet_notifiers or []
        self.interval = interval

    def notify(self, title: str, message: str) -> None:
        thread = NotificationThread(
            self.desktop_notifier, self.pushbullet_notifiers, title, message, self.interval
        )
        thread.start()
