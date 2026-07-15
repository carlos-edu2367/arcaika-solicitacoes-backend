import pytest
from redis.exceptions import ConnectionError, NoScriptError

from fastapi_limiter import FastAPILimiter

from infra.web.rate_limit import ResilientRateLimiter


class RedisWithFlushedScript:
    def __init__(self):
        self.evalsha_calls = []
        self.script_load_calls = []

    async def evalsha(self, sha, numkeys, key, times, milliseconds):
        self.evalsha_calls.append((sha, numkeys, key, times, milliseconds))
        if len(self.evalsha_calls) == 1:
            raise NoScriptError("No matching script.")
        return 0

    async def script_load(self, script):
        self.script_load_calls.append(script)
        return "reloaded-script-sha"


class RedisWithDroppedConnection:
    def __init__(self):
        self.evalsha_calls = []

    async def evalsha(self, sha, numkeys, key, times, milliseconds):
        self.evalsha_calls.append((sha, numkeys, key, times, milliseconds))
        if len(self.evalsha_calls) == 1:
            raise ConnectionError("Connection lost.")
        return 0


@pytest.mark.asyncio
async def test_rate_limiter_reloads_redis_script_after_it_is_flushed():
    redis = RedisWithFlushedScript()
    previous_redis = FastAPILimiter.redis
    previous_sha = FastAPILimiter.lua_sha
    try:
        FastAPILimiter.redis = redis
        FastAPILimiter.lua_sha = "expired-script-sha"

        result = await ResilientRateLimiter(times=5, seconds=60)._check("login-key")

        assert result == 0
        assert redis.script_load_calls == [FastAPILimiter.lua_script]
        assert redis.evalsha_calls == [
            ("expired-script-sha", 1, "login-key", "5", "60000"),
            ("reloaded-script-sha", 1, "login-key", "5", "60000"),
        ]
    finally:
        FastAPILimiter.redis = previous_redis
        FastAPILimiter.lua_sha = previous_sha


@pytest.mark.asyncio
async def test_rate_limiter_retries_after_a_dropped_redis_connection():
    redis = RedisWithDroppedConnection()
    previous_redis = FastAPILimiter.redis
    previous_sha = FastAPILimiter.lua_sha
    try:
        FastAPILimiter.redis = redis
        FastAPILimiter.lua_sha = "current-script-sha"

        result = await ResilientRateLimiter(times=5, seconds=60)._check("login-key")

        assert result == 0
        assert redis.evalsha_calls == [
            ("current-script-sha", 1, "login-key", "5", "60000"),
            ("current-script-sha", 1, "login-key", "5", "60000"),
        ]
    finally:
        FastAPILimiter.redis = previous_redis
        FastAPILimiter.lua_sha = previous_sha
