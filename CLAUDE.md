# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

基于 FastAPI 的异步分层后端架构模板（原 `fastapi-best-architecture`，参考 Dash-FastAPI-Admin）。采用 Controller → Service → DAO → Entity 四层架构，集成 JWT 鉴权、Redis 缓存、自动数据库迁移、Loguru 日志和异常统一处理。

- Python ≥ 3.9
- 依赖管理：`requirements.txt`（详见版本号）
- 虚拟环境：`.venv/` 已存在

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务（reload 模式）
python main.py
# 等价于
uvicorn main:app --host 127.0.0.1 --port 8081 --reload

# 切换环境（命令行参数覆盖 .env.dev）
python main.py --env prod   # 加载 .env.prod

# Swagger UI:   http://localhost:8081/api/docs
# ReDoc:        http://localhost:8081/api/redoc
# OpenAPI JSON: http://localhost:8081/api/openapi.json
```

未提供测试目录与 lint 工具配置，新增测试请直接放 `test/` 并以 `pytest` 运行（需自行在 requirements 中加入）。

## 启动生命周期（main.py）

应用通过 FastAPI `lifespan` 上下文启动，按顺序执行：

1. `init_redis(app)` — 创建 Redis 异步连接池并挂到 `app.state.redis`（`config/get_redis.py` + `utils/redis_client.py`）
2. `init_cache(app)` — 复用 `app.state.redis` 初始化 FastAPICache（`utils/cache_util.py`）
3. `init_create_table()` — `Base.metadata.create_all` 创建缺失表（`config/get_db.py`）
4. `DatabaseMigration.run_all_migrations(db)` — 增量添加缺失字段和索引（仅 MySQL，`utils/migrations_util.py`）
5. `close_redis(app)` — 关闭连接池

中间件顺序（CORS → GZip → 请求耗时）、异常处理器、分页器 (`fastapi_pagination`)、控制器列表都在 `main.py` 集中注册。

## 配置加载（config/env.py）

- 单例 `GetConfig` 通过 `@lru_cache` 缓存 `AppSettings/JwtSettings/DataBaseSettings/RedisSettings/UploadSettings`
- CLI `--env` 参数 → 设置 `APP_ENV` 环境变量 → 加载 `.env.{APP_ENV}`（默认 `.env.dev`）
- uvicorn 启动时跳过 argparse，需要通过环境变量切换环境
- **注意**：`.env.dev` 含真实数据库/Redis 凭据占位符；切换配置前修改对应值

## 分层架构

```
module_api/v1/
├── controller/   # APIRouter，仅做参数解析与响应包装
├── service/      # 业务逻辑（@classmethod 风格，薄层）
├── dao/          # SQLAlchemy 查询组装，返回 ORM 模型或 query 对象
├── entity/
│   ├── do/       # SQLAlchemy ORM 模型（继承 config.database.Base）
│   └── vo/       # Pydantic 请求/响应模型
└── filter/       # fastapi_filter 过滤器（继承 Filter，绑定 ORM 模型）
```

**调用方向**：Controller → Service → DAO → Entity。Service 在大多数场景是 DAO 的薄包装；当业务简单时可省略 Service 直接调 DAO。

### 新增模块的标准步骤

1. 在 `module_api/v1/entity/do/<name>_do.py` 定义 ORM 模型（继承 `config.database.Base`，`__tablename__` 必填）
2. **必须** 在 `config/models.py` 中 `import` 该模型，否则 SQLAlchemy 不会注册到 `Base.metadata`，自动建表和迁移都会跳过
3. 在 `module_api/v1/entity/vo/<name>_vo.py` 定义 Pydantic 模型（请求用 `Field(...)`，响应模型加 `model_config = ConfigDict(from_attributes=True)`）
4. DAO 层：纯 `select/update/insert/delete`；按主键/唯一字段查询返回 ORM 对象
5. Service 层：薄包装 DAO；复杂业务（事务编排、跨表）放在这里
6. Filter 层：继承 `fastapi_filter.contrib.sqlalchemy.Filter`，内部 `class Constants(Filter.Constants)` 绑定 `model = <ORM>`，通过字段后缀（`__ilike`/`__gte`/`__lte`/`__in` 等）暴露查询条件
7. Controller：`APIRouter(prefix='/api/v1/<name>')`，使用 `Depends(get_db)`、`FilterDepends(<Filter>)`、`paginate(db, query)` 分页
8. 在 `main.py` 的 `controller_list` 注册路由

### 接口缓存

```python
from fastapi_cache.decorator import cache
from utils.cache_util import get_cache_key_builder

