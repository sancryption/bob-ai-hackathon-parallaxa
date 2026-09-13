/**
 * JobPoller — renders job state with live polling.
 *
 * States:
 *  queued   → spinner + "Queued"
 *  running  → progress bar + percent + message
 *  complete → renders children with the job
 *  failed   → error panel with job.error
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/apiClient";
import type { JobRead } from "../types/api";
import { Loading, ErrorPanel, ProgressBar } from "./shared";

const POLL_MS = 1500;

interface JobPollerProps {
  jobId: number;
  onComplete?: (job: JobRead) => void;
  children: (job: JobRead) => React.ReactNode;
}

export function JobPoller({ jobId, onComplete, children }: JobPollerProps) {
  const [job, setJob] = useState<JobRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const poll = useCallback(async () => {
    try {
      const res = await api.getJob(jobId);
      setJob(res.data);
      if (res.data.status === "complete") {
        onComplete?.(res.data);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load job");
    }
  }, [jobId, onComplete]);

  useEffect(() => {
    let cancelled = false;

    async function schedule() {
      await poll();
      if (!cancelled) {
        setJob((current) => {
          if (!current) return current;
          if (current.status === "queued" || current.status === "running") {
            timerRef.current = setTimeout(schedule, POLL_MS);
          }
          return current;
        });
      }
    }

    schedule();
    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [poll]);

  if (error) return <ErrorPanel message={error} onRetry={poll} />;
  if (!job) return <Loading text="Checking job status…" />;

  if (job.status === "queued") {
    return <Loading text="Job queued — waiting to start…" />;
  }

  if (job.status === "running") {
    const p = job.progress;
    return (
      <ProgressBar
        percent={p?.percent ?? 0}
        message={p?.message ?? "Running…"}
        step={p?.step}
      />
    );
  }

  if (job.status === "failed") {
    return (
      <ErrorPanel
        code="JOB_FAILED"
        message={job.error ?? "Job failed without a message."}
      />
    );
  }

  // complete
  return <>{children(job)}</>;
}
