import { useState, useRef, useEffect } from "react";

// ─── Design tokens ───────────────────────────────────────────────────────────
const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Syne:wght@400;600;700;800&display=swap');

  :root {
    --bg: #0a0c10;
    --surface: #111318;
    --surface2: #181c22;
    --border: #1f2430;
    --accent: #00e5a0;
    --accent2: #4da6ff;
    --warn: #f5c842;
    --danger: #ff5c5c;
    --text: #e8eaf0;
    --muted: #5a6070;
    --dim: #353c4a;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    min-height: 100vh;
  }

  .app {
    max-width: 1100px;
    margin: 0 auto;
    padding: 48px 24px;
  }

  /* ── Header ── */
  .header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 48px;
    gap: 24px;
  }
  .logo {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .logo-icon {
    width: 44px; height: 44px;
    background: var(--accent);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px;
    flex-shrink: 0;
  }
  .logo-text h1 {
    font-family: 'Syne', sans-serif;
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: var(--text);
    line-height: 1;
  }
  .logo-text p {
    font-size: 11px;
    color: var(--muted);
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .badge {
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
    color: var(--accent);
    font-size: 10px;
    padding: 4px 10px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 600;
    align-self: flex-start;
    margin-top: 4px;
  }

  /* ── Form ── */
  .form-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 28px;
    margin-bottom: 32px;
  }
  .form-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
  .input-group {
    flex: 1;
    min-width: 260px;
  }
  .input-label {
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    display: block;
    margin-bottom: 8px;
  }
  .domain-input {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 16px;
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 14px;
    outline: none;
    transition: border-color 0.15s;
  }
  .domain-input:focus {
    border-color: var(--accent);
  }
  .domain-input::placeholder { color: var(--muted); }

  .num-controls {
    display: flex;
    gap: 12px;
  }
  .num-group {
    display: flex;
    flex-direction: column;
  }
  .num-group select {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    outline: none;
    cursor: pointer;
    min-width: 90px;
  }
  .num-group select:focus { border-color: var(--accent); }

  .run-btn {
    background: var(--accent);
    color: #000;
    border: none;
    border-radius: 8px;
    padding: 12px 28px;
    font-family: 'Syne', sans-serif;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    white-space: nowrap;
    transition: opacity 0.15s, transform 0.1s;
    align-self: flex-end;
    letter-spacing: 0.3px;
  }
  .run-btn:hover:not(:disabled) { opacity: 0.85; transform: translateY(-1px); }
  .run-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .server-note {
    margin-top: 14px;
    font-size: 11px;
    color: var(--muted);
  }
  .server-note code {
    color: var(--accent2);
    background: color-mix(in srgb, var(--accent2) 8%, transparent);
    padding: 1px 5px;
    border-radius: 3px;
  }

  /* ── Stage tracker ── */
  .stages {
    display: flex;
    gap: 0;
    margin-bottom: 32px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }
  .stage-item {
    flex: 1;
    padding: 16px 20px;
    border-right: 1px solid var(--border);
    position: relative;
    transition: background 0.2s;
  }
  .stage-item:last-child { border-right: none; }
  .stage-item.active { background: color-mix(in srgb, var(--accent) 6%, transparent); }
  .stage-item.done { background: color-mix(in srgb, var(--accent) 4%, transparent); }
  .stage-item.error { background: color-mix(in srgb, var(--danger) 6%, transparent); }

  .stage-num {
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .stage-name {
    font-size: 12px;
    font-weight: 500;
    color: var(--dim);
  }
  .stage-item.active .stage-name { color: var(--accent); }
  .stage-item.done .stage-name { color: var(--text); }
  .stage-item.error .stage-name { color: var(--danger); }

  .stage-dot {
    position: absolute;
    top: 16px; right: 16px;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--dim);
  }
  .stage-item.active .stage-dot { background: var(--accent); animation: pulse 1s infinite; }
  .stage-item.done .stage-dot { background: var(--accent); animation: none; }
  .stage-item.error .stage-dot { background: var(--danger); animation: none; }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  /* ── Log ── */
  .log-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 32px;
    overflow: hidden;
  }
  .log-header {
    padding: 12px 18px;
    border-bottom: 1px solid var(--border);
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .log-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); }
  .log-body {
    padding: 16px 18px;
    max-height: 220px;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--dim) transparent;
  }
  .log-line {
    font-size: 12px;
    line-height: 1.9;
    color: var(--muted);
    white-space: pre-wrap;
    word-break: break-all;
  }
  .log-line.ok   { color: var(--accent); }
  .log-line.err  { color: var(--danger); }
  .log-line.warn { color: var(--warn); }
  .log-line.dim  { color: var(--dim); }

  /* ── Email results ── */
  .results-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 12px;
  }
  .results-title {
    font-family: 'Syne', sans-serif;
    font-size: 20px;
    font-weight: 700;
  }
  .results-meta {
    font-size: 11px;
    color: var(--muted);
  }
  .results-meta span {
    color: var(--accent);
    font-weight: 600;
  }

  .stats-row {
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
    flex-wrap: wrap;
  }
  .stat-chip {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 18px;
    flex: 1;
    min-width: 120px;
  }
  .stat-chip .num {
    font-family: 'Syne', sans-serif;
    font-size: 24px;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 4px;
  }
  .stat-chip .label {
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.8px;
  }
  .stat-chip.accent .num { color: var(--accent); }
  .stat-chip.blue .num   { color: var(--accent2); }
  .stat-chip.warn .num   { color: var(--warn); }

  /* filter bar */
  .filter-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }
  .filter-btn {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 7px 14px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.15s;
  }
  .filter-btn.active {
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    border-color: color-mix(in srgb, var(--accent) 35%, transparent);
    color: var(--accent);
  }
  .copy-all-btn {
    margin-left: auto;
    background: color-mix(in srgb, var(--accent2) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--accent2) 30%, transparent);
    border-radius: 6px;
    padding: 7px 14px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--accent2);
    cursor: pointer;
    transition: all 0.15s;
  }
  .copy-all-btn:hover { opacity: 0.75; }

  /* email cards */
  .email-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .email-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    transition: border-color 0.15s;
  }
  .email-card:hover { border-color: var(--dim); }

  .avatar {
    width: 38px; height: 38px;
    border-radius: 8px;
    background: var(--surface2);
    display: flex; align-items: center; justify-content: center;
    font-size: 15px;
    font-weight: 700;
    flex-shrink: 0;
    font-family: 'Syne', sans-serif;
    color: var(--accent);
  }

  .email-info {
    flex: 1;
    min-width: 0;
  }
  .email-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 2px;
    font-family: 'Syne', sans-serif;
  }
  .email-role {
    font-size: 11px;
    color: var(--muted);
    margin-bottom: 4px;
  }
  .email-address {
    font-size: 13px;
    color: var(--accent);
    font-weight: 500;
    letter-spacing: 0.2px;
  }

  .email-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .conf-bar {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
  }
  .conf-num {
    font-size: 12px;
    font-weight: 600;
  }
  .conf-track {
    width: 64px;
    height: 3px;
    background: var(--dim);
    border-radius: 2px;
    overflow: hidden;
  }
  .conf-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.4s;
  }

  .pill {
    font-size: 9px;
    padding: 3px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 600;
    border: 1px solid transparent;
  }
  .pill.verified {
    color: var(--accent);
    border-color: color-mix(in srgb, var(--accent) 30%, transparent);
    background: color-mix(in srgb, var(--accent) 8%, transparent);
  }
  .pill.unverified {
    color: var(--warn);
    border-color: color-mix(in srgb, var(--warn) 30%, transparent);
    background: color-mix(in srgb, var(--warn) 8%, transparent);
  }
  .pill.mx {
    color: var(--accent2);
    border-color: color-mix(in srgb, var(--accent2) 25%, transparent);
    background: color-mix(in srgb, var(--accent2) 8%, transparent);
  }

  .copy-btn {
    width: 30px; height: 30px;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.15s;
    flex-shrink: 0;
  }
  .copy-btn:hover { border-color: var(--accent); }
  .copy-btn.copied { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 15%, transparent); }

  /* domain group label */
  .domain-group {
    margin-top: 20px;
  }
  .domain-label {
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 8px;
    padding-left: 4px;
    border-left: 2px solid var(--accent2);
    padding-left: 10px;
  }

  .empty-state {
    text-align: center;
    padding: 64px 24px;
    color: var(--muted);
  }
  .empty-state .icon { font-size: 40px; margin-bottom: 16px; opacity: 0.4; }
  .empty-state p { font-size: 13px; }

  /* search */
  .search-input {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 9px 14px;
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    outline: none;
    width: 220px;
    transition: border-color 0.15s;
  }
  .search-input:focus { border-color: var(--accent); }
  .search-input::placeholder { color: var(--muted); }
