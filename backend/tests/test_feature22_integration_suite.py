"""Feature 22 - Layer 2 integration tests.

These tests exercise multiple real AgroFlow layers together:
route -> Pydantic validation -> service/business logic -> transaction boundary ->
DB adapter -> response/state.

The source archive does not include a runnable PostgreSQL/Neon database or
credentials, so this suite uses a deterministic in-memory PostgreSQL-shaped
adapter at the DB boundary. It deliberately does NOT pretend to prove the
real Neon schema/SQL engine. Those DB-backed checks belong in an environment
with PostgreSQL available.
"""

from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# The supplied project requirements include these packages, but the isolated
# execution environment used for this archive may not have them installed.
# Stub only the import-time surface needed by AgroFlow's dependency modules;
# no production code is changed by these fallbacks.
try:
    import psycopg2  # noqa: F401
except ModuleNotFoundError:
    psycopg2 = types.ModuleType("psycopg2")
    psycopg2.Error = Exception
    psycopg2.connect = lambda *a, **k: None
    extras = types.ModuleType("psycopg2.extras")
    extras.RealDictCursor = object
    psycopg2.extras = extras
    sys.modules["psycopg2"] = psycopg2
    sys.modules["psycopg2.extras"] = extras

try:
    from jose import JWTError  # noqa: F401
except ModuleNotFoundError:
    jose = types.ModuleType("jose")
    jose.JWTError = type("JWTError", (Exception,), {})
    jose.jwt = types.SimpleNamespace()
    sys.modules["jose"] = jose

try:
    import passlib.context  # noqa: F401
except ModuleNotFoundError:
    passlib = types.ModuleType("passlib")
    context = types.ModuleType("passlib.context")
    context.CryptContext = type(
        "CryptContext",
        (),
        {
            "__init__": lambda self, *a, **k: None,
            "hash": lambda self, value: value,
            "verify": lambda self, plain, hashed: plain == hashed,
        },
    )
    passlib.context = context
    sys.modules["passlib"] = passlib
    sys.modules["passlib.context"] = context

# Backend imports are relative to backend/ when pytest is run with
# PYTHONPATH=backend.

from app.routes import procurement_routes, commitment_routes, delivery_routes
from app.services.commitment_service import create_commitment
from app.services.delivery_service import create_delivery
from app.services.inspection_service import inspect_delivery
from app.schemas.commitment_schema import SupplierCommitmentCreate
from app.schemas.delivery_schema import DeliveryCreate, DeliveryLineCreate, InspectionCreate
from app.schemas.procurement_schema import ProcurementCreate


class FakeConnection:
    """Small transaction-aware database adapter for deterministic tests."""

    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.commits = 0
        self.rollbacks = 0
        self.autocommit = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1
        self.cursor_obj.rollback()

    def close(self):
        pass


