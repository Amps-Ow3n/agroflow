import client from "./client";

export async function getMySupplier() {
  const { data } = await client.get("/suppliers/me");
  return data;
}
export async function getSupplier(id) {
  const { data } = await client.get(`/suppliers/${id}`);
  return data;
}
export async function addSupplierCapability(capability) {
  const { data } = await client.post("/suppliers/me/capabilities", { capability });
  return data;
}
export async function addSupplierProduct(product) {
  const { data } = await client.post("/suppliers/me/products", { product });
  return data;
}
export async function addSupplierContact(payload) {
  const { data } = await client.post("/suppliers/me/contacts", payload);
  return data;
}
export async function getSupplierEligibility(id) {
  const { data } = await client.get(`/suppliers/${id}/eligibility`);
  return data;
}
