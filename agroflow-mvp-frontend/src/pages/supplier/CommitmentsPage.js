import { useEffect, useState } from "react";
import { getSupplierCommitments, createCommitment, getSupplierCommitmentOrders } from "../../api/commitmentApi";
import { getApiError } from "../../utils/errors";
import { Page, Loading, Empty, Status, Alert } from "../../components/common/Page";

export default function CommitmentsPage() {
  const [orders, setOrders] = useState([]);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [ordersResponse, commitmentsResponse] = await Promise.all([
        getSupplierCommitmentOrders(),
        getSupplierCommitments(),
      ]);
      setOrders(ordersResponse.orders || ordersResponse || []);
      setData(commitmentsResponse.commitments || commitmentsResponse || []);
    } catch (err) {
      setError(getApiError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function commit(order) {
    const qty = window.prompt(
      `Promised quantity (ordered: ${order.quantity ?? "unknown"})`
    );
    if (!qty) return;

    const start = window.prompt("Delivery start (YYYY-MM-DD)");
    if (!start) return;

    const end = window.prompt("Delivery end (YYYY-MM-DD)", start);
    if (!end) return;

    setBusy(true);
    setError("");
    try {
      await createCommitment(order.purchase_order_id, {
        purchase_order_line_id: Number(order.purchase_order_line_id),
        promised_qty: Number(qty),
        delivery_start: start,
        delivery_end: end,
      });
      await load();
    } catch (err) {
      setError(getApiError(err, "Unable to submit commitment."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page
      title="Supplier commitments"
      subtitle="A commitment is a supplier promise, not proof of delivery."
    >
      {error && <Alert>{error}</Alert>}
      {loading ? (
        <Loading />
      ) : (
        <>
          <h5 className="mb-3">Orders eligible for commitment</h5>
          {orders.length > 0 ? (
            <div className="row g-3 mb-4">
              {orders.map((order) => (
                <div
                  className="col-lg-6"
                  key={`${order.purchase_order_id}-${order.purchase_order_line_id}`}
                >
                  <div className="card border-0 shadow-sm p-3">
                    <strong>{order.order_number}</strong>
                    <div>
                      {order.item_name || "Item"} · {order.quantity} {order.unit || ""}
                    </div>
                    <button
                      className="btn btn-dark btn-sm mt-3"
                      disabled={busy || order.has_active_commitment}
                      onClick={() => commit(order)}
                    >
                      {order.has_active_commitment ? "Already committed" : "Submit commitment"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <Empty>No eligible purchase orders.</Empty>
          )}

          <h5 className="mb-3">Existing commitments</h5>
          {data.length > 0 ? (
            data.map((commitment) => (
              <div className="card border-0 shadow-sm p-3 mb-2" key={commitment.id}>
                <div className="d-flex justify-content-between">
                  <strong>Commitment #{commitment.id}</strong>
                  <Status value={commitment.status} />
                </div>
                <div className="small text-muted">
                  Promised {commitment.promised_qty} · {commitment.delivery_start} → {commitment.delivery_end}
                </div>
              </div>
            ))
          ) : (
            <Empty>No commitments.</Empty>
          )}
        </>
      )}
    </Page>
  );
}
