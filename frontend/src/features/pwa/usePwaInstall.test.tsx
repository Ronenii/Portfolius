import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { usePwaInstall } from "./usePwaInstall";

class MockBeforeInstallPromptEvent extends Event {
  prompt = vi.fn().mockResolvedValue(undefined);
  userChoice = Promise.resolve({ outcome: "accepted" as const });

  constructor() {
    super("beforeinstallprompt", { cancelable: true });
  }
}

describe("usePwaInstall", () => {
  it("starts with canInstall false", () => {
    const { result } = renderHook(() => usePwaInstall());
    expect(result.current.canInstall).toBe(false);
  });

  it("sets canInstall true after beforeinstallprompt fires", () => {
    const { result } = renderHook(() => usePwaInstall());

    act(() => {
      window.dispatchEvent(new MockBeforeInstallPromptEvent());
    });

    expect(result.current.canInstall).toBe(true);
  });

  it("prevents the default mini-infobar via preventDefault", () => {
    const { result } = renderHook(() => usePwaInstall());
    const event = new MockBeforeInstallPromptEvent();
    const preventDefaultSpy = vi.spyOn(event, "preventDefault");

    act(() => {
      window.dispatchEvent(event);
    });

    expect(result.current.canInstall).toBe(true);
    expect(preventDefaultSpy).toHaveBeenCalled();
  });

  it("promptInstall calls the stored event's prompt() and then hides the button", async () => {
    const { result } = renderHook(() => usePwaInstall());
    const event = new MockBeforeInstallPromptEvent();

    act(() => {
      window.dispatchEvent(event);
    });
    expect(result.current.canInstall).toBe(true);

    await act(async () => {
      await result.current.promptInstall();
    });

    expect(event.prompt).toHaveBeenCalledTimes(1);
    expect(result.current.canInstall).toBe(false);
  });

  it("promptInstall is a no-op when no event has been captured", async () => {
    const { result } = renderHook(() => usePwaInstall());

    await act(async () => {
      await expect(result.current.promptInstall()).resolves.toBeUndefined();
    });

    expect(result.current.canInstall).toBe(false);
  });

  it("sets canInstall false when appinstalled fires", () => {
    const { result } = renderHook(() => usePwaInstall());

    act(() => {
      window.dispatchEvent(new MockBeforeInstallPromptEvent());
    });
    expect(result.current.canInstall).toBe(true);

    act(() => {
      window.dispatchEvent(new Event("appinstalled"));
    });

    expect(result.current.canInstall).toBe(false);
  });

  it("removes both listeners on unmount", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    const removeSpy = vi.spyOn(window, "removeEventListener");

    const { unmount } = renderHook(() => usePwaInstall());
    const registeredEvents = addSpy.mock.calls.map(([type]) => type);
    expect(registeredEvents).toContain("beforeinstallprompt");
    expect(registeredEvents).toContain("appinstalled");

    unmount();

    const removedEvents = removeSpy.mock.calls.map(([type]) => type);
    expect(removedEvents).toContain("beforeinstallprompt");
    expect(removedEvents).toContain("appinstalled");

    addSpy.mockRestore();
    removeSpy.mockRestore();
  });
});
