/** Shared micro-components used across the app. */
import type { ReactNode } from "react";

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------

interface BadgeProps { value: string; label?: string; }
export function Badge({ value, label }: BadgeProps) {
  const cls = value.replace(/[^a-z0-9_]/g, "_");
  return (
    <span className={`sr-badge sr-badge-${cls}`}>{label ?? value}</span>
  );
}

// ---------------------------------------------------------------------------
// MetricCard
// ---------------------------------------------------------------------------

interface MetricCardProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
}
export function MetricCard({ label, value, sub }: MetricCardProps) {
  return (
    <div className="sr-metric-card">
      <div className="sr-metric-label">{label}</div>
      <div className="sr-metric-value">{value}</div>
      {sub && <div className="sr-metric-sub">{sub}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------

export function Loading({ text = "Loading…" }: { text?: string }) {
  return (
    <div className="sr-loading">
      <span className="sr-spinner" role="status" aria-label="loading" />
      <span>{text}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ErrorPanel
// ---------------------------------------------------------------------------

interface ErrorPanelProps {
  code?: string;
  message: string;
  onRetry?: () => void;
}
export function ErrorPanel({ code, message, onRetry }: ErrorPanelProps) {
  return (
    <div className="sr-error-panel" role="alert">
      {code && <div className="sr-error-code">{code}</div>}
      <div>{message}</div>
      {onRetry && (
        <button className="sr-btn sr-btn-secondary" style={{ marginTop: "0.75rem" }} onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

interface EmptyProps { icon?: string; message: string; action?: ReactNode; }
export function Empty({ icon = "📭", message, action }: EmptyProps) {
  return (
    <div className="sr-empty">
      <div className="sr-empty-icon">{icon}</div>
      <p>{message}</p>
      {action && <div style={{ marginTop: "0.75rem" }}>{action}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProgressBar
// ---------------------------------------------------------------------------

interface ProgressBarProps {
  percent: number;
  message?: string;
  step?: string;
}
export function ProgressBar({ percent, message, step }: ProgressBarProps) {
  return (
    <div className="sr-progress-wrap">
      <div className="sr-progress-meta">
        <span>{message ?? "Processing…"}</span>
        <span>{Math.round(percent)}%</span>
      </div>
      <div className="sr-progress-bar-track" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
        <div className="sr-progress-bar-fill" style={{ width: `${percent}%` }} />
      </div>
      {step && <div style={{ fontSize: "0.75rem", color: "var(--text)", marginTop: "0.25rem" }}>{step}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ScoreBar
// ---------------------------------------------------------------------------

export function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  return (
    <div className="sr-score-bar-wrap">
      <div className="sr-score-bar-track">
        <div className="sr-score-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="sr-score-pct">{pct}%</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DisclaimerPanel
// ---------------------------------------------------------------------------

interface DisclaimerProps { text: string; }
export function DisclaimerPanel({ text }: DisclaimerProps) {
  return (
    <div className="sr-disclaimer">
      <strong>⚠ Assumptions & Limitations: </strong>{text}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Drawer
// ---------------------------------------------------------------------------

interface DrawerProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}
export function Drawer({ title, onClose, children }: DrawerProps) {
  return (
    <div className="sr-drawer-overlay" onClick={onClose}>
      <div className="sr-drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={title}>
        <div className="sr-drawer-header">
          <h3 className="sr-drawer-title">{title}</h3>
          <button className="sr-btn sr-btn-ghost" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

interface TabsProps {
  tabs: string[];
  active: string;
  onChange: (t: string) => void;
}
export function Tabs({ tabs, active, onChange }: TabsProps) {
  return (
    <div className="sr-tabs">
      {tabs.map((t) => (
        <button
          key={t}
          className={`sr-tab ${active === t ? "active" : ""}`}
          onClick={() => onChange(t)}
        >
          {t}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ExportButton
// ---------------------------------------------------------------------------

interface ExportButtonProps {
  label: string;
  onExport: () => Promise<void>;
  disabled?: boolean;
}
export function ExportButton({ label, onExport, disabled }: ExportButtonProps) {
  async function handleClick() {
    try { await onExport(); } catch { /* surfaced by caller */ }
  }
  return (
    <button className="sr-btn sr-btn-secondary" disabled={disabled} onClick={handleClick}>
      ↓ {label}
    </button>
  );
}
