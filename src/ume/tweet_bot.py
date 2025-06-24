from __future__ import annotations

import os
import logging
import httpx

logger = logging.getLogger(__name__)

DEFAULT_TWEET_URL = "https://api.twitter.com/2/tweets"


class TweetBot:
    """Simple interface for sending tweets."""

    def __init__(self, api_url: str | None = None, bearer_token: str | None = None) -> None:
        self.api_url = api_url or os.getenv("TWITTER_API_URL", DEFAULT_TWEET_URL)
        self.bearer_token = bearer_token or os.getenv("TWITTER_BEARER_TOKEN")

    def send_tweet(self, text: str) -> bool:
        if not self.bearer_token:
            raise ValueError("Missing Twitter bearer token")
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        try:
            response = httpx.post(
                self.api_url,
                json={"text": text},
                headers=headers,
                timeout=5,
            )
            response.raise_for_status()
            return response.status_code == 201
        except Exception:  # pragma: no cover - network errors are logged
            logger.exception("Failed to send tweet")
            return False
