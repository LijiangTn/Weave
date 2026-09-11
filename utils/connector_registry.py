"""
通用连接器注册中心
"""

from utils.connector_runtime import BaseConnector


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, BaseConnector] = {}

    def register(self, name: str, connector: BaseConnector) -> None:
        if name in self._connectors:
            raise ValueError(f'Connector {name} already registered')
        self._connectors[name] = connector

    def get(self, name: str) -> BaseConnector | None:
        return self._connectors.get(name)

    def require(self, name: str) -> BaseConnector:
        connector = self._connectors.get(name)
        if connector is None:
            raise KeyError(f'Connector {name} not registered')
        return connector

    def all(self) -> dict[str, BaseConnector]:
        return dict(self._connectors)

    def shutdown_all(self) -> None:
        for name, connector in self._connectors.items():
            if connector.state.value not in {'stopped', 'disconnected'}:
                from utils.log_util import logger

                logger.warning(
                    f'Connector {name} still in state {connector.state.value} at shutdown'
                )


connector_registry = ConnectorRegistry()
