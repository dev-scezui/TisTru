/** Keys exposed to the browser (Firebase web config is public by design). */
export type PublicEnvKey =
  | "NEXT_PUBLIC_FIREBASE_API_KEY"
  | "NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN"
  | "NEXT_PUBLIC_FIREBASE_PROJECT_ID"
  | "NEXT_PUBLIC_FIREBASE_APP_ID"
  | "NEXT_PUBLIC_ADMIN_PATH_SECRET";

export type PublicEnv = Partial<Record<PublicEnvKey, string>>;

declare global {
  interface Window {
    __TISTRU_ENV__?: PublicEnv;
  }
}

function trim(value: string | undefined): string {
  return (value ?? "").trim();
}

/**
 * Read a public env value. On Hugging Face / Docker, Next inlines NEXT_PUBLIC_*
 * at build time (often empty); start.sh writes window.__TISTRU_ENV__ at runtime.
 */
export function publicEnv(key: PublicEnvKey): string {
  if (typeof window !== "undefined") {
    const fromRuntime = trim(window.__TISTRU_ENV__?.[key]);
    if (fromRuntime) return fromRuntime;
  }
  return trim(process.env[key]);
}
