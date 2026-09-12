from pydantic import BaseModel
from typing import Optional


class SupplierEvaluationResponse(
    BaseModel
):

    id: int

    procurement_id: int

    supplier_id: int

    evaluation_status: str

    required_item_match: bool

    mandatory_eligible: bool

    verification_status: Optional[str]

    capacity_status: str

    historical_evidence_status: str

    historical_delivery_count: int

    historical_commitment_count: int

    fulfilled_quantity: float

    promised_quantity: float

    fulfilment_rate: Optional[float]

    on_time_delivery_rate: Optional[float]

    quantity_variance_rate: Optional[float]

    quality_acceptance_rate: Optional[float]

    indicator_explanation: str