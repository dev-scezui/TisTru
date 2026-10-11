"use client";

import React from "react";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User,
} from "firebase/auth";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Eye,
  KeyRound,
  LayoutDashboard,
  Loader2,
  LogOut,
  RefreshCw,
  SearchCheck,
  Server,
  Settings2,
  Shield,
  Sparkles,
  ExternalLink,
  FileText,
  Users,
} from "lucide-react";
import { adminFetch } from "../../lib/api";
import {
  friendlyAuthError,
  getFirebaseAuth,
  isFirebaseConfigured,
  reportAuthError,
} from "../../lib/firebase";

type Tab = "overview" | "config" | "traffic" | "reports";

type AdminSettings = {
  use_local_llm: boolean;
  ollama_base_url: string;
  ollama_model: string;
  openai_api_key: string;
  openai_base_url: string | null;
  openai_model: string;
  tavily_api_key: string;
  updated_at: string | null;
  updated_by: string | null;
};

type ReportListItem = {
  id: string;
  verdict?: string;
  url?: string | null;
  context_summary?: string;
  created_at?: string | null;
};

type Analytics = {
  range: string;
  fact_checks_by_day: Record<string, number>;
  verdict_mix: Record<string, number>;
  fact_check_ok: number;
  fact_check_error: number;
  fact_check_error_rate: number;
  page_views: number;
  unique_sessions: number;
  page_views_by_day: Record<string, number>;
  recent_reports: ReportListItem[];
  reports_in_range: ReportListItem[];
};

const NAV: { id: Tab; label: string; hint: string; icon: React.ReactNode }[] = [
  {
    id: "overview",
    label: "Overview",
    hint: "Health & verdicts",
    icon: <LayoutDashboard size={18} aria-hidden />,
  },
  {
    id: "reports",
    label: "Reports",
    hint: "Fact-check history",
    icon: <FileText size={18} aria-hidden />,
  },
  {
    id: "config",
    label: "Config",
    hint: "Models & keys",
    icon: <Settings2 size={18} aria-hidden />,
  },
  {
    id: "traffic",
    label: "Traffic",
    hint: "Views & sessions",
    icon: <BarChart3 size={18} aria-hidden />,
  },
];

function reportHref(id: string): string {
  return `/report?id=${encodeURIComponent(id)}`;
}

function reportLabel(r: ReportListItem): string {
  if (r.url) return r.url;
  return "Text / image check";
}

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function DayBars({
  data,
  empty,
}: {
  data: Record<string, number>;
  empty: string;
}) {
  const entries = Object.entries(data);
  if (!entries.length) {
    return <p className="admin-empty">{empty}</p>;
  }
  const max = Math.max(...entries.map(([, n]) => n), 1);
  return (
    <ul className="admin-bars" aria-label="Daily counts">
      {entries.map(([day, count], i) => (
        <li key={day} style={{ animationDelay: `${i * 40}ms` }}>
          <span className="admin-bars-day">{day.slice(5)}</span>
          <div className="admin-bars-track">
            <div
              className="admin-bars-fill"
              style={{ width: `${Math.max(6, (count / max) * 100)}%` }}
            />
          </div>
          <strong>{count}</strong>
        </li>
      ))}
    </ul>
  );
}

