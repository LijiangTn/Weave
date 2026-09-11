import os
import time
from loguru import logger
from config.env import AppSettings

log_path = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(log_path):
    os.mkdir(log_path)

app_name = AppSettings().app_name

log_path_error = os.path.join(log_path, f'{app_name}_error_{time.strftime("%Y-%m-%d")}.log')
log_path_other = os.path.join(log_path, f'{app_name}_other_{time.strftime("%Y-%m-%d")}.log')

logger.add(log_path_error, rotation='50MB', encoding='utf-8', enqueue=True, compression='zip', level='ERROR')
logger.add(log_path_other, rotation='50MB', encoding='utf-8', enqueue=True, compression='zip', level='DEBUG')
