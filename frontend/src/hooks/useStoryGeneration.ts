import { useState } from "react";
import type { GenerationRequest, GenerationStatus, Story } from "../types";
import { generateStory } from "../services/api";

export function useStoryGeneration(getToken: () => Promise<string>) {
  const [status, setStatus] = useState<GenerationStatus>("idle");
  const [story, setStory] = useState<Story | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function generate(request: GenerationRequest) {
    setStatus("uploading");
    setError(null);

    try {
      const token = await getToken();
      setStatus("processing");
      const result = await generateStory(request, token);
      setStory(result);
      setStatus("complete");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
      setStatus("error");
    }
  }

  function reset() {
    setStatus("idle");
    setStory(null);
    setError(null);
  }

  return { status, story, error, generate, reset };
}
