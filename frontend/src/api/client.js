const DEFAULT_BASE_URL = "http://localhost:8000";

export function getSettings() {
  return {
    baseUrl: localStorage.getItem("taskpilot:baseUrl") || DEFAULT_BASE_URL,
    apiKey: localStorage.getItem("taskpilot:apiKey") || "",
  };
}

export function saveSettings({ baseUrl, apiKey }) {
  localStorage.setItem("taskpilot:baseUrl", baseUrl);
  localStorage.setItem("taskpilot:apiKey", apiKey);
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  const { baseUrl, apiKey } = getSettings();
  const res = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore parse errors on empty/non-JSON bodies */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  health: () => request("/api/health"),
  stats: () => request("/api/dashboard/stats"),
  runs: (status) => request(`/api/agent/runs${status ? `?status=${status}` : ""}`),
  runDetail: (id) => request(`/api/agent/runs/${id}`),
  poll: () => request("/api/agent/poll", { method: "POST" }),
  approvals: () => request("/api/approvals"),
  approve: (id, reason) =>
    request(`/api/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ reason: reason || null }) }),
  reject: (id, reason) =>
    request(`/api/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ reason: reason || null }) }),
  gmailStatus: () => request("/api/auth/gmail/status"),
};

export { ApiError };
