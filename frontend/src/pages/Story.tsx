import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { StoryViewer } from "../components/StoryViewer";
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
      .catch((err) => {
        if (err && typeof err === "object" && "response" in err) {
          const status = (err as { response?: { status?: number } }).response?.status;
          if (status === 404) { setError("This story could not be found."); return; }
          if (status && status >= 500) { setError("Something went wrong on our end. Please try again in a moment."); return; }
        }
        if (err instanceof Error && err.message === "Network Error") {
          setError("Could not reach the server. Check your connection and try again.");
          return;
        }
        setError("Something unexpected happened. Please try again.");
      });
  }, [id, getToken]);

  if (error) {
    return (
      <main className="story-page">
        <div className="error-banner" role="alert">
          <div className="error-banner-body">
            <span className="error-banner-icon">!</span>
            <p className="error-banner-text">{error}</p>
          </div>
        </div>
        <Link to="/" className="story-back" style={{ marginTop: 16, display: "inline-flex" }}>
          {"\u2190"} Home
        </Link>
      </main>
    );
  }

  if (!story) {
    return (
      <main className="story-page">
        <div className="story-loading">
          <div className="uploader-spinner" />
          <p className="story-loading-text">Loading story...</p>
        </div>
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
