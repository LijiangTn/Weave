"""
FastAPICache 工具
"""
from typing import Optional
from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
from utils.log_util import logger


async def init_cache(app: FastAPI) -> None:
    """
    复用项目中已初始化的 Redis 连接（app.state.redis）
    不会重新创建 Redis 连接，而是使用 lifespan 中已创建的连接

    :param app: FastAPI 应用实例
    """
    try:
        # 从 app.state 获取已初始化的 Redis 客户端
        redis_client: Optional[aioredis.Redis] = getattr(app.state, "redis", None)

        if redis_client is None:
            logger.error("Redis 客户端未初始化，请确保在 init_cache 之前调用了 init_redis")
            raise RuntimeError("Redis 客户端未初始化")

        # 使用已有的 Redis 客户端初始化 FastAPICache
        FastAPICache.init(
            RedisBackend(redis_client),
            prefix="cache",  # 缓存键前缀
        )

        logger.info("Cache 初始化成功，使用已有的 Redis 连接")

    except Exception as e:
        logger.error(f"初始化 FastAPI Cache 失败: {e}")
        raise


def get_cache_key_builder():
    """
    自定义缓存键生成器

    默认的键格式：cache:{prefix}:{function_name}:{args}:{kwargs}
    可以根据需要自定义键的生成规则

    返回一个函数，该函数接收 (func, namespace, request, response, args, kwargs) 参数
    """
    def custom_key_builder(
        func,
        namespace: str = "",
        request = None,
        response = None,
        *args,
        **kwargs,
    ):
        """
        自定义缓存键生成逻辑

        可以根据请求参数、用户信息等生成不同的缓存键
        """
        from fastapi_cache import FastAPICache

        # 获取请求路径和查询参数
        prefix = FastAPICache.get_prefix()
        cache_key = f"{prefix}:{namespace}:{func.__module__}:{func.__name__}"

        # 添加查询参数到缓存键
        if request:
            query_params = str(sorted(request.query_params.items()))
            cache_key = f"{cache_key}:{query_params}"

        return cache_key

    return custom_key_builder