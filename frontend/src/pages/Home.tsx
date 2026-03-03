import { PaperUploader } from "../components/PaperUploader";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StoryViewer } from "../components/StoryViewer";
import { useStoryGeneration } from "../hooks/useStoryGeneration";

export function Home() {
  const { status, story, error, generate, reset } = useStoryGeneration();

  return (
    <main className="home-page">
      <h1>PaperTales</h1>
      <p className="tagline">
        Turn research papers into illustrated stories for young readers
      </p>

      {story ? (
        <>
          <button onClick={reset} className="btn-secondary">
            Create another story
          </button>
          <StoryViewer story={story} />
        </>
      ) : (
        <>
          <PaperUploader
            onSubmit={generate}
            disabled={status === "uploading" || status === "processing"}
          />
          <LoadingSpinner status={status} />
          {error && <p className="error-message">{error}</p>}
        </>
      )}
    </main>
  );
}
