import type { GenerationStatus } from "../types";

const STATUS_MESSAGES: Record<GenerationStatus, string> = {
  idle: "",
  uploading: "Uploading paper...",
  processing: "Generating your story... This may take a minute.",
  complete: "Story ready!",
  error: "Something went wrong.",
};

interface LoadingSpinnerProps {
  status: GenerationStatus;
  stageLabel?: string | null;
  currentStage?: number | null;
  totalStages?: number | null;
}

export function LoadingSpinner({ status, stageLabel, currentStage, totalStages }: LoadingSpinnerProps) {
  if (status === "idle" || status === "complete") return null;

  const hasStageInfo = status === "processing" && currentStage != null && totalStages != null && totalStages > 0;
  const progressPct = hasStageInfo ? Math.round((currentStage! / totalStages!) * 100) : 0;

  return (
    <div className="loading-spinner">
      {status !== "error" && <div className="spinner" />}
      <p className="loading-text">
        {hasStageInfo && stageLabel ? stageLabel : STATUS_MESSAGES[status]}
      </p>
      {hasStageInfo && (
        <div className="stage-progress">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progressPct}%` }} />
          </div>
          <span className="progress-label">
            Step {currentStage} of {totalStages}
          </span>
        </div>
      )}
    </div>
  );
}
