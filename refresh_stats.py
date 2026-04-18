import asyncio
from services.db_service import DBService
from database.connection import init_db_pool

async def test():
    await init_db_pool()
    await DBService.refresh_all_reputation()

asyncio.run(test())