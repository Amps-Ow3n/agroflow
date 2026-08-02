from fastapi import Request
from fastapi.responses import JSONResponse
import logging


logger = logging.getLogger("agroflow")


def error_response(
    code: str,
    message: str,
    status_code: int,
    details=None
):

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details
            }
        }
    )



async def global_exception_handler(
    request: Request,
    exc: Exception
):

    logger.exception(
        "Unhandled exception: %s",
        exc
    )

    return error_response(
        code="INTERNAL_SERVER_ERROR",
        message="Something went wrong. Please try again later.",
        status_code=500
    )