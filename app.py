# SPDX-License-Identifier: GPL-3.0-only

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from routers.v1.api import router as v1_router
from logutils import get_logger
from utils import get_env_var

logger = get_logger(__name__)

environment = get_env_var("ENVIRONMENT", "development").lower()
docs_url = None if environment == "production" else "/docs"
redoc_url = None if environment == "production" else "/redoc"

app = FastAPI(docs_url=docs_url, redoc_url=redoc_url)


@app.exception_handler(HTTPException)
def http_exception_handler(_, exc: HTTPException):
    logger.error(exc.detail)
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_, exc: RequestValidationError):
    first_error = exc.errors()[0]
    field = " ".join(str(loc) for loc in first_error["loc"])
    message = first_error.get("msg", "Invalid input")
    error_message = f"{field}, {message}"

    logger.error(error_message)
    return JSONResponse({"error": error_message}, status_code=400)


@app.exception_handler(Exception)
def internal_exception_handler(_, exc: Exception):
    logger.exception(exc)
    return JSONResponse(
        {"error": "Oops! Something went wrong. Please try again later."},
        status_code=500,
    )


app.include_router(v1_router, prefix="/v1")
