from os import remove, system
from os.path import exists, expanduser
from threading import Thread
from time import sleep, time

CONFIG_PATH = expanduser("~") + "/.ntfy.yml"


class NtfyClient:
    """Knows how to talk to the external ``ntfy`` CLI (single responsibility)."""

    def send(self, title: str, message: str) -> None:
        system('ntfy -t "{0}" send "{1}"'.format(title, message))

    def write_pushbullet_config(self, token: str, device: str) -> None:
        with open(CONFIG_PATH, "w+") as ntfy_file:
            ntfy_file.write('backends: ["pushbullet"]\n')
            ntfy_file.write('pushbullet: {"access_token": "' + token + '"')
            if device is not None:
                ntfy_file.write(', "device_iden": "' + device + '"')
            ntfy_file.write("}")

    def remove_config(self) -> None:
        if exists(CONFIG_PATH):
            remove(CONFIG_PATH)


class NotificationThread(Thread):
    def __init__(self, ntfy_client: NtfyClient, title: str, message: str, pushbullet, interval: int):
        super().__init__()
        self.ntfy_client = ntfy_client
        self.title = title
        self.message = message
        self.pushbullet = pushbullet  # (token, [devices]) or None
        self.interval = interval

    def run(self) -> None:
        if self.pushbullet:
            token, devices = self.pushbullet
            for device in devices:
                self.ntfy_client.write_pushbullet_config(token, device)
                self.ntfy_client.send(self.title, self.message)
            self.ntfy_client.remove_config()
        while True:
            start = time()
            self.ntfy_client.send(self.title, self.message)
            stop = time()
            remaining = self.interval - (stop - start)
            remaining = int(round(remaining if remaining > 0 else 0))
            sleep(remaining)


class NotificationService:
    """Starts background notifications without blocking the caller."""

    def __init__(self, ntfy_client: NtfyClient = None, pushbullet=None, interval: int = 10):
        self.ntfy_client = ntfy_client or NtfyClient()
        self.pushbullet = pushbullet
        self.interval = interval

    def notify(self, title: str, message: str) -> None:
        thread = NotificationThread(self.ntfy_client, title, message, self.pushbullet, self.interval)
        thread.start()
