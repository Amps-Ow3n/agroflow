import client from "./client";

export async function getSupplierPerformance(id) {
  const { data } = await client.get(`/suppliers/${id}/performance`);
  return data;
}
export async function getMySupplierPerformance() {
  const { data } = await client.get("/suppliers/me/performance");
  return data;
}
