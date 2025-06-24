import json
import httpx
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location(
    "ume.tweet_bot", Path(__file__).resolve().parents[1] / "src" / "ume" / "tweet_bot.py"
)
tweet_bot = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(tweet_bot)
TweetBot = tweet_bot.TweetBot
DEFAULT_TWEET_URL = tweet_bot.DEFAULT_TWEET_URL

respx = pytest.importorskip("respx")


def test_send_tweet_success() -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(DEFAULT_TWEET_URL).mock(return_value=httpx.Response(201))
        bot = TweetBot(bearer_token="token")
        assert bot.send_tweet("hello") is True
        assert route.called
        req = route.calls.last.request
        assert req.headers.get("Authorization") == "Bearer token"
        assert json.loads(req.content.decode()) == {"text": "hello"}


def test_send_tweet_failure() -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.post(DEFAULT_TWEET_URL).mock(return_value=httpx.Response(400))
        bot = TweetBot(bearer_token="token")
        assert bot.send_tweet("oops") is False


def test_send_tweet_missing_token() -> None:
    bot = TweetBot(bearer_token=None)
    with pytest.raises(ValueError):
        bot.send_tweet("hi")
