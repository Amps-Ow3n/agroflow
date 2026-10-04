import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getProcurement, updateProcurement } from "../../api/procurementApi";
import { getApiError } from "../../utils/errors";
import { Page, Loading, Alert } from "../../components/common/Page";

export default function ProcurementEditPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getProcurement(id).then((r) => {
      const p = r.procurement || r;
      const item = (r.items || [])[0] || {};
      setForm({
        title: p.title || "",
        description: p.description || "",
        required_by_date: p.required_by_date || "",
        location: p.location || "",
        item_name: item.item_name || p.item_name || "",
        quantity: item.quantity ?? p.quantity ?? "",
        unit: item.unit || p.unit || "kg",
      });
    }).catch((e) => setError(getApiError(e)));
  }, [id]);

  function set(k, v) { setForm((x) => ({ ...x, [k]: v })); }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await updateProcurement(id, {
        title: form.title,
        description: form.description || null,
        required_by_date: form.required_by_date,
        location: form.location,
        item_name: form.item_name,
        quantity: Number(form.quantity),
        unit: form.unit,
      });
      nav(`/school/procurements/${id}`);
    } catch (e) {
      setError(getApiError(e, "Unable to update procurement."));
    } finally {
      setBusy(false);
    }
  }

  if (!form) return <Page title="Edit procurement">{error ? <Alert>{error}</Alert> : <Loading />}</Page>;

  return (
    <Page title="Edit procurement" subtitle="Update the requirement before it reaches a state where editing is no longer allowed.">
      <form onSubmit={submit} className="card border-0 shadow-sm p-4">
        {error && <Alert>{error}</Alert>}
        <label className="form-label">Title</label>
        <input className="form-control mb-3" value={form.title} onChange={(e) => set("title", e.target.value)} required />
        <label className="form-label">Item</label>
        <input className="form-control mb-3" value={form.item_name} onChange={(e) => set("item_name", e.target.value)} required />
        <label className="form-label">Quantity</label>
        <input className="form-control mb-3" type="number" min="0.01" step="0.01" value={form.quantity} onChange={(e) => set("quantity", e.target.value)} required />
        <label className="form-label">Unit</label>
        <input className="form-control mb-3" value={form.unit} onChange={(e) => set("unit", e.target.value)} required />
        <label className="form-label">Required by</label>
        <input className="form-control mb-3" type="date" value={form.required_by_date} onChange={(e) => set("required_by_date", e.target.value)} required />
        <label className="form-label">Location</label>
        <input className="form-control mb-3" value={form.location} onChange={(e) => set("location", e.target.value)} required />
        <label className="form-label">Description</label>
        <textarea className="form-control" value={form.description} onChange={(e) => set("description", e.target.value)} />
        {error && <Alert>{error}</Alert>}
        <button className="btn btn-dark mt-4" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
      </form>
    </Page>
  );
}
