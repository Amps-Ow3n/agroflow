import axios from "axios";

const client = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || "http://localhost:8000",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

function getCookie(name) {
  const prefix = `${name}=`;
  const found = document.cookie.split("; ").find((row) => row.startsWith(prefix));
  return found ? decodeURIComponent(found.substring(prefix.length)) : null;
}

client.interceptors.request.use((config) => {
  const csrf = getCookie("agroflow_csrf");
  if (csrf && !["get", "head", "options"].includes((config.method || "get").toLowerCase())) {
    config.headers["X-CSRF-Token"] = csrf;
  }
  return config;
});

export default client;