class FakeCursor:
    """PostgreSQL-shaped cursor with only the SQL used by this suite.

    The goal is not to reimplement PostgreSQL. It is to provide a deterministic
    persistence boundary so the real AgroFlow services can be exercised across
    multiple layers without requiring a live Neon database.
    """

    def __init__(self):
        self.organizations = {
            1: {
                "id": 1,
                "name": "School A",
                "organization_type": "SCHOOL",
                "status": "ACTIVE",
                "verification_status": "VERIFIED",
            }
        }
        self.memberships = {100: {"organization_id": 1, "status": "ACTIVE"}}
        self.procurements = {}
        self.items = {}
        self.purchase_orders = {
            10: {
                "id": 10,
                "procurement_id": 1,
                "supplier_id": 50,
                "status": "ISSUED",
            }
        }
        self.po_lines = {
            101: {
                "id": 101,
                "purchase_order_id": 10,
                "procurement_item_id": 201,
                "quantity": Decimal("500"),
                "unit": "kg",
            }
        }
        self.suppliers = {
            50: {
                "id": 50,
                "organization_id": 2,
                "status": "ACTIVE",
                "supplier_name": "Supplier A",
                "organization_status": "ACTIVE",
                "verification_status": "VERIFIED",
            }
        }
        self.supplier_memberships = {200: {"organization_id": 2, "status": "ACTIVE"}}
        self.commitments = {}
        self.deliveries = {}
        self.delivery_lines = []
        self.inspections = {}
        self.corrective_actions = {}
        self.events = []
        self.audit_events = []
        self._next_procurement = 1
        self._next_item = 201
        self._next_commitment = 1001
        self._next_delivery = 3001
        self._next_inspection = 4001
        self._next_action = 5001
        self._next_event = 1
        self._next_audit = 1
        self.result = []
        self._snapshot = None

    def begin_snapshot(self):
        import copy
        self._snapshot = copy.deepcopy(self.__dict__)

    def rollback(self):
        if self._snapshot is not None:
            snap = self._snapshot
            self.__dict__.clear()
            self.__dict__.update(snap)

    def fetchone(self):
        if isinstance(self.result, list):
            return self.result[0] if self.result else None
        return self.result

    def fetchall(self):
        return list(self.result)

    def execute(self, sql, params=None):
        q = " ".join(sql.split()).upper()
        params = params or ()

        # -------------------- procurement --------------------
        if "SELECT O.ID,O.NAME,O.ORGANIZATION_TYPE,O.STATUS,O.VERIFICATION_STATUS" in q:
            uid = params[0]
            self.result = [self.organizations[1]] if uid in self.memberships else []
            return
        if "SELECT 1 FROM ORGANIZATION_MEMBERSHIPS OM" in q and "OM.ORGANIZATION_ID=%S" in q:
            uid, org_id = params[:2]
            self.result = [{"?column?": 1}] if self.memberships.get(uid, {}).get("organization_id") == org_id else []
            return
        if q.startswith("INSERT INTO PROCUREMENTS"):
            pid = self._next_procurement
            self._next_procurement += 1
            org_id, user_id, _, title, description, procurement_date, required_by, location, specs, quality, estimated, method, notes, department = params
            self.procurements[pid] = {
                "id": pid, "organization_id": org_id, "created_by": user_id,
                "requesting_user_id": user_id, "title": title, "description": description,
                "status": "DRAFT", "procurement_date": procurement_date,
                "required_by_date": required_by, "location": location,
                "specifications": specs, "quality_requirements": quality,
                "estimated_cost": estimated, "procurement_method": method,
                "notes": notes, "requesting_department": department,
                "procurement_identifier": None,
            }
            self.result = [{"id": pid}]
            return
        if q.startswith("UPDATE PROCUREMENTS SET PROCUREMENT_IDENTIFIER"):
            identifier, pid = params
            self.procurements[pid]["procurement_identifier"] = identifier
            self.result = []
            return
        if q.startswith("INSERT INTO PROCUREMENT_ITEMS"):
            pid, name, desc, quantity, unit = params
            item_id = self._next_item
            self._next_item += 1
            self.items[item_id] = {"id": item_id, "procurement_id": pid, "item_name": name, "description": desc, "quantity": quantity, "unit": unit}
            self.result = [{"id": item_id}]
            return
        if q.startswith("INSERT INTO PROCUREMENT_EVENTS"):
            event = {"id": self._next_event}
            self._next_event += 1
            self.events.append(event)
            self.result = [event]
            return
        if q.startswith("INSERT INTO AUDIT_EVENTS"):
            event = {"id": self._next_audit}
            self._next_audit += 1
            self.audit_events.append(event)
            self.result = [event]
            return

        # -------------------- commitment --------------------
        if "FROM SUPPLIERS S JOIN ORGANIZATIONS O" in q and "OM.USER_ID=%S" in q:
            uid = params[0]
            self.result = [self.suppliers[50]] if uid in self.supplier_memberships else []
            return
        if "FROM PURCHASE_ORDERS PO JOIN PURCHASE_ORDER_LINES POL" in q and "PO.ID=%S" in q:
            order_id, line_id, supplier_id = params[:3]
            line = self.po_lines.get(line_id)
            po = self.purchase_orders.get(order_id)
            if line and po and po["supplier_id"] == supplier_id:
                p = self.procurements.get(po["procurement_id"], {"status": "ORDERED", "organization_id": 1})
                self.result = [{
                    "purchase_order_id": order_id, "procurement_id": po["procurement_id"],
                    "supplier_id": supplier_id, "po_status": po["status"],
                    "purchase_order_line_id": line_id, "quantity": line["quantity"], "unit": line["unit"],
                    "procurement_item_id": line["procurement_item_id"], "item_name": "Maize flour",
                    "procurement_status": p.get("status", "ORDERED"), "organization_id": p.get("organization_id", 1),
                }]
            else:
                self.result = []
            return
        if "FROM SUPPLIER_COMMITMENTS WHERE PURCHASE_ORDER_LINE_ID=%S" in q:
            line_id, supplier_id = params[:2]
            self.result = [c for c in self.commitments.values() if c["purchase_order_line_id"] == line_id and c["supplier_id"] == supplier_id and c["status"] in {"SUBMITTED", "ACCEPTED"}]
            return
        if q.startswith("INSERT INTO SUPPLIER_COMMITMENTS"):
            order_id, line_id, supplier_id, promised, start, end, submitted_by = params
            cid = self._next_commitment
            self._next_commitment += 1
            row = {"id": cid, "purchase_order_id": order_id, "purchase_order_line_id": line_id,
                   "supplier_id": supplier_id, "promised_qty": promised, "delivery_start": start,
                   "delivery_end": end, "status": "SUBMITTED", "submitted_by": submitted_by}
            self.commitments[cid] = row
            self.result = [row]
            return

        # School-scoped commitment lookup used before recording a delivery.
        if q.startswith("SELECT SC.*,PO.PROCUREMENT_ID,PO.SUPPLIER_ID AS PO_SUPPLIER_ID,P.STATUS AS PROCUREMENT_STATUS") and "WHERE SC.ID=%S" in q:
            cid, uid = params[:2]
            c = self.commitments.get(cid)
            po = self.purchase_orders.get(c["purchase_order_id"]) if c else None
            p = self.procurements.get(po["procurement_id"]) if po else None
            ok = c and po and p and self.memberships.get(uid, {}).get("organization_id") == p.get("organization_id")
            self.result = [{**c, "procurement_id": po["procurement_id"], "po_supplier_id": po["supplier_id"], "procurement_status": p["status"], "organization_id": p["organization_id"]}] if ok else []
            return

        # -------------------- delivery --------------------
        if q.startswith("SELECT ID,COMMITMENT_ID,DELIVERY_STATUS FROM DELIVERIES WHERE ID=%S"):
            did = params[0]
            d = self.deliveries.get(did)
            self.result = [{"id": did, "commitment_id": d["commitment_id"], "delivery_status": d["delivery_status"]}] if d else []
            return

        if "SELECT PO.PROCUREMENT_ID FROM SUPPLIER_COMMITMENTS SC" in q and "WHERE SC.ID=%S" in q:
            cid = params[0]
            c = self.commitments.get(cid)
            po = self.purchase_orders.get(c["purchase_order_id"]) if c else None
            self.result = [{"procurement_id": po["procurement_id"]}] if c and po else []
            return
        if "SELECT P.* FROM PROCUREMENTS P JOIN ORGANIZATION_MEMBERSHIPS" in q:
            pid, uid = params[:2]
            p = self.procurements.get(pid)
            ok = p and self.memberships.get(uid, {}).get("organization_id") == p.get("organization_id")
            self.result = [p] if ok else []
            return
        if "FROM SUPPLIER_COMMITMENTS SC JOIN PURCHASE_ORDERS PO JOIN PROCUREMENTS P" in q and "WHERE SC.ID=%S" in q:
            cid, uid = params[:2]
            c = self.commitments.get(cid)
            po = self.purchase_orders.get(c["purchase_order_id"]) if c else None
            p = self.procurements.get(po["procurement_id"]) if po else None
            ok = c and po and p and self.memberships.get(uid, {}).get("organization_id") == p.get("organization_id")
            if ok:
                self.result = [{**c, "procurement_id": po["procurement_id"], "po_supplier_id": po["supplier_id"], "procurement_status": p["status"], "organization_id": p["organization_id"]}]
            else:
                self.result = []
            return
        if "SELECT COALESCE(MAX(DELIVERY_SEQUENCE),0)+1" in q:
            cid = params[0]
            seqs = [d["delivery_sequence"] for d in self.deliveries.values() if d["commitment_id"] == cid]
            self.result = [{"next_sequence": max(seqs, default=0) + 1}]
            return
        if q.startswith("INSERT INTO DELIVERIES"):
            cid, parent_id, seq, delivery_date, condition, notes, receiving_user_id = params
            did = self._next_delivery
            self._next_delivery += 1
            row = {"id": did, "commitment_id": cid, "parent_delivery_id": parent_id,
                   "delivery_sequence": seq, "delivery_date": delivery_date, "condition": condition,
                   "notes": notes, "receiving_user_id": receiving_user_id, "delivery_status": "AWAITING_INSPECTION",
                   "created_at": datetime.now(), "updated_at": datetime.now()}
            self.deliveries[did] = row
            self.result = [row]
            return
        if "SELECT PI.ID,PI.QUANTITY FROM PROCUREMENT_ITEMS PI" in q:
            item_id, order_id, line_id = params[:3]
            line = self.po_lines.get(line_id)
            self.result = [{"id": item_id, "quantity": line["quantity"]}] if line and line["procurement_item_id"] == item_id and line["purchase_order_id"] == order_id else []
            return
        if q.startswith("INSERT INTO DELIVERY_LINES"):
            did, item_id, qty = params
            self.delivery_lines.append({"id": len(self.delivery_lines)+1, "delivery_id": did, "procurement_item_id": item_id, "actual_quantity": qty})
            self.result = []
            return
        if "SELECT D.*,SC.PURCHASE_ORDER_ID" in q and "WHERE D.ID=%S" in q:
            did, uid = params[:2]
            d = self.deliveries.get(did)
            c = self.commitments.get(d["commitment_id"]) if d else None
            po = self.purchase_orders.get(c["purchase_order_id"]) if c else None
            p = self.procurements.get(po["procurement_id"]) if po else None
            ok = d and c and po and p and self.memberships.get(uid, {}).get("organization_id") == p.get("organization_id")
            if ok:
                self.result = [{**d, "purchase_order_id": c["purchase_order_id"], "purchase_order_line_id": c["purchase_order_line_id"], "supplier_id": c["supplier_id"], "procurement_id": po["procurement_id"], "organization_id": p["organization_id"], "procurement_status": p["status"]}]
            else:
                self.result = []
            return
        if q.startswith("SELECT DL.ID,DL.PROCUREMENT_ITEM_ID"):
            did = params[0]
            rows = []
            for x in self.delivery_lines:
                if x["delivery_id"] == did:
                    item = self.items.get(x["procurement_item_id"], {"item_name": "Maize flour", "unit": "kg"})
                    rows.append({**x, "item_name": item.get("item_name"), "unit": item.get("unit")})
            self.result = rows
            return

        # -------------------- inspection --------------------
        if q.startswith("SELECT PO.PROCUREMENT_ID FROM DELIVERIES D JOIN SUPPLIER_COMMITMENTS SC") and "WHERE D.ID=%S" in q:
            did = params[0]
            d = self.deliveries.get(did)
            c = self.commitments.get(d["commitment_id"]) if d else None
            po = self.purchase_orders.get(c["purchase_order_id"]) if c else None
            self.result = [{"procurement_id": po["procurement_id"]}] if d and c and po else []
            return

        if "FROM DELIVERIES D JOIN SUPPLIER_COMMITMENTS SC" in q and "WHERE D.ID=%S" in q:
            did, uid = params[:2]
            d = self.deliveries.get(did)
            c = self.commitments.get(d["commitment_id"]) if d else None
            po = self.purchase_orders.get(c["purchase_order_id"]) if c else None
            p = self.procurements.get(po["procurement_id"]) if po else None
            ok = d and c and po and p and self.memberships.get(uid, {}).get("organization_id") == p.get("organization_id")
            if ok:
                self.result = [{**d, "purchase_order_id": c["purchase_order_id"], "purchase_order_line_id": c["purchase_order_line_id"], "supplier_id": c["supplier_id"], "promised_qty": c["promised_qty"], "procurement_id": po["procurement_id"], "procurement_status": p["status"], "organization_id": p["organization_id"]}]
            else:
                self.result = []
            return
        if "SELECT ID FROM INSPECTIONS WHERE DELIVERY_ID=%S" in q:
            did = params[0]
            self.result = [{"id": i} for i, row in self.inspections.items() if row["delivery_id"] == did]
            return
        if "SELECT COALESCE(SUM(ACTUAL_QUANTITY),0) AS ACTUAL FROM DELIVERY_LINES" in q:
            did = params[0]
            total = sum(x["actual_quantity"] for x in self.delivery_lines if x["delivery_id"] == did)
            self.result = [{"actual": total}]
            return
        if q.startswith("INSERT INTO INSPECTIONS"):
            did, result, received, quality, delay, reason, notes, user_id = params
            iid = self._next_inspection
            self._next_inspection += 1
            row = {"id": iid, "delivery_id": did, "result": result, "received_qty": received,
                   "quality_status": quality, "delay_status": delay, "rejection_reason": reason,
                   "notes": notes, "inspected_by": user_id, "inspected_at": datetime.now()}
            self.inspections[iid] = row
            self.result = [row]
            return
        if q.startswith("UPDATE DELIVERIES SET DELIVERY_STATUS"):
            status, did = params[:2]
            self.deliveries[did]["delivery_status"] = status
            self.deliveries[did]["updated_at"] = datetime.now()
            self.result = [self.deliveries[did]]
            return
        if "SELECT POL.ID,POL.QUANTITY,COALESCE(SUM" in q:
            pid = params[0]
            rows = []
            for line in self.po_lines.values():
                accepted = Decimal("0")
                for d in self.deliveries.values():
                    if d["delivery_status"] == "ACCEPTED":
                        c = self.commitments.get(d["commitment_id"])
                        if c and c["purchase_order_line_id"] == line["id"]:
                            accepted += sum(x["actual_quantity"] for x in self.delivery_lines if x["delivery_id"] == d["id"] and x["procurement_item_id"] == line["procurement_item_id"])
                rows.append({"id": line["id"], "quantity": line["quantity"], "accepted": accepted})
            self.result = rows if rows else []
            return

        # -------------------- corrective action --------------------
        if "FROM INSPECTIONS I JOIN DELIVERIES D" in q and "WHERE I.ID=%S" in q and "CORRECTIVE_ACTIONS" not in q:
            iid, uid = params[:2]
            inspection = next((row for row in self.inspections.values() if row["id"] == iid), None)
            delivery = self.deliveries.get(inspection["delivery_id"]) if inspection else None
            commitment = self.commitments.get(delivery["commitment_id"]) if delivery else None
            po = self.purchase_orders.get(commitment["purchase_order_id"]) if commitment else None
            proc = self.procurements.get(po["procurement_id"]) if po else None
            ok = inspection and delivery and commitment and po and proc and self.memberships.get(uid, {}).get("organization_id") == proc.get("organization_id")
            if ok:
                self.result = [{**inspection, "commitment_id": commitment["id"], "delivery_status": delivery["delivery_status"], "procurement_id": po["procurement_id"], "organization_id": proc["organization_id"]}]
            else:
                self.result = []
            return
        if "SELECT ID FROM CORRECTIVE_ACTIONS WHERE INSPECTION_ID=%S" in q:
            iid = params[0]
            self.result = [{"id": row["id"]} for row in self.corrective_actions.values() if row["inspection_id"] == iid]
            return
        if q.startswith("INSERT INTO CORRECTIVE_ACTIONS"):
            iid, description, created_by = params
            aid = self._next_action
            self._next_action += 1
            row = {"id": aid, "inspection_id": iid, "description": description, "status": "OPEN", "created_by": created_by}
            self.corrective_actions[aid] = row
            self.result = [row]
            return
        if "UPDATE CORRECTIVE_ACTIONS SET STATUS='COMPLETED'" in q:
            replacement_id, parent_id = params
            for row in self.corrective_actions.values():
                inspection = self.inspections.get(row["inspection_id"])
                if inspection and inspection["delivery_id"] == parent_id and row["status"] == "OPEN":
                    row["status"] = "COMPLETED"
                    row["replacement_delivery_id"] = replacement_id
            self.result = []
            return

        # -------------------- generic SELECT/transition helpers --------------------
        if "FROM PROCUREMENTS P" in q and "JOIN USERS U" in q and "FOR UPDATE" in q:
            pid, uid = params[:2]
            p = self.procurements.get(pid)
            self.result = [p] if p and self.memberships.get(uid, {}).get("organization_id") == p.get("organization_id") else []
            return
        if q.startswith("UPDATE PROCUREMENTS SET STATUS="):
            target = params[0]
            pid = params[-1]
            self.procurements[pid]["status"] = target
            self.result = []
            return
        if "INSERT INTO PROCUREMENT_EVENTS" in q:
            event = {"id": self._next_event}
            self._next_event += 1
            self.events.append(event)
            self.result = [event]
            return
        if "INSERT INTO AUDIT_EVENTS" in q:
            event = {"id": self._next_audit}
            self._next_audit += 1
            self.audit_events.append(event)
            self.result = [event]
            return

        raise AssertionError(f"Unexpected SQL in integration test: {sql}")


