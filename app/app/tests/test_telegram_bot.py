import importlib
from unittest.mock import MagicMock

import pytest


def test_redis_token_storage(monkeypatch):
    # Create a fake redis client with hset/hgetall/delete
    store = {}

    class FakeRedis:
        def hset(self, key, mapping=None, **kwargs):
            # support both mapping= and kwargs
            if mapping:
                store[key] = mapping.copy()
            elif kwargs:
                store.setdefault(key, {}).update(kwargs)

        def hgetall(self, key):
            return store.get(key, {}).copy()

        def delete(self, key):
            store.pop(key, None)

    tb = importlib.import_module('app.telegram_bot')
    monkeypatch.setattr(tb, 'redis_client', FakeRedis())

    # Ensure empty
    a, r = tb._get_tokens(42)
    assert a is None and r is None

    tb._store_tokens(42, 'access-token', 'refresh-token')
    a, r = tb._get_tokens(42)
    assert a == 'access-token'
    assert r == 'refresh-token'

    tb._pop_tokens(42)
    a, r = tb._get_tokens(42)
    assert a is None and r is None


def test_redis_store_partial(monkeypatch):
    store = {}

    class FakeRedis:
        def hset(self, key, mapping=None, **kwargs):
            if mapping:
                store[key] = mapping.copy()
            elif kwargs:
                store.setdefault(key, {}).update(kwargs)

        def hgetall(self, key):
            return store.get(key, {}).copy()

        def delete(self, key):
            store.pop(key, None)

    tb = importlib.import_module('app.telegram_bot')
    monkeypatch.setattr(tb, 'redis_client', FakeRedis())

    tb._store_tokens(99, 'only-access', None)
    a, r = tb._get_tokens(99)
    assert a == 'only-access'
    assert r is None
