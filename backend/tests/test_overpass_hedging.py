"""
Tests for OverpassProvider._post's mirror-hedging logic in isolation (no real
network). This exists specifically because the crowd/places-nearby smoke
tests mock OverpassProvider.nearby() itself, so they never exercise the
hedging/racing code path added to fix real 504/timeout reports from
overpass-api.de. These tests use plain asyncio.run() rather than
pytest-asyncio (not a project dependency) and monkeypatch httpx.AsyncClient
with a fake that simulates configurable per-URL delay/outcome, so timing
behaviour (not just the final result) can be asserted quickly and
deterministically.
"""
import asyncio
import time

import httpx
import pytest

from app.integrations.overpass import OverpassProvider
from app.integrations.base import ProviderError


class _FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def _make_fake_client(behaviors: dict, calls: list):
    """behaviors: url -> ("ok", payload) | ("error", exc) | ("slow_ok", delay, payload)."""

    class _FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None, headers=None):
            calls.append(url)
            behavior = behaviors[url]
            kind = behavior[0]
            if kind == "ok":
                return _FakeResponse(behavior[1])
            if kind == "slow_ok":
                await asyncio.sleep(behavior[1])
                return _FakeResponse(behavior[2])
            if kind == "timeout":
                await asyncio.sleep(behavior[1])
                raise httpx.TimeoutException("simulated timeout")
            if kind == "error":
                raise httpx.HTTPStatusError("simulated 504", request=None, response=None)
            raise AssertionError(f"unhandled behavior {behavior}")

    return _FakeClient


def _provider_with_mirrors(mirrors):
    p = OverpassProvider()
    p.mirrors = mirrors
    return p


def test_healthy_primary_returns_immediately_and_never_calls_other_mirrors(monkeypatch):
    calls = []
    mirrors = ["http://primary", "http://mirror2", "http://mirror3"]
    behaviors = {
        "http://primary": ("ok", {"elements": [{"id": 1}]}),
        "http://mirror2": ("error",),
        "http://mirror3": ("error",),
    }
    monkeypatch.setattr("app.integrations.overpass.httpx.AsyncClient", _make_fake_client(behaviors, calls))
    provider = _provider_with_mirrors(mirrors)

    start = time.monotonic()
    result = asyncio.run(provider._post("QUERY", per_mirror_timeout=5.0, hedge_delay=5.0))
    elapsed = time.monotonic() - start

    assert result == {"elements": [{"id": 1}]}
    assert calls == ["http://primary"], "a healthy primary must not trigger any hedge calls to the other mirrors"
    assert elapsed < 1.0, f"a healthy primary should resolve almost instantly, took {elapsed:.2f}s"


def test_slow_primary_is_hedged_by_second_mirror_without_waiting_full_timeout(monkeypatch):
    calls = []
    mirrors = ["http://primary", "http://mirror2", "http://mirror3"]
    behaviors = {
        "http://primary": ("slow_ok", 10.0, {"elements": [{"id": "slow"}]}),  # would eventually succeed, but too slowly
        "http://mirror2": ("ok", {"elements": [{"id": "fast"}]}),
        "http://mirror3": ("error",),
    }
    monkeypatch.setattr("app.integrations.overpass.httpx.AsyncClient", _make_fake_client(behaviors, calls))
    provider = _provider_with_mirrors(mirrors)

    start = time.monotonic()
    result = asyncio.run(provider._post("QUERY", per_mirror_timeout=15.0, hedge_delay=1.5))
    elapsed = time.monotonic() - start

    assert result == {"elements": [{"id": "fast"}]}, "should return the faster hedged mirror's result, not wait for the slow primary"
    assert calls[0] == "http://primary"
    assert "http://mirror2" in calls, "second mirror should have been hedged in after hedge_delay"
    # Must return close to hedge_delay (not per_mirror_timeout=15s) -- this is the whole point of hedging.
    assert elapsed < 4.0, f"hedging should return well before the primary's own timeout, took {elapsed:.2f}s"


def test_all_mirrors_failing_raises_aggregated_provider_error(monkeypatch):
    calls = []
    mirrors = ["http://primary", "http://mirror2"]
    behaviors = {
        "http://primary": ("error",),
        "http://mirror2": ("error",),
    }
    monkeypatch.setattr("app.integrations.overpass.httpx.AsyncClient", _make_fake_client(behaviors, calls))
    provider = _provider_with_mirrors(mirrors)

    with pytest.raises(ProviderError):
        asyncio.run(provider._post("QUERY", per_mirror_timeout=2.0, hedge_delay=0.2))
    assert set(calls) == {"http://primary", "http://mirror2"}, "every mirror should genuinely have been tried before giving up"


def test_worst_case_stays_bounded_not_the_sum_of_every_mirror_timeout(monkeypatch):
    """
    Regression test for the actual bug just reported: a first version of this fix tried
    mirrors strictly one-after-another, so 3 overloaded/timing-out mirrors at ~15s each
    took up to 45s -- longer than the frontend's own request timeout, which is exactly
    what surfaced as "Request timed out" in the UI even though the fix was live. Hedging
    must keep the worst case close to hedge_delay*(mirrors-1) + per_mirror_timeout.
    """
    calls = []
    mirrors = ["http://primary", "http://mirror2", "http://mirror3"]
    per_mirror_timeout = 3.0
    hedge_delay = 1.0
    behaviors = {
        "http://primary": ("timeout", per_mirror_timeout),
        "http://mirror2": ("timeout", per_mirror_timeout),
        "http://mirror3": ("timeout", per_mirror_timeout),
    }
    monkeypatch.setattr("app.integrations.overpass.httpx.AsyncClient", _make_fake_client(behaviors, calls))
    provider = _provider_with_mirrors(mirrors)

    start = time.monotonic()
    with pytest.raises(ProviderError):
        asyncio.run(provider._post("QUERY", per_mirror_timeout=per_mirror_timeout, hedge_delay=hedge_delay))
    elapsed = time.monotonic() - start

    naive_sequential_worst_case = len(mirrors) * per_mirror_timeout  # 9.0s
    hedged_expected_worst_case = hedge_delay * (len(mirrors) - 1) + per_mirror_timeout  # 5.0s
    assert elapsed < naive_sequential_worst_case, (
        f"took {elapsed:.2f}s -- must be faster than sequential retry's {naive_sequential_worst_case:.1f}s"
    )
    assert elapsed < hedged_expected_worst_case + 1.0, f"took {elapsed:.2f}s, expected close to {hedged_expected_worst_case:.1f}s"
