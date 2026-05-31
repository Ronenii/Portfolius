import { describe, expect, it, vi } from "vitest";

import { fetchBackendHealth } from "./api";

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
});