class FakeDB:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.connection = FakeConnection(self.cursor_obj)

    def get(self):
        return self.connection, self.cursor_obj


@contextmanager
def fake_transaction(conn):
    conn.autocommit = False
    conn.cursor_obj.begin_snapshot()
    try:
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def school_user():
    return {
        "user": {"id": 100, "status": "ACTIVE", "is_system_admin": False},
        "memberships": [
            {
                "status": "ACTIVE",
                "organization": {
                    "id": 1, "status": "ACTIVE", "verification_status": "VERIFIED",
                    "organization_type": "SCHOOL",
                },
            }
        ],
    }


def supplier_user():
    return {
        "user": {"id": 200, "status": "ACTIVE", "is_system_admin": False},
        "memberships": [
            {
                "status": "ACTIVE",
                "organization": {
                    "id": 2, "status": "ACTIVE", "verification_status": "VERIFIED",
                    "organization_type": "SUPPLIER",
                },
            }
        ],
    }


def procurement_payload():
    return ProcurementCreate(
        title="Maize procurement",
        required_by_date=date(2026, 10, 1),
        item_name="Maize flour",
        quantity=Decimal("500"),
        unit="kg",
        location="Kampala",
        procurement_method="QUOTATION",
    )


def install_procurement_route(fake_db):
    procurement_routes.get_db = fake_db.get
    procurement_routes.write_transaction = fake_transaction


