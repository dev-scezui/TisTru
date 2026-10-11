import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  type Auth,
  type UserCredential,
} from "firebase/auth";

import { API_URL } from "./api";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export function isFirebaseConfigured(): boolean {
  return Boolean(
    firebaseConfig.apiKey &&
      firebaseConfig.authDomain &&
      firebaseConfig.projectId,
  );
}

let app: FirebaseApp | undefined;
let auth: Auth | undefined;
let googleProvider: GoogleAuthProvider | undefined;

export function getFirebaseAuth(): Auth {
  if (!isFirebaseConfigured()) {
    throw new Error("Firebase web config is missing");
  }
  if (!app) {
    app = getApps()[0] ?? initializeApp(firebaseConfig);
  }
  if (!auth) {
    auth = getAuth(app);
  }
  return auth;
}

function getGoogleProvider(): GoogleAuthProvider {
  if (!googleProvider) {
    googleProvider = new GoogleAuthProvider();
    googleProvider.setCustomParameters({ prompt: "select_account" });
  }
  return googleProvider;
}

const USER_CANCELLED_AUTH_CODES = new Set([
  "auth/popup-closed-by-user",
  "auth/cancelled-popup-request",
]);

export function getFirebaseAuthCode(err: unknown): string | null {
  if (typeof err === "object" && err !== null && "code" in err) {
    const code = (err as { code: unknown }).code;
    return typeof code === "string" ? code : null;
  }
  return null;
}

/** True when the user dismissed the sign-in UI — not a real failure. */
export function isAuthCancelled(err: unknown): boolean {
  const code = getFirebaseAuthCode(err);
  return code !== null && USER_CANCELLED_AUTH_CODES.has(code);
}

/**
 * Message safe to show in the UI. Empty string means show nothing
 * (user cancelled). Never returns raw Firebase error text.
 */
export function friendlyAuthError(err: unknown, fallback: string): string {
  if (isAuthCancelled(err)) return "";
  return fallback;
}

/** Fire-and-forget: log auth issues on the API server, never surface to the UI. */
export function reportAuthError(err: unknown, event: string): void {
  if (typeof window === "undefined") return;
  const code = getFirebaseAuthCode(err);
  const detail =
    err instanceof Error
      ? err.message.slice(0, 300)
      : typeof err === "string"
        ? err.slice(0, 300)
        : "unknown";
  const body = JSON.stringify({
    event,
    code,
    detail,
    cancelled: isAuthCancelled(err),
  });
  void fetch(`${API_URL}/api/client-log`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => undefined);
}

export async function signInWithGoogle(): Promise<UserCredential> {
  const authClient = getFirebaseAuth();
  return signInWithPopup(authClient, getGoogleProvider());
}
