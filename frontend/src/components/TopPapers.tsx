import { useEffect, useState } from "react";
import type { TopPapersResponse } from "../types";
import { getTopPapers } from "../services/api";

interface TopPapersProps {
  getToken: () => Promise<string>;
}

export function TopPapers({ getToken }: TopPapersProps) {
  const [data, setData] = useState<TopPapersResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetch() {
      try {
        const token = await getToken();
        const result = await getTopPapers(token);
        if (!cancelled) setData(result);
      } catch {
        // Non-critical — just don't show top papers
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetch();
    return () => { cancelled = true; };
  }, [getToken]);

  if (loading || !data || Object.keys(data).length === 0) {
    return null;
  }

  return (
    <section className="top-papers">
      <h2>Top Rated Stories</h2>
      {Object.entries(data).map(([field, papers]) => (
        <div key={field} className="top-papers-field">
          <h3>{field}</h3>
          <ul>
            {papers.map((paper) => (
              <li key={paper.id}>
                <a href={`/story/${paper.id}`}>
                  {paper.title || paper.paperTitle}
                </a>
                <span className="top-paper-meta">
                  {" "}&#9650; {paper.upvotes} &middot; {paper.ageGroup} &middot; {paper.style.replace("_", " ")}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
