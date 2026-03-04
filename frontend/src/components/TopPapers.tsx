import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { TopPapersResponse } from "../types";
import { getTopPapers } from "../services/api";
import { FIELD_COLORS, FIELD_ABBR, FLOAT_POSITIONS } from "../constants";

interface TopPapersProps {
  getToken: () => Promise<string>;
}

interface FlatPaper {
  id: string;
  title: string;
  paperTitle: string;
  upvotes: number;
  style: string;
  field: string;
}

const ANIM_CLASSES = ["float-anim-a", "float-anim-b", "float-anim-c"];

export function TopPapers({ getToken }: TopPapersProps) {
  const [papers, setPapers] = useState<FlatPaper[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function fetch() {
      try {
        const token = await getToken();
        const data: TopPapersResponse = await getTopPapers(token);
        if (cancelled) return;

        const flat = Object.entries(data)
          .flatMap(([field, list]) => list.map((p) => ({ ...p, field })))
          .sort((a, b) => b.upvotes - a.upvotes)
          .slice(0, 12);

        setPapers(flat);
      } catch {
        // Non-critical
      }
    }

    fetch();
    return () => {
      cancelled = true;
    };
  }, [getToken]);

  if (papers.length === 0) return null;

  return (
    <div className="floating-papers">
      {papers.map((paper, i) => {
        const pos = FLOAT_POSITIONS[i % FLOAT_POSITIONS.length];
        const color = FIELD_COLORS[paper.field] || "#9ca3af";
        const abbr = FIELD_ABBR[paper.field] || "OT";
        const animClass = ANIM_CLASSES[i % ANIM_CLASSES.length];
        const delay = `${(i * 0.6).toFixed(1)}s`;
        const duration = `${6 + (i % 4)}s`;

        return (
          <Link
            to={`/story/${paper.id}`}
            key={paper.id}
            className={`floating-card ${animClass}`}
            style={
              {
                ...pos,
                "--float-delay": delay,
                "--float-dur": duration,
              } as React.CSSProperties
            }
          >
            <div className="floating-card-header">
              <span
                className="field-badge"
                style={{ backgroundColor: color }}
              >
                {abbr}
              </span>
              <span className="floating-card-field" style={{ color }}>
                {paper.field}
              </span>
            </div>
            <span className="floating-card-title">
              {(paper.title || paper.paperTitle || "Untitled").slice(0, 50)}
            </span>
            <span className="floating-card-meta">
              {"\u25B2"} {paper.upvotes} · {paper.style.replace("_", " ")}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
