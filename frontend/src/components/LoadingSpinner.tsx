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
}

export function LoadingSpinner({ status }: LoadingSpinnerProps) {
  if (status === "idle" || status === "complete") return null;

  return (
    <div className="loading-spinner">
      {status === "error" ? null : <div className="spinner" />}
      <p>{STATUS_MESSAGES[status]}</p>
    </div>
  );
}
