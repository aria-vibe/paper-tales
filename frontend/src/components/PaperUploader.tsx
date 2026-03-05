import { useState, useEffect } from "react";
import type { AgeGroup, GenerationRequest, GenerationStatus, QuotaInfo, StoryStyle } from "../types";
import { getQuota } from "../services/api";

interface PaperUploaderProps {
  onSubmit: (request: GenerationRequest) => void;
  disabled?: boolean;
  getToken: () => Promise<string>;
  status: GenerationStatus;
  stageLabel?: string | null;
  currentStage?: number | null;
  totalStages?: number | null;
  error?: string | null;
  onDismissError?: () => void;
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

export function PaperUploader({ onSubmit, disabled, getToken, status, stageLabel, currentStage, totalStages, error, onDismissError }: PaperUploaderProps) {
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
        <fieldset className="option-group" disabled={disabled}>
          <legend className="option-label">Age group</legend>
          <div className="option-chips">
            {AGE_GROUPS.map((ag) => (
              <button
                key={ag.value}
                type="button"
                className={`option-chip${ageGroup === ag.value ? " option-chip--active" : ""}`}
                onClick={() => setAgeGroup(ag.value)}
              >
                {ag.label}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset className="option-group" disabled={disabled}>
          <legend className="option-label">Story style</legend>
          <div className="option-chips">
            {STORY_STYLES.map((s) => (
              <button
                key={s.value}
                type="button"
                className={`option-chip${style === s.value ? " option-chip--active" : ""}`}
                onClick={() => setStyle(s.value)}
              >
                {s.label}
              </button>
            ))}
          </div>
        </fieldset>
      </div>

      {status === "uploading" || status === "processing" ? (
        <ProgressSection
          status={status}
          stageLabel={stageLabel}
          currentStage={currentStage}
          totalStages={totalStages}
        />
      ) : (
        <>
          {error ? (
            <div className="uploader-error" role="alert">
              <div className="uploader-error-body">
                <span className="uploader-error-icon">!</span>
                <p className="uploader-error-text">{error}</p>
              </div>
              <button type="button" className="uploader-submit" onClick={onDismissError}>
                Try again
              </button>
            </div>
          ) : (
            <>
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
            </>
          )}
        </>
      )}
    </form>
  );
}

function ProgressSection({
  status,
  stageLabel,
  currentStage,
  totalStages,
}: {
  status: GenerationStatus;
  stageLabel?: string | null;
  currentStage?: number | null;
  totalStages?: number | null;
}) {
  const hasStageInfo = status === "processing" && currentStage != null && totalStages != null && totalStages > 0;
  const progressPct = hasStageInfo ? Math.round((currentStage! / totalStages!) * 100) : 0;
  const showBar = hasStageInfo && progressPct > 0;

  return (
    <div className="uploader-progress">
      {showBar ? (
        <div className="uploader-progress-bar">
          <div
            className="uploader-progress-fill"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      ) : (
        <div className="uploader-spinner" />
      )}
      <p className="uploader-progress-label">
        {hasStageInfo && stageLabel
          ? stageLabel
          : status === "uploading"
            ? "Uploading paper..."
            : "Starting generation..."}
      </p>
      {showBar && (
        <span className="uploader-progress-step">
          Step {currentStage} of {totalStages} &middot; {progressPct}%
        </span>
      )}
    </div>
  );
}
