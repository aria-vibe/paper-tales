import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { listUserJobs } from "../services/api";
import type { JobHistoryItem } from "../types";

interface MyStoriesProps {
  open: boolean;
  onClose: () => void;
  getToken: () => Promise<string>;
}

const PAGE_SIZE = 10;

const STYLE_LABELS: Record<string, string> = {
  fairy_tale: "Fairy Tale",
  adventure: "Adventure",
  sci_fi: "Sci-Fi",
  comic_book: "Comic Book",
};

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  complete: { label: "Complete", className: "status-complete" },
  processing: { label: "Processing", className: "status-processing" },
  error: { label: "Failed", className: "status-error" },
  timed_out: { label: "Timed Out", className: "status-error" },
};

function extractPaperName(url: string): string {
  try {
    const u = new URL(url);
    const parts = u.pathname.split("/").filter(Boolean);
    return parts[parts.length - 1] || u.hostname;
  } catch {
    return url;
  }
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export function MyStories({ open, onClose, getToken }: MyStoriesProps) {
  const [jobs, setJobs] = useState<JobHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [initialLoad, setInitialLoad] = useState(true);
  const offsetRef = useRef(0);
  const drawerRef = useRef<HTMLDivElement>(null);

  const loadPage = useCallback(
    async (reset: boolean) => {
      setLoading(true);
      try {
        const token = await getToken();
        const offset = reset ? 0 : offsetRef.current;
        const { jobs: fetched } = await listUserJobs(token, PAGE_SIZE, offset);
        if (reset) {
          setJobs(fetched);
          offsetRef.current = fetched.length;
        } else {
          setJobs((prev) => [...prev, ...fetched]);
          offsetRef.current += fetched.length;
        }
        setHasMore(fetched.length === PAGE_SIZE);
      } catch {
        // silently fail — user can retry
      } finally {
        setLoading(false);
        setInitialLoad(false);
      }
    },
    [getToken]
  );

  // Lazy load when drawer opens
  useEffect(() => {
    if (open) {
      setInitialLoad(true);
      setHasMore(true);
      offsetRef.current = 0;
      loadPage(true);
    }
  }, [open, loadPage]);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Close on click outside drawer
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        drawerRef.current &&
        !drawerRef.current.contains(e.target as Node)
      ) {
        onClose();
      }
    };
    // Delay to avoid closing on the same click that opened it
    const timeout = setTimeout(() => {
      window.addEventListener("mousedown", handler);
    }, 0);
    return () => {
      clearTimeout(timeout);
      window.removeEventListener("mousedown", handler);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="drawer-overlay">
      <aside className="drawer" ref={drawerRef} role="dialog" aria-label="My Stories">
        <div className="drawer-header">
          <h2 className="drawer-title">My Stories</h2>
          <button className="drawer-close" onClick={onClose} aria-label="Close">
            {"\u2715"}
          </button>
        </div>

        <div className="drawer-body">
          {initialLoad && loading ? (
            <div className="drawer-loading">
              <div className="uploader-spinner" />
              <p className="drawer-loading-text">Loading stories...</p>
            </div>
          ) : jobs.length === 0 ? (
            <p className="drawer-empty">
              No stories yet. Generate your first story!
            </p>
          ) : (
            <>
              <ul className="drawer-list">
                {jobs.map((job) => {
                  const status = STATUS_LABELS[job.status] ?? {
                    label: job.status,
                    className: "",
                  };
                  const content = (
                    <div className="drawer-item-inner">
                      <div className="drawer-item-top">
                        <span className={`drawer-status ${status.className}`}>
                          {status.label}
                        </span>
                        <span className="drawer-date">
                          {formatDate(job.created_at)}
                        </span>
                      </div>
                      <p className="drawer-item-paper">
                        {extractPaperName(job.paper_url)}
                      </p>
                      <div className="drawer-item-meta">
                        <span className="drawer-chip">
                          Ages {job.age_group}
                        </span>
                        <span className="drawer-chip">
                          {STYLE_LABELS[job.style] ?? job.style}
                        </span>
                      </div>
                    </div>
                  );

                  return (
                    <li key={job.job_id} className="drawer-item">
                      {job.status === "complete" && job.story_id ? (
                        <Link
                          to={`/story/${job.story_id}`}
                          className="drawer-item-link"
                          onClick={onClose}
                        >
                          {content}
                        </Link>
                      ) : (
                        <div className="drawer-item-static">{content}</div>
                      )}
                    </li>
                  );
                })}
              </ul>

              {hasMore && (
                <button
                  className="drawer-load-more"
                  onClick={() => loadPage(false)}
                  disabled={loading}
                >
                  {loading ? "Loading..." : "Load more"}
                </button>
              )}
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
