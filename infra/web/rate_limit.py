from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from redis.exceptions import ConnectionError as RedisConnectionError, NoScriptError


class ResilientRateLimiter(RateLimiter):
    """Recover from Redis script eviction and one dropped connection."""

    async def _check(self, key):
        try:
            return await super()._check(key)
        except NoScriptError:
            redis = FastAPILimiter.redis
            FastAPILimiter.lua_sha = await redis.script_load(FastAPILimiter.lua_script)
            return await super()._check(key)
        except RedisConnectionError:
            return await super()._check(key)
