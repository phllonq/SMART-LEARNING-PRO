const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiClientError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.data = data;
  }
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("smart_learning_session_token");
}

export function setAuthToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) {
    sessionStorage.setItem("smart_learning_session_token", token);
  } else {
    sessionStorage.removeItem("smart_learning_session_token");
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
}

function buildApiUrl(endpoint: string): string {
  const base = API_BASE_URL.replace(/\/+$/, "");
  let path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  if (base.endsWith("/api/v1") && path.startsWith("/api/v1/")) {
    path = path.slice("/api/v1".length);
  }
  return `${base}${path}`;
}

async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, headers, ...restOptions } = options;

  let url = buildApiUrl(endpoint);

  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes("?") ? "&" : "?") + queryString;
    }
  }

  const token = getAuthToken();
  const isFormData =
    typeof FormData !== "undefined" && restOptions.body instanceof FormData;
  const requestHeaders: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    Accept: "application/json",
    ...(headers as Record<string, string>),
  };

  if (token) {
    requestHeaders["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...restOptions,
    headers: requestHeaders,
    credentials: "include", // For cookies
  });

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  let data: unknown;
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    let errorMessage = `Yêu cầu thất bại với mã lỗi ${response.status}`;
    if (typeof data === "object" && data !== null && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === "string") {
        errorMessage = detail;
      } else if (Array.isArray(detail)) {
        errorMessage = detail
          .map((item) => (typeof item === "object" && item?.msg ? item.msg : JSON.stringify(item)))
          .join(", ");
      }
    } else if (typeof data === "string" && data.length > 0) {
      errorMessage = data;
    }

    throw new ApiClientError(response.status, errorMessage, data);
  }

  return data as T;
}

export const apiClient = {
  get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, { ...options, method: "GET" });
  },

  post<T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, {
      ...options,
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },

  postForm<T>(
    endpoint: string,
    formData: FormData,
    options?: RequestOptions
  ): Promise<T> {
    return request<T>(endpoint, {
      ...options,
      method: "POST",
      body: formData,
    });
  },

  async downloadFile(endpoint: string, fallbackFilename?: string): Promise<void> {
    const url = buildApiUrl(endpoint);
    const token = getAuthToken();
    const requestHeaders: Record<string, string> = {};
    if (token) {
      requestHeaders["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(url, {
      method: "GET",
      headers: requestHeaders,
      credentials: "include",
    });

    if (!response.ok) {
      let msg = `Tải tệp thất bại (mã ${response.status})`;
      try {
        const errData = await response.json();
        if (typeof errData?.detail === "string") {
          msg = errData.detail;
        }
      } catch {
        // ignore JSON parse failure
      }
      throw new ApiClientError(response.status, msg);
    }

    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    let filename = fallbackFilename || "download";
    const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    const asciiMatch = disposition.match(/filename="?([^";]+)"?/i);
    if (utf8Match?.[1]) {
      filename = decodeURIComponent(utf8Match[1]);
    } else if (asciiMatch?.[1]) {
      filename = asciiMatch[1];
    }

    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(blobUrl);
  },

  put<T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, {
      ...options,
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },

  patch<T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, {
      ...options,
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  },

  delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, { ...options, method: "DELETE" });
  },
};
