import { API_URL } from "./api";
import { adminPathSlug } from "./adminPath";

const SESSION_KEY = "tistru_session_id";

function getSessionId(): string {
  try {
    const existing = sessionStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    sessionStorage.setItem(SESSION_KEY, id);
    return id;
  } catch {
    return `anon-${Date.now()}`;
  }
}

export function trackPageview(pathname: string): void {
  if (typeof window === "undefined") return;

  const adminSlug = adminPathSlug();
  if (adminSlug && (pathname === `/${adminSlug}` || pathname.startsWith(`/${adminSlug}/`))) {
    return;
  }

  const body = JSON.stringify({
    path: pathname || "/",
    session_id: getSessionId(),
  });

  const url = `${API_URL}/api/analytics/pageview`;
  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon(url, blob);
      return;
    }
  } catch {
    // fall through to fetch
  }

  void fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => undefined);
}
