import client from "./client";

export async function getSupplierCommitmentOrders() {
  const { data } = await client.get("/supplier/commitment-orders");
  return data;
}
export async function createCommitment(orderId, payload) {
  const { data } = await client.post(`/purchase-orders/${orderId}/commitment`, payload);
  return data;
}
export async function getSupplierCommitments() {
  const { data } = await client.get("/supplier/commitments");
  return data;
}
export async function getProcurementCommitment(id) {
  const { data } = await client.get(`/procurements/${id}/commitment`);
  return data;
}
export async function acceptCommitment(id) {
  const { data } = await client.post(`/commitments/${id}/accept`);
  return data;
}
export async function rejectCommitment(id, reason) {
  const { data } = await client.post(`/commitments/${id}/reject`, { reason });
  return data;
}
