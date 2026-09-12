import client from "./client";

export async function recordDelivery(payload) {
  const { data } = await client.post("/deliveries/", payload);
  return data;
}
export async function getDelivery(id) {
  const { data } = await client.get(`/deliveries/${id}`);
  return data;
}
export async function getProcurementDeliveries(id) {
  const { data } = await client.get(`/deliveries/procurement/${id}`);
  return data;
}
export async function inspectDelivery(id, payload) {
  const { data } = await client.post(`/deliveries/${id}/inspect`, payload);
  return data;
}
export async function createCorrectiveAction(inspectionId, payload) {
  const { data } = await client.post(`/deliveries/${inspectionId}/corrective-action`, payload);
  return data;
}
export async function getDeliveryHistory(id) {
  const { data } = await client.get(`/deliveries/${id}/history`);
  return data;
}
export async function getProcurementInspectionHistory(id) {
  const { data } = await client.get(`/deliveries/procurement/${id}/inspection-history`);
  return data;
}
