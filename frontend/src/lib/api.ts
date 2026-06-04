export type BackendHealth =
  | { status: "ok" }
  | { status: "error"; message: string };

type Fetcher = typeof fetch;

const defaultApiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function normalizeApiUrl(apiUrl: string): string {
  return apiUrl.replace(/\/+$/, "");
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

export async function fetchBackendHealth(
  apiUrl: string,
  fetcher: Fetcher = fetch
): Promise<BackendHealth> {
  try {
    const response = await fetcher(`${normalizeApiUrl(apiUrl)}/healthz`, {
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      return {
        status: "error",
        message: `Backend returned HTTP ${response.status}`,
      };
    }

    const body = (await response.json()) as { status?: string };
    if (body.status !== "ok") {
      return {
        status: "error",
        message: "Backend health response was not ok",
      };
    }

    return { status: "ok" };
  } catch (error) {
    return { status: "error", message: errorMessage(error) };
  }
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiRequestOptions = {
  accessToken?: string | null;
  apiUrl?: string;
  body?: unknown;
  fetcher?: Fetcher;
  method?: "GET" | "POST" | "PUT" | "DELETE";
};

async function responseMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown; message?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (typeof body.message === "string") {
      return body.message;
    }
  } catch {
    // Fall back to a status-based message below.
  }

  return `API request failed with HTTP ${response.status}`;
}

export async function apiRequest<T = unknown>(
  path: string,
  {
    accessToken,
    apiUrl = defaultApiUrl,
    body,
    fetcher = fetch,
    method = "GET",
  }: ApiRequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const requestInit: RequestInit = {
    headers,
    method,
  };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestInit.body = JSON.stringify(body);
  }

  const response = await fetcher(`${normalizeApiUrl(apiUrl)}${path}`, requestInit);

  if (!response.ok) {
    throw new ApiError(response.status, await responseMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
