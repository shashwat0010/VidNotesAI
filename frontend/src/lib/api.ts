const BASE_URL = typeof window !== "undefined" 
  ? (window.location.origin.includes("localhost:3000") ? "http://localhost:8000/api/v1" : "/api/v1")
  : "http://backend:8000/api/v1";

class ApiClient {
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
    const response = await fetch(`${BASE_URL}${path}`, {
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
    const response = await fetch(`${BASE_URL}${path}`, {
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
    const response = await fetch(`${BASE_URL}${path}`, {
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
    const response = await fetch(`${BASE_URL}${path}`, {
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
    const response = await fetch(`${BASE_URL}${path}`, {
      method: "DELETE",
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(errData.detail || "Request failed");
    }
    return response.json() as Promise<T>;
  }
}

export const api = new ApiClient();
export { BASE_URL };
