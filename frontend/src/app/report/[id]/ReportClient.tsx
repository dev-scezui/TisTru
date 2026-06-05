"use client";

import React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Copy,
  ExternalLink,
  Globe2,
  Link2,
  Gauge,
  SearchCheck,
  ShieldQuestion,
  XCircle,
} from "lucide-react";
import { RichText } from "@/components/RichText";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Verdict =
  | "legitimate"
  | "likely_legitimate"
  | "uncertain"
  | "likely_fake"
  | "fake";

type EvidenceItem = {
  title: string;
  url: string;
  snippet: string;
  source: string | null;
  stance: string;
  credibility: number;
};

type Report = {
  url: string | null;
  context_summary: string;
  image_key_info: string | null;
  key_claims: string[];
  evidence: EvidenceItem[];
  scores: {
    legitimacy: number;
    evidence_strength: number;
    source_credibility: number;
    contradiction_risk: number;
  };
  verdict: Verdict;
  verdict_reason: string;
};

export default function ReportClient() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");
  const [report, setReport] = React.useState<Report | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!id) {
      setError("Missing report id");
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_URL}/api/reports/${id}`);
        const payload = await res.json();
        if (!res.ok) {
          throw new Error(payload.detail || "Report not found");
        }
        if (!cancelled) setReport(payload);
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Failed to load report",
          );
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <main className="shell">
      <section className="report-header">
        <div className="report-header-inner">
          <div className="mark">
            <SearchCheck size={22} />
          </div>
          <div className="report-header-url">
            <Link2 size={16} />
            <span>{report?.url || "Uploaded image"}</span>
          </div>
          <Link className="report-header-action" href="/">
            New investigation
          </Link>
        </div>
      </section>

      {isLoading && <EmptyState isLoading={true} />}
      {error && (
        <div className="error centered">
          <AlertTriangle size={18} />
          {error}
        </div>
      )}
      {report && <ReportView report={report} />}
    </main>
  );
}

function EmptyState({ isLoading }: { isLoading: boolean }) {
  return (
    <section className="empty-state">
      <div className="radar">
        <Globe2 size={54} />
      </div>
      <h2>
        {isLoading ? "Investigation running" : "Ready for a source or image"}
      </h2>
      <p>
        {isLoading
          ? "The backend is extracting context, searching evidence, and composing a report."
          : "Switch between URL and image mode from the homepage to start a new check."}
      </p>
    </section>
  );
}

function ReportView({ report }: { report: Report }) {
  const verdict = verdictCopy(report.verdict);
  const legitimacy = Math.max(0, Math.min(100, report.scores.legitimacy));
  const [copied, setCopied] = React.useState(false);

  function copyLink() {
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <section className="report">
      <div className={`verdict ${verdict.tone}`}>
        <div className="verdict-main">
          <p className="eyebrow">Final verdict</p>
          <div className="verdict-heading">
            <h2>{verdict.label}</h2>
            <div className="verdict-score" aria-label={`Legitimacy score ${legitimacy} percent`}>
              <strong>{legitimacy}%</strong>
              <span>legitimacy score</span>
            </div>
          </div>
          <RichText text={report.verdict_reason} className="verdict-reason" />
        </div>
        <div className="verdict-icon" aria-hidden>
          {report.verdict === "fake" || report.verdict === "likely_fake" ? (
            <XCircle size={54} />
          ) : report.verdict.includes("legitimate") ? (
            <CheckCircle2 size={54} />
          ) : (
            <ShieldQuestion size={54} />
          )}
        </div>
      </div>

      <div className="share-bar">
        <button className="share-button" onClick={copyLink}>
          <Copy size={16} />
          {copied ? "Link copied!" : "Copy shareable link"}
        </button>
      </div>

      <div className="score-grid">
        <Score label="Legitimacy" value={report.scores.legitimacy} />
        <Score
          label="Evidence strength"
          value={report.scores.evidence_strength}
        />
        <Score
          label="Source credibility"
          value={report.scores.source_credibility}
        />
        <Score
          label="Contradiction risk"
          value={report.scores.contradiction_risk}
          inverted
        />
      </div>

      <div className="report-grid">
        <article className="panel span-2">
          <p className="eyebrow">Context summary</p>
          <h3>What the artifact appears to claim</h3>
          <p>{report.context_summary}</p>
        </article>

        {report.image_key_info && (
          <article className="panel">
            <p className="eyebrow">Image key info</p>
            <h3>What was extracted from the upload</h3>
            <p>{report.image_key_info}</p>
          </article>
        )}

        <article className={`panel ${report.image_key_info ? "" : "span-2"}`}>
          <p className="eyebrow">Extracted claims</p>
          <h3>Check targets</h3>
          <ul className="claims">
            {report.key_claims.length ? (
              report.key_claims.map((claim) => <li key={claim}>{claim}</li>)
            ) : (
              <li>No explicit factual claims were extracted.</li>
            )}
          </ul>
        </article>

        <article className="panel evidence-panel span-2">
          <p className="eyebrow">Evidence trail</p>
          <h3>Sources inspected</h3>
          <EvidenceAccordion items={report.evidence} />
        </article>
      </div>
    </section>
  );
}

function Score({
  label,
  value,
  inverted = false,
}: {
  label: string;
  value: number;
  inverted?: boolean;
}) {
  const display = Math.max(0, Math.min(100, value));
  return (
    <article className="score-card">
      <div>
        <Gauge size={20} />
        <span>{label}</span>
      </div>
      <strong>{display}</strong>
      <meter min="0" max="100" value={inverted ? 100 - display : display} />
    </article>
  );
}

function EvidenceAccordion({ items }: { items: EvidenceItem[] }) {
  const [openIndex, setOpenIndex] = React.useState<number | null>(null);

  function toggle(index: number) {
    setOpenIndex((prev) => (prev === index ? null : index));
  }

  return (
    <div className="evidence-accordion">
      {items.map((item, index) => {
        const isOpen = openIndex === index;
        const stance = stanceInfo(item.stance);
        return (
          <div
            className={`evidence-file ${isOpen ? "open" : ""} ${stance.tone}`}
            key={item.url + index}
          >
            <button
              className="evidence-header"
              onClick={() => toggle(index)}
              aria-expanded={isOpen}
            >
              <div className="evidence-meta">
                <span className="evidence-badge">
                  {item.source || "Unknown source"}
                </span>
                <span className="evidence-stance">{stance.label}</span>
              </div>
              <div className="evidence-title-row">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="evidence-title-link"
                  onClick={(e) => e.stopPropagation()}
                >
                  {item.title}
                </a>
                <span
                  className="evidence-cred"
                  title="Combines domain reputation with search relevance"
                >
                  {Math.round(item.credibility * 100)}% source trust
                </span>
              </div>
              <ChevronDown size={18} className="evidence-chevron" />
            </button>
            <div className="evidence-body" hidden={!isOpen}>
              <div className="evidence-body-inner">
                <p className="evidence-snippet">{item.snippet}</p>
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="evidence-link"
                >
                  <ExternalLink size={14} />
                  Open source
                </a>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function stanceInfo(stance: string) {
  const s = stance.toLowerCase();
  if (s.includes("contradict")) return { label: "Contradictory", tone: "bad" };
  if (s.includes("support") || s.includes("confirm"))
    return { label: "Supporting", tone: "good" };
  return { label: "Neutral", tone: "unknown" };
}

function verdictCopy(verdict: Verdict) {
  const labels: Record<Verdict, { label: string; tone: string }> = {
    legitimate: { label: "Legitimate", tone: "good" },
    likely_legitimate: { label: "Likely legitimate", tone: "good" },
    uncertain: { label: "Uncertain", tone: "unknown" },
    likely_fake: { label: "Likely fake", tone: "bad" },
    fake: { label: "Fake", tone: "bad" },
  };
  return labels[verdict];
}
