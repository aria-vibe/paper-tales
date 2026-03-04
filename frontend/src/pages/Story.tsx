import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { StoryViewer } from "../components/StoryViewer";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { getStory } from "../services/api";
import type { Story as StoryType } from "../types";

interface StoryProps {
  getToken: () => Promise<string>;
}

export function Story({ getToken }: StoryProps) {
  const { id } = useParams<{ id: string }>();
  const [story, setStory] = useState<StoryType | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getToken()
      .then((token) => getStory(id, token))
      .then(setStory)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load story")
      );
  }, [id, getToken]);

  if (error) return <p className="error-message">{error}</p>;
  if (!story) return <LoadingSpinner status="processing" />;

  return (
    <main className="story-page">
      <StoryViewer story={story} />
    </main>
  );
}
