import { useCallback, useEffect, useRef, useState } from "react";

/**
 * The DOM lib does not ship a type for this event (it's not yet a stable
 * standard), so it's typed locally with just the members this hook uses.
 */
interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

type UsePwaInstallResult = {
  /** True once the browser has offered an install prompt and it hasn't been
   * consumed (or the app installed) yet. Drives whether an install button
   * should render at all. */
  canInstall: boolean;
  /** Replays the captured install prompt. Resolves once the user has made a
   * choice (or immediately, as a no-op, if no prompt has been captured). */
  promptInstall: () => Promise<void>;
};

/**
 * Captures the browser's `beforeinstallprompt` event so the app can offer its
 * own install affordance instead of relying on the browser's mini-infobar,
 * and hides that affordance again once the app is installed.
 */
export function usePwaInstall(): UsePwaInstallResult {
  const [canInstall, setCanInstall] = useState(false);
  const deferredPromptRef = useRef<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    function handleBeforeInstallPrompt(event: Event) {
      event.preventDefault();
      deferredPromptRef.current = event as BeforeInstallPromptEvent;
      setCanInstall(true);
    }

    function handleAppInstalled() {
      deferredPromptRef.current = null;
      setCanInstall(false);
    }

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    window.addEventListener("appinstalled", handleAppInstalled);

    return () => {
      window.removeEventListener(
        "beforeinstallprompt",
        handleBeforeInstallPrompt
      );
      window.removeEventListener("appinstalled", handleAppInstalled);
    };
  }, []);

  const promptInstall = useCallback(async () => {
    const deferredPrompt = deferredPromptRef.current;
    if (!deferredPrompt) {
      return;
    }
    await deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPromptRef.current = null;
    setCanInstall(false);
  }, []);

  return { canInstall, promptInstall };
}
