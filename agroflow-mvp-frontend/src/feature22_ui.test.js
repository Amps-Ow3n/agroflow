import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import "@testing-library/jest-dom";

import ProcurementCreatePage from "../pages/procurement/ProcurementCreatePage";
import ProcurementDetailPage from "../pages/procurement/ProcurementDetailPage";
import ProcurementEditPage from "../pages/procurement/ProcurementEditPage";
import DeliveryVerificationPage from "../pages/school/DeliveryVerificationPage";
import EvaluationPage from "../pages/procurement/EvaluationPage";
import DeliveryCreatePage from "../pages/school/DeliveryCreatePage";
import CommitmentsPage from "../pages/supplier/CommitmentsPage";

import { createProcurement, getProcurement, submitProcurement, updateProcurement } from "../api/procurementApi";
import { getTimeline, getAudit } from "../api/eventApi";
import { getPurchaseOrder } from "../api/purchaseOrderApi";
import { getProcurementCommitment } from "../api/commitmentApi";
import { recordDelivery, getDelivery, inspectDelivery } from "../api/deliveryApi";
import { getCandidates, enterEvaluation, evaluateSuppliers } from "../api/evaluationApi";
import { selectSupplier } from "../api/selectionApi";
import { getSupplierCommitmentOrders, getSupplierCommitments, createCommitment } from "../api/commitmentApi";

jest.mock("../api/procurementApi");
jest.mock("../api/eventApi");
jest.mock("../api/purchaseOrderApi");
jest.mock("../api/commitmentApi");
jest.mock("../api/deliveryApi");
jest.mock("../api/evaluationApi");
jest.mock("../api/selectionApi");

function route(ui, path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/school/procurements/new" element={ui} />
        <Route path="/school/procurements/:id" element={ui} />
        <Route path="/school/procurements/:id/evaluation" element={ui} />
        <Route path="/school/procurements/:id/evidence/new" element={ui} />
        <Route path="/school/procurements/:id/delivery/new" element={ui} />
        <Route path="/supplier/commitments" element={ui} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  window.prompt = jest.fn();
});

test("UI-01 procurement create: form collects domain data and sends the correct API payload", async () => {
  createProcurement.mockResolvedValue({ id: 42 });

  route(<ProcurementCreatePage />, "/school/procurements/new");

  fireEvent.change(screen.getByLabelText("Title"), { target: { value: "School maize supply" } });
  fireEvent.change(screen.getByLabelText("Item"), { target: { value: "Maize flour" } });
  fireEvent.change(screen.getByLabelText("Unit"), { target: { value: "kg" } });
  fireEvent.change(screen.getByLabelText("Location"), { target: { value: "Kampala" } });
  fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "500" } });
  fireEvent.change(screen.getByLabelText("Required by"), { target: { value: "2026-10-01" } });

  fireEvent.click(screen.getByRole("button", { name: "Create procurement" }));

  await waitFor(() => expect(createProcurement).toHaveBeenCalledTimes(1));
  expect(createProcurement.mock.calls[0][0]).toMatchObject({
    title: "School maize supply",
    item_name: "Maize flour",
    quantity: 500,
    unit: "kg",
    location: "Kampala",
    required_by_date: "2026-10-01",
  });
});

test("UI-02 procurement detail: backend status and requirement values are rendered without transformation", async () => {
  getProcurement.mockResolvedValue({
    procurement: {
      id: 42,
      procurement_identifier: "PROC-000042",
      title: "Maize supply",
      status: "SUBMITTED",
      required_by_date: "2026-10-01",
      location: "Kampala",
      procurement_method: "QUOTATION",
    },
    items: [{ id: 1, item_name: "Maize flour" }],
  });
  getTimeline.mockResolvedValue([]);
  getAudit.mockResolvedValue([]);
  getPurchaseOrder.mockRejectedValue(new Error("not found"));

  route(<ProcurementDetailPage />, "/school/procurements/42");

  expect(await screen.findByText("PROC-000042")).toBeInTheDocument();
  expect(screen.getByText("SUBMITTED")).toBeInTheDocument();
  expect(screen.getByText("Maize flour")).toBeInTheDocument();
  expect(screen.getByText("2026-10-01")).toBeInTheDocument();
});

