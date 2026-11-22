"""Mattermost incoming webhooks. URLs come from MATTERMOST_WEBHOOK_<NAME>."""
import os
import time

import httpx


class WebhookNotConfigured(RuntimeError):
    pass


def webhook_url(name: str) -> str:
    var = f"MATTERMOST_WEBHOOK_{name.upper()}"
    url = os.environ.get(var, "").strip()
    if not url:
        raise WebhookNotConfigured(f"{var} is not set")
    return url


def post(name: str, texts: list[str], transport: httpx.BaseTransport | None = None) -> None:
    url = webhook_url(name)
    with httpx.Client(timeout=30, transport=transport) as client:
        for i, text in enumerate(texts):
            if i:
                time.sleep(1)  # keep multi-part posts in order
            client.post(url, json={"text": text}).raise_for_status()
