import logging
from typing import Any, Dict, List, Optional

from notifier import PushbulletNotifier

logger = logging.getLogger("bms.notify")

RECIPIENTS_KEY = "pushbullet_recipients"


class PushbulletSender:
    """Sends a push to every configured Pushbullet recipient.

    Recipients are Pushbullet access tokens added from the UI, one per person
    who wants alerts. No environment variable is required. ``PUSHBULLET_TOKEN``
    is still honoured as an extra recipient for headless setups.
    """

    def __init__(self, db, env_token: str = ""):
        self.db = db
        self.env_token = (env_token or "").strip()

    def recipients(self) -> List[Dict[str, Any]]:
        stored = self.db.get_json_setting(RECIPIENTS_KEY, []) or []
        recipients: List[Dict[str, Any]] = []
        seen = set()
        for item in stored:
            token = (item.get("token") or "").strip()
            if not token or token in seen:
                continue
            seen.add(token)
            recipients.append(
                {
                    "id": item.get("id") or token[-6:],
                    "label": (item.get("label") or "").strip(),
                    "token": token,
                    "device": (item.get("device") or "").strip(),
                    "source": "database",
                }
            )
        if self.env_token and self.env_token not in seen:
            recipients.append(
                {
                    "id": "env",
                    "label": "Environment token",
                    "token": self.env_token,
                    "device": "",
                    "source": "env",
                }
            )
        return recipients

    def is_configured(self) -> bool:
        return bool(self.recipients())

    def send(
        self, title: str, message: str, recipient_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Push to the given recipients, or to everyone when ``None``."""
        available = self.recipients()
        if recipient_ids is None:
            if not available:
                raise RuntimeError("No Pushbullet recipient configured — add one in Settings")
            targets = available
        else:
            wanted = list(dict.fromkeys(recipient_ids))
            by_id = {item["id"]: item for item in available}
            targets = [by_id[rid] for rid in wanted if rid in by_id]

            if not targets:
                if not wanted:
                    raise RuntimeError(
                        "This watch has no Pushbullet recipient — pick one in the watch settings"
                    )
                raise RuntimeError(
                    "The recipients for this watch no longer exist — update the watch"
                )

        results: List[Dict[str, Any]] = []
        for recipient in targets:
            name = recipient["label"] or ("••••" + recipient["token"][-4:])
            try:
                PushbulletNotifier(recipient["token"], recipient["device"] or None).send(
                    title, message
                )
                results.append({"id": recipient["id"], "label": name, "ok": True})
            except Exception as exc:
                logger.warning("push to %s failed: %s", name, exc)
                results.append(
                    {"id": recipient["id"], "label": name, "ok": False, "error": str(exc)}
                )

        sent = sum(1 for item in results if item["ok"])
        if sent == 0:
            detail = "; ".join(f"{item['label']}: {item['error']}" for item in results)
            raise RuntimeError(f"Pushbullet delivery failed for every recipient ({detail})")
        return {"sent": sent, "total": len(results), "results": results}