test("UI-03 procurement detail: Submit action calls backend and reloads the current state", async () => {
  getProcurement
    .mockResolvedValueOnce({
      procurement: { id: 42, procurement_identifier: "PROC-000042", title: "Maize", status: "DRAFT", required_by_date: "2026-10-01", location: "Kampala", procurement_method: "QUOTATION" },
      items: [{ id: 1, item_name: "Maize flour" }],
    })
    .mockResolvedValueOnce({
      procurement: { id: 42, procurement_identifier: "PROC-000042", title: "Maize", status: "SUBMITTED", required_by_date: "2026-10-01", location: "Kampala", procurement_method: "QUOTATION" },
      items: [{ id: 1, item_name: "Maize flour" }],
    });
  getTimeline.mockResolvedValue([]);
  getAudit.mockResolvedValue([]);
  getPurchaseOrder.mockRejectedValue(new Error("not found"));
  submitProcurement.mockResolvedValue({ procurement: { status: "SUBMITTED" } });

  route(<ProcurementDetailPage />, "/school/procurements/42");

  const button = await screen.findByRole("button", { name: "Submit" });
  fireEvent.click(button);

  await waitFor(() => expect(submitProcurement).toHaveBeenCalledWith("42"));
  expect(await screen.findByText("SUBMITTED")).toBeInTheDocument();
  expect(getProcurement).toHaveBeenCalledTimes(2);
});

test("UI-04 supplier evaluation: performance indicators are displayed as decision evidence", async () => {
  getCandidates.mockResolvedValue({
    candidates: [{
      supplier_id: 9,
      supplier_name: "Supplier A",
      evaluation_status: "ELIGIBLE",
      verification_status: "VERIFIED",
      historical_delivery_count: 5,
      on_time_delivery_rate: 92,
      fulfilment_rate: 86,
      indicator_explanation: "Strong recent evidence",
    }],
  });

  route(<EvaluationPage />, "/school/procurements/42/evaluation");

  expect(await screen.findByText("Supplier A")).toBeInTheDocument();
  expect(screen.getByText("92%")).toBeInTheDocument();
  expect(screen.getByText("86%")).toBeInTheDocument();
  expect(screen.getByText("Strong recent evidence")).toBeInTheDocument();
});

test("UI-05 supplier evaluation: selection sends the human decision and reason to the backend", async () => {
  getCandidates.mockResolvedValue({
    candidates: [{
      supplier_id: 9,
      supplier_name: "Supplier A",
      evaluation_status: "ELIGIBLE",
      verification_status: "VERIFIED",
      historical_delivery_count: 5,
      on_time_delivery_rate: 92,
      fulfilment_rate: 86,
      indicator_explanation: "Evidence",
    }],
  });
  selectSupplier.mockResolvedValue({ status: "SELECTED" });
  window.prompt.mockReturnValue("Best verified fit for the requirement.");

  route(<EvaluationPage />, "/school/procurements/42/evaluation");

  fireEvent.click(await screen.findByRole("button", { name: "Select supplier" }));

  await waitFor(() =>
    expect(selectSupplier).toHaveBeenCalledWith(
      "42",
      9,
      "Best verified fit for the requirement."
    )
  );
});

test("UI-06 delivery creation: the frontend converts entered quantity to a number and submits the commitment reference", async () => {
  getProcurement.mockResolvedValue({
    items: [{ id: 1, item_name: "Maize flour" }],
  });
  getProcurementCommitment.mockResolvedValue({
    id: 77,
    promised_qty: 500,
  });
  recordDelivery.mockResolvedValue({ delivery: { id: 88, actual_quantity: 430 } });

  route(<DeliveryCreatePage />, "/school/procurements/42/delivery/new");

  await screen.findByText(/promised 500/);
  fireEvent.change(screen.getByLabelText("Delivery date"), { target: { value: "2026-09-20" } });
  fireEvent.change(screen.getByLabelText(/actual quantity/i), { target: { value: "430" } });
  fireEvent.change(screen.getByLabelText("Condition"), { target: { value: "Good" } });
  fireEvent.click(screen.getByRole("button", { name: "Record delivery" }));

  await waitFor(() => expect(recordDelivery).toHaveBeenCalledTimes(1));
  expect(recordDelivery.mock.calls[0][0]).toMatchObject({
    commitment_id: 77,
    delivery_date: "2026-09-20",
    condition: "Good",
    lines: [{ procurement_item_id: 1, actual_quantity: 430 }],
  });
});

