const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function adminFetch<T>(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    const body = await response.text();
    let message = body || `Request failed (${response.status})`;
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        message = parsed.detail;
      }
    } catch {
      /* keep raw body */
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export { API_URL };