def test_integration_procurement_create_persists_and_returns_identifier():
    db = FakeDB()
    install_procurement_route(db)

    app = FastAPI()
    app.include_router(procurement_routes.router)
    app.dependency_overrides[procurement_routes.require_procurement_create] = school_user

    client = TestClient(app)
    response = client.post("/procurements", json={
        "title": "Maize procurement",
        "required_by_date": "2026-10-01",
        "item_name": "Maize flour",
        "quantity": 500,
        "unit": "kg",
        "location": "Kampala",
        "procurement_method": "QUOTATION",
    })

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["procurement_identifier"] == "PROC-000001"
    assert body["organization_id"] == 1
    assert db.cursor_obj.procurements[1]["status"] == "DRAFT"
    assert db.cursor_obj.items[201]["quantity"] == Decimal("500")
    assert db.connection.commits == 1
    assert len(db.cursor_obj.events) == 1
    assert len(db.cursor_obj.audit_events) == 1


def test_integration_procurement_create_rejects_invalid_payload_before_database_write():
    db = FakeDB()
    install_procurement_route(db)
    app = FastAPI()
    app.include_router(procurement_routes.router)
    app.dependency_overrides[procurement_routes.require_procurement_create] = school_user
    client = TestClient(app)

    response = client.post("/procurements", json={
        "title": "Maize procurement",
        "required_by_date": "2026-10-01",
        "item_name": "Maize flour",
        "quantity": 0,
        "unit": "kg",
        "location": "Kampala",
        "procurement_method": "QUOTATION",
    })

    assert response.status_code == 422
    assert db.cursor_obj.procurements == {}
    assert db.connection.commits == 0


