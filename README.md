# Weave

<div align="center">
  <img src="logo.png" alt="Weave Logo" width="160" />
</div>

<div align="center">
  <strong>把微信「文件传输助手」变成可编程的本地同步服务</strong>
</div>

<div align="center">
  为 <a href="https://github.com/LijiangTn/obsidian-wechat-inbox">obsidian-wechat-inbox</a>
  等本地收件箱提供 Bot API、文件落盘、消息持久化能力。
</p>

<div align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="Python 3.9+" /></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.124-009688.svg" alt="FastAPI 0.124" /></a>
  <a href="https://www.sqlalchemy.org"><img src="https://img.shields.io/badge/SQLAlchemy-2.0-red.svg" alt="SQLAlchemy 2.0" /></a>
  <br />
  <a href="https://github.com/CJackHwang/wx-filehelper-api"><img src="https://img.shields.io/badge/based%20on-wx--filehelper--api-lightgrey.svg" alt="based on wx-filehelper-api" /></a>
  <a href="https://github.com/LijiangTn/obsidian-wechat-inbox"><img src="https://img.shields.io/badge/paired%20with-obsidian--wechat--inbox-07C160.svg" alt="paired with obsidian-wechat-inbox" /></a>
</div>

---

## 这是什么

**Weave** 是一个跑在你本机上的 FastAPI 后端，把微信「文件传输助手」暴露成：

