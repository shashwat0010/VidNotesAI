const getApiBaseUrl = (): string => {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "");
  }
  if (typeof window !== "undefined") {
    // If running directly on a browser port like 3000, 3001, etc.
    const { hostname, port, protocol } = window.location;
    // Production under reverse proxy (port 80, 443 or empty port)
    if (port === "" || port === "80" || port === "443") {
      return "/api/v1";
    }
    // Local dev: point directly to FastAPI backend on port 8000
    return `${protocol}//${hostname}:8000/api/v1`;
  }
  return "http://localhost:8000/api/v1";
};

export const BASE_URL = getApiBaseUrl();

class ApiClient {
  private getBaseUrl(): string {
    return getApiBaseUrl();
  }

  private getHeaders(isMultipart = false): HeadersInit {
    const headers: Record<string, string> = {};
    if (!isMultipart) {
      headers["Content-Type"] = "application/json";
    }
    
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("vidnotes_token");
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }
    return headers;
  }

  async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.getBaseUrl()}${path}`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(errData.detail || "Request failed");
    }
    return response.json();
  }

  async post<T>(path: string, body: any): Promise<T> {
    const response = await fetch(`${this.getBaseUrl()}${path}`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(errData.detail || "Request failed");
    }
    return response.json();
  }

  async postForm<T>(path: string, formData: FormData): Promise<T> {
    const response = await fetch(`${this.getBaseUrl()}${path}`, {
      method: "POST",
      headers: this.getHeaders(true),
      body: formData,
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(errData.detail || "Request failed");
    }
    return response.json();
  }

  async put<T>(path: string, body: any): Promise<T> {
    const response = await fetch(`${this.getBaseUrl()}${path}`, {
      method: "PUT",
      headers: this.getHeaders(),
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(errData.detail || "Request failed");
    }
    return response.json();
  }

  async delete<T>(path: string): Promise<T> {
    const response = await fetch(`${this.getBaseUrl()}${path}`, {
      method: "DELETE",
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(errData.detail || "Request failed");
    }
    if (response.status === 204) {
      return {} as T;
    }
    return response.json().catch(() => ({})) as Promise<T>;
  }

  async downloadBlob(path: string): Promise<Blob> {
    const response = await fetch(`${this.getBaseUrl()}${path}`, {
      method: "GET",
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Download failed" }));
      throw new Error(errData.detail || "Download failed");
    }
    return response.blob();
  }
}

export const api = new ApiClient();