def test_integration_commitment_persists_only_after_capacity_validation():
    db = FakeDB()
    db.cursor_obj.procurements[1] = {"id": 1, "organization_id": 1, "status": "ORDERED"}
    payload = SupplierCommitmentCreate(
        purchase_order_line_id=101,
        promised_qty=Decimal("500"),
        delivery_start=date(2026, 9, 25),
        delivery_end=date(2026, 9, 30),
    )

    commitment_routes.get_db = db.get
    commitment_routes.write_transaction = fake_transaction
    result = commitment_routes.submit_commitment(10, payload, supplier_user())

    assert result["created"] is True
    assert result["status"] == "SUBMITTED"
    assert len(db.cursor_obj.commitments) == 1
    assert db.connection.commits == 1

    db2 = FakeDB()
    db2.cursor_obj.procurements[1] = {"id": 1, "organization_id": 1, "status": "ORDERED"}
    commitment_routes.get_db = db2.get
    commitment_routes.write_transaction = fake_transaction
    too_large = payload.model_copy(update={"promised_qty": Decimal("501")})
    with pytest.raises(Exception) as exc:
        commitment_routes.submit_commitment(10, too_large, supplier_user())
    assert getattr(exc.value, "status_code", None) == 409
    assert db2.cursor_obj.commitments == {}
    assert db2.connection.commits == 0
    assert db2.connection.rollbacks == 1


