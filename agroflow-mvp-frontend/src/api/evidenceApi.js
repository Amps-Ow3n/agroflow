import client from "./client";

export async function uploadEvidence(procurementId, { file, documentType, visibility = "INTERNAL", eventId = null }) {
  const form = new FormData();
  form.append("document_type", documentType);
  form.append("visibility", visibility);
  if (eventId) form.append("event_id", String(eventId));
  form.append("file", file);
  const { data } = await client.post(`/evidence/${procurementId}/upload`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export function evidenceDownloadUrl(evidenceId) {
  const base = process.env.REACT_APP_API_BASE_URL || "http://localhost:8000";
  return `${base}/evidence/${evidenceId}/download`;
}
