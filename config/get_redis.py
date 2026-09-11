"""
Redis 连接管理
"""
from typing import Optional
from fastapi import Request

from utils.redis_client import RedisUtil
from config.env import RedisConfig
from utils.log_util import logger


async def init_redis(app: Optional[object] = None):
    """
    初始化 Redis 单例连接池并可选地将实例保存到 FastAPI 的 app.state.redis
    在应用启动时调用（lifespan/startup）。
    返回已创建的 redis 实例。
    """
    # 使用新的按 DB 客户端获取接口，返回默认配置的 DB 客户端
    redis = await RedisUtil.get_client(RedisConfig.redis_database)
    if app is not None and hasattr(app, "state"):
        try:
            app.state.redis = redis
        except Exception as e:
            logger.warning(f"设置 app.state.redis 失败: {e}")
    return redis


async def get_redis(request: Optional[Request] = None):
    """
    获取 Redis 单例实例；如果在 FastAPI 请求上下文中并且 app.state.redis 可用，则优先返回。
    可在路由中作为 Depends(get_redis) 使用。
    """
    try:
        if request is not None and hasattr(request.app, "state") and getattr(request.app.state, "redis", None) is not None:
            return request.app.state.redis
    except Exception:
        # 忽略并回退到全局单例
        pass

    return await RedisUtil.get_client()


async def close_redis(app: Optional[object] = None):
    """
    关闭 Redis 单例并清理 app.state.redis（如果提供）。
    在应用 shutdown 时调用。
    """
    await RedisUtil.close_all(app)