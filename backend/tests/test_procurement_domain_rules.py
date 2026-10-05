import pytest
from pydantic import ValidationError
from app.schemas.procurement_schema import ProcurementCreate
from app.services.procurement_service import VALID_TRANSITIONS


def base(item_name, unit):
    return ProcurementCreate(
        title="Food supply",
        required_by_date="2027-01-15",
        item_name=item_name,
        quantity="500",
        unit=unit,
        location="Kampala",
        procurement_method="QUOTATION",
    )


def test_product_unit_rule_rejects_volume_for_beans():
    with pytest.raises(ValidationError):
        base("Beans", "l")


def test_product_unit_rule_accepts_mass_for_beans():
    assert base("Beans", "kg").unit == "kg"


def test_supported_unit_is_normalized():
    assert base("Maize Flour", " KG ").unit == "kg"


def test_acceptance_can_be_completed_but_not_skipped():
    assert VALID_TRANSITIONS["ACCEPTED"] == {"COMPLETED"}
    assert "COMPLETED" not in VALID_TRANSITIONS["INSPECTION"]
