import client from "./client";

export async function enterEvaluation(id) {
  const { data } = await client.post(`/procurements/${id}/enter-evaluation`);
  return data;
}
export async function evaluateSuppliers(id) {
  const { data } = await client.post(`/procurements/${id}/supplier-evaluation`);
  return data;
}
export async function getCandidates(id) {
  const { data } = await client.get(`/procurements/${id}/supplier-candidates`);
  return data;
}