@router.get('/list')
@cache(expire=120, key_builder=get_cache_key_builder())
async def get_list(...): ...
```

缓存 key 由 `utils/cache_util.py:get_cache_key_builder()` 生成，自动包含请求路径与 query 参数。

## 统一响应与异常

- **响应**：`utils/response_util.py:ResponseUtil.{success,failure,unauthorized,forbidden,error,streaming}` 返回 `{code, msg, data?, success, time}`，HTTP 状态码恒为 200，业务码通过 `code` 字段区分（参见 `config/constant.py:HttpStatusConstant`）
- **异常类**（`exceptions/exception.py`）：`AuthException`、`LoginException`、`PermissionException`、`ServiceException`、`ServiceWarning`、`ModelValidatorException`
- **全局处理器**：`exceptions/handle.py:handle_exception(app)` 在 `main.py` 注册，覆盖自定义异常、`HTTPException`、兜底 `Exception`
- 在 Service/DAO 中 `raise ServiceException(msg=...)` 即可被捕获并返回统一格式

## 关键工具模块（utils/）

| 文件 | 用途 |
|------|------|
| `response_util.py` | 统一响应包装（success/failure/unauthorized/forbidden/error） |
| `cache_util.py` | FastAPICache 初始化 + 自定义 cache key builder |
| `redis_client.py` | `RedisUtil` 多 DB 单例连接池（带重试），按 `database` 维度缓存 |
| `migrations_util.py` | 启动时增量迁移（仅 MySQL），通过 `information_schema` 对比，自动 `ADD COLUMN` / `CREATE INDEX` |
| `log_util.py` | Loguru，按级别和日期分文件（`logs/<app>_error_<date>.log` / `_other_`），50MB 轮转 |
| `cron_util.py` | 6/7 段 Cron 表达式校验 |
| `pwd_util.py` | passlib bcrypt 加密/校验 |
| `common_util.py` | `snake_case ↔ camelCase` 转换、Excel 导出/模板、字节工具 |
| `upload_util.py` | 文件名校验、随机码、时间戳等 |
| `string_util.py` / `time_format_util.py` / `message_util.py` | 字符串/时间/消息工具 |

## 数据库与 Redis 配置

- **数据库**：`config/database.py` 根据 `DB_TYPE` 拼装 `mysql+asyncmy://` 或 `postgresql+asyncpg://` URL；引擎在模块导入时立即创建，`pool_size=50`，`pool_recycle=3600`
- **Redis**：`utils/redis_client.py:RedisUtil.get_client(db)` 按 DB 维度缓存客户端；`app.state.redis` 在 `init_redis` 中挂载，Controller 中通过 `Depends(get_redis)` 拿
- 自动迁移工具 `DatabaseMigration` 仅适配 MySQL（`information_schema.COLUMNS` 查询），切换 PostgreSQL 后该模块需重写

## 环境变量速查

`.env.dev` / `.env.prod` 中的关键键：`APP_ENV` / `APP_NAME` / `APP_HOST` / `APP_PORT` / `APP_RELOAD`；`JWT_SECRET_KEY` / `JWT_EXPIRE_MINUTES`；`DB_TYPE` / `DB_HOST` / `DB_PORT` / `DB_USERNAME` / `DB_PASSWORD` / `DB_DATABASE` / `DB_ECHO` / `DB_POOL_SIZE`；`REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` / `REDIS_DATABASE`。详见 `config/env.py`。

## 新建模型时的检查清单

- [ ] `module_api/v1/entity/do/<name>_do.py` 定义并继承 `Base`
- [ ] 在 `config/models.py` 中 `import`，加入 `__all__`
- [ ] DAO 中至少包含按主键查询的 `classmethod`
- [ ] VO 响应模型设置 `model_config = ConfigDict(from_attributes=True)`
- [ ] Filter 的 `Constants.model` 指向正确的 ORM 类
- [ ] Controller 在 `main.py:controller_list` 注册，带 `tags=[...]`

## 现有模块示例

- `module_api/v1/controller/user_controller.py` — 完整演示：登录/注册/登出占位 + `@cache` 装饰的列表查询（分页 + filter 组合）
- `module_api/v1/controller/index_controller.py` — 最小 Hello World 路由

## 注意事项

- `module_api/` 下目前仅 `v1/`，新增版本请创建 `v2/` 并在 `main.py` 单独注册
- `controller_list` 中每个 controller 必须暴露名为 `<name>Controller` 的 `APIRouter` 实例（约定，非强制）
- 所有日志通过 `utils.log_util.logger` 输出（已配置 Loguru sink），不要直接 `print`
- 控制器中建议使用 `Depends(get_db)` 注入会话，不要全局共享 `AsyncSessionLocal()`
- `app.state.redis` 与 `RedisUtil` 单例任选其一；前者随 app 生命周期，后者独立可用