/** Login/admin UI path segment from env (literal URL, not encoded). */
export function adminPathSlug(): string {
  const secret = (process.env.NEXT_PUBLIC_ADMIN_PATH_SECRET ?? "").trim();
  if (!secret) return "";
  return secret.replace(/^\/+|\/+$/g, "");
}

export function isAdminSlug(slug: string): boolean {
  const expected = adminPathSlug();
  return Boolean(expected) && slug === expected;
}
