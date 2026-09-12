import client from "./client";

export async function login(email, password) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);
  const response = await client.post("/login", body, { headers: { "Content-Type": "application/x-www-form-urlencoded" } });
  return response.data;
}

export async function register(payload) {
  const response = await client.post("/register", payload);
  return response.data;
}

export async function logout() {
  const response = await client.post("/logout");
  return response.data;
}

export async function getCurrentIdentity() {
  const response = await client.get("/identity/me");
  return response.data;
}
