from typing import Optional

from notifier import PushbulletNotifier


class PushbulletSender:
    """Resolves the Pushbullet credentials at send time.

    The token can come from the environment (``PUSHBULLET_TOKEN``) or the
    settings table, so it never has to be baked into the image or sent to the
    browser.
    """

    def __init__(self, db, env_token: str = ""):
        self.db = db
        self.env_token = env_token

    def token(self) -> Optional[str]:
        return self.env_token or self.db.get_setting("pushbullet_token")

    def device(self) -> Optional[str]:
        return self.db.get_setting("pushbullet_device")

    def is_configured(self) -> bool:
        return bool(self.token())

    def send(self, title: str, message: str) -> None:
        token = self.token()
        if not token:
            raise RuntimeError(
                "Pushbullet token is not configured; set PUSHBULLET_TOKEN or add it in Settings"
            )
        PushbulletNotifier(token, self.device()).send(title, message)
