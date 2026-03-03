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

export function PaperUploader({ onSubmit, disabled }: PaperUploaderProps) {
  const [file, setFile] = useState<File | null>(null);
  const [arxivUrl, setArxivUrl] = useState("");
  const [ageGroup, setAgeGroup] = useState<AgeGroup>("10-13");
  const [style, setStyle] = useState<StoryStyle>("adventure");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file && !arxivUrl) return;

    onSubmit({
      file: file ?? undefined,
      arxivUrl: arxivUrl || undefined,
      ageGroup,
      style,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="paper-uploader">
      <h2>Upload a Research Paper</h2>

      <div className="form-group">
        <label htmlFor="pdf-upload">PDF File</label>
        <input
          id="pdf-upload"
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          disabled={disabled}
        />
      </div>

      <div className="form-group">
        <label htmlFor="arxiv-url">Or paste an arXiv URL</label>
        <input
          id="arxiv-url"
          type="url"
          placeholder="https://arxiv.org/abs/..."
          value={arxivUrl}
          onChange={(e) => setArxivUrl(e.target.value)}
          disabled={disabled}
        />
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

      <button type="submit" disabled={disabled || (!file && !arxivUrl)}>
        Generate Story
      </button>
    </form>
  );
}
