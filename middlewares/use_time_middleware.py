import time
from fastapi import Request, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class UseTimeMiddleware(BaseHTTPMiddleware):
    """ 计算耗时中间件"""

    def __init__(self, app):
        super().__init__(app)

    #################################### 重写BaseHTTPMiddleware类中的dispatch方法 ####################################
    async def dispatch(self, request: Request, call_next) -> Response:
        """ 请求耗时 """
        start_time = time.time()
        # 调用下一个中间件或路由处理函数
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

def add_user_time_middleware(app: FastAPI):
    """ 注册中间件 """
    app.add_middleware(UseTimeMiddleware)
