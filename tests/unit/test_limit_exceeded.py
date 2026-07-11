"""Tests for the spend/quota limit classifier and its webhook routing.

A limit-exceeded error means the provider rejected the request because a
billing or usage limit is exhausted (OpenRouter monthly key limit, out of
credits, OpenAI insufficient_quota). These must fire the Limit Exceeded
webhook instead of Auth Failure, and must not shadow the transient-429
retry path or the Gemini daily/structural classifiers (#491).
"""

import json
import threading
from unittest.mock import patch

import httpx

from llm_client import is_limit_exceeded_error, StructuralRateLimitError


class _FakeResponse:
    def __init__(self, text=None, headers=None):
        self.text = text
        self.headers = headers or {}


class _FakeError(Exception):
    """Mimics provider error: carries .status_code, .body and/or .response."""
    def __init__(self, message="", status_code=None, body=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.response = response


OPENROUTER_KEY_LIMIT_403 = (
    "Error code: 403 - {'error': {'message': 'Key limit exceeded "
    "(monthly limit). Manage it using https://openrouter.ai/keys', "
    "'code': 403}}"
)

# Google's transient per-minute 429 message mentions both "quota" and
# "billing"; it must stay on the retry path.
GEMINI_PER_MINUTE_429 = (
    "429 RESOURCE_EXHAUSTED. You exceeded your current quota, please check "
    "your plan and billing details."
)


class TestLimitExceededClassifier:
    def test_openrouter_monthly_key_limit_403(self):
        err = _FakeError(OPENROUTER_KEY_LIMIT_403, status_code=403)
        assert is_limit_exceeded_error(err) is True

    def test_402_always_limit_exceeded(self):
        err = _FakeError("Insufficient credits", status_code=402)
        assert is_limit_exceeded_error(err) is True

    def test_openai_insufficient_quota_429(self):
        body = {"error": {"message": "You exceeded your current quota",
                          "type": "insufficient_quota",
                          "code": "insufficient_quota"}}
        err = _FakeError("Error code: 429", status_code=429, body=body)
        assert is_limit_exceeded_error(err) is True

    def test_anthropic_low_credit_400(self):
        err = _FakeError(
            "Your credit balance is too low to access the Anthropic API",
            status_code=400,
        )
        assert is_limit_exceeded_error(err) is True

    def test_invalid_key_401_not_limit(self):
        err = _FakeError("Invalid API key provided", status_code=401)
        assert is_limit_exceeded_error(err) is False

    def test_invalid_key_403_not_limit(self):
        err = _FakeError("Forbidden: key disabled", status_code=403)
        assert is_limit_exceeded_error(err) is False

    def test_generic_429_not_limit(self):
        err = _FakeError("Rate limit exceeded, retry in 20s", status_code=429)
        assert is_limit_exceeded_error(err) is False

    def test_gemini_per_minute_429_not_limit(self):
        err = _FakeError(GEMINI_PER_MINUTE_429, status_code=429)
        assert is_limit_exceeded_error(err) is False

    def test_no_status_code_not_limit(self):
        err = _FakeError("Key limit exceeded (monthly limit)")
        assert is_limit_exceeded_error(err) is False

    def test_500_not_limit(self):
        err = _FakeError("billing service unavailable", status_code=500)
        assert is_limit_exceeded_error(err) is False

    def test_response_text_fallback(self):
        text = json.dumps({"error": {"message": "Key limit exceeded (monthly limit)"}})
        err = _FakeError("Error code: 403", status_code=403,
                         response=_FakeResponse(text=text))
        assert is_limit_exceeded_error(err) is True


def _call_window(client, max_retries=5):
    from utils import llm_call
    return llm_call.call_llm_for_window(
        llm_client=client,
        model="test-model",
        system_prompt="sys",
        prompt="user",
        llm_timeout=1.0,
        max_retries=max_retries,
        max_tokens=4096,
        slug="t",
        episode_id="e",
        window_label="w",
    )


class TestRetryLoopRouting:
    """The retry loop must fire Limit Exceeded (not Auth Failure) for
    billing errors, fail fast, and leave the auth and Gemini paths alone."""

    def _run(self, error, monkeypatch, max_retries=5):
        from utils import llm_call

        calls = {"n": 0}
        fired = {"limit": 0, "auth": 0}

        class _Client:
            def messages_create(self, **kw):
                calls["n"] += 1
                raise error

        monkeypatch.setattr(llm_call.time, "sleep", lambda s: None)
        monkeypatch.setattr(llm_call.random, "uniform", lambda a, b: 0.0)
        monkeypatch.setattr(
            "webhook_service.fire_limit_exceeded_event",
            lambda *a, **kw: fired.__setitem__("limit", fired["limit"] + 1),
        )
        monkeypatch.setattr(
            "webhook_service.fire_auth_failure_event",
            lambda *a, **kw: fired.__setitem__("auth", fired["auth"] + 1),
        )
        response, last_error = _call_window(_Client(), max_retries=max_retries)
        return response, last_error, calls["n"], fired

    def test_key_limit_403_fires_limit_not_auth(self, monkeypatch):
        err = _FakeError(OPENROUTER_KEY_LIMIT_403, status_code=403)
        response, last_error, n, fired = self._run(err, monkeypatch)
        assert response is None
        assert last_error is err
        assert n == 1
        assert fired == {"limit": 1, "auth": 0}

    def test_insufficient_quota_429_fast_fails(self, monkeypatch):
        body = {"error": {"message": "You exceeded your current quota",
                          "type": "insufficient_quota",
                          "code": "insufficient_quota"}}
        err = _FakeError("Error code: 429", status_code=429, body=body)
        # Message contains "429" so _is_retryable would keep it in both the
        # main loop and the secondary retry without the fast-fail guards.
        response, last_error, n, fired = self._run(err, monkeypatch)
        assert response is None
        assert n == 1
        assert fired == {"limit": 1, "auth": 0}

    def test_invalid_key_401_still_fires_auth(self, monkeypatch):
        import openai
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        err = openai.AuthenticationError(
            "Invalid API key provided",
            response=httpx.Response(401, request=request),
            body={"error": {"message": "Invalid API key provided"}},
        )
        response, last_error, n, fired = self._run(err, monkeypatch)
        assert response is None
        assert n == 1
        assert fired == {"limit": 0, "auth": 1}

    def test_gemini_daily_quota_still_routes_structural(self, monkeypatch):
        body = {
            "error": {
                "message": "You exceeded your current quota (429 rate limit)",
                "status": "RESOURCE_EXHAUSTED",
                "details": [{
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{
                        "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                        "quotaValue": "50",
                        "quotaDimensions": {"model": "gemini-2.5-pro"},
                    }],
                }],
            }
        }
        err = _FakeError("429 rate limit", status_code=429, body=body)
        response, last_error, n, fired = self._run(err, monkeypatch)
        assert response is None
        assert isinstance(last_error, StructuralRateLimitError)
        assert n == 1
        assert fired == {"limit": 0, "auth": 0}


