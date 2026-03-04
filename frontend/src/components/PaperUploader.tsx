import { useState } from "react";
import type { AgeGroup, GenerationRequest, StoryStyle } from "../types";

interface PaperUploaderProps {
  onSubmit: (request: GenerationRequest) => void;
  disabled?: boolean;
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

const SUPPORTED_ARCHIVES = [
  "arxiv.org",
  "biorxiv.org",
  "medrxiv.org",
  "chemrxiv.org",
  "ssrn.com",
  "eartharxiv.org",
  "psyarxiv.com",
  "osf.io",
];

export function PaperUploader({ onSubmit, disabled }: PaperUploaderProps) {
  const [paperUrl, setPaperUrl] = useState("");
  const [ageGroup, setAgeGroup] = useState<AgeGroup>("10-13");
  const [style, setStyle] = useState<StoryStyle>("adventure");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!paperUrl) return;

    onSubmit({
      paperUrl,
      ageGroup,
      style,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="paper-uploader">
      <h2>Enter a Research Paper URL</h2>

      <div className="form-group">
        <label htmlFor="paper-url">Paper URL</label>
        <input
          id="paper-url"
          type="url"
          placeholder="https://arxiv.org/abs/2301.12345"
          value={paperUrl}
          onChange={(e) => setPaperUrl(e.target.value)}
          disabled={disabled}
        />
        <p className="form-hint">
          Supported: {SUPPORTED_ARCHIVES.join(", ")}
        </p>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label htmlFor="age-group">Age Group</label>
          <select
            id="age-group"
            value={ageGroup}
            onChange={(e) => setAgeGroup(e.target.value as AgeGroup)}
            disabled={disabled}
          >
            {AGE_GROUPS.map((ag) => (
              <option key={ag.value} value={ag.value}>
                {ag.label}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="story-style">Story Style</label>
          <select
            id="story-style"
            value={style}
            onChange={(e) => setStyle(e.target.value as StoryStyle)}
            disabled={disabled}
          >
            {STORY_STYLES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <button type="submit" disabled={disabled || !paperUrl}>
        Generate Story
      </button>
    </form>
  );
}
