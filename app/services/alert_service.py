import os

import requests


class AlertService:
    def __init__(self) -> None:
        self.webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
        self.enabled = os.getenv("ALERT_ON_FAILURE", "false").strip().lower() == "true"

    def send_failure_alert(self, message: str, details: dict) -> bool:
        if not self.enabled or not self.webhook_url:
            return False

        payload = {
            "text": message,
            "details": details,
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=12)
            response.raise_for_status()
            return True
        except Exception:
            return False
