"""
简洁的 Redis 单例管理器
"""
from redis import asyncio as aioredis
from redis.exceptions import AuthenticationError, TimeoutError, RedisError
from config.env import RedisConfig
from utils.log_util import logger
import asyncio
import time
from typing import Optional


class RedisUtil:
    """
    简洁的 Redis 单例管理器

    - 在应用启动时创建单个连接池（默认 DB）
    - 提供 get_instance() 访问已创建的单例
    - 提供 close_redis_pool() 在 shutdown 时关闭连接
    """
    # 按 database 缓存多个 Redis 客户端（每个 DB 使用独立连接池）
    _clients: dict[int, aioredis.Redis] = {}
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

    @classmethod
    async def _create_client(cls, database: int) -> aioredis.Redis:
        """
        创建并返回指定 database 的 Redis 客户端（带重试）。
        """
        retry = 0
        start = time.time()
        while retry < cls.MAX_RETRIES:
            try:
                logger.info(f'创建 Redis 客户端 -> {RedisConfig.redis_host}:{RedisConfig.redis_port} (db={database}) 尝试 {retry+1}/{cls.MAX_RETRIES}')
                client = await aioredis.from_url(
                    f'redis://{RedisConfig.redis_host}:{RedisConfig.redis_port}',
                    username=RedisConfig.redis_username,
                    password=RedisConfig.redis_password,
                    db=database,
                    encoding='utf-8',
                    decode_responses=True,
                    socket_timeout=10,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=15,
                )
                ok = await client.ping()
                if ok:
                    logger.info(f'Redis 客户端创建成功，db={database}，耗时: {time.time() - start:.2f}s')
                    return client
                else:
                    await client.close()
                    raise ConnectionError("ping 返回 False")
            except AuthenticationError as e:
                logger.error(f'Redis 认证失败: {e}')
                raise
            except (TimeoutError, ConnectionError, RedisError) as e:
                logger.error(f'连接 Redis 失败: {e}; 重试中...')
            except Exception as e:
                logger.error(f'创建 Redis 客户端发生未知错误: {e}')

            retry += 1
            if retry >= cls.MAX_RETRIES:
                logger.error('达到最大重试次数，放弃创建 Redis 客户端')
                raise ConnectionError(f"无法连接到 Redis: {RedisConfig.redis_host}:{RedisConfig.redis_port}")
            await asyncio.sleep(cls.RETRY_DELAY)

        # 不应到达这里
        raise ConnectionError("Redis 创建逻辑异常")

    @classmethod
    async def get_client(cls, database: int = RedisConfig.redis_database) -> aioredis.Redis:
        """
        返回指定 database 的 Redis 客户端；若不存在则创建并缓存。
        """
        client = cls._clients.get(database)
        if client is not None:
            try:
                await client.ping()
                return client
            except Exception:
                # 不可用则关闭并移除缓存，稍后重建
                try:
                    await client.close()
                except Exception:
                    pass
                cls._clients.pop(database, None)

        client = await cls._create_client(database)
        cls._clients[database] = client
        return client

    @classmethod
    async def close_all(cls, app=None) -> None:
        """
        关闭所有已缓存的客户端并清理 app.state（如果传入）。
        """
        try:
            for c in list(cls._clients.values()):
                try:
                    await c.close()
                except Exception as e:
                    logger.error(f"关闭 Redis 客户端失败: {e}")
            cls._clients.clear()

            if app is not None and hasattr(app, "state") and hasattr(app.state, "redis"):
                try:
                    delattr(app.state, "redis")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f'关闭 Redis 过程中发生错误: {e}')