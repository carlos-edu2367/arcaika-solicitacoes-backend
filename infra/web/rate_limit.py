from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from redis.exceptions import NoScriptError


class ResilientRateLimiter(RateLimiter):
    """Reload the limiter script if Redis evicts its script cache."""

    async def _check(self, key):
        try:
            return await super()._check(key)
        except NoScriptError:
            redis = FastAPILimiter.redis
            FastAPILimiter.lua_sha = await redis.script_load(FastAPILimiter.lua_script)
            return await super()._check(key)
