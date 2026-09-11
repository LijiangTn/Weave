"""
微信 session 内存对象 + DB 持久化

session 内容：
- entry_host / login_host / file_host（解析后的主机）
- device_id / uuid / uuid_ts
- skey / sid / uin / pass_ticket / user_name
- synckey dict
- cookies（httpx cookie jar 序列化）
"""

from dataclasses import dataclass, field
from typing import Any

from connectors.wechat.sync_state import SyncStateRepo

################################# 内存 session 数据类 #################################
@dataclass
class WeChatSession:
    entry_host: str = ''
    login_host: str = ''
    file_host: str = ''
    device_id: str = ''
    uuid: str = ''
    uuid_ts: float = 0.0
    skey: str = ''
    sid: str = ''
    uin: str = ''
    pass_ticket: str = ''
    user_name: str = ''
    synckey: dict[str, Any] = field(default_factory=lambda: {'Count': 0, 'List': []})
    cookies: list[dict[str, Any]] = field(default_factory=list)

    def has_auth(self) -> bool:
        return bool(self.skey and self.sid and self.uin and self.pass_ticket)

    def to_dict(self) -> dict[str, Any]:
        return {
            'entry_host': self.entry_host,
            'login_host': self.login_host,
            'file_host': self.file_host,
            'device_id': self.device_id,
            'uuid': self.uuid,
            'uuid_ts': self.uuid_ts,
            'skey': self.skey,
            'sid': self.sid,
            'uin': self.uin,
            'pass_ticket': self.pass_ticket,
            'user_name': self.user_name,
            'synckey': self.synckey,
            'cookies': self.cookies,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'WeChatSession':
        return cls(
            entry_host=data.get('entry_host', ''),
            login_host=data.get('login_host', ''),
            file_host=data.get('file_host', ''),
            device_id=data.get('device_id', ''),
            uuid=data.get('uuid', ''),
            uuid_ts=float(data.get('uuid_ts') or 0.0),
            skey=data.get('skey', ''),
            sid=data.get('sid', ''),
            uin=str(data.get('uin', '') or ''),
            pass_ticket=data.get('pass_ticket', ''),
            user_name=data.get('user_name', ''),
            synckey=data.get('synckey') or {'Count': 0, 'List': []},
            cookies=data.get('cookies') or [],
        )

################################# session 持久化仓库 #################################
class WeChatSessionStore:
    """session 持久化（写入 sync_state 表，key='session'）"""

    KEY = 'session'

    def __init__(self, repo: SyncStateRepo) -> None:
        self.repo = repo

    async def load(self) -> WeChatSession | None:
        data = await self.repo.get_json(self.KEY)
        if data is None:
            return None
        return WeChatSession.from_dict(data)

    async def save(self, session: WeChatSession) -> None:
        await self.repo.set_json(self.KEY, session.to_dict())

    async def clear(self) -> None:
        await self.repo.delete(self.KEY)