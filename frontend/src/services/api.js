import { apiClient } from "./apiClient.js";

const LONG = { timeout: 0 };

export const authApi = {
  signup: (payload) => apiClient.post("/auth/signup", payload).then((r) => r.data),
  login: (payload) => apiClient.post("/auth/login", payload).then((r) => r.data),
  me: () => apiClient.get("/auth/me").then((r) => r.data),
};

export const videoApi = {
  list: () => apiClient.get("/videos").then((r) => r.data),
  get: (id) => apiClient.get(`/videos/${id}`).then((r) => r.data),
  remove: (id) => apiClient.delete(`/videos/${id}`),
  retryDetection: (id) => apiClient.post(`/videos/${id}/prepare`).then((r) => r.data),
  upload: (file, title, onProgress, signal) => {
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    return apiClient
      .post("/videos", form, {
        ...LONG,
        signal,
        onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
      })
      .then((r) => r.data);
  },
  analyses: (id) => apiClient.get(`/videos/${id}/analyses`).then((r) => r.data),
  startAnalysis: (id, payload) => apiClient.post(`/videos/${id}/analyses`, payload).then((r) => r.data),
};

export const analysisApi = {
  recent: () => apiClient.get("/analyses").then((r) => r.data),
  get: (id) => apiClient.get(`/analyses/${id}`).then((r) => r.data),
  remove: (id) => apiClient.delete(`/analyses/${id}`),
};

export const systemApi = {
  health: () => apiClient.get("/health").then((r) => r.data),
};