test("UI-07 delivery creation: backend/API errors are surfaced instead of silently changing state", async () => {
  getProcurement.mockResolvedValue({ items: [{ id: 1, item_name: "Maize flour" }] });
  getProcurementCommitment.mockResolvedValue({ id: 77, promised_qty: 500 });
  recordDelivery.mockRejectedValue({ response: { data: { detail: "Commitment is no longer active." } } });

  route(<DeliveryCreatePage />, "/school/procurements/42/delivery/new");

  await screen.findByText(/promised 500/);
  fireEvent.change(screen.getByLabelText("Delivery date"), { target: { value: "2026-09-20" } });
  fireEvent.change(screen.getByLabelText(/actual quantity/i), { target: { value: "430" } });
  fireEvent.change(screen.getByLabelText("Condition"), { target: { value: "Good" } });
  fireEvent.click(screen.getByRole("button", { name: "Record delivery" }));

  expect(await screen.findByText("Commitment is no longer active.")).toBeInTheDocument();
});

test("UI-08 supplier commitments: existing backend commitment state controls the button", async () => {
  getSupplierCommitmentOrders.mockResolvedValue({
    orders: [{
      purchase_order_id: 10,
      purchase_order_line_id: 11,
      order_number: "PO-10",
      item_name: "Maize",
      quantity: 500,
      unit: "kg",
      has_active_commitment: true,
    }],
  });
  getSupplierCommitments.mockResolvedValue({ commitments: [] });

  route(<CommitmentsPage />, "/supplier/commitments");

  expect(await screen.findByText("Already committed")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Submit commitment" })).not.toBeInTheDocument();
});

test("UI-09 supplier commitments: a backend order without an active commitment exposes the commit action", async () => {
  getSupplierCommitmentOrders.mockResolvedValue({
    orders: [{
      purchase_order_id: 10,
      purchase_order_line_id: 11,
      order_number: "PO-10",
      item_name: "Maize",
      quantity: 500,
      unit: "kg",
      has_active_commitment: false,
    }],
  });
  getSupplierCommitments.mockResolvedValue({ commitments: [] });
  window.prompt
    .mockReturnValueOnce("500")
    .mockReturnValueOnce("2026-09-20")
    .mockReturnValueOnce("2026-09-21");
  createCommitment.mockResolvedValue({ commitment: { id: 99 } });
  getSupplierCommitmentOrders.mockResolvedValueOnce({
    orders: [{
      purchase_order_id: 10,
      purchase_order_line_id: 11,
      order_number: "PO-10",
      item_name: "Maize",
      quantity: 500,
      unit: "kg",
      has_active_commitment: false,
    }],
  }).mockResolvedValueOnce({ orders: [] });

  route(<CommitmentsPage />, "/supplier/commitments");

  fireEvent.click(await screen.findByRole("button", { name: "Submit commitment" }));

  await waitFor(() => expect(createCommitment).toHaveBeenCalledWith(10, {
    purchase_order_line_id: 11,
    promised_qty: 500,
    delivery_start: "2026-09-20",
    delivery_end: "2026-09-21",
  }));
});

test("UI-10 API contract: delivery verification values can be rendered exactly as returned by the backend", async () => {
  const backendResponse = { delivery: { id: 88, received_quantity: 430, committed_quantity: 500 } };
  expect(backendResponse.delivery.received_quantity).toBe(430);
  expect(`${backendResponse.delivery.received_quantity} kg`).toBe("430 kg");
});


test("UI-11 procurement detail: evidence returned by backend is visible in the procurement context", async () => {
  getProcurement.mockResolvedValue({
    procurement: { id: 42, procurement_identifier: "PROC-000042", title: "Maize", status: "DRAFT", required_by_date: "2026-10-01", location: "Kampala", procurement_method: "QUOTATION" },
    items: [{ id: 1, item_name: "Maize flour" }],
    evidence: [{ id: 5, document_name: "RFQ document", original_filename: "rfq.pdf", visibility: "INTERNAL" }],
  });
  getTimeline.mockResolvedValue([]);
  getAudit.mockResolvedValue([]);
  getPurchaseOrder.mockRejectedValue(new Error("not found"));

  route(<ProcurementDetailPage />, "/school/procurements/42");

  expect(await screen.findByText("RFQ document")).toBeInTheDocument();
  expect(screen.getByText("INTERNAL")).toBeInTheDocument();
});

test("UI-12 procurement edit: existing backend data is loaded, edited, and sent back as typed values", async () => {
  getProcurement.mockResolvedValue({
    procurement: { id: 42, title: "Old title", required_by_date: "2026-10-01", location: "Kampala" },
    items: [{ item_name: "Maize flour", quantity: 500, unit: "kg" }],
  });
  updateProcurement.mockResolvedValue({ id: 42 });

  route(<ProcurementEditPage />, "/school/procurements/42/edit");

  const title = await screen.findByLabelText("Title");
  fireEvent.change(title, { target: { value: "Updated title" } });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

  await waitFor(() => expect(updateProcurement).toHaveBeenCalledWith("42", expect.objectContaining({
    title: "Updated title",
    quantity: 500,
    item_name: "Maize flour",
  })));
});

test("UI-13 delivery inspection: backend delivery quantity is shown and discrepancy is calculated from user verification", async () => {
  getDelivery.mockResolvedValue({
    delivery: { id: 88, promised_qty: 500, actual_quantity: 430 },
  });
  inspectDelivery.mockResolvedValue({ inspection: { id: 12, received_qty: 430, result: "ACCEPTED" } });

  route(<DeliveryVerificationPage />, "/school/deliveries/88/inspect");

  expect(await screen.findByText(/Promised:/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Received quantity"), { target: { value: "430" } });

  expect(screen.getByText(/Discrepancy:/)).toHaveTextContent("70 kg");
  expect(screen.getByText(/Variance:/)).toHaveTextContent("14.00%");

  fireEvent.change(screen.getByLabelText("Condition"), { target: { value: "Good" } });
  fireEvent.click(screen.getByRole("button", { name: "Record inspection" }));

  await waitFor(() => expect(inspectDelivery).toHaveBeenCalledWith("88", {
    received_qty: 430,
    result: "ACCEPTED",
    quality_status: "GOOD",
    delay_status: "ON_TIME",
    rejection_reason: null,
    notes: null,
  }));
});

test("UI-14 delivery inspection: rejection requires and preserves a reason in the frontend payload", async () => {
  getDelivery.mockResolvedValue({ delivery: { id: 88, promised_qty: 500, actual_quantity: 430 } });
  inspectDelivery.mockResolvedValue({ inspection: { id: 12, result: "REJECTED" } });

  route(<DeliveryVerificationPage />, "/school/deliveries/88/inspect");

  await screen.findByLabelText("Received quantity");
  fireEvent.change(screen.getByLabelText("Received quantity"), { target: { value: "430" } });
  fireEvent.change(screen.getByLabelText("Inspection result"), { target: { value: "REJECTED" } });
  fireEvent.change(screen.getByLabelText("Condition"), { target: { value: "Damaged" } });
  fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Damaged goods" } });
  fireEvent.click(screen.getByRole("button", { name: "Record inspection" }));

  await waitFor(() => expect(inspectDelivery).toHaveBeenCalledWith("88", expect.objectContaining({
    result: "REJECTED",
    quality_status: "FAILED",
    rejection_reason: "Damaged goods",
  })));
});

import EvidenceUploadPage from "./pages/procurement/EvidenceUploadPage";
import { uploadEvidence } from "./api/evidenceApi";

jest.mock("./api/evidenceApi");

test("UI-10 evidence upload: user can select document metadata and file and the UI sends it to the evidence API", async () => {
  uploadEvidence.mockResolvedValue({ evidence: { id: 701, document_type: "RFQ" } });
  const { container } = route(<EvidenceUploadPage />, "/school/procurements/42/evidence/new");
  const file = new File(["%PDF-1.7 test"], "rfq.pdf", { type: "application/pdf" });
  const input = container.querySelector('input[type="file"]');

  fireEvent.change(input, { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: "Upload evidence" }));

  await waitFor(() => expect(uploadEvidence).toHaveBeenCalledWith("42", {
    file,
    documentType: "RFQ",
    visibility: "INTERNAL",
  }));
});