export default function AdminDashboard() {
  const [user, setUser] = React.useState<User | null>(null);
  const [authReady, setAuthReady] = React.useState(false);
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [authError, setAuthError] = React.useState("");
  const [loggingIn, setLoggingIn] = React.useState(false);
  const [tab, setTab] = React.useState<Tab>("overview");
  const [range, setRange] = React.useState<"7d" | "30d">("7d");
  const [settings, setSettings] = React.useState<AdminSettings | null>(null);
  const [analytics, setAnalytics] = React.useState<Analytics | null>(null);
  const [loadError, setLoadError] = React.useState("");
  const [loadingData, setLoadingData] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [saveMsg, setSaveMsg] = React.useState("");
  const [saveOk, setSaveOk] = React.useState(false);

  const [form, setForm] = React.useState({
    use_local_llm: false,
    ollama_base_url: "",
    ollama_model: "",
    openai_api_key: "",
    openai_base_url: "",
    openai_model: "",
    tavily_api_key: "",
  });

  // Wait until mount so /runtime-config.js (HF/Docker) is available.
  const [firebaseReady, setFirebaseReady] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    const configured = isFirebaseConfigured();
    setFirebaseReady(configured);
    if (!configured) {
      setAuthReady(true);
      return;
    }
    const auth = getFirebaseAuth();
    return onAuthStateChanged(auth, (next) => {
      setUser(next);
      setAuthReady(true);
    });
  }, []);

  const withToken = React.useCallback(async () => {
    if (!user) throw new Error("Not signed in");
    return user.getIdToken();
  }, [user]);

  const refresh = React.useCallback(async () => {
    if (!user) return;
    setLoadError("");
    setLoadingData(true);
    try {
      const token = await withToken();
      const [nextSettings, nextAnalytics] = await Promise.all([
        adminFetch<AdminSettings>("/api/admin/settings", token),
        adminFetch<Analytics>(`/api/admin/analytics?range=${range}`, token),
      ]);
      setSettings(nextSettings);
      setAnalytics(nextAnalytics);
      setForm({
        use_local_llm: nextSettings.use_local_llm,
        ollama_base_url: nextSettings.ollama_base_url || "",
        ollama_model: nextSettings.ollama_model || "",
        openai_api_key: "",
        openai_base_url: nextSettings.openai_base_url || "",
        openai_model: nextSettings.openai_model || "",
        tavily_api_key: "",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load admin data";
      setLoadError(
        message === "Admin access required"
          ? "This account is not an admin. Sign in with an allowlisted email/password operator account (Google sign-in is for regular users only)."
          : message,
      );
    } finally {
      setLoadingData(false);
    }
  }, [user, range, withToken]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onLogin(event: React.FormEvent) {
    event.preventDefault();
    setAuthError("");
    setLoggingIn(true);
    try {
      const auth = getFirebaseAuth();
      await signInWithEmailAndPassword(auth, email.trim(), password);
    } catch (err) {
      reportAuthError(err, "admin_login");
      const message = friendlyAuthError(
        err,
        "Login failed. Check your email and password.",
      );
      if (message) setAuthError(message);
    } finally {
      setLoggingIn(false);
    }
  }

  async function onSave(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setSaveMsg("");
    setSaveOk(false);
    try {
      const token = await withToken();
      const body: Record<string, unknown> = {
        use_local_llm: form.use_local_llm,
        ollama_base_url: form.ollama_base_url,
        ollama_model: form.ollama_model,
        openai_base_url: form.openai_base_url || null,
        openai_model: form.openai_model,
      };
      if (form.openai_api_key.trim()) body.openai_api_key = form.openai_api_key.trim();
      if (form.tavily_api_key.trim()) body.tavily_api_key = form.tavily_api_key.trim();

      const updated = await adminFetch<AdminSettings>("/api/admin/settings", token, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setSettings(updated);
      setForm((prev) => ({ ...prev, openai_api_key: "", tavily_api_key: "" }));
      setSaveMsg("Saved — changes apply immediately.");
      setSaveOk(true);
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "Save failed");
      setSaveOk(false);
    } finally {
      setSaving(false);
    }
  }

  if (firebaseReady === null || !authReady) {
    return (
      <div className="admin-root">
        <div className="admin-boot">
          <Loader2 className="admin-spin" size={22} aria-hidden />
          <p>Loading console…</p>
        </div>
      </div>
    );
  }

  if (!firebaseReady) {
    return (
      <div className="admin-root">
        <div className="admin-login-wrap">
          <section className="admin-login-panel admin-reveal">
            <div className="admin-login-mark">
              <AlertTriangle size={22} aria-hidden />
            </div>
            <h1>Firebase not configured</h1>
            <p className="admin-lede">
              Set <code>NEXT_PUBLIC_FIREBASE_*</code> (and{" "}
              <code>NEXT_PUBLIC_ADMIN_PATH_SECRET</code> or{" "}
              <code>ADMIN_PATH_SECRET</code>) on the Space, then rebuild/restart
              so runtime-config can load.
            </p>
          </section>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="admin-root">
        <div className="admin-login-wrap">
          <section className="admin-login-panel admin-reveal">
            <div className="admin-login-brand">
              <div className="admin-login-mark">
                <Shield size={22} aria-hidden />
              </div>
              <div>
                <p className="eyebrow">TisTru</p>
                <h1>Operator access</h1>
              </div>
            </div>
            <p className="admin-lede">
              Sign in with a Firebase Auth account to manage models, keys, and
              traffic.
            </p>
            <form className="admin-form" onSubmit={onLogin}>
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="username"
                  placeholder="you@example.com"
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  placeholder="••••••••"
                />
              </label>
              {authError ? (
                <p className="admin-banner error" role="alert">
                  {authError}
                </p>
              ) : null}
              <button type="submit" className="admin-btn primary" disabled={loggingIn}>
                {loggingIn ? (
                  <>
                    <Loader2 className="admin-spin" size={16} aria-hidden />
                    Signing in…
                  </>
                ) : (
                  <>
                    <KeyRound size={16} aria-hidden />
                    Sign in
                  </>
                )}
              </button>
            </form>
          </section>
        </div>
      </div>
    );
  }

  const activeNav = NAV.find((n) => n.id === tab)!;
  const errorPct = analytics
    ? Math.round(analytics.fact_check_error_rate * 100)
    : null;
  const verdictEntries = Object.entries(analytics?.verdict_mix || {});
  const verdictTotal = verdictEntries.reduce((s, [, n]) => s + n, 0) || 1;

  return (
    <div className="admin-root">
      <div className="admin-frame admin-reveal">
        <aside className="admin-sidebar">
          <div className="admin-brand">
            <div className="admin-brand-mark">
              <SearchCheck size={20} aria-hidden />
            </div>
            <div>
              <strong>TisTru</strong>
              <span>Ops console</span>
            </div>
          </div>

          <nav className="admin-nav" aria-label="Admin sections">
            {NAV.map((item) => (
              <button
                key={item.id}
                type="button"
                className={tab === item.id ? "active" : ""}
                onClick={() => setTab(item.id)}
              >
                <span className="admin-nav-icon">{item.icon}</span>
                <span className="admin-nav-text">
                  <strong>{item.label}</strong>
                  <small>{item.hint}</small>
                </span>
              </button>
            ))}
          </nav>

          <div className="admin-sidebar-foot">
            <div className="admin-user">
              <span className="admin-user-dot" aria-hidden />
              <div>
                <strong>{user.email}</strong>
                <small>Signed in</small>
              </div>
            </div>
            <button
              type="button"
              className="admin-btn ghost block"
              onClick={() => void signOut(getFirebaseAuth())}
            >
              <LogOut size={16} aria-hidden />
              Sign out
            </button>
          </div>
        </aside>

        <div className="admin-main">
          <header className="admin-topbar">
            <div>
              <p className="eyebrow">{activeNav.hint}</p>
              <h1>{activeNav.label}</h1>
            </div>
            <div className="admin-topbar-actions">
              <div className="admin-range" role="group" aria-label="Date range">
                {(["7d", "30d"] as const).map((r) => (
                  <button
                    key={r}
                    type="button"
                    className={range === r ? "active" : ""}
                    onClick={() => setRange(r)}
                  >
                    {r === "7d" ? "7 days" : "30 days"}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="admin-btn ghost"
                onClick={() => void refresh()}
                disabled={loadingData}
              >
                <RefreshCw
                  size={16}
                  aria-hidden
                  className={loadingData ? "admin-spin" : undefined}
                />
                Refresh
              </button>
            </div>
          </header>

          {loadError ? (
            <p className="admin-banner error" role="alert">
              {loadError}
            </p>
          ) : null}

          {tab === "overview" ? (
            <div className="admin-stack">
              <section className="admin-metrics">
                <article className="admin-metric">
                  <div className="admin-metric-head">
                    <CheckCircle2 size={16} aria-hidden />
                    <span>Fact-checks</span>
                  </div>
                  <p className="admin-metric-value">
                    {analytics?.fact_check_ok ?? "—"}
                  </p>
                  <p className="admin-metric-sub">Successful in range</p>
                </article>
                <article className="admin-metric">
                  <div className="admin-metric-head">
                    <AlertTriangle size={16} aria-hidden />
                    <span>Errors</span>
                  </div>
                  <p className="admin-metric-value">
                    {analytics?.fact_check_error ?? "—"}
                  </p>
                  <p className="admin-metric-sub">
                    {errorPct === null ? "—" : `${errorPct}% error rate`}
                  </p>
                </article>
                <article className="admin-metric">
                  <div className="admin-metric-head">
                    <Sparkles size={16} aria-hidden />
                    <span>AI mode</span>
                  </div>
                  <p className="admin-metric-value">
                    {settings ? (settings.use_local_llm ? "Local" : "API") : "—"}
                  </p>
                  <p className="admin-metric-sub">
                    {settings?.use_local_llm
                      ? settings.ollama_model
                      : settings?.openai_model || "—"}
                  </p>
                </article>
                <article className="admin-metric">
                  <div className="admin-metric-head">
                    <Activity size={16} aria-hidden />
                    <span>Page views</span>
                  </div>
                  <p className="admin-metric-value">
                    {analytics?.page_views ?? "—"}
                  </p>
                  <p className="admin-metric-sub">
                    {analytics?.unique_sessions ?? "—"} unique sessions
                  </p>
                </article>
              </section>

              <div className="admin-split">
                <section className="admin-panel">
                  <header className="admin-panel-head">
                    <h2>Verdict mix</h2>
                    <span className="admin-chip">{range}</span>
                  </header>
                  {verdictEntries.length ? (
                    <ul className="admin-verdicts">
                      {verdictEntries.map(([label, count], i) => (
                        <li key={label} style={{ animationDelay: `${i * 50}ms` }}>
                          <div className="admin-verdicts-row">
                            <span>{label.replace(/_/g, " ")}</span>
                            <strong>{count}</strong>
                          </div>
                          <div className="admin-bars-track">
                            <div
                              className="admin-bars-fill soft"
                              style={{
                                width: `${Math.max(4, (count / verdictTotal) * 100)}%`,
                              }}
                            />
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="admin-empty">No fact-check events yet</p>
                  )}
                </section>

                <section className="admin-panel">
                  <header className="admin-panel-head">
                    <h2>Recent reports</h2>
                  </header>
                  {(analytics?.recent_reports || []).length ? (
                    <ul className="admin-reports">
                      {analytics!.recent_reports.map((r) => (
                        <li key={r.id}>
                          <span
                            className={`admin-verdict-pill ${r.verdict || "unknown"}`}
                          >
                            {(r.verdict || "unknown").replace(/_/g, " ")}
                          </span>
                          <div>
                            <a
                              href={reportHref(r.id)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="admin-report-link"
                              aria-label={`Open report ${r.id} in new tab`}
                            >
                              <strong>{reportLabel(r)}</strong>
                              <ExternalLink size={12} aria-hidden />
                            </a>
                            {r.context_summary ? (
                              <small>{r.context_summary}</small>
                            ) : null}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="admin-empty">No reports stored</p>
                  )}
                </section>
              </div>
            </div>
          ) : null}

          {tab === "config" ? (
            <form className="admin-stack" onSubmit={onSave}>
              <section className="admin-panel">
                <header className="admin-panel-head">
                  <div>
                    <h2>Model provider</h2>
                    <p>Switch between local Ollama and an online OpenAI-compatible API.</p>
                  </div>
                  <span className="admin-chip">
                    Updated {formatWhen(settings?.updated_at)}
                    {settings?.updated_by ? ` · ${settings.updated_by}` : ""}
                  </span>
                </header>

                <div className="admin-mode-toggle" role="group" aria-label="LLM mode">
                  <button
                    type="button"
                    className={!form.use_local_llm ? "active" : ""}
                    onClick={() =>
                      setForm((prev) => ({ ...prev, use_local_llm: false }))
                    }
                  >
                    <Sparkles size={16} aria-hidden />
                    Online API
                  </button>
                  <button
                    type="button"
                    className={form.use_local_llm ? "active" : ""}
                    onClick={() =>
                      setForm((prev) => ({ ...prev, use_local_llm: true }))
                    }
                  >
                    <Server size={16} aria-hidden />
                    Local Ollama
                  </button>
                </div>
              </section>

              <div className="admin-split">
                <section className={`admin-panel ${form.use_local_llm ? "" : "dimmed"}`}>
                  <header className="admin-panel-head">
                    <h2>Ollama</h2>
                    <p>Used when local mode is on.</p>
                  </header>
                  <div className="admin-form">
                    <label>
                      Base URL
                      <input
                        value={form.ollama_base_url}
                        onChange={(e) =>
                          setForm((prev) => ({
                            ...prev,
                            ollama_base_url: e.target.value,
                          }))
                        }
                        placeholder="http://localhost:11434/v1"
                      />
                    </label>
                    <label>
                      Model
                      <input
                        value={form.ollama_model}
                        onChange={(e) =>
                          setForm((prev) => ({
                            ...prev,
                            ollama_model: e.target.value,
                          }))
                        }
                        placeholder="llama3.1"
                      />
                    </label>
                  </div>
                </section>

                <section className={`admin-panel ${form.use_local_llm ? "dimmed" : ""}`}>
                  <header className="admin-panel-head">
                    <h2>OpenAI-compatible</h2>
                    <p>Used when online mode is on.</p>
                  </header>
                  <div className="admin-form">
                    <label>
                      API key
                      <span className="admin-field-meta">
                        current: {settings?.openai_api_key ?? "not set"}
                      </span>
                      <input
                        type="password"
                        value={form.openai_api_key}
                        placeholder="Leave blank to keep current"
                        onChange={(e) =>
                          setForm((prev) => ({
                            ...prev,
                            openai_api_key: e.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Base URL
                      <input
                        value={form.openai_base_url}
                        onChange={(e) =>
                          setForm((prev) => ({
                            ...prev,
                            openai_base_url: e.target.value,
                          }))
                        }
                        placeholder="https://api.openai.com/v1"
                      />
                    </label>
                    <label>
                      Model
                      <input
                        value={form.openai_model}
                        onChange={(e) =>
                          setForm((prev) => ({
                            ...prev,
                            openai_model: e.target.value,
                          }))
                        }
                        placeholder="gpt-4o-mini"
                      />
                    </label>
                  </div>
                </section>
              </div>

              <section className="admin-panel">
                <header className="admin-panel-head">
                  <div>
                    <h2>Evidence search</h2>
                    <p>Tavily powers web evidence. Leave blank to keep the current key.</p>
                  </div>
                </header>
                <div className="admin-form narrow">
                  <label>
                    Tavily API key
                    <span className="admin-field-meta">
                      current: {settings?.tavily_api_key ?? "not set"}
                    </span>
                    <input
                      type="password"
                      value={form.tavily_api_key}
                      placeholder="Leave blank to keep current"
                      onChange={(e) =>
                        setForm((prev) => ({
                          ...prev,
                          tavily_api_key: e.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
              </section>

              <div className="admin-save-bar">
                {saveMsg ? (
                  <p className={`admin-banner inline ${saveOk ? "ok" : "error"}`}>
                    {saveMsg}
                  </p>
                ) : (
                  <p className="admin-save-hint">
                    Secrets are never shown in full. Blank key fields keep the
                    existing value.
                  </p>
                )}
                <button type="submit" className="admin-btn primary" disabled={saving}>
                  {saving ? (
                    <>
                      <Loader2 className="admin-spin" size={16} aria-hidden />
                      Saving…
                    </>
                  ) : (
                    <>
                      <Settings2 size={16} aria-hidden />
                      Save configuration
                    </>
                  )}
                </button>
              </div>
            </form>
          ) : null}

          {tab === "reports" ? (
            <div className="admin-stack">
              <section className="admin-panel">
                <header className="admin-panel-head">
                  <div>
                    <h2>Fact-check reports</h2>
                    <p>All stored reports in the selected range.</p>
                  </div>
                  <span className="admin-chip">
                    {(analytics?.reports_in_range || []).length} · {range}
                  </span>
                </header>
                {(analytics?.reports_in_range || []).length ? (
                  <div className="admin-table-wrap">
                    <table className="admin-reports-table">
                      <thead>
                        <tr>
                          <th>Verdict</th>
                          <th>URL</th>
                          <th>Summary</th>
                          <th>Date</th>
                          <th>Open</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analytics!.reports_in_range.map((r) => (
                          <tr key={r.id}>
                            <td>
                              <span
                                className={`admin-verdict-pill ${r.verdict || "unknown"}`}
                              >
                                {(r.verdict || "unknown").replace(/_/g, " ")}
                              </span>
                            </td>
                            <td className="admin-table-url">
                              {reportLabel(r)}
                            </td>
                            <td className="admin-table-summary">
                              {r.context_summary || "—"}
                            </td>
                            <td className="admin-table-date">
                              {formatWhen(r.created_at)}
                            </td>
                            <td>
                              <a
                                href={reportHref(r.id)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="admin-btn ghost compact"
                              >
                                <ExternalLink size={14} aria-hidden />
                                Open
                              </a>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="admin-empty">No reports in this range</p>
                )}
              </section>
            </div>
          ) : null}

          {tab === "traffic" ? (
            <div className="admin-stack">
              <section className="admin-metrics two">
                <article className="admin-metric">
                  <div className="admin-metric-head">
                    <Eye size={16} aria-hidden />
                    <span>Page views</span>
                  </div>
                  <p className="admin-metric-value">
                    {analytics?.page_views ?? "—"}
                  </p>
                  <p className="admin-metric-sub">Across public routes</p>
                </article>
                <article className="admin-metric">
                  <div className="admin-metric-head">
                    <Users size={16} aria-hidden />
                    <span>Unique sessions</span>
                  </div>
                  <p className="admin-metric-value">
                    {analytics?.unique_sessions ?? "—"}
                  </p>
                  <p className="admin-metric-sub">sessionStorage IDs</p>
                </article>
              </section>

              <div className="admin-split">
                <section className="admin-panel">
                  <header className="admin-panel-head">
                    <h2>Views by day</h2>
                    <span className="admin-chip">{range}</span>
                  </header>
                  <DayBars
                    data={analytics?.page_views_by_day || {}}
                    empty="No page views yet"
                  />
                </section>
                <section className="admin-panel">
                  <header className="admin-panel-head">
                    <h2>Fact-checks by day</h2>
                    <span className="admin-chip">{range}</span>
                  </header>
                  <DayBars
                    data={analytics?.fact_checks_by_day || {}}
                    empty="No fact-checks yet"
                  />
                </section>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
