from config.database import async_engine, AsyncSessionLocal, Base
from utils.log_util import logger
# 导入所有模型，确保它们被注册到 Base.metadata
import config.models  # noqa: F401

async def get_db():
    """
    每一个请求处理完毕后会关闭当前连接，不同的请求使用不同的连接

    :return:
    """
    async with AsyncSessionLocal() as current_db:
        yield current_db

async def init_create_table():
    """
    应用启动时初始化数据库连接

    :return:
    """
    # 在应用启动时初始化数据库连接
    logger.info('初始化数据库连接...')
    # 使用异步上下文管理器创建数据库连接，并创建所有定义的表
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 完成表的创建后，记录成功信息
    logger.info('数据库连接成功')

