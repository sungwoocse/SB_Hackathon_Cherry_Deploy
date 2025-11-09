const sanitize = (value?: string | null): string | undefined => {
  if (!value) return undefined;
  return value.replace(/\/+$/, "");
};

const DEFAULT_BASE_URL =
  process.env.NODE_ENV === "development"
    ? "http://127.0.0.1:9001"
    : "https://delight.13-125-116-92.nip.io";

export const API_BASE_URL = sanitize(process.env.NEXT_PUBLIC_API_BASE_URL) || DEFAULT_BASE_URL;

export const JSON_HEADERS = { "Content-Type": "application/json" };

export const withBaseUrl = (path: string): string => {
  if (path.startsWith("http")) return path;
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
};
