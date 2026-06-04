import { describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, fetchBackendHealth } from "./api";

describe("fetchBackendHealth", () => {
  it("returns ok when the backend health endpoint responds", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        headers: { "Content-Type": "application/json" },
      })
    );

    await expect(fetchBackendHealth("http://api.test", fetcher)).resolves.toEqual({
      status: "ok",
    });

    expect(fetcher).toHaveBeenCalledWith("http://api.test/healthz", {
      headers: { Accept: "application/json" },
    });
  });

  it("returns an error state when the backend cannot be reached", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("network down"));

    await expect(fetchBackendHealth("http://api.test", fetcher)).resolves.toEqual({
      status: "error",
      message: "network down",
    });
  });

  it("does not attach an auth header to health requests", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        headers: { "Content-Type": "application/json" },
      })
    );

    await fetchBackendHealth("http://api.test", fetcher);

    expect(fetcher).toHaveBeenCalledWith("http://api.test/healthz", {
      headers: { Accept: "application/json" },
    });
  });
});

describe("apiRequest", () => {
  it("attaches a bearer token and sends JSON payloads", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 1 }), {
        headers: { "Content-Type": "application/json" },
      })
    );

    await expect(
      apiRequest<{ id: number }>("/api/v1/profile", {
        accessToken: "access-token",
        apiUrl: "http://api.test/",
        body: { display_name: "Ronen" },
        fetcher,
        method: "PUT",
      })
    ).resolves.toEqual({ id: 1 });

    expect(fetcher).toHaveBeenCalledWith("http://api.test/api/v1/profile", {
      body: JSON.stringify({ display_name: "Ronen" }),
      headers: {
        Accept: "application/json",
        Authorization: "Bearer access-token",
        "Content-Type": "application/json",
      },
      method: "PUT",
    });
  });

  it("returns undefined for 204 responses", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));

    await expect(
      apiRequest("/api/v1/holdings/1", {
        accessToken: "access-token",
        apiUrl: "http://api.test",
        fetcher,
        method: "DELETE",
      })
    ).resolves.toBeUndefined();
  });

  it("throws ApiError with status for 401 and 404 responses", async () => {
    const unauthorizedFetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid authentication credentials" }), {
        headers: { "Content-Type": "application/json" },
        status: 401,
      })
    );
    const notFoundFetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Profile not found" }), {
        headers: { "Content-Type": "application/json" },
        status: 404,
      })
    );

    await expect(
      apiRequest("/api/v1/profile", {
        apiUrl: "http://api.test",
        fetcher: unauthorizedFetcher,
      })
    ).rejects.toMatchObject({ message: "Invalid authentication credentials", status: 401 });

    const notFoundRequest = apiRequest("/api/v1/profile", {
      apiUrl: "http://api.test",
      fetcher: notFoundFetcher,
    });

    await expect(notFoundRequest).rejects.toBeInstanceOf(ApiError);
    await expect(notFoundRequest).rejects.toMatchObject({
      message: "Profile not found",
      status: 404,
    });
  });
});
