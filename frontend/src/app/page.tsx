"use client";

import React from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  onAuthStateChanged,
  signOut,
  type User,
} from "firebase/auth";
import {
  AlertTriangle,
  Check,
  FileSearch,
  ImageUp,
  Link2,
  Loader2,
  LogIn,
  LogOut,
  SearchCheck,
  Type,
  X,
} from "lucide-react";
import {
  friendlyAuthError,
  getFirebaseAuth,
  isFirebaseConfigured,
  reportAuthError,
  signInWithGoogle,
} from "../lib/firebase";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const MAX_TEXT_CHARS = 8000;
const MIN_TEXT_CHARS = 20;
const MAX_URL_LENGTH = 2048;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

const URL_PATTERN = /^https?:\/\/[^\s]+$/i;

type ComposeMode = "url" | "text" | "image";

const INVESTIGATION_STEPS = [
  {
    id: "extract",
    label: "Reading source",
    detail: "Pulling text, metadata, or image details from your submission.",
  },
  {
    id: "claims",
    label: "Extracting claims",
    detail: "Summarizing context into checkable factual statements.",
  },
  {
    id: "evidence",
    label: "Searching evidence",
    detail: "Querying independent sources for corroboration.",
  },
  {
    id: "verdict",
    label: "Scoring verdict",
    detail: "Weighing evidence and composing the final report.",
  },
] as const;

const WHY_POINTS = [
  {
    title: "Misinformation moves fast",
    body: "A claim can travel farther in an hour than a correction ever will. Checking first slows the spread.",
  },
  {
    title: "Share with context",
    body: "Knowing what holds up — and what does not — helps you decide what deserves attention.",
  },
  {
    title: "Reduce real-world harm",
    body: "False health, election, and safety claims cost trust and sometimes lives. Verification is a public good.",
  },
] as const;

function detectMode(composeText: string, imageFile: File | null): ComposeMode | null {
  if (imageFile) return "image";
  const trimmed = composeText.trim();
  if (!trimmed) return null;
  if (trimmed.length <= MAX_URL_LENGTH && URL_PATTERN.test(trimmed)) return "url";
  return "text";
}

function fileFromClipboardBlob(blob: File | Blob): File {
  const type = blob.type || "image/png";
  const ext = type.split("/")[1]?.replace("jpeg", "jpg") || "png";
  if (blob instanceof File && blob.name) return blob;
  return new File([blob], `pasted-image.${ext}`, { type });
}

function validateImageFile(file: File): string | null {
  const mime = file.type.toLowerCase().split(";")[0].trim();
  if (!ALLOWED_IMAGE_TYPES.has(mime)) {
    return "Image must be JPG, PNG, or WebP.";
  }
  if (file.size > MAX_IMAGE_BYTES) {
    return "Image must be 5 MB or smaller.";
  }
  if (file.size === 0) {
    return "Image file is empty.";
  }
  return null;
}

function friendlyFactCheckError(detail: unknown, status: number): string {
  if (detail === "auth_required") {
    return "Sign in with Google to continue investigating.";
  }
  if (detail === "daily_limit" || status === 429) {
    if (detail === "daily_limit") {
      return "Daily investigation limit reached. Try again tomorrow.";
    }
    return "Too many investigations. Try again shortly.";
  }
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  return "Unable to complete investigation";
}

