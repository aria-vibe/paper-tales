import { useCallback, useRef, useState } from "react";
import type { GenerationRequest, GenerationStatus, Story } from "../types";
import { generateStory, getJobStatus } from "../services/api";

const POLL_INTERVAL = 5_000;

function friendlyError(err: unknown): string {
  if (err && typeof err === "object" && "response" in err) {
    const resp = (err as { response?: { status?: number; data?: { detail?: string } } }).response;
    const status = resp?.status;
    const detail = resp?.data?.detail;

    if (status === 409) return detail || "You already have a story being generated.";
    if (status === 422) return detail || "That URL doesn't look right. Please check it and try again.";
    if (status === 429) return "Too many requests. Please wait a moment and try again.";
    if (status === 413) return "That paper is too large to process. Try a shorter one.";
    if (status && status >= 500) return "Something went wrong on our end. Please try again in a moment.";
    if (status === 401 || status === 403) return "Your session expired. Please sign in again.";
  }
  if (err instanceof Error) {
    if (err.message === "Network Error") return "Could not reach the server. Check your connection and try again.";
    if (err.message.includes("timeout")) return "The request timed out. Please try again.";
  }
  return "Something unexpected happened. Please try again.";
}

export function useStoryGeneration(getToken: () => Promise<string>) {
  const [status, setStatus] = useState<GenerationStatus>("idle");
  const [story, setStory] = useState<Story | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stageLabel, setStageLabel] = useState<string | null>(null);
  const [currentStage, setCurrentStage] = useState<number | null>(null);
  const [totalStages, setTotalStages] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  async function generate(request: GenerationRequest) {
    setStatus("uploading");
    setError(null);
    setStageLabel(null);
    setCurrentStage(null);
    setTotalStages(null);
    stopPolling();

    try {
      const token = await getToken();
      setStatus("processing");
      const result = await generateStory(request, token);

      // If the backend returned a cached story directly (has 'id' and 'scenes')
      if ("scenes" in result) {
        setStory(result as Story);
        setStatus("complete");
        return;
      }

      // Async job — set initial stage info and poll for status
      const jobResult = result as { jobId: string; currentStage?: number; totalStages?: number; stageLabel?: string };
      const jobId = jobResult.jobId;

      if (jobResult.currentStage != null) setCurrentStage(jobResult.currentStage);
      if (jobResult.totalStages != null) setTotalStages(jobResult.totalStages);
      if (jobResult.stageLabel) setStageLabel(jobResult.stageLabel);

      pollRef.current = setInterval(async () => {
        try {
          const freshToken = await getToken();
          const job = await getJobStatus(jobId, freshToken);

          // Update stage fields on every poll
          if (job.currentStage != null) setCurrentStage(job.currentStage);
          if (job.totalStages != null) setTotalStages(job.totalStages);
          if (job.stageLabel) setStageLabel(job.stageLabel);

          if (job.status === "complete" && job.story) {
            stopPolling();
            setStory(job.story);
            setStatus("complete");
          } else if (job.status === "error" || job.status === "timed_out") {
            stopPolling();
            setError(job.status === "timed_out"
              ? "Story generation took too long. Please try again."
              : "Story generation failed. Please try again.");
            setStatus("error");
          }
        } catch (pollErr) {
          // Ignore transient poll errors — keep polling
        }
      }, POLL_INTERVAL);
    } catch (err: unknown) {
      stopPolling();
      setError(friendlyError(err));
      setStatus("error");
    }
  }

  function reset() {
    stopPolling();
    setStatus("idle");
    setStory(null);
    setError(null);
    setStageLabel(null);
    setCurrentStage(null);
    setTotalStages(null);
  }

  return { status, story, error, generate, reset, stageLabel, currentStage, totalStages };
}
