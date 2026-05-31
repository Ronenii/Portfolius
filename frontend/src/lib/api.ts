export type BackendHealth =
  | { status: "ok" }
  | { status: "error"; message: string };

type Fetcher = typeof fetch;

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
