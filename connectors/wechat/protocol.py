"""
微信文件传输助手协议实现
"""

import hashlib
import json
import os
import random
import re
import time
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import httpx

from config.env import WechatConfig
from connectors.wechat.session import WeChatSession
from utils.log_util import logger

################################# host 解析表与工具函数 #################################
# ponytail: 一个 host 常量决定三个 host, 抽到 _resolve_hosts 即可, 不要为多 host 搞配置
HOST_TABLE: dict[str, tuple[str, str]] = {
    'cmfilehelper.weixin.qq.com': ('login.wx8.qq.com', 'file.wx8.qq.com'),
    'szfilehelper.weixin.qq.com': ('login.wx2.qq.com', 'file.wx2.qq.com'),
}

def resolve_hosts(entry_host: str) -> tuple[str, str]:
    if entry_host in HOST_TABLE:
        return HOST_TABLE[entry_host]
    return 'login.wx.qq.com', 'file.wx.qq.com'


_SANITIZE_PATTERNS = [
    re.compile(r'(pass_ticket\s*[=:]\s*)([^&\s"\',;]+)', re.IGNORECASE),
    re.compile(r'(webwx_data_ticket\s*[=:]\s*)([^&\s"\',;]+)', re.IGNORECASE),
    re.compile(r'(skey\s*[=:]\s*)([^&\s"\',;]+)', re.IGNORECASE),
    re.compile(r'(sid\s*[=:]\s*)([^&\s"\',;]+)', re.IGNORECASE),
    re.compile(r'(wxsid\s*[=:]\s*)([^&\s"\',;]+)', re.IGNORECASE),
    re.compile(r'(deviceid\s*[=:]\s*)([^&\s"\',;]+)', re.IGNORECASE),
    re.compile(r'(uin\s*[=:]\s*)([^&\s"\',;]+)', re.IGNORECASE),
    re.compile(r'(aeskey\s*[=:]\s*)([^&\s"\',;]+)', re.IGNORECASE),
    re.compile(r'(signature\s*[=:]\s*)([^&\s"\',;]+)', re.IGNORECASE),
]

_SANITIZE_JSON_PATTERNS = [
    re.compile(r'("pass_ticket"\s*:\s*")[^"]*(")', re.IGNORECASE),
    re.compile(r'("webwx_data_ticket"\s*:\s*")[^"]*(")', re.IGNORECASE),
    re.compile(r'("Skey"\s*:\s*")[^"]*(")', re.IGNORECASE),
    re.compile(r'("Sid"\s*:\s*")[^"]*(")', re.IGNORECASE),
    re.compile(r'("DeviceID"\s*:\s*")[^"]*(")', re.IGNORECASE),
    re.compile(r'("Signature"\s*:\s*")[^"]*(")', re.IGNORECASE),
    re.compile(r'("AESKey"\s*:\s*")[^"]*(")', re.IGNORECASE),
]

def regex_group(text: str, pattern: str, flags: int = 0) -> str:
    match = re.search(pattern, text, flags)
    return match.group(1) if match else ''

def extract_xml_tag(xml_text: str, tag: str) -> str:
    return regex_group(xml_text, rf'<{tag}>(.*?)</{tag}>', flags=re.S)

def gen_device_id() -> str:
    return ''.join(str(random.randint(0, 9)) for _ in range(15))

def format_synccheck_key(synckey: dict[str, Any]) -> str:
    pairs = [
        f"{item.get('Key')}_{item.get('Val')}"
        for item in (synckey or {}).get('List') or []
        if 'Key' in item and 'Val' in item
    ]
    return '|'.join(pairs)

