import { publicEnv } from "./publicEnv";

function readAdminPathSecret(): string {
  // Client: runtime-config.js (HF/Docker) or NEXT_PUBLIC_* from next dev.
  if (typeof window !== "undefined") {
    return publicEnv("NEXT_PUBLIC_ADMIN_PATH_SECRET");
  }
  // Server: prefer non-NEXT_PUBLIC so HF/Docker runtime env is not build-inlined.
  const env = process.env as Record<string, string | undefined>;
  return (
    env.ADMIN_PATH_SECRET?.trim() ||
    env.NEXT_PUBLIC_ADMIN_PATH_SECRET?.trim() ||
    ""
  );
}

/** Login/admin UI path segment from env (literal URL, not encoded). */
export function adminPathSlug(): string {
  const secret = readAdminPathSecret();
  if (!secret) return "";
  return secret.replace(/^\/+|\/+$/g, "");
}

export function isAdminSlug(slug: string): boolean {
  const expected = adminPathSlug();
  return Boolean(expected) && slug === expected;
}
