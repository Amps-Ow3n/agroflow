import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getDelivery, inspectDelivery } from "../../api/deliveryApi";
import { getApiError } from "../../utils/errors";
import { Page, Loading, Alert } from "../../components/common/Page";

export default function DeliveryVerificationPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [delivery, setDelivery] = useState(null);
  const [received, setReceived] = useState("");
  const [result, setResult] = useState("ACCEPTED");
  const [condition, setCondition] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getDelivery(id).then((r) => setDelivery(r.delivery || r))
      .catch((e) => setError(getApiError(e)));
  }, [id]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await inspectDelivery(id, {
        received_qty: Number(received),
        result,
        quality_status: result === "ACCEPTED" ? "GOOD" : "FAILED",
        delay_status: "ON_TIME",
        rejection_reason: result === "REJECTED" ? (reason || null) : null,
        notes: reason || null,
      });
      nav(-1);
    } catch (e) {
      setError(getApiError(e, "Unable to inspect delivery."));
    } finally {
      setBusy(false);
    }
  }

  if (!delivery) return <Page title="Inspect delivery">{error ? <Alert>{error}</Alert> : <Loading />}</Page>;

  const promised = Number(delivery.promised_quantity ?? delivery.promised_qty ?? 0);
  const actual = Number(delivery.actual_quantity ?? delivery.received_quantity ?? 0);
  const receivedNumber = received === "" ? null : Number(received);
  const shortfall = receivedNumber == null ? Math.max(promised - actual, 0) : Math.max(promised - receivedNumber, 0);
  const variance = promised > 0 && receivedNumber != null ? (shortfall / promised) * 100 : null;

  return (
    <Page title="Inspect delivery" subtitle="The receiving side records what was actually received and decides whether the delivery is acceptable.">
      <div className="card border-0 shadow-sm p-4">
        {error && <Alert>{error}</Alert>}
        <div className="alert alert-info">
          Promised: <strong>{promised} kg</strong> · Recorded delivery: <strong>{actual} kg</strong>
          {receivedNumber != null && <> · Received: <strong>{receivedNumber} kg</strong></>}
        </div>
        {receivedNumber != null && <div className="alert alert-warning">
          Discrepancy: <strong>{shortfall} kg</strong>{variance != null && <> · Variance: <strong>{variance.toFixed(2)}%</strong></>}
        </div>}
        <form onSubmit={submit}>
          <label className="form-label">Received quantity</label>
          <input className="form-control mb-3" type="number" min="0" step="0.01" value={received} onChange={(e) => setReceived(e.target.value)} required />
          <label className="form-label">Inspection result</label>
          <select className="form-select mb-3" value={result} onChange={(e) => setResult(e.target.value)}>
            <option>ACCEPTED</option>
            <option>REJECTED</option>
          </select>
          <label className="form-label">Condition</label>
          <textarea className="form-control mb-3" value={condition} onChange={(e) => setCondition(e.target.value)} required />
          <label className="form-label">Reason</label>
          <textarea className="form-control" value={reason} onChange={(e) => setReason(e.target.value)} />
          <button className="btn btn-dark mt-3" disabled={busy}>{busy ? "Saving…" : "Record inspection"}</button>
        </form>
      </div>
    </Page>
  );
}