class TestFireLimitExceededEvent:
    def setup_method(self):
        import webhook_service
        webhook_service._last_limit_exceeded_time = 0.0

    def _fire(self, webhooks):
        import webhook_service

        dispatched = []

        def _record(wh, context):
            dispatched.append((wh, context))

        class _SyncThread:
            def __init__(self, target=None, args=(), daemon=None):
                self._target = target
                self._args = args

            def start(self):
                self._target(*self._args)

        with patch('webhook_service.load_webhooks', return_value=webhooks), \
             patch('webhook_service._prepare_and_dispatch', side_effect=_record), \
             patch.object(threading, 'Thread', _SyncThread):
            webhook_service.fire_limit_exceeded_event(
                'openrouter', 'test-model',
                'Key limit exceeded (monthly limit)', 403,
            )
        return dispatched

    def test_event_in_valid_events(self):
        from webhook_service import VALID_EVENTS, EVENT_LIMIT_EXCEEDED
        assert EVENT_LIMIT_EXCEEDED in VALID_EVENTS

    def test_dispatches_to_subscriber_with_context(self):
        webhooks = [{'enabled': True, 'events': ['Limit Exceeded'], 'url': 'http://x'}]
        dispatched = self._fire(webhooks)
        assert len(dispatched) == 1
        context = dispatched[0][1]
        assert context['event'] == 'Limit Exceeded'
        assert context['provider'] == 'openrouter'
        assert context['model'] == 'test-model'
        assert context['error_message'] == 'Key limit exceeded (monthly limit)'
        assert context['status_code'] == 403

    def test_skips_non_subscribers(self):
        webhooks = [
            {'enabled': True, 'events': ['Auth Failure'], 'url': 'http://x'},
            {'enabled': False, 'events': ['Limit Exceeded'], 'url': 'http://y'},
        ]
        assert self._fire(webhooks) == []

    def test_dedup_window_suppresses_second_fire(self):
        webhooks = [{'enabled': True, 'events': ['Limit Exceeded'], 'url': 'http://x'}]
        assert len(self._fire(webhooks)) == 1
        # Second fire inside the 5-minute window is suppressed.
        assert self._fire(webhooks) == []