`;

// ─── Stage definitions ────────────────────────────────────────────────────────
const STAGES = [
  { label: "Company Discovery" },
  { label: "Lead Discovery" },
  { label: "Email Resolution" },
];

// ─── Utility ─────────────────────────────────────────────────────────────────
function confColor(conf) {
  if (conf >= 70) return "var(--accent)";
  if (conf >= 40) return "var(--warn)";
  return "var(--danger)";
}

function initials(name) {
  return (name || "?").split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase();
}

// ─── Copy hook ────────────────────────────────────────────────────────────────
function useCopy() {
  const [copied, setCopied] = useState(null);
  const copy = (text, id) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(id);
      setTimeout(() => setCopied(null), 1500);
    });
  };
  return { copied, copy };
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function VocalPipeline() {
  const [domain, setDomain] = useState("");
  const [limit, setLimit]   = useState(5);
  const [perCo, setPerCo]   = useState(2);
  const [running, setRunning] = useState(false);
  const [logs, setLogs]       = useState([]);
  const [stages, setStages]   = useState([null, null, null]); // null | "active" | "done" | "error"
  const [resolved, setResolved] = useState([]);
  const [filter, setFilter]   = useState("all");
  const [search, setSearch]   = useState("");
  const [hasRun, setHasRun]   = useState(false);
  const [serverUrl, setServerUrl] = useState("http://localhost:8000");

  const logRef  = useRef(null);
  const esRef   = useRef(null);
  const { copied, copy } = useCopy();

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  // cleanup on unmount
  useEffect(() => () => esRef.current?.close(), []);

  const addLog = (msg, type = "") => setLogs(prev => [...prev, { msg, type }]);

  const setStage = (idx, status) =>
    setStages(prev => prev.map((s, i) => (i === idx ? status : s)));

  async function runPipeline() {
    if (!domain.trim()) return;
    setRunning(true);
    setLogs([]);
    setResolved([]);
    setStages([null, null, null]);
    setHasRun(true);

    try {
      const resp = await fetch(`${serverUrl}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seed_domain: domain.trim(), limit, per_co: perCo }),
      });

      if (!resp.ok) {
        addLog(`Server error: ${resp.status} ${resp.statusText}`, "err");
        setRunning(false);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const lines = part.trim().split("\n");
          let event = "", data = "";
          for (const l of lines) {
            if (l.startsWith("event: ")) event = l.slice(7);
            if (l.startsWith("data: ")) data = l.slice(6);
          }
          if (!event || !data) continue;
          try {
            const payload = JSON.parse(data);
            if (event === "log")      addLog(payload.msg, payload.type);
            if (event === "stage")    setStage(payload.stage, payload.status);
            if (event === "resolved") setResolved(payload.resolved || []);
            if (event === "done")     setRunning(false);
          } catch {  }
        }
      }
    } catch (err) {
      addLog(`Connection error: ${err.message}`, "err");
      addLog("Make sure your FastAPI server is running on the URL above.", "warn");
    } finally {
      setRunning(false);
    }
  }

  // ── Filtered emails ──────────────────────────────────────────────────────
  const filtered = resolved.filter(r => {
    if (filter === "verified"   && !r.email_verified) return false;
    if (filter === "unverified" &&  r.email_verified) return false;
    if (search && !(
      r.name?.toLowerCase().includes(search.toLowerCase()) ||
      r.email?.toLowerCase().includes(search.toLowerCase()) ||
      r.role?.toLowerCase().includes(search.toLowerCase()) ||
      r.domain?.toLowerCase().includes(search.toLowerCase())
    )) return false;
    return true;
  });

  // group by domain
  const grouped = {};
  for (const r of filtered) {
    const d = r.domain || "unknown";
    if (!grouped[d]) grouped[d] = [];
    grouped[d].push(r);
  }

  const verified = resolved.filter(r => r.email_verified).length;
  const mxOk     = resolved.filter(r => r.mx_valid).length;
  const avgConf  = resolved.length
    ? Math.round(resolved.reduce((s, r) => s + (r.email_confidence || 0), 0) / resolved.length)
    : 0;

  function copyAll() {
    const text = filtered.map(r => `${r.name}\t${r.role}\t${r.email}`).join("\n");
    navigator.clipboard.writeText(text);
  }

  return (
    <>
      <style>{CSS}</style>
      <div className="app">

        {/* Header */}
        <div className="header">
          <div className="logo">
            <div className="logo-icon">📡</div>
            <div className="logo-text">
              <h1>Vocal</h1>
              <p>Email Pipeline</p>
            </div>
          </div>
          <div className="badge">Email Discovery</div>
        </div>

        {/* Form */}
        <div className="form-card">
          <div className="form-row">
            <div className="input-group">
              <label className="input-label">Seed Domain</label>
              <input
                className="domain-input"
                value={domain}
                onChange={e => setDomain(e.target.value)}
                placeholder="openai.com"
                onKeyDown={e => e.key === "Enter" && !running && runPipeline()}
              />
            </div>
            <div className="num-controls">
              <div className="num-group">
                <label className="input-label">Companies</label>
                <select value={limit} onChange={e => setLimit(+e.target.value)}>
                  {[3,5,8,10,15].map(n => <option key={n}>{n}</option>)}
                </select>
              </div>
              <div className="num-group">
                <label className="input-label">Per Co</label>
                <select value={perCo} onChange={e => setPerCo(+e.target.value)}>
                  {[1,2,3,4,5].map(n => <option key={n}>{n}</option>)}
                </select>
              </div>
            </div>
            <button className="run-btn" onClick={runPipeline} disabled={running || !domain.trim()}>
              {running ? "Running…" : "Run Pipeline"}
            </button>
          </div>
          <div className="form-row" style={{marginTop: 14, gap: 8, alignItems: "center"}}>
            <span className="input-label" style={{margin:0}}>Server URL:</span>
            <input
              className="domain-input"
              style={{width: 240, padding: "8px 12px", fontSize: 12}}
              value={serverUrl}
              onChange={e => setServerUrl(e.target.value)}
            />
          </div>
          <p className="server-note">
            Start your backend: <code>cd vocal_app && uvicorn server:app --reload --port 8000</code>
          </p>
        </div>

        {/* Stage tracker — only when running or done */}
        {(running || hasRun) && (
          <div className="stages">
            {STAGES.map((s, i) => (
              <div key={i} className={`stage-item ${stages[i] || ""}`}>
                <div className="stage-num">Stage {i + 1}</div>
                <div className="stage-name">{s.label}</div>
                <div className="stage-dot" />
              </div>
            ))}
          </div>
        )}

        {/* Logs */}
        {(running || logs.length > 0) && (
          <div className="log-card">
            <div className="log-header">
              <div className="log-dot" />
              Live Output
            </div>
            <div className="log-body" ref={logRef}>
              {logs.map((l, i) => (
                <div key={i} className={`log-line ${l.type || ""}`}>{l.msg}</div>
              ))}
              {running && <div className="log-line dim">▌</div>}
            </div>
          </div>
        )}

        {/* Email Results */}
        {resolved.length > 0 && (
          <div>
            <div className="results-header">
              <h2 className="results-title">Discovered Emails</h2>
              <div className="results-meta">
                <span>{resolved.length}</span> contacts resolved
              </div>
            </div>

            {/* Stats */}
            <div className="stats-row">
              <div className="stat-chip accent">
                <div className="num">{resolved.length}</div>
                <div className="label">Total Emails</div>
              </div>
              <div className="stat-chip accent">
                <div className="num">{verified}</div>
                <div className="label">Verified</div>
              </div>
              <div className="stat-chip blue">
                <div className="num">{mxOk}</div>
                <div className="label">MX Valid</div>
              </div>
              <div className="stat-chip warn">
                <div className="num">{avgConf}%</div>
                <div className="label">Avg Confidence</div>
              </div>
            </div>

            {/* Filter bar */}
            <div className="filter-bar">
              {["all","verified","unverified"].map(f => (
                <button
                  key={f}
                  className={`filter-btn ${filter === f ? "active" : ""}`}
                  onClick={() => setFilter(f)}
                >
                  {f === "all" ? `All (${resolved.length})` :
                   f === "verified" ? `Verified (${verified})` :
                   `Unverified (${resolved.length - verified})`}
                </button>
              ))}
              <input
                className="search-input"
                placeholder="Search name, email, role…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
              <button className="copy-all-btn" onClick={copyAll}>⎘ Copy All</button>
            </div>

            {/* Email cards grouped by domain */}
            {filtered.length === 0 ? (
              <div className="empty-state">
                <div className="icon">🔍</div>
                <p>No emails match the current filter.</p>
              </div>
            ) : (
              <div className="email-grid">
                {Object.entries(grouped).map(([dom, contacts]) => (
                  <div key={dom} className="domain-group">
                    <div className="domain-label">{dom}</div>
                    {contacts.map((r, i) => {
                      const id = `${dom}-${i}`;
                      const conf = r.email_confidence || 0;
                      return (
                        <div key={id} className="email-card" style={{marginBottom: 6}}>
                          <div className="avatar">{initials(r.name)}</div>
                          <div className="email-info">
                            <div className="email-name">{r.name || "Unknown"}</div>
                            <div className="email-role">{r.role || "—"}</div>
                            <div className="email-address">{r.email || "—"}</div>
                          </div>
                          <div className="email-meta">
                            <div className="conf-bar">
                              <span className="conf-num" style={{color: confColor(conf)}}>{conf}%</span>
                              <div className="conf-track">
                                <div className="conf-fill" style={{width: `${conf}%`, background: confColor(conf)}} />
                              </div>
                            </div>
                            {r.email_verified
                              ? <span className="pill verified">✓ Verified</span>
                              : <span className="pill unverified">~ Unverified</span>}
                            {r.mx_valid && <span className="pill mx">MX✓</span>}
                            <button
                              className={`copy-btn ${copied === id ? "copied" : ""}`}
                              onClick={() => copy(r.email, id)}
                              title="Copy email"
                            >
                              {copied === id ? "✓" : "⎘"}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Empty state — after run with no results */}
        {hasRun && !running && resolved.length === 0 && (
          <div className="empty-state">
            <div className="icon">📭</div>
            <p>No emails resolved. Check your API keys in <code>.env</code> and try again.</p>
          </div>
        )}

      </div>
    </>
  );
}
