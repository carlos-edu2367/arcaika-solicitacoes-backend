from sqlalchemy import text
from infra.db.setup import db  # seu async engine

async def add_column():
    async with db.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE anexos_solicitacao
            ADD COLUMN classe VARCHAR NOT NULL DEFAULT 'cliente';
        """))

import asyncio

asyncio.run(add_column())