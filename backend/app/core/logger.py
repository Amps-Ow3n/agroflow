import logging
from typing import Optional

from app.core.request_context import (
    get_request_id
)

# ======================================================
# CENTRAL LOGGER CONFIGURATION
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "request=%(request_id)s | "
        "user=%(user_id)s | "
        "action=%(action)s | "
        "entity=%(entity)s | "
        "%(message)s"
    )
)

logger = logging.getLogger("agroflow")

def _extra(
    request_id: Optional[str]=None,
    user_id: Optional[int]="-",
    action: Optional[str]="-",
    entity: Optional[str]="-"
):

    if request_id is None:
        request_id = get_request_id()


    return {

        "request_id": request_id,

        "user_id": user_id,

        "action": action,

        "entity": entity

    }

# ======================================================
# INFO
# ======================================================

def log_info(
    message,
    request_id="-",
    user_id="-",
    action="-",
    entity="-",
    extra=None
):
    logger.info(
    message,
    extra={
        **_extra(
            request_id,
            user_id,
            action,
            entity
        ),
        "details": extra or {}
    }
)

# ======================================================
# WARNING
# ======================================================

def log_warning(
    message,
    request_id="-",
    user_id="-",
    action="-",
    entity="-",
    extra=None
):
    logger.warning(
    message,
    extra={
        **_extra(
            request_id,
            user_id,
            action,
            entity
        ),
        "details": extra or {}
    }
)

# ======================================================
# ERROR
# ======================================================

def log_error(

    message,

    user_id="-",

    action="-",

    entity="-",

    exception=None,

    extra=None

):

    logger.error(

        message,

        extra={

            **_extra(
                user_id=user_id,
                action=action,
                entity=entity
            ),

            "exception": str(exception) if exception else "-",

            "details": extra or {}

        }

    )