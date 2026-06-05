"use client";

import React from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Check,
  FileSearch,
  ImageUp,
  Link2,
  Loader2,
  SearchCheck,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

export default function HomePage() {
  const [mode, setMode] = React.useState<"image" | "url">("url");
  const [url, setUrl] = React.useState("");
  const [imageFile, setImageFile] = React.useState<File | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [activeStep, setActiveStep] = React.useState(0);
  const [error, setError] = React.useState("");
  const router = useRouter();
  const progressRef = React.useRef<HTMLElement>(null);
  const formRef = React.useRef<HTMLFormElement>(null);

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

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsLoading(true);
    setActiveStep(0);

    try {
      if (mode === "image" && !imageFile) {
        throw new Error("Choose an image file to investigate.");
      }
      if (mode === "url" && !url.trim()) {
        throw new Error("Paste a URL to investigate.");
      }

      const formData = new FormData();
      if (mode === "url") {
        formData.append("url", url.trim());
      }
      if (mode === "image" && imageFile) {
        formData.append("image", imageFile);
      }
      formData.append("mode", mode);

      const response = await fetch(`${API_URL}/api/fact-check`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Unable to complete investigation");
      }
      router.push(`/report?id=${payload.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="shell home">
      <section className="hero hero-home">
        <div className="hero-top">
          <div className="mark">
            <SearchCheck size={22} />
          </div>
          <div className="hero-copy">
            <p className="eyebrow">AI-assisted claim investigation</p>
            <h1>Check a link or image before it spreads.</h1>
            <p className="lede lede-short">
              Paste a URL or upload a screenshot. TisTru extracts claims,
              searches sources, and returns a scored verdict.
            </p>
          </div>
        </div>

        <form className="investigate-form" onSubmit={submit} ref={formRef}>
          <fieldset className="source-fieldset" disabled={isLoading}>
            <legend className="source-legend">What are you checking?</legend>

            <div
              className="source-tabs"
              role="tablist"
              aria-label="Investigation source type"
            >
              <button
                className={
                  mode === "url" ? "source-tab active" : "source-tab"
                }
                type="button"
                role="tab"
                id="tab-url"
                aria-selected={mode === "url"}
                aria-controls="panel-url"
                onClick={() => setMode("url")}
              >
                <Link2 size={16} aria-hidden />
                Paste a URL
              </button>
              <button
                className={
                  mode === "image" ? "source-tab active" : "source-tab"
                }
                type="button"
                role="tab"
                id="tab-image"
                aria-selected={mode === "image"}
                aria-controls="panel-image"
                onClick={() => setMode("image")}
              >
                <ImageUp size={16} aria-hidden />
                Upload an image
              </button>
            </div>

            <div className="investigate-row">
              <div
                className="source-panel"
                role="tabpanel"
                id={mode === "url" ? "panel-url" : "panel-image"}
                aria-labelledby={mode === "url" ? "tab-url" : "tab-image"}
              >
                {mode === "url" ? (
                  <label className="input-block">
                    <span className="input-label">Post or article URL</span>
                    <div className="search-field">
                      <Link2 className="input-icon" size={18} aria-hidden />
                      <input
                        value={url}
                        onChange={(event) => setUrl(event.target.value)}
                        placeholder="https://example.com/post-or-article"
                        type="url"
                        inputMode="url"
                        autoComplete="url"
                        required
                      />
                    </div>
                  </label>
                ) : (
                  <label className="input-block upload-block">
                    <span className="input-label">Screenshot, meme, or photo</span>
                    <span className="upload-field">
                      <input
                        accept="image/*"
                        onChange={(event) =>
                          setImageFile(event.target.files?.[0] ?? null)
                        }
                        type="file"
                        required
                      />
                      <span className="upload-icon" aria-hidden>
                        <ImageUp size={18} />
                      </span>
                      <span className="upload-text">
                        {imageFile
                          ? imageFile.name
                          : "Choose a file — JPG, PNG, or WebP"}
                      </span>
                    </span>
                  </label>
                )}
              </div>

              <button
                className="investigate-button"
                type="submit"
                disabled={isLoading}
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
          </fieldset>
        </form>

        {error && (
          <div className="error" role="alert">
            <AlertTriangle size={18} aria-hidden />
            {error}
          </div>
        )}

        {isLoading && (
          <InvestigationProgress
            ref={progressRef}
            activeStep={activeStep}
            mode={mode}
          />
        )}
      </section>

      {!isLoading && (
        <section className="process-strip" aria-label="How TisTru works">
          {[
            "Extract source context",
            "Identify checkable claims",
            "Search independent evidence",
            "Score and deliver verdict",
          ].map((item, index) => (
            <article className="process-step" key={item}>
              <span className="process-num">0{index + 1}</span>
              <p>{item}</p>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}

const InvestigationProgress = React.forwardRef<
  HTMLElement,
  { activeStep: number; mode: "image" | "url" }
>(function InvestigationProgress({ activeStep, mode }, ref) {
  const current = INVESTIGATION_STEPS[activeStep] ?? INVESTIGATION_STEPS[0];

  return (
    <section className="investigation-progress" ref={ref} aria-live="polite">
      <div className="investigation-progress-head">
        <Loader2 className="spin investigation-spinner" size={18} aria-hidden />
        <div>
          <p className="investigation-title">Investigation in progress</p>
          <p className="investigation-source">
            {mode === "url"
              ? "Analyzing the URL you submitted"
              : "Analyzing the image you uploaded"}
          </p>
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
