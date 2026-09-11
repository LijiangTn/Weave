"""
连接器访问服务
"""

from fastapi import HTTPException

from utils.connector_registry import connector_registry
from utils.connector_runtime import BaseConnector


def get_wechat_connector() -> BaseConnector:
    connector = connector_registry.get('wechat')
    if connector is None:
        raise HTTPException(status_code=503, detail='wechat connector not initialized')
    return connector
