import { useState, useEffect } from "react";
import type { AgeGroup, GenerationRequest, QuotaInfo, StoryStyle } from "../types";
import { getQuota } from "../services/api";

interface PaperUploaderProps {
  onSubmit: (request: GenerationRequest) => void;
  disabled?: boolean;
  getToken: () => Promise<string>;
}

const AGE_GROUPS: { value: AgeGroup; label: string }[] = [
  { value: "6-9", label: "Ages 6-9" },
  { value: "10-13", label: "Ages 10-13" },
  { value: "14-17", label: "Ages 14-17" },
];

const STORY_STYLES: { value: StoryStyle; label: string }[] = [
  { value: "fairy_tale", label: "Fairy Tale" },
  { value: "adventure", label: "Adventure" },
  { value: "sci_fi", label: "Sci-Fi" },
  { value: "comic_book", label: "Comic Book" },
];

export function PaperUploader({ onSubmit, disabled, getToken }: PaperUploaderProps) {
  const [paperUrl, setPaperUrl] = useState("");
  const [ageGroup, setAgeGroup] = useState<AgeGroup>("10-13");
  const [style, setStyle] = useState<StoryStyle>("adventure");
  const [quota, setQuota] = useState<QuotaInfo | null>(null);

  useEffect(() => {
    let cancelled = false;
    getToken()
      .then((token) => getQuota(token))
      .then((q) => {
        if (!cancelled) setQuota(q);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [getToken, disabled]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!paperUrl) return;
    onSubmit({ paperUrl, ageGroup, style });
  }

  const quotaExhausted = quota !== null && quota.remaining <= 0;

  return (
    <form onSubmit={handleSubmit} className="paper-uploader">
      <input
        className="uploader-url"
        type="url"
        placeholder="Paste a research paper URL..."
        value={paperUrl}
        onChange={(e) => setPaperUrl(e.target.value)}
        disabled={disabled}
      />
      <p className="uploader-hint">
        Supports arXiv, bioRxiv, medRxiv, ChemRxiv, SSRN, EarthArXiv,
        PsyArXiv, OSF
      </p>

      <div className="uploader-options">
        <select
          value={ageGroup}
          onChange={(e) => setAgeGroup(e.target.value as AgeGroup)}
          disabled={disabled}
          aria-label="Age group"
        >
          {AGE_GROUPS.map((ag) => (
            <option key={ag.value} value={ag.value}>
              {ag.label}
            </option>
          ))}
        </select>
        <select
          value={style}
          onChange={(e) => setStyle(e.target.value as StoryStyle)}
          disabled={disabled}
          aria-label="Story style"
        >
          {STORY_STYLES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <button
        type="submit"
        className="uploader-submit"
        disabled={disabled || !paperUrl || quotaExhausted}
      >
        Generate Story
      </button>

      {quota !== null && (
        <p className="uploader-quota">
          {quotaExhausted
            ? "Daily limit reached. Try again tomorrow."
            : `${quota.remaining}/${quota.limit} generations remaining today`}
          {quota.isAnonymous && !quotaExhausted && (
            <span className="quota-hint"> — sign in for more</span>
          )}
        </p>
      )}
    </form>
  );
}