export default function HomePage() {
  const [composeText, setComposeText] = React.useState("");
  const [imageFile, setImageFile] = React.useState<File | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [activeStep, setActiveStep] = React.useState(0);
  const [error, setError] = React.useState("");
  const [isDragging, setIsDragging] = React.useState(false);
  const [user, setUser] = React.useState<User | null>(null);
  const [authReady, setAuthReady] = React.useState(!isFirebaseConfigured());
  const [authBusy, setAuthBusy] = React.useState(false);
  const [needsSignIn, setNeedsSignIn] = React.useState(false);
  const router = useRouter();
  const progressRef = React.useRef<HTMLElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const mode = detectMode(composeText, imageFile);
  const canSubmit = mode !== null && !isLoading;
  const firebaseReady = isFirebaseConfigured();

  React.useEffect(() => {
    if (!firebaseReady) {
      setAuthReady(true);
      return;
    }
    try {
      const auth = getFirebaseAuth();
      return onAuthStateChanged(auth, (next) => {
        setUser(next);
        setAuthReady(true);
        if (next) setNeedsSignIn(false);
      });
    } catch {
      setAuthReady(true);
    }
  }, [firebaseReady]);

  React.useEffect(() => {
    if (!isLoading) {
      setActiveStep(0);
      return;
    }

    progressRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });

    const timers = INVESTIGATION_STEPS.slice(1).map((_, index) =>
      window.setTimeout(() => setActiveStep(index + 1), (index + 1) * 4200),
    );

    return () => timers.forEach(clearTimeout);
  }, [isLoading]);

  React.useEffect(() => {
    function onPaste(event: ClipboardEvent) {
      const items = event.clipboardData?.items;
      if (!items) return;

      for (const item of items) {
        if (!item.type.startsWith("image/")) continue;
        const blob = item.getAsFile();
        if (!blob) continue;

        const file = fileFromClipboardBlob(blob);
        const validationError = validateImageFile(file);
        if (validationError) {
          setError(validationError);
          event.preventDefault();
          break;
        }
        setImageFile(file);
        setError("");
        event.preventDefault();
        break;
      }
    }

    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, []);

  React.useEffect(() => {
    if (!needsSignIn || user) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setNeedsSignIn(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [needsSignIn, user]);

  function acceptImage(file: File | null) {
    if (!file) {
      setImageFile(null);
      return;
    }
    const validationError = validateImageFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    setImageFile(file);
    setError("");
  }

  async function handleGoogleSignIn() {
    if (!firebaseReady) {
      setError("Sign-in is not configured.");
      return;
    }
    setAuthBusy(true);
    setError("");
    try {
      await signInWithGoogle();
    } catch (err) {
      reportAuthError(err, "google_sign_in");
      const message = friendlyAuthError(
        err,
        "Google sign-in failed. Please try again.",
      );
      if (message) setError(message);
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleSignOut() {
    if (!firebaseReady) return;
    setAuthBusy(true);
    try {
      await signOut(getFirebaseAuth());
    } catch (err) {
      reportAuthError(err, "sign_out");
      setError("Sign-out failed. Please try again.");
    } finally {
      setAuthBusy(false);
    }
  }

  async function postFactCheck(
    formData: FormData,
    token: string | null,
  ): Promise<{ ok: true; id: string } | { ok: false; status: number; detail: unknown }> {
    const headers: HeadersInit = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(`${API_URL}/api/fact-check`, {
      method: "POST",
      body: formData,
      headers,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      return { ok: false, status: response.status, detail: payload.detail };
    }
    return { ok: true, id: payload.id as string };
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const detected = detectMode(composeText, imageFile);
    if (!detected) {
      setError("Paste a URL, claim, or image to investigate.");
      return;
    }

    if (detected === "text") {
      const trimmed = composeText.trim();
      if (trimmed.length < MIN_TEXT_CHARS) {
        setError(`Text must be at least ${MIN_TEXT_CHARS} characters.`);
        return;
      }
      if (trimmed.length > MAX_TEXT_CHARS) {
        setError("Text is too long.");
        return;
      }
    }

    if (detected === "url") {
      const trimmed = composeText.trim();
      if (trimmed.length > MAX_URL_LENGTH) {
        setError("URL is too long.");
        return;
      }
    }

    if (detected === "image" && imageFile) {
      const validationError = validateImageFile(imageFile);
      if (validationError) {
        setError(validationError);
        return;
      }
    }

    if (needsSignIn && !user && firebaseReady) {
      setError("");
      return;
    }

    setIsLoading(true);
    setActiveStep(0);
    setNeedsSignIn(false);

    try {
      const formData = new FormData();
      if (detected === "url") {
        formData.append("url", composeText.trim());
      } else if (detected === "text") {
        formData.append("text", composeText.trim());
      } else if (imageFile) {
        formData.append("image", imageFile);
      }
      formData.append("mode", detected);
      const form = event.currentTarget;
      const website = (form.elements.namedItem("website") as HTMLInputElement | null)?.value ?? "";
      const company = (form.elements.namedItem("company") as HTMLInputElement | null)?.value ?? "";
      formData.append("website", website);
      formData.append("company", company);

      let token: string | null = null;
      if (user) {
        token = await user.getIdToken();
      }

      const result = await postFactCheck(formData, token);

      if (!result.ok && result.detail === "auth_required" && firebaseReady) {
        setNeedsSignIn(true);
        setError("");
        return;
      }

      if (!result.ok) {
        throw new Error(friendlyFactCheckError(result.detail, result.status));
      }
      router.push(`/report?id=${result.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="shell home">
      <section className="banner" aria-label="Investigate">
        {firebaseReady ? (
          <header className="home-topbar" aria-label="Account">
            {user ? (
              <>
                <span className="home-auth-email">{user.email ?? "Signed in"}</span>
                <button
                  type="button"
                  className="home-auth-button"
                  onClick={() => void handleSignOut()}
                  disabled={authBusy || isLoading || !authReady}
                >
                  <LogOut size={14} aria-hidden />
                  Sign out
                </button>
              </>
            ) : (
              <button
                type="button"
                className="home-auth-button home-auth-button-primary"
                onClick={() => void handleGoogleSignIn()}
                disabled={authBusy || isLoading}
              >
                <LogIn size={14} aria-hidden />
                Sign in with Google
              </button>
            )}
          </header>
        ) : null}

        <div className="hero hero-home">
          <div className="hero-top">
            <div className="mark">
              <SearchCheck size={22} />
            </div>
            <div className="hero-copy">
              <p className="eyebrow">AI-assisted claim investigation</p>
              <h1>Check a claim before it spreads.</h1>
              <p className="lede lede-short">
                Paste a URL, paragraph, or screenshot. TisTru extracts claims,
                searches sources, and returns a scored verdict.
              </p>
            </div>
            <div className="image-banner">
              <Image src="/tistru2.png" alt="TisTru" width={200} height={200} />
            </div>
          </div>

        <form className="investigate-form" onSubmit={submit}>
          <fieldset className="source-fieldset" disabled={isLoading}>
            <legend className="source-legend">What are you checking?</legend>

            <div
              className={
                isDragging ? "compose-box dragging" : "compose-box"
              }
              onDragEnter={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={(event) => {
                event.preventDefault();
                if (!event.currentTarget.contains(event.relatedTarget as Node)) {
                  setIsDragging(false);
                }
              }}
              onDrop={(event) => {
                event.preventDefault();
                setIsDragging(false);
                const file = event.dataTransfer.files?.[0];
                if (file?.type.startsWith("image/")) {
                  acceptImage(file);
                }
              }}
            >
              <label className="input-block compose-input-block">
                <span className="input-label">URL, claim, or paragraph</span>
                <textarea
                  className="compose-textarea"
                  value={composeText}
                  onChange={(event) => setComposeText(event.target.value)}
                  placeholder="Paste a URL, claim, or paragraph — or drop / paste an image"
                  rows={3}
                  maxLength={MAX_TEXT_CHARS}
                  disabled={Boolean(imageFile)}
                />
              </label>

              <div className="hp-field" aria-hidden="true">
                <label>
                  Website
                  <input
                    type="text"
                    name="website"
                    tabIndex={-1}
                    autoComplete="off"
                  />
                </label>
                <label>
                  Company
                  <input
                    type="text"
                    name="company"
                    tabIndex={-1}
                    autoComplete="off"
                  />
                </label>
              </div>

              <div className="compose-meta">
                <div className="compose-meta-left">
                  {mode ? (
                    <span className={`detect-chip detect-${mode}`}>
                      {mode === "url" ? (
                        <Link2 size={14} aria-hidden />
                      ) : mode === "text" ? (
                        <Type size={14} aria-hidden />
                      ) : (
                        <ImageUp size={14} aria-hidden />
                      )}
                      Detected: {mode === "url" ? "URL" : mode === "text" ? "Text" : "Image"}
                    </span>
                  ) : (
                    <span className="detect-hint">Waiting for input</span>
                  )}

                  {imageFile ? (
                    <div className="image-preview-row">
                      <ImageUp size={14} aria-hidden />
                      <span className="image-preview-name">{imageFile.name}</span>
                      <button
                        type="button"
                        className="image-clear"
                        onClick={() => {
                          setImageFile(null);
                          if (fileInputRef.current) fileInputRef.current.value = "";
                        }}
                        aria-label="Remove image"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ) : null}
                </div>

                <div className="compose-actions">
                  <label className="compose-upload">
                    <input
                      ref={fileInputRef}
                      accept="image/jpeg,image/png,image/webp"
                      type="file"
                      onChange={(event) =>
                        acceptImage(event.target.files?.[0] ?? null)
                      }
                    />
                    <ImageUp size={16} aria-hidden />
                    {imageFile ? "Replace image" : "Add image"}
                  </label>

                  <button
                    className="investigate-button"
                    type="submit"
                    disabled={!canSubmit}
                    aria-busy={isLoading}
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="spin" size={18} aria-hidden />
                        Investigating…
                      </>
                    ) : (
                      <>
                        <FileSearch size={18} aria-hidden />
                        Investigate
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </fieldset>
        </form>

        {needsSignIn && !user && (
          <div
            className="auth-modal-backdrop"
            role="presentation"
            onClick={() => setNeedsSignIn(false)}
          >
            <div
              className="auth-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="auth-modal-title"
              aria-describedby="auth-modal-desc"
              onClick={(event) => event.stopPropagation()}
            >
              <button
                type="button"
                className="auth-modal-close"
                onClick={() => setNeedsSignIn(false)}
                aria-label="Close"
              >
                <X size={16} />
              </button>
              <p className="auth-modal-title" id="auth-modal-title">
                Free investigation used
              </p>
              <p className="auth-modal-body" id="auth-modal-desc">
                Sign in with Google to keep investigating. Nothing runs until you
                choose to sign in.
              </p>
              <div className="auth-modal-actions">
                <button
                  type="button"
                  className="home-auth-button"
                  onClick={() => setNeedsSignIn(false)}
                  disabled={authBusy}
                >
                  Not now
                </button>
                <button
                  type="button"
                  className="home-auth-button home-auth-button-primary"
                  onClick={() => void handleGoogleSignIn()}
                  disabled={authBusy || isLoading}
                >
                  <LogIn size={14} aria-hidden />
                  Sign in with Google
                </button>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="error" role="alert">
            <AlertTriangle size={18} aria-hidden />
            {error}
          </div>
        )}

        {isLoading && mode && (
          <InvestigationProgress
            ref={progressRef}
            activeStep={activeStep}
            mode={mode}
          />
        )}
        </div>
      </section>

      {!isLoading && (
        <>
          <section className="home-section why-section" aria-labelledby="why-heading">
            <h2 id="why-heading">Why fact-checking matters</h2>
            <p className="section-lede">
              Verification is not cynicism — it is how you keep signal above noise
              before a claim becomes consensus.
            </p>
            <ol className="why-list">
              {WHY_POINTS.map((point, index) => (
                <li key={point.title}>
                  <span className="process-num">0{index + 1}</span>
                  <div>
                    <p className="why-title">{point.title}</p>
                    <p className="why-body">{point.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section
            className="home-section how-section"
            aria-labelledby="how-heading"
          >
            <h2 id="how-heading">How TisTru arrives at a result</h2>
            <p className="section-lede">
              Every investigation follows the same pipeline — from your source to
              a scored verdict with cited evidence.
            </p>
            <div className="process-strip process-strip-rich" aria-label="Investigation steps">
              {INVESTIGATION_STEPS.map((step, index) => (
                <article className="process-step" key={step.id}>
                  <span className="process-num">0{index + 1}</span>
                  <p className="process-step-title">{step.label}</p>
                  <p>{step.detail}</p>
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  );
}

const InvestigationProgress = React.forwardRef<
  HTMLElement,
  { activeStep: number; mode: ComposeMode }
>(function InvestigationProgress({ activeStep, mode }, ref) {
  const current = INVESTIGATION_STEPS[activeStep] ?? INVESTIGATION_STEPS[0];

  const sourceLabel =
    mode === "url"
      ? "Analyzing the URL you submitted"
      : mode === "text"
        ? "Analyzing the text you submitted"
        : "Analyzing the image you uploaded";

  return (
    <section className="investigation-progress" ref={ref} aria-live="polite">
      <div className="investigation-progress-head">
        <Loader2 className="spin investigation-spinner" size={18} aria-hidden />
        <div>
          <p className="investigation-title">Investigation in progress</p>
          <p className="investigation-source">{sourceLabel}</p>
        </div>
      </div>

      <p className="investigation-current">
        <span className="investigation-current-label">Now:</span>{" "}
        {current.detail}
      </p>

      <ol className="investigation-steps">
        {INVESTIGATION_STEPS.map((step, index) => {
          const done = index < activeStep;
          const currentStep = index === activeStep;

          return (
            <li
              key={step.id}
              className={
                done
                  ? "investigation-step done"
                  : currentStep
                    ? "investigation-step active"
                    : "investigation-step"
              }
            >
              <span className="investigation-step-icon" aria-hidden>
                {done ? (
                  <Check size={14} />
                ) : currentStep ? (
                  <Loader2 className="spin" size={14} />
                ) : (
                  <span className="investigation-step-dot" />
                )}
              </span>
              <span className="investigation-step-label">{step.label}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
});