################################# 微信 HTTP 协议封装 #################################
class WeChatProtocol:
    """
    微信协议封装：负责 HTTP 请求与会话字段填充。
    不做后台调度、不做 session 持久化，由 connector / sync_worker 调用。
    """

    def __init__(
        self,
        *,
        entry_host: str,
        mmweb_appid: str,
        to_user_name: str,
        lang: str = 'zh_CN',
    ) -> None:
        self.entry_host = entry_host
        self.login_host, self.file_host = resolve_hosts(entry_host)
        self.mmweb_appid = mmweb_appid
        self.to_user_name = to_user_name
        self.lang = lang
        self.client: httpx.AsyncClient | None = None
        self.session = WeChatSession(entry_host=entry_host)
        self.trace_enabled = WechatConfig.wechat_trace_enabled
        self.trace_redact = WechatConfig.wechat_trace_redact
        self.trace_max_body = WechatConfig.wechat_trace_max_body
        self.trace_dir = Path(WechatConfig.wechat_trace_dir)
        self.trace_log_file = self.trace_dir / 'wechat_http_trace.jsonl'
        self.trace_lock = None
        self.trace_seq = 0
        self._trace_buffer: deque[str] = deque(maxlen=100)
        self._trace_flush_interval = 2.0
        self._trace_flush_task: Any = None

    def bind_session(self, session: WeChatSession) -> None:
        """connector 在加载历史 session 时调用，重新解析 hosts"""
        self.session = session
        if session.entry_host:
            self.entry_host = session.entry_host
        self.login_host, self.file_host = resolve_hosts(self.entry_host)

    ################################# HTTP 客户端生命周期 #################################
    async def open(self) -> None:
        if self.client is not None:
            return
        timeout = httpx.Timeout(connect=10.0, read=40.0, write=40.0, pool=10.0)
        if self.trace_enabled:
            self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            event_hooks={
                'request': [self._trace_on_request],
                'response': [self._trace_on_response],
            },
        )
        if self.trace_lock is None:
            import asyncio

            self.trace_lock = asyncio.Lock()
        if self.trace_enabled and self._trace_flush_task is None:
            import asyncio

            self._trace_flush_task = asyncio.create_task(self._trace_flush_loop())

    async def close(self) -> None:
        if self._trace_flush_task is not None:
            self._trace_flush_task.cancel()
            try:
                await self._trace_flush_task
            except Exception:
                pass
            self._trace_flush_task = None
        await self._flush_trace_buffer()
        if self.client is None:
            return
        await self.client.aclose()
        self.client = None

    ################################# Cookie 序列化 #################################
    def capture_cookies(self) -> list[dict[str, Any]]:
        if self.client is None:
            return []
        cookies: list[dict[str, Any]] = []
        for cookie in self.client.cookies.jar:
            cookies.append(
                {
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                    'expires': cookie.expires,
                }
            )
        return cookies

    def restore_cookies(self, cookies: list[dict[str, Any]]) -> None:
        if self.client is None:
            return
        for item in cookies:
            try:
                self.client.cookies.set(
                    item.get('name', ''),
                    item.get('value', ''),
                    domain=item.get('domain'),
                    path=item.get('path', '/'),
                )
            except Exception:
                continue

    ################################# 登录流程 #################################
    async def get_login_qr(self) -> bytes:
        """返回 PNG 二维码字节流；已登录则返回空"""
        if self.client is None:
            await self.open()
        assert self.client is not None

        if self.session.has_auth() and self.session.uuid:
            return b''

        # uuid 缺失或超过 240s 重新申请
        if not self.session.uuid or (time.time() - self.session.uuid_ts > 240):
            await self._jslogin_get_uuid()

        resp = await self.client.get(f'https://login.weixin.qq.com/qrcode/{self.session.uuid}')
        resp.raise_for_status()
        return resp.content

    async def poll_login(self) -> int:
        """
        轮询一次登录状态。
        返回 code：200 已授权 / 201 已扫码等待确认 / 408 等待扫码 / 0 失败 / 其他异常
        """
        if self.client is None:
            await self.open()
        assert self.client is not None
        if not self.session.uuid:
            return 0

        now = int(time.time() * 1000)
        r_value = ~int(time.time())
        url = (
            f'https://{self.login_host}/cgi-bin/mmwebwx-bin/login'
            f'?loginicon=true&uuid={quote(self.session.uuid, safe="")}&tip=1'
            f'&r={r_value}&_={now}&appid={self.mmweb_appid}'
        )
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            body = resp.text
        except Exception as exc:
            logger.warning(f'[wechat] poll_login network error: {exc}')
            return 0

        code_str = regex_group(body, r'window\.code\s*=\s*(\d+)')
        code = int(code_str) if code_str else 0

        if code == 200:
            redirect_uri = regex_group(body, r'window\.redirect_uri\s*=\s*"([^"]+)"')
            if redirect_uri:
                await self._complete_login(redirect_uri)
        elif code in {400, 500, 0}:
            self.session.uuid = ''
        return code

    async def _jslogin_get_uuid(self) -> None:
        assert self.client is not None
        redirect_uri = quote(
            f'https://{self.entry_host}/cgi-bin/mmwebwx-bin/webwxnewloginpage', safe=''
        )
        now = int(time.time() * 1000)
        url = (
            f'https://{self.login_host}/jslogin?appid={self.mmweb_appid}'
            f'&redirect_uri={redirect_uri}&fun=new&lang={self.lang}&_={now}'
        )
        resp = await self.client.get(url)
        resp.raise_for_status()
        uuid = regex_group(resp.text, r'window\.QRLogin\.uuid\s*=\s*"([^"]+)"')
        if not uuid:
            raise RuntimeError(f'jslogin response missing uuid: {resp.text[:200]}')
        self.session.uuid = uuid
        self.session.uuid_ts = time.time()

    async def _complete_login(self, redirect_uri: str) -> None:
        assert self.client is not None
        parsed = urlparse(redirect_uri)
        query = parse_qs(parsed.query)
        domain = parsed.netloc or self.entry_host

        self.entry_host = domain
        self.login_host, self.file_host = resolve_hosts(domain)
        self.session.entry_host = domain

        url = f'https://{domain}/cgi-bin/mmwebwx-bin/webwxnewloginpage'
        params = {
            'fun': 'new',
            'version': 'v2',
            'ticket': (query.get('ticket') or [''])[0],
            'uuid': (query.get('uuid') or [self.session.uuid])[0],
            'lang': (query.get('lang') or [self.lang])[0],
            'scan': (query.get('scan') or [''])[0],
        }
        resp = await self.client.get(url, params=params, headers={'mmweb_appid': self.mmweb_appid})
        resp.raise_for_status()

        xml = resp.text
        self.session.skey = extract_xml_tag(xml, 'skey')
        self.session.sid = extract_xml_tag(xml, 'wxsid')
        self.session.uin = extract_xml_tag(xml, 'wxuin')
        self.session.pass_ticket = extract_xml_tag(xml, 'pass_ticket')

        if not self.session.has_auth():
            raise RuntimeError('webwxnewloginpage missing auth fields')

        ok = await self._webwxinit()
        if not ok:
            raise RuntimeError('webwxinit failed')

    async def _webwxinit(self) -> bool:
        assert self.client is not None
        url = f'https://{self.entry_host}/cgi-bin/mmwebwx-bin/webwxinit'
        params = {
            'r': ~int(time.time() * 1000),
            'lang': self.lang,
            'pass_ticket': self.session.pass_ticket,
        }
        payload = {'BaseRequest': self._base_request()}
        try:
            resp = await self.client.post(
                url,
                params=params,
                json=payload,
                headers={'mmweb_appid': self.mmweb_appid},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning(f'[wechat] webwxinit error: {exc}')
            return False

        if (data.get('BaseResponse') or {}).get('Ret') != 0:
            return False

        user = data.get('User') or {}
        if user.get('UserName'):
            self.session.user_name = user['UserName']
        if user.get('Uin') is not None:
            self.session.uin = str(user['Uin'])

        sync = data.get('SyncKey') or {'Count': 0, 'List': []}
        self.session.synckey = sync
        return True

    ################################# 消息同步轮询 #################################
    async def synccheck(self) -> str:
        """
        返回 'hasMsg' / 'wait' / 'loginout' / 'resync'
        """
        if self.client is None or not self.session.has_auth():
            return 'loginout'

        synckey = format_synccheck_key(self.session.synckey)
        url = f'https://{self.entry_host}/cgi-bin/mmwebwx-bin/synccheck'
        params = {
            'r': int(time.time() * 1000),
            'skey': self.session.skey,
            'sid': self.session.sid,
            'uin': self.session.uin,
            'deviceid': self.session.device_id,
            'synckey': synckey,
            'mmweb_appid': self.mmweb_appid,
        }
        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            body = resp.text
        except Exception as exc:
            logger.warning(f'[wechat] synccheck error: {exc}')
            return 'resync'

        retcode = regex_group(body, r'retcode\s*:\s*"?(\d+)"?')
        selector = regex_group(body, r'selector\s*:\s*"?(\d+)"?')
        if retcode != '0':
            return 'loginout'
        if selector and selector != '0':
            return 'hasMsg'
        return 'wait'

    async def webwxsync(self) -> dict[str, Any]:
        """
        拉取增量消息并更新 synckey。
        返回原始响应 dict；调用方按需解析 AddMsgList。
        """
        if self.client is None or not self.session.has_auth():
            return {'AddMsgList': [], 'BaseResponse': {'Ret': -1}}

        url = f'https://{self.entry_host}/cgi-bin/mmwebwx-bin/webwxsync'
        params = {
            'sid': self.session.sid,
            'skey': self.session.skey,
            'pass_ticket': self.session.pass_ticket,
        }
        payload = {
            'BaseRequest': self._base_request(),
            'SyncKey': self.session.synckey,
            'rr': ~int(time.time() * 1000),
        }
        try:
            resp = await self.client.post(
                url,
                params=params,
                json=payload,
                headers={'mmweb_appid': self.mmweb_appid},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning(f'[wechat] webwxsync error: {exc}')
            return {'AddMsgList': [], 'BaseResponse': {'Ret': -1}}

        if (data.get('BaseResponse') or {}).get('Ret') != 0:
            return data
        if data.get('SyncKey'):
            self.session.synckey = data['SyncKey']
        return data

    def _base_request(self) -> dict[str, Any]:
        uin = self.session.uin
        try:
            uin_int: Any = int(uin)
        except (TypeError, ValueError):
            uin_int = uin
        return {
            'Uin': uin_int,
            'Sid': self.session.sid,
            'Skey': self.session.skey,
            'DeviceID': self.session.device_id,
        }

    def get_cookie(self, name: str) -> str:
        if self.client is None:
            return ''
        for cookie in self.client.cookies.jar:
            if cookie.name == name:
                return cookie.value
        return ''

    ################################# 发送消息与文件 #################################
    async def send_text(self, message: str) -> bool:
        if self.client is None or not self.session.has_auth() or not message:
            return False
        url = (
            f'/cgi-bin/mmwebwx-bin/webwxsendmsg'
            f'?lang={self.lang}&pass_ticket={quote(self.session.pass_ticket, safe="")}'
        )
        payload = {'Type': 1, 'Content': message}
        data = await self._post_message(url, payload)
        return data is not None

    async def send_file(self, file_path: str) -> bool:
        if self.client is None or not self.session.has_auth():
            return False
        path = Path(file_path)
        if not path.exists():
            return False
        file_size = path.stat().st_size
        if file_size > 25 * 1024 * 1024:
            logger.warning('[wechat] direct protocol only supports files up to 25MB')
            return False
        mime_type = (
            'image/jpeg'
            if path.suffix.lower() in {'.jpg', '.jpeg'}
            else (
                'image/png'
                if path.suffix.lower() == '.png'
                else 'application/octet-stream'
            )
        )
        import mimetypes

        guessed, _ = mimetypes.guess_type(path.name)
        mime_type = guessed or mime_type
        media_type = 'pic' if mime_type.startswith('image/') else 'doc'
        media_id = await self._webwxuploadmedia(
            path=path,
            mime_type=mime_type,
            media_type=media_type,
            file_md5=self._md5_file(path),
            client_media_id=self._gen_msg_id(),
        )
        if not media_id:
            return False
        if media_type == 'pic':
            url = (
                f'/cgi-bin/mmwebwx-bin/webwxsendmsgimg'
                f'?fun=async&f=json&pass_ticket={quote(self.session.pass_ticket, safe="")}'
            )
            payload = {'MediaId': media_id, 'Type': 3, 'Content': ''}
        else:
            url = (
                f'/cgi-bin/mmwebwx-bin/webwxsendappmsg'
                f'?fun=async&f=json&lang={self.lang}&pass_ticket={quote(self.session.pass_ticket, safe="")}'
            )
            payload = {
                'Type': 6,
                'Content': self._build_appmsg_xml(path.name, file_size, media_id),
            }
        data = await self._post_message(url, payload)
        return data is not None

    async def download_image(self, raw: dict[str, Any]) -> bytes | None:
        """下载图片（MsgType=3）"""
        if self.client is None or not self.session.has_auth():
            return None
        url = (
            f'https://{self.entry_host}/cgi-bin/mmwebwx-bin/webwxgetmsgimg'
            f'?MsgID={raw.get("MsgId")}&skey={quote(self.session.skey, safe="")}&type=slave'
            f'&mmweb_appid={self.mmweb_appid}'
        )
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            return resp.content
        except Exception as exc:
            logger.warning(f'[wechat] download_image failed: {exc}')
            return None

    async def download_file(self, raw: dict[str, Any]) -> bytes | None:
        """下载文件（MsgType=49, AppMsgType=6）"""
        if self.client is None or not self.session.has_auth():
            return None
        webwx_data_ticket = self.get_cookie('webwx_data_ticket')
        sender = raw.get('FromUserName', '')
        media_id = raw.get('MediaId', '')
        encry_filename = raw.get('EncryFileName', '')
        url = (
            f'https://{self.file_host}/cgi-bin/mmwebwx-bin/webwxgetmedia'
            f'?sender={quote(str(sender), safe="")}'
            f'&mediaid={quote(str(media_id), safe="")}'
            f'&encryfilename={quote(str(encry_filename), safe="")}'
            f'&fromuser={quote(str(self.session.uin), safe="")}'
            f'&pass_ticket={quote(self.session.pass_ticket, safe="")}'
            f'&webwx_data_ticket={quote(webwx_data_ticket, safe="")}'
            f'&sid={quote(self.session.sid, safe="")}'
            f'&mmweb_appid={self.mmweb_appid}'
        )
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            return resp.content
        except Exception as exc:
            logger.warning(f'[wechat] download_file failed: {exc}')
            return None

    ################################# Trace 状态与记录 #################################
    def get_trace_status(self) -> dict[str, Any]:
        size = self.trace_log_file.stat().st_size if self.trace_log_file.exists() else 0
        return {
            'enabled': self.trace_enabled,
            'redact': self.trace_redact,
            'max_body': self.trace_max_body,
            'file': str(self.trace_log_file),
            'exists': self.trace_log_file.exists(),
            'size_bytes': size,
        }

    async def read_recent_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.trace_enabled or not self.trace_log_file.exists():
            return []
        rows: deque[str] = deque(maxlen=max(1, min(limit, 1000)))
        with self.trace_log_file.open('r', encoding='utf-8') as file_obj:
            for line in file_obj:
                line = line.strip()
                if line:
                    rows.append(line)
        records: list[dict[str, Any]] = []
        for line in rows:
            try:
                records.append(json.loads(line))
            except Exception:
                records.append({'raw': line})
        return records

    async def clear_traces(self) -> bool:
        if self.trace_log_file.exists():
            self.trace_log_file.unlink()
        return True

    ################################# 内部 POST 与上传实现 #################################
    async def _post_message(self, url: str, msg_fields: dict[str, Any]) -> dict[str, Any] | None:
        assert self.client is not None
        msg_id = self._gen_msg_id()
        payload = {
            'BaseRequest': self._base_request(),
            'Msg': {
                'ClientMsgId': msg_id,
                'LocalID': msg_id,
                'FromUserName': self.session.user_name,
                'ToUserName': self.to_user_name,
                **msg_fields,
            },
            'Scene': 0,
        }
        full_url = f'https://{self.entry_host}{url}'
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        try:
            resp = await self.client.post(
                full_url,
                content=body,
                headers={
                    'mmweb_appid': self.mmweb_appid,
                    'Content-Type': 'application/json; charset=utf-8',
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning(f'[wechat] post_message failed: {exc}')
            return None
        if (data.get('BaseResponse') or {}).get('Ret') != 0:
            return None
        return data

    async def _webwxuploadmedia(
        self,
        *,
        path: Path,
        mime_type: str,
        media_type: str,
        file_md5: str,
        client_media_id: str,
    ) -> str:
        assert self.client is not None
        file_size = path.stat().st_size
        webwx_data_ticket = self.get_cookie('webwx_data_ticket')
        upload_req = {
            'UploadType': 2,
            'BaseRequest': self._base_request(),
            'ClientMediaId': client_media_id,
            'TotalLen': file_size,
            'StartPos': 0,
            'DataLen': file_size,
            'MediaType': 4,
            'FromUserName': self.session.user_name,
            'ToUserName': self.to_user_name,
            'FileMd5': file_md5,
        }
        data = {
            'name': path.name,
            'type': mime_type,
            'lastModifiedDate': 'Thu Jan 01 1970 08:00:00 GMT+0800',
            'size': str(file_size),
            'mediatype': media_type,
            'uploadmediarequest': json.dumps(upload_req, ensure_ascii=False),
            'webwx_data_ticket': webwx_data_ticket,
            'pass_ticket': self.session.pass_ticket,
        }
        upload_url = (
            f'https://{self.file_host}/cgi-bin/mmwebwx-bin/webwxuploadmedia'
            f'?f=json&random={self._random_string(4)}'
        )
        with path.open('rb') as file_obj:
            files = {'filename': (path.name, file_obj, mime_type)}
            try:
                resp = await self.client.post(
                    upload_url,
                    data=data,
                    files=files,
                    headers={'mmweb_appid': self.mmweb_appid},
                )
                resp.raise_for_status()
                result = resp.json()
            except Exception as exc:
                logger.warning(f'[wechat] webwxuploadmedia failed: {exc}')
                return ''
        if (result.get('BaseResponse') or {}).get('Ret') != 0:
            logger.warning(f'[wechat] webwxuploadmedia ret != 0: {result}')
            return ''
        return str(result.get('MediaId', ''))

    ################################# Trace Hook 与落盘 #################################
    async def _trace_on_request(self, request: httpx.Request) -> None:
        request.extensions['trace_start'] = time.perf_counter()
        self.trace_seq += 1
        trace_id = f'{int(time.time() * 1000)}-{self.trace_seq}'
        request.extensions['trace_id'] = trace_id
        if not self.trace_enabled:
            return
        content_type = request.headers.get('content-type', '')
        if 'multipart/form-data' in content_type:
            body_preview = '<<multipart omitted>>'
        else:
            body_preview = self._request_body_preview(request, content_type)
        await self._append_trace(
            {
                'event': 'request',
                'id': trace_id,
                'ts': int(time.time() * 1000),
                'method': request.method,
                'url': self._sanitize_text(str(request.url)),
                'headers': self._sanitize_headers(dict(request.headers.items())),
                'body_preview': body_preview,
            }
        )

    async def _trace_on_response(self, response: httpx.Response) -> None:
        request = response.request
        trace_id = request.extensions.get('trace_id', '')
        started = request.extensions.get('trace_start')
        duration_ms = int((time.perf_counter() - started) * 1000) if isinstance(started, float) else None
        if not self.trace_enabled:
            return
        content_type = response.headers.get('content-type', '')
        if self._is_textual_content_type(content_type):
            try:
                raw = await response.aread()
                body_preview = self._bytes_preview(raw, content_type)
            except Exception as exc:
                body_preview = f'<<read error: {exc}>>'
        else:
            body_preview = f'<<binary {content_type or "unknown"} omitted>>'
        await self._append_trace(
            {
                'event': 'response',
                'id': trace_id,
                'ts': int(time.time() * 1000),
                'method': request.method,
                'url': self._sanitize_text(str(request.url)),
                'status_code': response.status_code,
                'duration_ms': duration_ms,
                'headers': self._sanitize_headers(dict(response.headers.items())),
                'body_preview': body_preview,
            }
        )

    async def _append_trace(self, row: dict[str, Any]) -> None:
        if not self.trace_enabled:
            return
        self._trace_buffer.append(json.dumps(row, ensure_ascii=False))

    async def _trace_flush_loop(self) -> None:
        import asyncio

        while True:
            try:
                await asyncio.sleep(self._trace_flush_interval)
                await self._flush_trace_buffer()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f'[wechat] trace flush error: {exc}')

    async def _flush_trace_buffer(self) -> None:
        if not self._trace_buffer:
            return
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        lines_to_write: list[str] = []
        if self.trace_lock is None:
            import asyncio

            self.trace_lock = asyncio.Lock()
        async with self.trace_lock:
            while self._trace_buffer:
                try:
                    lines_to_write.append(self._trace_buffer.popleft())
                except IndexError:
                    break
        if lines_to_write:
            self.trace_log_file.parent.mkdir(parents=True, exist_ok=True)
            with self.trace_log_file.open('a', encoding='utf-8') as file_obj:
                file_obj.write('\n'.join(lines_to_write) + '\n')

    def _request_body_preview(self, request: httpx.Request, content_type: str) -> str:
        try:
            payload = request.content
            if isinstance(payload, str):
                text = payload
            elif isinstance(payload, (bytes, bytearray)):
                text = self._bytes_preview(bytes(payload), content_type)
            else:
                text = '<<stream omitted>>'
        except Exception:
            return '<<stream omitted>>'
        return self._sanitize_text(text)

    def _bytes_preview(self, payload: bytes, content_type: str) -> str:
        if not payload:
            return ''
        clipped = payload[: self.trace_max_body]
        suffix = f' ...<truncated {len(payload) - len(clipped)} bytes>' if len(payload) > len(clipped) else ''
        try:
            text = clipped.decode('utf-8')
        except UnicodeDecodeError:
            text = clipped.decode('latin1', errors='replace')
        if not self._is_textual_content_type(content_type):
            return f'<<non-text {content_type or "unknown"} {len(payload)} bytes>>'
        return self._sanitize_text(text + suffix)

    def _is_textual_content_type(self, content_type: str) -> bool:
        value = (content_type or '').lower()
        return any(word in value for word in ['json', 'text', 'xml', 'javascript', 'html', 'x-www-form-urlencoded'])

    def _sanitize_headers(self, headers: dict[str, Any]) -> dict[str, Any]:
        redacted: dict[str, Any] = {}
        for key, value in headers.items():
            if key.lower() in {'cookie', 'set-cookie', 'authorization'}:
                redacted[key] = '***'
            else:
                redacted[key] = self._sanitize_text(str(value))
        return redacted

    def _sanitize_text(self, text: str) -> str:
        if not self.trace_redact:
            return text or ''
        sanitized = str(text or '')
        for pattern in _SANITIZE_PATTERNS:
            sanitized = pattern.sub(r'\1***', sanitized)
        for pattern in _SANITIZE_JSON_PATTERNS:
            sanitized = pattern.sub(r'\1***\2', sanitized)
        return sanitized

    ################################# 工具方法 #################################
    def _build_appmsg_xml(self, file_name: str, file_size: int, media_id: str) -> str:
        ext = Path(file_name).suffix.replace('.', '') or 'bin'
        return (
            "<appmsg appid='wxeb7ec651dd0aefa9' sdkver=''><title>"
            f"{file_name}</title><des></des><action></action><type>6</type>"
            "<content></content><url></url><lowurl></lowurl><appattach>"
            f"<totallen>{file_size}</totallen><attachid>{media_id}</attachid>"
            f"<fileext>{ext}</fileext></appattach><extinfo></extinfo></appmsg>"
        )

    def _gen_msg_id(self) -> str:
        return str(int(time.time() * 1000)) + str(random.randint(100, 999))

    def _md5_file(self, path: Path) -> str:
        digest = hashlib.md5()
        with path.open('rb') as file_obj:
            for chunk in iter(lambda: file_obj.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    def _random_string(self, n: int) -> str:
        alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789'
        return ''.join(random.choice(alphabet) for _ in range(n))
