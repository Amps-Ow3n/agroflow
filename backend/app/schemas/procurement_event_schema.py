from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ProcurementEventOut(
    BaseModel
):

    id: int

    procurement_id: int

    event_type: str

    title: str

    description: str | None

    actor_id: int

    actor_name: str

    entity_type: str | None

    entity_id: int | None

    occurred_at: datetime

    metadata: dict[str, Any] | None

    evidence: list[dict]


class AuditEventOut(
    BaseModel
):

    id: int

    procurement_id: int

    actor_id: int

    actor_name: str

    action: str

    entity_type: str

    entity_id: int | None

    previous_state: dict | None

    new_state: dict | None

    metadata: dict | None

    created_at: datetime