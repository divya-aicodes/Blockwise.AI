import axios from "axios";
export const api = axios.create({ baseURL: "/api", timeout: 65000 });
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail))
      return detail
        .map((item: { msg?: string }) => item.msg || "Invalid input")
        .join("; ");
    if (!error.response)
      return "Backend unavailable. Check the connection and try again.";
    return `Request failed (${error.response.status}). Please try again.`;
  }
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}
