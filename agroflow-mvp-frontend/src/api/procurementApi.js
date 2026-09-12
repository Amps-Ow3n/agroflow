import client from "./client";

export async function createProcurement(payload) {
  const { data } = await client.post("/procurements", payload);
  return data;
}
export async function getProcurements(status = "") {
  const { data } = await client.get("/procurements", {
    params: status ? { status } : undefined,
  });
  return data;
}
export async function getProcurement(id) {
  const { data } = await client.get(`/procurements/${id}`);
  return data;
}
export async function updateProcurement(id, payload) {
  const { data } = await client.put(`/procurements/${id}`, payload);
  return data;
}
export async function submitProcurement(id) {
  const { data } = await client.post(`/procurements/${id}/submit`);
  return data;
}
export async function cancelProcurement(id, reason) {
  const { data } = await client.post(`/procurements/${id}/cancel`, { reason });
  return data;
}
export async function transitionProcurement(id, status, reason = null) {
  const { data } = await client.post(`/procurements/${id}/transition`, {
    status,
    reason,
  });
  return data;
}
