import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { uploadEvidence } from "../../api/evidenceApi";
import { getApiError } from "../../utils/errors";
import { Page, Alert } from "../../components/common/Page";

const TYPES = [
  "RFQ", "QUOTATION", "SUPPLIER_RESPONSE", "EVALUATION", "PURCHASE_ORDER",
  "COMMITMENT", "DELIVERY_NOTE", "GRN", "INSPECTION_RECORD", "INVOICE", "APPROVAL",
];

export default function EvidenceUploadPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [documentType, setDocumentType] = useState("RFQ");
  const [visibility, setVisibility] = useState("INTERNAL");
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (!file) {
      setError("Choose a PDF, JPEG, or PNG file.");
      return;
    }
    setBusy(true);
    try {
      await uploadEvidence(id, { file, documentType, visibility });
      nav(`/school/procurements/${id}`);
    } catch (err) {
      setError(getApiError(err, "Unable to upload evidence."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page title="Upload evidence" subtitle="Attach evidence to this procurement so the record can show what happened.">
      <form onSubmit={submit} className="card border-0 shadow-sm p-4" encType="multipart/form-data">
        <div className="mb-3">
          <label className="form-label">Document type</label>
          <select className="form-select" value={documentType} onChange={(e) => setDocumentType(e.target.value)}>
            {TYPES.map((type) => <option key={type}>{type}</option>)}
          </select>
        </div>
        <div className="mb-3">
          <label className="form-label">Visibility</label>
          <select className="form-select" value={visibility} onChange={(e) => setVisibility(e.target.value)}>
            <option>INTERNAL</option>
            <option>SUPPLIER_VISIBLE</option>
          </select>
        </div>
        <div className="mb-3">
          <label className="form-label">Evidence file</label>
          <input className="form-control" type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setFile(e.target.files?.[0] || null)} required />
          <div className="form-text">Phase A accepts PDF, JPEG, and PNG files subject to the backend size and content validation rules.</div>
        </div>
        {error && <Alert>{error}</Alert>}
        <button className="btn btn-dark" disabled={busy}>{busy ? "Uploading…" : "Upload evidence"}</button>
      </form>
    </Page>
  );
}
