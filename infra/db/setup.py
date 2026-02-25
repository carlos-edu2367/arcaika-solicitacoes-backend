from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from infra.config import Settings

Base = declarative_base()
db = create_async_engine(Settings.DATABASE_URL)

AsyncSessionLocal = sessionmaker(
    db,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session