def test_integration_delivery_records_against_accepted_commitment():
    db = FakeDB()
    c = db.cursor_obj
    c.procurements[1] = {"id": 1, "organization_id": 1, "status": "COMMITTED"}
    c.commitments[1001] = {
        "id": 1001, "purchase_order_id": 10, "purchase_order_line_id": 101,
        "supplier_id": 50, "promised_qty": Decimal("500"), "status": "ACCEPTED",
    }
    payload = DeliveryCreate(
        commitment_id=1001,
        delivery_date=date(2026, 9, 30),
        condition="Good",
        lines=[DeliveryLineCreate(procurement_item_id=201, actual_quantity=Decimal("430"))],
    )
    delivery_routes.get_db = db.get
    delivery_routes.write_transaction = fake_transaction
    result = delivery_routes.record_delivery(payload, school_user())

    assert result["id"] == 3001
    assert result["delivery_status"] == "AWAITING_INSPECTION"
    assert c.deliveries[3001]["commitment_id"] == 1001
    assert c.delivery_lines[0]["actual_quantity"] == Decimal("430")
    assert db.connection.commits == 1


def test_integration_inspection_updates_delivery_and_records_accepted_quantity():
    db = FakeDB()
    c = db.cursor_obj
    c.procurements[1] = {"id": 1, "organization_id": 1, "status": "DELIVERY"}
    c.commitments[1001] = {
        "id": 1001, "purchase_order_id": 10, "purchase_order_line_id": 101,
        "supplier_id": 50, "promised_qty": Decimal("500"), "status": "ACCEPTED",
    }
    c.deliveries[3001] = {
        "id": 3001, "commitment_id": 1001, "delivery_sequence": 1,
        "delivery_date": date(2026, 9, 30), "condition": "Good", "notes": None,
        "receiving_user_id": 100, "delivery_status": "AWAITING_INSPECTION",
        "created_at": datetime.now(), "updated_at": datetime.now(), "parent_delivery_id": None,
    }
    c.delivery_lines.append({"id": 1, "delivery_id": 3001, "procurement_item_id": 201, "actual_quantity": Decimal("430")})
    payload = InspectionCreate(
        received_qty=Decimal("430"), result="ACCEPTED", quality_status="GOOD", delay_status="ON_TIME"
    )
    result = inspect_delivery(c, 3001, 100, payload)

    assert result["inspection"]["received_qty"] == Decimal("430")
    assert result["delivery"]["delivery_status"] == "ACCEPTED"
    assert c.inspections[4001]["result"] == "ACCEPTED"


