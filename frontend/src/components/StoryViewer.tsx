import { useState, useRef, useCallback, useEffect } from "react";
import type { Story } from "../types";
import { VoteButtons } from "./VoteButtons";

interface StoryViewerProps {
  story: Story;
  getToken?: () => Promise<string>;
}

function getDifficultyFromAccuracy(
  rating: number | string | undefined
): { label: string; className: string } {
  if (rating === undefined)
    return { label: "Unknown", className: "difficulty-unknown" };
  if (typeof rating === "string") {
    const r = rating.toLowerCase();
    if (r === "excellent")
      return { label: "Easy Read", className: "difficulty-easy" };
    if (r === "good")
      return { label: "Moderate", className: "difficulty-moderate" };
    return { label: "Challenging", className: "difficulty-hard" };
  }
  if (rating >= 0.85) return { label: "Easy Read", className: "difficulty-easy" };
  if (rating >= 0.65)
    return { label: "Moderate", className: "difficulty-moderate" };
  return { label: "Challenging", className: "difficulty-hard" };
}

function GlossaryText({
  text,
  glossary,
}: {
  text: string;
  glossary: Record<string, string>;
}) {
  const terms = Object.keys(glossary);
  if (terms.length === 0) return <>{text}</>;

  // Build regex that matches any glossary term (case-insensitive, whole word)
  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const regex = new RegExp(`\\b(${escaped.join("|")})\\b`, "gi");

  const parts: { text: string; term?: string }[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: text.slice(lastIndex, match.index) });
    }
    // Find original-case term key
    const matchedKey =
      terms.find((t) => t.toLowerCase() === match![0].toLowerCase()) ??
      match[0];
    parts.push({ text: match[0], term: matchedKey });
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex) });
  }

  return (
    <>
      {parts.map((p, i) =>
        p.term ? (
          <span key={i} className="glossary-word" data-tooltip={glossary[p.term]}>
            {p.text}
          </span>
        ) : (
          <span key={i}>{p.text}</span>
        )
      )}
    </>
  );
}

