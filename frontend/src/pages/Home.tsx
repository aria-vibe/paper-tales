import type { User } from "firebase/auth";
import { PaperUploader } from "../components/PaperUploader";
import { StoryViewer } from "../components/StoryViewer";
import { TopPapers } from "../components/TopPapers";
import { useStoryGeneration } from "../hooks/useStoryGeneration";

interface HomeProps {
  user: User | null;
  getToken: () => Promise<string>;
}

export function Home({ getToken }: HomeProps) {
  const { status, story, error, generate, reset, stageLabel, currentStage, totalStages, activeRequest, foundPaperTitle } = useStoryGeneration(getToken);

  if (story) {
    return (
      <main className="home-page">
        <div className="story-container">
          <button onClick={reset} className="story-back">
            {"\u2190"} New story
          </button>
          <StoryViewer story={story} getToken={getToken} />
        </div>
      </main>
    );
  }

  return (
    <main className="home-page">
      <TopPapers getToken={getToken} />
      <div className="home-hero">
        <div className="home-center">
          <div className="hero-content">
            <h1 className="hero-title">PaperTales</h1>
            <p className="hero-tagline">
              Turn research papers into illustrated stories for young readers
            </p>
          </div>
          <PaperUploader
            onSubmit={generate}
            disabled={status === "uploading" || status === "processing"}
            getToken={getToken}
            status={status}
            stageLabel={stageLabel}
            currentStage={currentStage}
            totalStages={totalStages}
            error={error}
            onDismissError={reset}
            activeRequest={activeRequest}
            foundPaperTitle={foundPaperTitle}
          />
        </div>
      </div>
    </main>
  );
}
