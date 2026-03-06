import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { TopPapersResponse } from "../types";
import { getTopPapers } from "../services/api";
import { FIELD_COLORS, FIELD_ICONS } from "../constants";

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

// 3 concentric rings: inner (most liked) → outer (least liked)
// Radii are large enough that cards clear the center content zone;
// a CSS radial mask on .floating-papers fades any stragglers.
const RINGS = [
  { radius: 30, count: 4, startAngle: -55 },
  { radius: 40, count: 4, startAngle: -10 },
  { radius: 48, count: 4, startAngle: -38 },
];

function getRadialPos(index: number): { left: string; top: string } {
  let acc = 0;
  for (const ring of RINGS) {
    if (index < acc + ring.count) {
      const pos = index - acc;
      const angleDeg = ring.startAngle + pos * (360 / ring.count);
      const angleRad = angleDeg * (Math.PI / 180);
      let x = 50 + ring.radius * Math.cos(angleRad);
      let y = 50 + ring.radius * 0.8 * Math.sin(angleRad);
      // Clamp to viewport (card ~320×110px)
      x = Math.max(2, Math.min(x, 76));
      y = Math.max(8, Math.min(y, 84));
      return {
        left: `${x.toFixed(1)}%`,
        top: `${y.toFixed(1)}%`,
      };
    }
    acc += ring.count;
  }
  return { left: "5%", top: "5%" };
}

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
        const pos = getRadialPos(i);
        const tier = i < 4 ? 0 : i < 8 ? 1 : 2;
        const color = FIELD_COLORS[paper.field] || "#9ca3af";
        const icon = FIELD_ICONS[paper.field] || FIELD_ICONS["Other"];
        const animClass = ANIM_CLASSES[i % ANIM_CLASSES.length];
        const delay = `${(i * 0.6).toFixed(1)}s`;
        const duration = `${6 + (i % 4)}s`;

        return (
          <Link
            to={`/story/${paper.id}`}
            key={paper.id}
            className={`floating-card floating-tier-${tier} ${animClass}`}
            style={
              {
                ...pos,
                "--float-delay": delay,
                "--float-dur": duration,
              } as React.CSSProperties
            }
          >
            <div className="floating-card-header">
              <img
                className="field-icon"
                src={icon}
                alt={paper.field}
                width={28}
                height={28}
              />
              <span className="floating-card-field" style={{ color }}>
                {paper.field}
              </span>
            </div>
            <span className="floating-card-title">
              {paper.title || "Untitled"}
            </span>
            {paper.paperTitle && (
              <span className="floating-card-paper">
                {paper.paperTitle}
              </span>
            )}
            <span className="floating-card-meta">
              {"\u25B2"} {paper.upvotes} · {paper.style.replace("_", " ")}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
