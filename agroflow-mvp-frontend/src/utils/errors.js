export function getApiError(error, fallback = "Something went wrong.") {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message).join(", ");
  }
  if (typeof detail === "string") return detail;
  const message = error?.response?.data?.error?.message;
  if (message) return message;
  return error?.message || fallback;
}
