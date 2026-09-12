import pytest
from fastapi import HTTPException

from app.services.domain_invariants import (
    require_po_line_belongs_to_po,
    require_commitment_belongs_to_po_line,
    require_commitment_supplier_matches_po,
    require_inspection_belongs_to_delivery,
    require_corrective_action_follows_rejection,
    require_supplier_matches_organization,
    require_user_belongs_to_organization,
)


def test_po_line_belongs_to_po():
    assert require_po_line_belongs_to_po({"purchase_order_id": 10}, 10)


def test_po_line_wrong_po_rejected():
    with pytest.raises(HTTPException):
        require_po_line_belongs_to_po({"purchase_order_id": 10}, 99)


def test_commitment_belongs_to_po_line():
    assert require_commitment_belongs_to_po_line({"purchase_order_line_id": 20}, 20)


def test_commitment_supplier_matches_po():
    assert require_commitment_supplier_matches_po({"supplier_id": 7}, 7)


def test_inspection_belongs_to_delivery():
    assert require_inspection_belongs_to_delivery({"delivery_id": 30}, 30)


def test_corrective_action_requires_rejection():
    assert require_corrective_action_follows_rejection({"result": "REJECTED"})


def test_corrective_action_after_acceptance_rejected():
    with pytest.raises(HTTPException):
        require_corrective_action_follows_rejection({"result": "ACCEPTED"})


def test_supplier_matches_supplier_organization():
    supplier = {"organization_id": 100}
    organization = {"id": 100, "organization_type": "SUPPLIER", "status": "ACTIVE"}
    assert require_supplier_matches_organization(supplier, organization) == supplier


def test_user_belongs_to_organization():
    assert require_user_belongs_to_organization({"organization_id": 100}, 100)
