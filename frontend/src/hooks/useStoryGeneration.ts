import { useCallback, useRef, useState } from "react";
import type { GenerationRequest, GenerationStatus, Story } from "../types";
import { generateStory, getJobStatus } from "../services/api";

const POLL_INTERVAL = 5_000;

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
            setError(job.error || "Generation failed");
            setStatus("error");
          }
        } catch (pollErr) {
          // Ignore transient poll errors — keep polling
        }
      }, POLL_INTERVAL);
    } catch (err: unknown) {
      stopPolling();
      // Handle 409 conflict (concurrent job)
      if (err && typeof err === "object" && "response" in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } };
        if (axiosErr.response?.status === 409) {
          setError(axiosErr.response.data?.detail || "You already have a story being generated.");
          setStatus("error");
          return;
        }
      }
      setError(err instanceof Error ? err.message : "Generation failed");
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
