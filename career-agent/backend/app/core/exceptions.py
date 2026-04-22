from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "message": exc.detail, "data": None},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"code": 422, "message": "参数校验失败", "data": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(_, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"服务器异常: {exc}", "data": None},
        )
