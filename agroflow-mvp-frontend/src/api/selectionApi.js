import client from "./client";

export async function selectSupplier(procurementId, supplierId, decisionReason) {
  const { data } = await client.post(`/procurements/${procurementId}/selection`, {
    supplier_id: supplierId,
    decision_reason: decisionReason,
  });
  return data;
}
export async function reselectSupplier(procurementId, supplierId, decisionReason) {
  const { data } = await client.post(`/procurements/${procurementId}/reselection`, {
    supplier_id: supplierId,
    decision_reason: decisionReason,
  });
  return data;
}
export async function getSelectionHistory(id) {
  const { data } = await client.get(`/procurements/${id}/selection-history`);
  return data;
}
