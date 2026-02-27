from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter
from infra.config import Settings
from infra.db.setup import Base, db
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):

    redis_client = redis.from_url(
        Settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )

    await FastAPILimiter.init(redis_client)
    app.state.redis = redis_client


    async with db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.engine = db

    yield

    await redis_client.close()
    await db.dispose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)
from infra.web.routes.solicitacoes import router as solicitacao_router
from infra.web.routes.user import router as user_router
from infra.web.routes.local_user import router as local_user_router

app.include_router(user_router)
app.include_router(solicitacao_router)
app.include_router(local_user_router)