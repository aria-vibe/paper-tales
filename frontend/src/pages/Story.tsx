import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
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

  if (error) {
    return (
      <main className="story-page">
        <p className="error-message">{error}</p>
        <Link to="/" className="story-back" style={{ marginTop: 16, display: "inline-flex" }}>
          {"\u2190"} Home
        </Link>
      </main>
    );
  }

  if (!story) {
    return (
      <main className="story-page">
        <LoadingSpinner status="processing" />
      </main>
    );
  }

  return (
    <main className="story-page">
      <Link to="/" className="story-back">
        {"\u2190"} Home
      </Link>
      <StoryViewer story={story} getToken={getToken} />
    </main>
  );
}
