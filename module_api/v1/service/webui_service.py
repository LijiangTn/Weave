"""
WebUI 服务
"""

import base64
import time
from pathlib import Path
from typing import Any

from config.env import AppConfig
from module_api.v1.service.framework_service import FrameworkService
from module_api.v1.service.wechat_service import WechatService
from utils.connector_runtime import BaseConnector


class WebUIService:
    _html_path = Path(__file__).resolve().parent.parent / 'assets' / 'webui' / 'index.html'

    @classmethod
    async def get_qr_payload(cls, connector: BaseConnector) -> dict[str, Any]:
        login = await WechatService.get_login_status(connector)
        if login.get('logged_in'):
            return {
                'logged_in': True,
                'qr_base64': None,
                'message': '已登录',
            }
        try:
            png_bytes = await WechatService.get_qr(connector)
        except Exception as exc:
            return {
                'logged_in': False,
                'qr_base64': None,
                'error': str(exc),
                'message': f'获取二维码失败: {exc}',
            }
        if not png_bytes:
            return {
                'logged_in': True,
                'qr_base64': None,
                'message': '已登录',
            }
        return {
            'logged_in': False,
            'qr_base64': base64.b64encode(png_bytes).decode('ascii'),
            'uuid': login.get('uuid'),
            'uuid_age': login.get('uuid_age_seconds') or 0,
            'message': '请扫码登录',
        }

    @classmethod
    async def get_status_payload(cls, connector: BaseConnector, *, poll_login: bool = False) -> dict[str, Any]:
        if poll_login or not connector.is_logged_in:
            await WechatService.check_login_status(connector, poll=True)
        login_detail = await WechatService.get_login_status(connector)
        uptime = int(time.time() - FrameworkService._started_at)
        return {
            'app_name': AppConfig.app_name,
            'version': AppConfig.app_version,
            'uptime': uptime,
            'uptime_str': cls._format_uptime(uptime),
            'logged_in': login_detail.get('logged_in', False),
            'login_status': login_detail.get('status', 'unknown'),
            'login_code': login_detail.get('code', 0),
            'has_uuid': login_detail.get('has_uuid', False),
            'uuid_age': login_detail.get('uuid_age_seconds'),
            'chat_enabled': FrameworkService._chat_enabled,
            'tasks_count': len(FrameworkService._tasks),
            'plugins_count': FrameworkService.list_plugins()['loaded_count'],
            'entry_host': login_detail.get('entry_host', ''),
            'login_status_text': cls._get_login_status_text(login_detail),
        }

    @classmethod
    def render_page(cls) -> str:
        if not cls._html_path.exists():
            return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{AppConfig.app_name}</title>
</head>
<body>
  <h1>{AppConfig.app_name}</h1>
  <p>Version: {AppConfig.app_version}</p>
</body>
</html>"""
        html = cls._html_path.read_text(encoding='utf-8')
        html = html.replace('{{app_name}}', AppConfig.app_name)
        html = html.replace('{{version}}', AppConfig.app_version)
        return html

    @staticmethod
    def _format_uptime(seconds: int) -> str:
        if seconds < 60:
            return f'{seconds}秒'
        if seconds < 3600:
            return f'{seconds // 60}分{seconds % 60}秒'
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f'{hours}小时{minutes}分'

    @staticmethod
    def _get_login_status_text(login_detail: dict[str, Any]) -> str:
        if login_detail.get('logged_in'):
            return '已登录'
        code = login_detail.get('code', 0)
        status = login_detail.get('status', '')
        if code == 201:
            return '已扫码，请在手机上确认'
        if code == 408:
            return '等待扫码...'
        if status == 'qr_expired':
            return '二维码已过期，请刷新'
        if status == 'need_qr':
            return '请扫描二维码'
        if status == 'qr_ready':
            return '二维码已就绪'
        return '等待登录'