def test_integration_inspection_rejects_received_quantity_above_delivery_without_persisting_inspection():
    db = FakeDB()
    c = db.cursor_obj
    c.procurements[1] = {"id": 1, "organization_id": 1, "status": "DELIVERY"}
    c.commitments[1001] = {
        "id": 1001, "purchase_order_id": 10, "purchase_order_line_id": 101,
        "supplier_id": 50, "promised_qty": Decimal("500"), "status": "ACCEPTED",
    }
    c.deliveries[3001] = {
        "id": 3001, "commitment_id": 1001, "delivery_sequence": 1,
        "delivery_date": date(2026, 9, 30), "condition": "Good", "notes": None,
        "receiving_user_id": 100, "delivery_status": "AWAITING_INSPECTION",
        "created_at": datetime.now(), "updated_at": datetime.now(), "parent_delivery_id": None,
    }
    c.delivery_lines.append({"id": 1, "delivery_id": 3001, "procurement_item_id": 201, "actual_quantity": Decimal("430")})
    payload = InspectionCreate(
        received_qty=Decimal("431"), result="ACCEPTED", quality_status="GOOD", delay_status="ON_TIME"
    )

    with pytest.raises(Exception) as exc:
        inspect_delivery(c, 3001, 100, payload)
    assert getattr(exc.value, "status_code", None) == 409
    assert c.inspections == {}
    assert c.deliveries[3001]["delivery_status"] == "AWAITING_INSPECTION"


