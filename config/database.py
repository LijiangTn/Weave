import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from urllib.parse import quote_plus
from config.env import DataBaseConfig


def _build_database_url() -> str:
    db_type = (DataBaseConfig.db_type or '').lower()
    if db_type == 'sqlite':
        path = os.getenv('SQLITE_PATH', 'weave.db')
        return f'sqlite+aiosqlite:///{path}'
    if db_type == 'postgresql':
        return (
            f'postgresql+asyncpg://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
            f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
        )
    # 默认 mysql
    return (
        f'mysql+asyncmy://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
        f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
    )


ASYNC_SQLALCHEMY_DATABASE_URL = _build_database_url()

# SQLite 不需要连接池参数
_is_sqlite = (DataBaseConfig.db_type or '').lower() == 'sqlite'

# 创建异步引擎
async_engine = create_async_engine(
    ASYNC_SQLALCHEMY_DATABASE_URL,
    echo=DataBaseConfig.db_echo,
    **(
        {}
        if _is_sqlite
        else {
            'max_overflow': DataBaseConfig.db_max_overflow,
            'pool_size': DataBaseConfig.db_pool_size,
            'pool_recycle': DataBaseConfig.db_pool_recycle,
            'pool_timeout': DataBaseConfig.db_pool_timeout,
        }
    ),
)
# 创建异步会话工厂
# ponytail: expire_on_commit=False 避免 commit 后访问字段触发 lazy load,
# 后台 worker 没有请求上下文无法走 greenlet
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    expire_on_commit=False,
)

# 声明基类，用于定义ORM模型
class Base(AsyncAttrs, DeclarativeBase):
    pass
