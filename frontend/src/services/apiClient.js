import axios from "axios";

import { cleanText } from "../utils/format.js";

const API_ORIGIN = import.meta.env.VITE_API_ORIGIN || "";
const TOKEN_KEY = "football-ai-analyst.token";

export const apiClient = axios.create({ baseURL: `${API_ORIGIN}/api/v1`, timeout: 30000 });

export const tokenStore = {
  get: () => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token) => {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* storage blocked: the session lasts until reload */
    }
  },
  clear: () => {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

apiClient.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let onUnauthorized = () => {};
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const isAuthCall = /\/auth\/(login|signup)$/.test(error.config?.url ?? "");
    if (error.response?.status === 401 && tokenStore.get() && !isAuthCall) onUnauthorized();
    return Promise.reject(error);
  }
);

export function assetUrl(path) {
  return path ? `${API_ORIGIN}${path}` : null;
}

export function errorStatus(error) {
  return error?.response?.status ?? null;
}

export function isNotFound(error) {
  return errorStatus(error) === 404;
}

export function isCancelled(error) {
  return axios.isCancel(error) || error?.code === "ERR_CANCELED";
}

/** True when the backend could not be reached at all (down, restarting, offline, proxy error). */
export function isOffline(error) {
  if (!error) return false;
  if (error.code === "ERR_NETWORK" || error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") return true;
  const status = errorStatus(error);
  return [502, 503, 504].includes(status) || (status === 500 && typeof error.response?.data?.detail !== "string");
}

export function errorMessage(error, fallback = "Something went wrong. Please try again.") {
  if (!error) return fallback;
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = String(d?.loc?.at?.(-1) ?? "").replace(/_/g, " ");
        const message = String(d?.ctx?.reason ?? d?.msg ?? "is invalid").replace(/^(Value error, |String )/, "");
        return field && field !== "body" ? `${field[0].toUpperCase()}${field.slice(1)}: ${message}` : message;
      })
      .join(" · ");
  }
  if (typeof detail === "string" && detail) return cleanText(detail);
  if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") return "The ScoutAI server took too long to respond. Please try again.";
  if (isOffline(error)) return "Can't reach the ScoutAI server right now. Check your connection and try again in a moment.";
  const status = errorStatus(error);
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You don't have access to this item.";
  if (status === 404) return "This item no longer exists.";
  if (status === 413) return "The file is too large for the server to accept.";
  if (status >= 500) return "The ScoutAI server hit an unexpected problem. Please try again.";
  return fallback;
}
