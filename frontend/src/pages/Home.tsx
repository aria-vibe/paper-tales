import type { User } from "firebase/auth";
import { PaperUploader } from "../components/PaperUploader";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StoryViewer } from "../components/StoryViewer";
import { TopPapers } from "../components/TopPapers";
import { useStoryGeneration } from "../hooks/useStoryGeneration";

interface HomeProps {
  user: User | null;
  getToken: () => Promise<string>;
}

export function Home({ user, getToken }: HomeProps) {
  const { status, story, error, generate, reset } = useStoryGeneration(getToken);

  return (
    <main className="home-page">
      <h1>PaperTales</h1>
      <p className="tagline">
        Turn research papers into illustrated stories for young readers
      </p>

      {!user ? (
        <p className="sign-in-prompt">Sign in with Google to get started.</p>
      ) : story ? (
        <>
          <button onClick={reset} className="btn-secondary">
            Create another story
          </button>
          <StoryViewer story={story} getToken={getToken} />
        </>
      ) : (
        <>
          <PaperUploader
            onSubmit={generate}
            disabled={status === "uploading" || status === "processing"}
          />
          <LoadingSpinner status={status} />
          {error && <p className="error-message">{error}</p>}
          <TopPapers getToken={getToken} />
        </>
      )}
    </main>
  );
}
