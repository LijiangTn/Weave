import argparse
import os
import sys
from dotenv import load_dotenv
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Literal

class AppSettings(BaseSettings):
    """
    应用配置
    """

    app_env: str = os.getenv('APP_ENV', 'dev')
    app_name: str = os.getenv('APP_NAME', 'Weave')
    app_root_path: str = os.getenv('APP_ROOT_PATH', '/dev-api')
    app_host: str = os.getenv('APP_HOST', '0.0.0.0')
    app_port: int = os.getenv('APP_PORT', 9099)
    app_version: str = os.getenv('APP_VERSION', '1.0.0')
    app_reload: bool = os.getenv('APP_RELOAD', True)
    app_ip_location_query: bool = os.getenv('APP_IP_LOCATION_QUERY', True)
    app_same_time_login: bool = os.getenv('APP_SAME_TIME_LOGIN', True)
    log_path: str = os.getenv('LOG_PATH', 'logs/')

class JwtSettings(BaseSettings):
    """
    Jwt配置
    """

    jwt_secret_key: str = os.getenv('JWT_SECRET_KEY', '')
    jwt_algorithm: str = os.getenv('JWT_ALGORITHM', '')
    jwt_expire_minutes: int = os.getenv('JWT_EXPIRE_MINUTES', 1440)
    jwt_redis_expire_minutes: int = os.getenv('JWT_REDIS_EXPIRE_MINUTES', 30)

class DataBaseSettings(BaseSettings):
    """
    数据库配置
    """

    db_type: Literal['mysql', 'postgresql', 'sqlite'] = os.getenv('DB_TYPE', 'mysql')
    db_host: str = os.getenv('DB_HOST', '127.0.0.1')
    db_port: int = os.getenv('DB_PORT', 3306)
    db_username: str = os.getenv('DB_USERNAME', 'root')
    db_password: str = os.getenv('DB_PASSWORD', '')
    db_database: str = os.getenv('DB_DATABASE', 'wechat')
    db_echo: bool = os.getenv('DB_ECHO', True)
    db_max_overflow: int = os.getenv('DB_MAX_OVERFLOW', 10)
    db_pool_size: int = os.getenv('DB_POOL_SIZE', 50)
    db_pool_recycle: int = os.getenv('DB_POOL_RECYCLE', 3600)
    db_pool_timeout: int = os.getenv('DB_POOL_TIMEOUT', 30)

class RedisSettings(BaseSettings):
    """
    Redis配置
    """

    redis_host: str = os.getenv('REDIS_HOST', '127.0.0.1')
    redis_port: int = os.getenv('REDIS_PORT', 6379)
    redis_username: str = os.getenv('REDIS_USERNAME', '')
    redis_password: str = os.getenv('REDIS_PASSWORD', '')
    redis_database: int = os.getenv('REDIS_DATABASE', 0)

class StorageSettings(BaseSettings):
    """
    网关文件存储配置
    """

    storage_dir: str = os.getenv('STORAGE_DIR', 'storage')
    file_date_subdir: bool = os.getenv('FILE_DATE_SUBDIR', 'true') == 'true'
    max_file_size: int = int(os.getenv('MAX_FILE_SIZE', str(25 * 1024 * 1024)))

class WechatSettings(BaseSettings):
    """
    微信连接器配置
    """

    wechat_enabled: bool = os.getenv('WECHAT_ENABLED', 'false') == 'true'
    wechat_auto_connect: bool = os.getenv('WECHAT_AUTO_CONNECT', 'true') == 'true'
    wechat_entry_host: str = os.getenv('WECHAT_ENTRY_HOST', 'szfilehelper.weixin.qq.com')
    wechat_mmweb_appid: str = os.getenv('WECHAT_MMWEB_APPID', 'wx_webfilehelper')
    wechat_to_user_name: str = os.getenv('WECHAT_TO_USER_NAME', 'filehelper')
    wechat_lang: str = os.getenv('WECHAT_LANG', 'zh_CN')
    wechat_poll_interval: float = float(os.getenv('WECHAT_POLL_INTERVAL', '1.0'))
    wechat_poll_min_interval: float = float(os.getenv('WECHAT_POLL_MIN_INTERVAL', '0.5'))
    wechat_poll_max_interval: float = float(os.getenv('WECHAT_POLL_MAX_INTERVAL', '3.0'))
    wechat_heartbeat_interval: int = int(os.getenv('WECHAT_HEARTBEAT_INTERVAL', '30'))
    wechat_reconnect_delay: int = int(os.getenv('WECHAT_RECONNECT_DELAY', '5'))
    wechat_max_reconnect_attempts: int = int(os.getenv('WECHAT_MAX_RECONNECT_ATTEMPTS', '10'))
    wechat_auto_download: bool = os.getenv('WECHAT_AUTO_DOWNLOAD', 'true') == 'true'
    wechat_trace_enabled: bool = os.getenv('WECHAT_TRACE_ENABLED', 'false') == 'true'
    wechat_trace_redact: bool = os.getenv('WECHAT_TRACE_REDACT', 'true') == 'true'
    wechat_trace_max_body: int = int(os.getenv('WECHAT_TRACE_MAX_BODY', '4096'))
    wechat_trace_dir: str = os.getenv('WECHAT_TRACE_DIR', os.path.join(os.getcwd(), 'trace_logs'))

