import client from "./client";

export async function createPurchaseOrder(procurementId, payload) {
  const { data } = await client.post(`/purchase-orders/procurements/${procurementId}`, payload);
  return data;
}
export async function getPurchaseOrder(procurementId) {
  const { data } = await client.get(`/purchase-orders/procurements/${procurementId}`);
  return data;
}
