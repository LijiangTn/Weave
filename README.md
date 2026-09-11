<div align="center">
  <img src="./logo.png" alt="Weave Logo" width="240" />
</div>

<div align="center">
  <h1>Weave</h1>
</div>

<div align="center">
  <strong>把微信「文件传输助手」变成本地优先的可编程同步入口。</strong>
</div>

<br />

<div align="center">
  Weave 主要解决的是：如何把微信「文件传输助手」里的临时消息，
  稳定变成可保存、可归档、可继续加工的本地输入流。
</div>

<br />

<div align="center">
  目前它已经解决了扫码登录、消息同步、文本发送、图片与文件接收落盘、
  本地消息持久化，以及与 <a href="https://github.com/LijiangTn/obsidian-wechat-inbox">obsidian-wechat-inbox</a> 的配套接入问题。
</div>

<br />

<div align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="Python 3.9+" /></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.124-009688.svg" alt="FastAPI 0.124" /></a>
  <a href="https://www.sqlalchemy.org"><img src="https://img.shields.io/badge/SQLAlchemy-2.0-red.svg" alt="SQLAlchemy 2.0" /></a>
  <a href="https://github.com/LijiangTn/obsidian-wechat-inbox"><img src="https://img.shields.io/badge/Obsidian-Plugin-7C3AED.svg" alt="Obsidian Plugin" /></a>
  <a href="https://github.com/CJackHwang/wx-filehelper-api"><img src="https://img.shields.io/badge/Based%20on-wx--filehelper--api-lightgrey.svg" alt="Based on wx-filehelper-api" /></a>
  <img src="https://img.shields.io/badge/Local--first-Privacy%20friendly-22C55E.svg" alt="Local-first Privacy friendly" />
</div>

---

## 项目定位

Weave 主要做三件事：

1. 接管微信「文件传输助手」的登录、轮询、发送和附件上传。
2. 把消息、文件、同步状态持久化到本地数据库和存储目录。
3. 为上层客户端提供统一接口，尤其是与 `obsidian-wechat-inbox` 的配合使用。

它不是一个独立的知识管理产品，更适合作为本地消息接入层和协议适配层。

## 推荐搭配