class UploadSettings:
    """
    上传配置
    """

    UPLOAD_PREFIX = os.getenv('UPLOAD_PREFIX', '/profile')
    DEFAULT_ALLOWED_EXTENSION = [
        # 图片
        'bmp',
        'gif',
        'jpg',
        'jpeg',
        'png',
        # word excel powerpoint
        'doc',
        'docx',
        'xls',
        'xlsx',
        'ppt',
        'pptx',
        'html',
        'htm',
        'txt',
        # 压缩文件
        'rar',
        'zip',
        'gz',
        'bz2',
        # 视频格式
        'mp4',
        'avi',
        'rmvb',
        # pdf
        'pdf',
    ]

class CachePathConfig:
    """
    缓存目录配置
    """

    PATH = os.path.join(os.path.abspath(os.getcwd()), os.getenv('CACHE_PATH', 'caches'))
    PATHSTR = os.getenv('CACHE_PATH_STR', 'caches')

class GetConfig:
    """
    获取配置
    """

    def __init__(self):
        self.parse_cli_args()

    @lru_cache()
    def get_app_config(self):
        """
        获取应用配置
        """
        # 实例化应用配置模型
        return AppSettings()

    @lru_cache()
    def get_jwt_config(self):
        """
        获取Jwt配置
        """
        # 实例化Jwt配置模型
        return JwtSettings()

    @lru_cache()
    def get_database_config(self):
        """
        获取数据库配置
        """
        # 实例化数据库配置模型
        return DataBaseSettings()

    @lru_cache()
    def get_redis_config(self):
        """
        获取Redis配置
        """
        # 实例化Redis配置模型
        return RedisSettings()

    @lru_cache()
    def get_upload_config(self):
        """
        获取数据库配置
        """
        # 实例上传配置
        return UploadSettings()

    @lru_cache()
    def get_storage_config(self):
        """
        获取存储配置
        """
        return StorageSettings()

    @lru_cache()
    def get_wechat_config(self):
        """
        获取微信连接器配置
        """
        return WechatSettings()

    @staticmethod
    def parse_cli_args():
        """
        解析命令行参数
        """
        argv0 = sys.argv[0] if sys.argv else ''
        if 'uvicorn' in argv0 or 'pytest' in argv0 or 'py.test' in argv0:
            # pytest/uvicorn 启动时不消费自定义参数
            pass
        else:
            # 使用argparse定义命令行参数
            parser = argparse.ArgumentParser(description='命令行参数')
            parser.add_argument('--env', type=str, default='', help='运行环境')
            # parse_known_args 允许透传未识别参数（避免与 pytest 等冲突）
            args, _ = parser.parse_known_args()
            # 设置环境变量，如果未设置命令行参数，默认APP_ENV为dev
            os.environ['APP_ENV'] = args.env if args.env else 'dev'
        # 读取运行环境
        run_env = os.environ.get('APP_ENV', '')
        # 运行环境未指定时默认加载.env.dev
        env_file = '.env.dev'
        # 运行环境不为空时按命令行参数加载对应.env文件
        if run_env != '':
            env_file = f'.env.{run_env}'
        # 加载配置
        load_dotenv(env_file)

# 实例化获取配置类
get_config = GetConfig()
# 应用配置
AppConfig = get_config.get_app_config()
# Jwt配置
JwtConfig = get_config.get_jwt_config()
# 数据库配置
DataBaseConfig = get_config.get_database_config()
# Redis配置
RedisConfig = get_config.get_redis_config()
# 上传配置
UploadConfig = get_config.get_upload_config()
# 存储配置
StorageConfig = get_config.get_storage_config()
# 微信连接器配置
WechatConfig = get_config.get_wechat_config()