export function StoryViewer({ story, getToken }: StoryViewerProps) {
  const [currentScene, setCurrentScene] = useState(0);
  const trackRef = useRef<HTMLDivElement>(null);
  const touchStartX = useRef(0);
  const touchDeltaX = useRef(0);
  const isDragging = useRef(false);
  const total = story.scenes.length;
  const glossary = story.glossary ?? {};
  const difficulty = getDifficultyFromAccuracy(story.factCheck?.accuracy_rating);

  const goTo = useCallback(
    (index: number) => {
      setCurrentScene(Math.max(0, Math.min(index, total - 1)));
    },
    [total]
  );

  const goNext = useCallback(() => goTo(currentScene + 1), [currentScene, goTo]);
  const goPrev = useCallback(() => goTo(currentScene - 1), [currentScene, goTo]);

  // Keyboard navigation
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight") goNext();
      else if (e.key === "ArrowLeft") goPrev();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [goNext, goPrev]);

  // Touch handlers for swipe
  function onTouchStart(e: React.TouchEvent) {
    touchStartX.current = e.touches[0].clientX;
    touchDeltaX.current = 0;
    isDragging.current = true;
  }

  function onTouchMove(e: React.TouchEvent) {
    if (!isDragging.current) return;
    touchDeltaX.current = e.touches[0].clientX - touchStartX.current;
    if (trackRef.current) {
      const base = -(currentScene * 100);
      const pct = (touchDeltaX.current / trackRef.current.parentElement!.clientWidth) * 100;
      trackRef.current.style.transition = "none";
      trackRef.current.style.transform = `translateX(${base + pct}%)`;
    }
  }

  function onTouchEnd() {
    isDragging.current = false;
    if (trackRef.current) {
      trackRef.current.style.transition = "";
      trackRef.current.style.transform = "";
    }
    const threshold = 50;
    if (touchDeltaX.current < -threshold) goNext();
    else if (touchDeltaX.current > threshold) goPrev();
    touchDeltaX.current = 0;
  }

  return (
    <article className="story-viewer">
      <header className="story-header">
        <h1>{story.title}</h1>
        <div className="story-meta-row">
          <span className="story-meta-tag">
            {story.style.replace("_", " ")}
          </span>
          <span className="story-meta-tag">Ages {story.ageGroup}</span>
          {story.fieldOfStudy && (
            <span className="story-meta-tag story-meta-field">
              {story.fieldOfStudy}
            </span>
          )}
          <span className={`story-meta-tag ${difficulty.className}`}>
            {difficulty.label}
          </span>
        </div>
        {story.paperTitle && (
          <p className="story-paper-title">{story.paperTitle}</p>
        )}
        {story.titleAudioBase64 && (
          <audio
            controls
            src={`data:audio/mpeg;base64,${story.titleAudioBase64}`}
            className="scene-audio title-audio"
          >
            Your browser does not support the audio element.
          </audio>
        )}
        {getToken && (
          <VoteButtons
            storyId={story.id}
            initialUpvotes={story.upvotes ?? 0}
            initialDownvotes={story.downvotes ?? 0}
            initialUserVote={story.userVote}
            getToken={getToken}
          />
        )}
      </header>

      {/* Scene carousel */}
      <div className="scene-carousel">
        <div className="scene-counter">
          {currentScene + 1} / {total}
        </div>

        <div
          className="scene-viewport"
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
        >
          <div
            ref={trackRef}
            className="scene-track"
            style={{ transform: `translateX(-${currentScene * 100}%)` }}
          >
            {story.scenes.map((s, i) => (
              <div key={i} className="scene-slide">
                <div className="scene-card">
                  <div className="scene-layout">
                    {(s.imageBase64 || s.imageUrl) && (
                      <div className="scene-image-wrapper">
                        <img
                          src={
                            s.imageBase64
                              ? `data:image/png;base64,${s.imageBase64}`
                              : s.imageUrl
                          }
                          alt={`Scene ${i + 1}`}
                          className="scene-image"
                          loading={Math.abs(i - currentScene) > 1 ? "lazy" : "eager"}
                        />
                      </div>
                    )}
                    <div className="scene-content">
                      <p className="scene-text">
                        <GlossaryText text={s.text} glossary={glossary} />
                      </p>
                      {(s.audioBase64 || s.audioUrl) && (
                        <audio
                          controls
                          src={
                            s.audioBase64
                              ? `data:audio/mpeg;base64,${s.audioBase64}`
                              : s.audioUrl
                          }
                          className="scene-audio"
                        >
                          Your browser does not support the audio element.
                        </audio>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Navigation */}
        <div className="scene-nav">
          <button
            className="scene-nav-btn"
            onClick={goPrev}
            disabled={currentScene === 0}
            aria-label="Previous scene"
          >
            {"\u2190"}
          </button>

          <div className="scene-dots">
            {story.scenes.map((_, i) => (
              <button
                key={i}
                className={`scene-dot ${i === currentScene ? "active" : ""}`}
                onClick={() => goTo(i)}
                aria-label={`Go to scene ${i + 1}`}
              />
            ))}
          </div>

          <button
            className="scene-nav-btn"
            onClick={goNext}
            disabled={currentScene === total - 1}
            aria-label="Next scene"
          >
            {"\u2192"}
          </button>
        </div>
      </div>

      {story.conclusionAudioBase64 && (
        <footer className="story-conclusion-audio">
          <p className="conclusion-label">Conclusion</p>
          <audio
            controls
            src={`data:audio/mpeg;base64,${story.conclusionAudioBase64}`}
            className="scene-audio"
          >
            Your browser does not support the audio element.
          </audio>
        </footer>
      )}
    </article>
  );
}