- 一个 [Telegram Bot API](https://core.telegram.org/bots/api) 兼容的 HTTP 服务
  （`/bot/sendMessage`、`/bot/sendDocument`、`/bot/getUpdates` 等）
- 一个可被本地 Obsidian 插件
  [`obsidian-wechat-inbox`](https://github.com/LijiangTn/obsidian-wechat-inbox)
  轮询的消息源
- 一个会把你发送 / 收到的文本、图片、文件落盘到本地存储与 SQLite /
  MySQL / PostgreSQL 的同步服务

整个服务**默认监听 `127.0.0.1:8081`**，不连云、不上传 Vault 内容、不依赖任何远程代码。

---

## 与 `obsidian-wechat-inbox` 搭配使用

Weave 本身不是一个完整的收件箱。
它负责登录微信、收发消息、保存文件；要把这些消息沉淀到 Obsidian 知识库，
请同时安装官方收件箱插件：

> **[LijiangTn/obsidian-wechat-inbox](https://github.com/LijiangTn/obsidian-wechat-inbox)**
> *(Weave 的默认搭档 —— 扫码登录、按天归档、Obsidian 侧栏视图、消息索引)*

`obsidian-wechat-inbox` 默认连接 `http://127.0.0.1:8081`，与 Weave 的默认端口一致。
启动 Weave 后，在 Obsidian 设置中确认地址，即可：

- 用 Weave 提供的二维码扫码登录微信
- 自动把微信「文件传输助手」收到的内容写入 Vault
- 按 `YYYY-MM-DD.md` 归档
- 在 Obsidian 侧栏查看最近消息、状态、错误

我们建议**只通过 `obsidian-wechat-inbox` 消费 Weave 提供的消息流**，
以保证消息存档、状态机、错误恢复的语义一致。

---

## 基于 `wx-filehelper-api` 二次开发

Weave 的**对外接口协议、消息存储语义与
[`CJackHwang/wx-filehelper-api`](https://github.com/CJackHwang/wx-filehelper-api)
保持一致**，并在此之上做了系统性升级。

| 升级项 | 说明 |
| ------ | ---- |
| **异步分层架构** | Controller → Service → DAO → Entity，使用 SQLAlchemy 2.0 异步 ORM |
| **多数据库支持** | `DB_TYPE` 切换 SQLite / MySQL / PostgreSQL，迁移和连接池全部异步 |
| **完整的接口契约** | `rootController` / `botController` / `filesController` / `frameworkController` / `wechatController` / `webuiController` 与 wx-filehelper-api 一一对应 |
| **稳定的消息归一化** | `UnifiedMessage` 8 种类型（text / image / file / audio / video / link / system / unknown），worker 协议与公共契约分层 |
| **可观测性** | `/trace/recent`、`/framework/state`、`/health`、`/stability` 端点；微信 HTTP 请求体可落盘用于排查 |
| **可扩展 Connector** | 抽象 `BaseConnector`，可挂多个即时通信协议 |

特别感谢 [@CJackHwang](https://github.com/CJackHwang) 提供的 `wx-filehelper-api`
协议与 WebUI 设计 —— Weave 的接口命名、返回结构、数据库字段语义都从该项目继承而来。

---

## 特性

- **Telegram Bot API 兼容** — `getMe` / `getUpdates` / `sendMessage` / `sendDocument` /
  `sendPhoto` / `copyMessage` / `setWebhook` / `getFile` ...
- **完整的微信协议实现** — `webwxinit` / `webwxsync` / `webwxsendmsg` /
  `webwxuploadmedia` / `synccheck` 长轮询
- **本地优先** — 消息、文件、会话状态全在本地；重启不丢消息
- **自动文件下载** — 收到的图片 / 文件自动落盘到 `STORAGE_DIR`，按日期分目录
- **会话持久化** — 扫码登录后保存 `skey` / `sid` / `uin` / `pass_ticket`，重启免重新登录
- **心跳 + 自适应重连** — 微信断线后指数退避重连
- **可观测 HTTP trace** — 把请求体 / 响应体的预览落盘到 `trace_logs/`，便于排障
- **WebUI** — `/webui` 路径下可视化扫码 / 查看状态
- **Cron 定时任务** — `/framework/tasks` 可注册定时命令
- **可热重载的插件** — `/plugins/reload`

---

## 快速开始

### 1. 安装

要求 **Python 3.9+**。

```bash
git clone https://github.com/yourname/weave.git
cd weave
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 配置

默认的 `.env.dev` 已经是可直接启动的 SQLite + 微信启用配置，关键项：

```bash
APP_PORT=8081                # 与 obsidian-wechat-inbox 默认连接地址一致
DB_TYPE=sqlite               # 也可切到 mysql / postgresql
SQLITE_PATH=weave.db
STORAGE_DIR=storage
WECHAT_ENABLED=true
WECHAT_AUTO_CONNECT=false    # 首次必须手动扫码
WECHAT_TRACE_ENABLED=true    # 排障时建议开
```

> ⚠️ `WECHAT_TRACE_ENABLED=true` 会把微信请求体写到 `trace_logs/`，
> 内含 `skey` / `pass_ticket` 等敏感信息。开启后请勿把 `trace_logs/`
> 提交到 Git。

### 3. 启动

```bash
python main.py
```

启动后：

| 入口 | 地址 |
| ---- | ---- |
| 接口文档 | <http://127.0.0.1:8081/api/docs> |
| 登录二维码（WebUI） | <http://127.0.0.1:8081/webui> |
| 健康检查 | <http://127.0.0.1:8081/health> |
| 微信登录状态 | <http://127.0.0.1:8081/login/status> |

### 4. 扫码

浏览器打开 `/webui`，用手机微信扫码并在手机上点击「登录」。

### 5. 接入 Obsidian

按 [`obsidian-wechat-inbox` 安装指南](https://github.com/LijiangTn/obsidian-wechat-inbox#installation)
安装插件，**保持连接地址为 `http://127.0.0.1:8081`**，即可在 Obsidian 中看到同步进来的消息。

---

## 接口速览

Weave 的对外接口与 `wx-filehelper-api` 完全对齐。
下面只列出高频端点；完整定义见 `http://127.0.0.1:8081/api/docs`。

### 根接口（旧协议）

| Method | Path | 说明 |
| ------ | ---- | ---- |
| `GET`  | `/qr` | 获取登录二维码 PNG |
| `GET`  | `/login/status` | 登录状态 |
| `GET`  | `/messages` | 历史消息（已持久化） |
| `POST` | `/save_session` | 保存当前会话 |
| `POST` | `/send` | 发送文本 |
| `POST` | `/upload` | 上传文件 |

### Telegram Bot API 兼容

| Method | Path |
| ------ | ---- |
| `GET`  | `/bot/getMe` / `/bot/getUpdates` / `/bot/getFile` / `/bot/getChat` |
| `POST` | `/bot/sendMessage` / `/bot/sendDocument` / `/bot/sendDocument/upload` |
| `POST` | `/bot/sendPhoto` / `/bot/sendPhoto/upload` / `/bot/copyMessage` |
| `POST` | `/bot/setWebhook` / `/bot/deleteWebhook` / `GET /bot/getWebhookInfo` |

### 文件与存储

| Method | Path | 说明 |
| ------ | ---- | ---- |
| `GET`    | `/downloads` | 下载目录文件列表 |
| `GET`    | `/files/metadata` | 数据库中的文件元信息 |
| `DELETE` | `/files/{msg_id}` | 删除某个文件 |
| `POST`   | `/files/cleanup` | 清理过期文件 |
| `GET`    | `/store/stats` | 消息存储统计 |
| `GET`    | `/store/messages` | 查询历史消息 |

### 框架、Trace 与 WebUI

| Method | Path | 说明 |
| ------ | ---- | ---- |
| `GET`  | `/framework/state` | 框架运行状态 |
| `POST` | `/framework/chat_mode` | 开关聊天模式 |
| `POST` | `/framework/execute` | 执行命令 |
| `GET` / `POST` / `DELETE` | `/framework/tasks[/{id}]` | 定时任务 |
| `GET`  | `/plugins` / `POST /plugins/reload` | 插件列表与热重载 |
| `GET`  | `/health` / `/stability` | 健康检查 |
| `GET`  | `/trace/status` / `/trace/recent` / `POST /trace/clear` | 微信 HTTP trace |
| `GET`  | `/wechat/session/save` | 主动保存微信会话 |
| `GET`  | `/webui` / `/webui/qr` / `/webui/status` | WebUI |

---

## 项目结构

```
weave/
├── main.py                       # FastAPI 入口 + lifespan
├── config/                       # 配置加载（.env.{dev,prod}） + 数据库引擎 + ORM 基类
├── connectors/wechat/            # 微信协议：protocol / normalizer / session / sync_worker
├── module_api/v1/
│   ├── controller/               # APIRouter：root / bot / files / framework / wechat / webui
│   ├── service/                  # 业务编排
│   ├── dao/                      # SQLAlchemy 异步查询
│   ├── entity/{do,vo}/           # ORM 模型 / Pydantic 请求与响应
│   └── filter/                   # fastapi_filter 过滤器
├── workers/                      # 后台任务（文件下载等）
├── tasks/                        # 定时任务
├── middlewares/                  # CORS / GZip / 请求耗时
├── exceptions/                   # 统一异常类 + 全局处理器
├── utils/                        # response_util / cache_util / redis_client / log_util ...
├── tests/                        # pytest
├── storage/                      # 落盘文件（已 gitignore）
├── trace_logs/                   # 微信 HTTP trace（已 gitignore）
├── .env.dev / .env.prod
├── requirements.txt
└── main.py
```

---

## 关键环境变量

完整列表见 [.env.dev](.env.dev) 与 [config/env.py](config/env.py)。

| 变量 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `APP_PORT` | `8081` | 监听端口 |
| `DB_TYPE` | `sqlite` | `sqlite` / `mysql` / `postgresql` |
| `SQLITE_PATH` | `weave.db` | SQLite 数据库路径 |
| `STORAGE_DIR` | `storage` | 落盘目录 |
| `WECHAT_ENABLED` | `true` | 启用微信连接器 |
| `WECHAT_AUTO_CONNECT` | `false` | 启动时自动扫码（首次必须手动） |
| `WECHAT_ENTRY_HOST` | `szfilehelper.weixin.qq.com` | 微信入口主机 |
| `WECHAT_POLL_INTERVAL` | `1.0` | 同步轮询基准间隔（秒） |
| `WECHAT_HEARTBEAT_INTERVAL` | `30` | 心跳间隔（秒） |
| `WECHAT_AUTO_DOWNLOAD` | `true` | 自动下载收到的图片 / 文件 |
| `WECHAT_TRACE_ENABLED` | `false` | 是否记录微信 HTTP 请求体 |

### 数据库

默认 SQLite，零配置即可启动。

```bash
# 切到 MySQL
DB_TYPE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USERNAME=root
DB_PASSWORD=...
DB_DATABASE=weave
```

> ⚠️ 启动期 `DatabaseMigration` 自动迁移工具**仅适配 MySQL**；
> 切换到 PostgreSQL 后需要手动迁移。

---

## 排障速查

| 现象 | 可能原因 | 处理 |
| ---- | -------- | ---- |
| 启动后 `/login/status` 一直 `waiting_qr` | 还没扫码 | 打开 `/webui` 扫码 |
| 微信收到的是 `\u725b\u903c` 之类转义串 | 不会发生 —— Weave 已修过 `httpx ensure_ascii=True` 坑 | 仍出现请开 `WECHAT_TRACE_ENABLED=true` 抓 `webwxsendmsg` 请求体 |
| Obsidian 插件报"无法连接" | 端口 / 防火墙 | 确认 Weave 在 8081 运行：`curl http://127.0.0.1:8081/health` |
| 长时间运行后掉线 | 微信侧 `synccheck` 失败 | 已实现指数退避重连；查看 `/framework/state` |
| 重启后要求重新扫码 | 会话文件没保存 | 调用 `/wechat/session/save` 或开启 `WECHAT_AUTO_CONNECT` |

---

## 安全与隐私

Weave 默认**本地运行**：

- ✅ 消息、文件、会话、Trace 全在本地（`weave.db` / `storage/` / `trace_logs/`）
- ✅ 不向任何第三方发送你的微信内容或 Vault 内容
- ✅ 不执行任何远程代码
- ⚠️ **不要**把 `STORAGE_DIR` 直接同步到云盘之前先排查敏感内容
- ⚠️ `WECHAT_TRACE_ENABLED=true` 会把微信请求体写到 `trace_logs/`，
  内含 `skey` / `pass_ticket` —— 开启后请勿把 `trace_logs/` 提交到 Git

---

## 开发

```bash
# 运行测试
pytest -q

# 单文件
pytest tests/test_wechat_protocol.py -q

# 语法检查所有 Python 文件
python -m py_compile $(git ls-files '*.py')
```

开发期建议开：

```bash
WECHAT_TRACE_ENABLED=true
DB_ECHO=true
```

---

## 与 `wx-filehelper-api` 的差异

| 维度 | wx-filehelper-api | Weave |
| ---- | ----------------- | ----- |
| 架构 | 脚本式（`main.py` + plugins 文件夹） | FastAPI 分层（Controller / Service / DAO） |
| 协议实现 | `direct_bot.py` | `connectors/wechat/protocol.py` |
| 持久化 | `SQLite + dataclass` | `SQLAlchemy 2.0 async ORM` |
| 数据库 | SQLite only | SQLite / MySQL / PostgreSQL |
| 插件 | 文件夹扫描 | 模块化（`/plugins/reload`） |
| HTTP trace | 文件日志 | `/trace/recent` + 落盘 |
| 文件下载 | 同步 | 异步 worker |
| 兼容客户端 | 旧 wx-filehelper-api 客户端 | 同时兼容 `obsidian-wechat-inbox` |

**对外接口协议（URL、参数、返回 JSON 字段名）保持一致**，
旧的 SDK 与脚本可直接对接 Weave，无需修改。

---

## 致谢

- [`CJackHwang/wx-filehelper-api`](https://github.com/CJackHwang/wx-filehelper-api) —
  Weave 的接口协议、WebUI、消息存储语义全部继承自该项目。
  特别感谢 [@CJackHwang](https://github.com/CJackHwang) 的开源贡献。
- [`LijiangTn/obsidian-wechat-inbox`](https://github.com/LijiangTn/obsidian-wechat-inbox) —
  Weave 默认搭配的 Obsidian 收件箱插件。
- [Telegram Bot API](https://core.telegram.org/bots/api) — Weave 兼容的接口规范。
- [FastAPI](https://fastapi.tiangolo.com) / [SQLAlchemy](https://www.sqlalchemy.org) /
  [Pydantic](https://docs.pydantic.dev) / [httpx](https://www.python-httpx.org) — 底层依赖。

---

## License

本项目基于 [MIT License](LICENSE) 发布。
