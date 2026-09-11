from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config.env import AppConfig, StorageConfig, WechatConfig
from config.get_db import init_create_table, get_db
from connectors.wechat.connector import WeChatConnector
from connectors.wechat.sync_state import SyncStateRepo
from exceptions.handle import handle_exception
from middlewares.handle import handle_middleware
from module_api.v1.controller.bot_controller import botController
from module_api.v1.controller.files_controller import filesController
from module_api.v1.controller.framework_controller import frameworkController
from module_api.v1.controller.root_controller import rootController
from module_api.v1.controller.wechat_controller import wechatController
from module_api.v1.controller.webui_controller import webuiController
from module_api.v1.service.framework_service import FrameworkService
from module_api.v1.service.message_pipeline_service import MessagePipelineService
from tasks.task_manager import task_manager
from utils.connector_registry import connector_registry
from utils.log_util import logger
from utils.migrations_util import DatabaseMigration
from workers.file_downloader import WeChatFileDownloader
#################################### 生命周期 ####################################
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f'{AppConfig.app_name} 开始启动')
    FrameworkService.mark_started()
    Path(StorageConfig.storage_dir).mkdir(parents=True, exist_ok=True)
    if not getattr(app.state, 'static_routes_mounted', False):
        app.mount('/static', StaticFiles(directory=StorageConfig.storage_dir, check_dir=False), name='static')
        app.mount('/webui-static', StaticFiles(directory=_webui_dir), name='webui-static')
        app.state.static_routes_mounted = True
    await init_create_table()
    ############################## 数据库迁移 ##############################
    try:
        async for db in get_db():
            await DatabaseMigration.run_all_migrations(db)
            break
    except Exception as e:
        logger.error(f"数据库迁移失败: {str(e)}")

    ############################## 微信连接器 + 消息管道 ##############################
    wechat_connector: WeChatConnector | None = None
    if WechatConfig.wechat_enabled:
        try:
            async for db in get_db():
                sync_repo = SyncStateRepo(db=db, source=WeChatConnector.source)
                wechat_connector = WeChatConnector(
                    config=WechatConfig,
                    storage=StorageConfig,
                    sync_state_repo=sync_repo,
                )
                downloader = WeChatFileDownloader(protocol=wechat_connector.protocol)

                async def handle_unified_message(unified):
                    await MessagePipelineService.handle_incoming_message(unified, downloader)

                wechat_connector.set_message_handler(handle_unified_message)
                connector_registry.register(wechat_connector.source, wechat_connector)
                if WechatConfig.wechat_auto_connect:
                    await wechat_connector.start()
                break
        except Exception as exc:
            logger.error(f'微信连接器初始化失败: {exc}')

    logger.info(f'{AppConfig.app_name} 启动完成')
    yield

    logger.info(f'{AppConfig.app_name} 开始关闭')
    ############################## 微信连接器关闭 ##############################
    if wechat_connector is not None:
        try:
            await wechat_connector.stop()
        except Exception as exc:
            logger.warning(f'关闭微信连接器失败: {exc}')
    ############################## 取消所有后台任务 ##############################
    await task_manager.cancel_all()
    logger.info(f'{AppConfig.app_name} 已关闭')

#################################### 创建应用 ####################################
app = FastAPI(
    debug=False,
    title=AppConfig.app_name,
    description=f'{AppConfig.app_name}接口文档',
    version=AppConfig.app_version,
    docs_url='/api/docs',
    redoc_url='/api/redoc',
    openapi_url='/api/openapi.json',
    lifespan=lifespan,
)
#################################### 注册中间件 ####################################
handle_middleware(app)

#################################### 注册异常 ####################################
handle_exception(app)

#################################### WebUI 静态资源 ####################################
_webui_dir = Path(__file__).resolve().parent / 'module_api' / 'v1' / 'assets' / 'webui'

#################################### 路由列表 ####################################
controller_list = [
    {'router': rootController, 'tags': ['根接口']},
    {'router': botController, 'tags': ['Telegram Bot API']},
    {'router': wechatController, 'tags': ['微信扩展']},
    {'router': filesController, 'tags': ['文件存储']},
    {'router': frameworkController, 'tags': ['框架管理']},
    {'router': webuiController, 'tags': ['WebUI']},
]

#################################### 路由注册 ####################################
for controller in controller_list:
    app.include_router(router=controller.get('router'), tags=controller.get('tags'))

if __name__ == '__main__':
    uvicorn.run("main:app", host="127.0.0.1", port=8081, reload=True)
