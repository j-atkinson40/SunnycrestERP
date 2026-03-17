/**
 * Axios client for platform admin API endpoints (/api/platform/).
 *
 * Uses platform_access_token / platform_refresh_token stored separately
 * from tenant tokens.  No X-Company-Slug header is sent.
 */

import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const platformClient = axios.create({
  baseURL: `${API_BASE_URL}/api/platform`,
  headers: { "Content-Type": "application/json" },
});

// Attach platform access token
platformClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("platform_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 with platform refresh token
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null) => {
  failedQueue.forEach((prom) => {
    if (token) prom.resolve(token);
    else prom.reject(error);
  });
  failedQueue = [];
};

// Auth endpoints that should never trigger token refresh or redirect
const AUTH_PATHS = ["/auth/login", "/auth/refresh"];

platformClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const requestUrl: string = originalRequest?.url || "";

    // Never intercept auth endpoint errors — let them bubble to callers
    if (AUTH_PATHS.some((p) => requestUrl.includes(p))) {
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return platformClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = localStorage.getItem("platform_refresh_token");
        if (!refreshToken) throw new Error("No platform refresh token");

        const { data } = await axios.post(
          `${API_BASE_URL}/api/platform/auth/refresh`,
          { refresh_token: refreshToken }
        );
        localStorage.setItem("platform_access_token", data.access_token);
        localStorage.setItem("platform_refresh_token", data.refresh_token);
        processQueue(null, data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return platformClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem("platform_access_token");
        localStorage.removeItem("platform_refresh_token");
        // Only redirect if not already on the login page
        if (!window.location.pathname.endsWith("/login")) {
          window.location.href = "/login";
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export default platformClient;
