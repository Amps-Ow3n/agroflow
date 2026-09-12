import client from "./client";

export async function getTimeline(id) {
  const { data } = await client.get(`/procurements/${id}/timeline`);
  return data.events || [];
}
export async function getAudit(id) {
  const { data } = await client.get(`/procurements/${id}/audit`);
  return data.events || [];
}