Weave 推荐与 [LijiangTn/obsidian-wechat-inbox](https://github.com/LijiangTn/obsidian-wechat-inbox) 一起使用。

典型链路是：

`微信文件传输助手 -> Weave -> obsidian-wechat-inbox -> Obsidian Vault`

其中：

- Weave 负责扫码登录、同步消息、发送文本、上传文件、保存会话。
- `obsidian-wechat-inbox` 负责把消息写入 Obsidian、本地归档、侧栏展示和知识库工作流整合。

如果你的目标是把微信消息稳定沉淀到 Obsidian，本项目应视为后端服务，`obsidian-wechat-inbox` 才是默认配套客户端。

## 致谢与来源

本项目在 [CJackHwang/wx-filehelper-api](https://github.com/CJackHwang/wx-filehelper-api) 的基础上进行了工程化重构和扩展。

感谢原项目提供的接口协议设计、WebUI 交互思路以及整体能力基础。Weave 在保留原有对外协议语义的前提下，改为 FastAPI 分层架构实现，并补充了异步 ORM、可观测性和更清晰的模块边界。

## 主要特性

- 对外接口协议尽量与 `wx-filehelper-api` 保持一致
- 基于 FastAPI + SQLAlchemy 2.0 async ORM 的分层实现
- 支持 SQLite / MySQL / PostgreSQL
- 支持 Telegram Bot API 风格接口
- 支持微信二维码登录、会话持久化、自动重连
- 支持文本、图片、文件等消息的统一落盘
- 提供 WebUI、Trace、任务调度、运行状态查看等能力
- 默认本地运行，不依赖云端服务

## 架构说明

项目内部遵循分层结构：

- `controller`：HTTP 接口层
- `service`：业务编排层
- `dao`：数据访问层
- `entity/do`：ORM 实体
- `entity/vo`：请求与响应模型
- `connectors/wechat`：微信协议实现与消息归一化

核心入口在 `main.py`，应用启动后会：

1. 初始化数据库表结构
2. 初始化微信连接器
3. 建立消息处理管道
4. 注册根接口、Bot API、文件接口、框架接口和 WebUI

## 快速开始

### 1. 安装

要求 Python 3.9 及以上。

```bash
git clone https://github.com/LijiangTn/Weave.git
cd weave
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
```

macOS / Linux：

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

### 2. 配置

项目默认通过 `.env.dev` 加载开发环境配置。常用项如下：

```bash
APP_NAME=Weave
APP_PORT=8081

DB_TYPE=sqlite
SQLITE_PATH=weave.db

STORAGE_DIR=storage

WECHAT_ENABLED=true
WECHAT_AUTO_CONNECT=false
WECHAT_ENTRY_HOST=szfilehelper.weixin.qq.com
WECHAT_TRACE_ENABLED=false
```

说明：

- 本地直接体验时，推荐先用 SQLite。
- 首次启动建议 `WECHAT_AUTO_CONNECT=false`，先手动扫码完成会话建立。
- 排障时可临时开启 `WECHAT_TRACE_ENABLED=true`。

### 3. 启动

```bash
python main.py
```

按当前项目入口，默认启动地址为：

- `http://127.0.0.1:8081`

常用页面：

- 接口文档：`http://127.0.0.1:8081/api/docs`
- WebUI：`http://127.0.0.1:8081/webui`
- 登录状态：`http://127.0.0.1:8081/login/status`
- 健康检查：`http://127.0.0.1:8081/health`

## 与 Obsidian 配合使用

安装并配置 [obsidian-wechat-inbox](https://github.com/LijiangTn/obsidian-wechat-inbox) 后，将后端地址指向：

```text
http://127.0.0.1:8081
```

完成后，你可以通过以下流程工作：

1. 打开 Weave 的 `/webui` 页面获取二维码
2. 手机微信扫码登录
3. 在 Obsidian 插件中连接本地 Weave 服务
4. 通过微信文件传输助手发送文本、图片、文件
5. 在 Obsidian 中查看自动同步和归档结果

## 接口概览

下面列出当前项目中最常用的一组接口。

### 根接口

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/` | 根信息 |
| `GET` | `/qr` | 获取登录二维码 |
| `GET` | `/login/status` | 查询登录状态 |
| `GET` | `/messages` | 查询消息 |
| `POST` | `/save_session` | 保存会话 |
| `POST` | `/send` | 发送文本 |
| `POST` | `/upload` | 上传文件 |

### Telegram Bot API 风格接口

| Method | Path |
| --- | --- |
| `GET` | `/bot/getUpdates` |
| `GET` | `/bot/getMe` |
| `GET` | `/bot/getChat` |
| `GET` | `/bot/getFile` |
| `POST` | `/bot/sendMessage` |
| `POST` | `/bot/sendDocument` |
| `POST` | `/bot/sendDocument/upload` |
| `POST` | `/bot/sendPhoto` |
| `POST` | `/bot/sendPhoto/upload` |
| `POST` | `/bot/copyMessage` |
| `POST` | `/bot/setWebhook` |
| `POST` | `/bot/deleteWebhook` |
| `GET` | `/bot/getWebhookInfo` |

### 文件与存储接口

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/downloads` | 查看下载目录 |
| `GET` | `/files/metadata` | 查询文件元数据 |
| `DELETE` | `/files/{msg_id}` | 删除文件 |
| `POST` | `/files/cleanup` | 清理历史文件 |
| `GET` | `/store/stats` | 查询存储统计 |
| `GET` | `/store/messages` | 查询存储消息 |

### 框架与调试接口

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/framework/state` | 运行状态 |
| `POST` | `/framework/chat_mode` | 聊天模式开关 |
| `POST` | `/framework/execute` | 执行框架命令 |
| `GET` | `/framework/tasks` | 查询任务 |
| `POST` | `/framework/tasks` | 新建任务 |
| `DELETE` | `/framework/tasks/{task_id}` | 删除任务 |
| `POST` | `/framework/tasks/{task_id}/enabled` | 启停任务 |
| `POST` | `/framework/tasks/{task_id}/run` | 立即执行任务 |
| `GET` | `/plugins` | 查看插件 |
| `POST` | `/plugins/reload` | 重载插件 |
| `GET` | `/health` | 健康检查 |
| `GET` | `/stability` | 稳定性状态 |
| `GET` | `/trace/status` | Trace 状态 |
| `GET` | `/trace/recent` | 最近 Trace |
| `POST` | `/trace/clear` | 清理 Trace |
| `POST` | `/wechat/session/save` | 保存微信会话 |
| `GET` | `/webui` | 调试面板 |

完整接口以 `/api/docs` 为准。

## WebUI

项目内置 WebUI，默认路径：

```text
/webui
```

新的 WebUI 主要用于：

- 扫码登录和状态查看
- Bot API 调试
- 消息列表浏览
- 文件存储管理
- 框架任务管理
- 协议 Trace 查看

如果你是本地开发或排障，优先从 WebUI 和 `/api/docs` 开始。

## 项目结构

```text
weave/
├── config/
├── connectors/
│   └── wechat/
├── exceptions/
├── middlewares/
├── module_api/
│   └── v1/
│       ├── controller/
│       ├── dao/
│       ├── entity/
│       ├── filter/
│       └── service/
├── tasks/
├── tests/
├── utils/
├── workers/
├── main.py
└── requirements.txt
```

## 环境变量建议

常用变量如下：

| 变量 | 说明 |
| --- | --- |
| `APP_NAME` | 应用名称 |
| `APP_PORT` | 应用端口 |
| `DB_TYPE` | 数据库类型：`sqlite` / `mysql` / `postgresql` |
| `SQLITE_PATH` | SQLite 文件路径 |
| `STORAGE_DIR` | 文件存储目录 |
| `WECHAT_ENABLED` | 是否启用微信连接器 |
| `WECHAT_AUTO_CONNECT` | 启动时是否自动连接 |
| `WECHAT_ENTRY_HOST` | 微信入口域名 |
| `WECHAT_POLL_INTERVAL` | 同步轮询间隔 |
| `WECHAT_HEARTBEAT_INTERVAL` | 心跳间隔 |
| `WECHAT_AUTO_DOWNLOAD` | 是否自动下载附件 |
| `WECHAT_TRACE_ENABLED` | 是否启用 HTTP Trace |

## 安全说明

Weave 的设计目标是本地优先，但仍建议注意以下事项：

- 不要把带有真实凭据的 `.env.*` 文件直接公开
- 不要把 `trace_logs/` 中的敏感请求记录提交到仓库
- 不要忽视 `skey`、`sid`、`pass_ticket` 等会话字段的泄漏风险
- 如果启用了附件自动下载，请留意 `storage/` 目录中的敏感文件


## 与 `wx-filehelper-api` 的关系

Weave 不是对原项目的简单改名复制，而是在接口兼容目标下进行的一次后端重构。

重点差异在于：

- 实现方式从脚本式组织改为 FastAPI 分层架构
- 数据访问改为 ORM 和异步数据库会话
- 补充了更清晰的 Controller / Service / DAO 边界
- 增加了 WebUI 调试能力、Trace 能力和更规范的工程组织

但对外接口、返回结构和数据库语义，仍然以 `wx-filehelper-api` 的兼容目标为核心。

## 支持与反馈

如果这个项目对你有帮助，欢迎点一颗 ⭐ Star——这是它持续迭代的最大动力。

使用中遇到问题，或有更好的想法与改进建议，欢迎提交 [Issues](https://github.com/LijiangTn/Weave/issues)。无论是 Bug 反馈、功能建议、文档疑问还是使用经验，都会对这个项目有帮助。

没有别的期望，只希望大家能把 Weave 用起来。它现在还不够完善，但只要大家愿意用、愿意提想法，我会抽时间持续打磨。

## License

本项目使用 [MIT License](LICENSE)。
