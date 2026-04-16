import { useCallback, useEffect, useState } from "react";

export type MicPermission = "granted" | "denied" | "prompt" | "unavailable";

export function useMicrophone() {
  const [permission, setPermission] = useState<MicPermission>("unavailable");

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      // Mobile detection — assume mic available
      if (/Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) {
        setPermission("prompt");
      }
      return;
    }

    // Check permission state
    navigator.permissions
      ?.query({ name: "microphone" as PermissionName })
      .then((status) => {
        setPermission(status.state as MicPermission);
        status.onchange = () => {
          setPermission(status.state as MicPermission);
        };
      })
      .catch(() => {
        // Permissions API not supported — assume prompt
        setPermission("prompt");
      });
  }, []);

  const requestPermission = useCallback(async (): Promise<boolean> => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Stop tracks immediately — we just needed permission
      stream.getTracks().forEach((t) => t.stop());
      setPermission("granted");
      return true;
    } catch {
      setPermission("denied");
      return false;
    }
  }, []);

  return {
    permission,
    showMic: permission === "granted" || permission === "prompt",
    isGranted: permission === "granted",
    requestPermission,
  };
}