def test_integration_transaction_rolls_back_partial_write_when_delivery_line_is_invalid():
    db = FakeDB()
    c = db.cursor_obj
    c.procurements[1] = {"id": 1, "organization_id": 1, "status": "COMMITTED"}
    c.commitments[1001] = {
        "id": 1001, "purchase_order_id": 10, "purchase_order_line_id": 101,
        "supplier_id": 50, "promised_qty": Decimal("500"), "status": "ACCEPTED",
    }
    payload = DeliveryCreate(
        commitment_id=1001,
        delivery_date=date(2026, 9, 30),
        condition="Good",
        lines=[
            DeliveryLineCreate(procurement_item_id=999, actual_quantity=Decimal("430"))
        ],
    )
    delivery_routes.get_db = db.get
    delivery_routes.write_transaction = fake_transaction

    with pytest.raises(Exception) as exc:
        delivery_routes.record_delivery(payload, school_user())
    assert getattr(exc.value, "status_code", None) == 400
    assert c.deliveries == {}
    assert c.delivery_lines == []
    assert db.connection.rollbacks == 1


def test_integration_evidence_service_validates_file_then_persists_metadata(tmp_path):
    from io import BytesIO
    from fastapi import UploadFile
    from starlette.datastructures import Headers
    from app.services.evidence_document_service import create_evidence_document

    db = FakeDB()
    c = db.cursor_obj
    c.procurements[1] = {"id": 1, "organization_id": 1, "status": "DRAFT"}

    # Add the SELECT used by evidence service through a tiny wrapper around
    # the same fake cursor rather than changing the production service.
    original_execute = c.execute
    def execute_with_evidence(sql, params=None):
        q = " ".join(sql.split()).upper()
        if q.startswith("SELECT P.ID, P.ORGANIZATION_ID, P.STATUS FROM PROCUREMENTS"):
            pid, uid = params
            p = c.procurements.get(pid)
            c.result = [{"id": pid, "organization_id": p["organization_id"], "status": p["status"]}] if p and c.memberships.get(uid, {}).get("organization_id") == p["organization_id"] else []
            return
        if q.startswith("SELECT ID FROM PROCUREMENT_EVENTS"):
            c.result = []
            return
        if q.startswith("INSERT INTO EVIDENCE_DOCUMENTS"):
            c.result = [{
                "id": 7001, "procurement_id": 1, "event_id": None,
                "document_type": "RFQ", "document_name": "rfq.pdf",
                "original_filename": "rfq.pdf", "mime_type": "application/pdf",
                "file_size": 8, "storage_reference": "procurements/1/evidence/fake.pdf",
                "visibility": "INTERNAL", "uploaded_by": 100, "uploaded_at": datetime.now(),
            }]
            return
        return original_execute(sql, params)
    c.execute = execute_with_evidence

    file = UploadFile(
        filename="rfq.pdf",
        file=BytesIO(b"%PDF-1.7"),
        headers=Headers({"content-type": "application/pdf"}),
    )
    row = create_evidence_document(c, Path(tmp_path), 1, 100, file, "RFQ", "INTERNAL")

    assert row["document_type"] == "RFQ"
    assert row["visibility"] == "INTERNAL"
    assert row["procurement_id"] == 1
    stored = list((Path(tmp_path) / "procurements" / "1" / "evidence").glob("*.pdf"))
    assert len(stored) == 1
    stored[0].unlink()


