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

  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const regex = new RegExp(`\\b(${escaped.join("|")})\\b`, "gi");

  const parts: { text: string; term?: string }[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: text.slice(lastIndex, match.index) });
    }
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
  const stageRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const touchStartX = useRef(0);
  const touchDeltaX = useRef(0);
  const isDragging = useRef(false);
  const glossary = story.glossary ?? {};
  const difficulty = getDifficultyFromAccuracy(story.factCheck?.accuracy_rating);

  const allScenes = [
    ...story.scenes,
    ...(story.whatWeLearned
      ? [{ text: story.whatWeLearned, audioBase64: story.conclusionAudioBase64 }]
      : []),
  ];
  const total = allScenes.length;

  const pauseAllAudio = useCallback(() => {
    stageRef.current
      ?.querySelectorAll("audio")
      .forEach((a) => { a.pause(); });
  }, []);

  const goTo = useCallback(
    (index: number) => {
      pauseAllAudio();
      setCurrentScene(Math.max(0, Math.min(index, total - 1)));
    },
    [total, pauseAllAudio]
  );

  const goNext = useCallback(() => goTo(currentScene + 1), [currentScene, goTo]);
  const goPrev = useCallback(() => goTo(currentScene - 1), [currentScene, goTo]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight") goNext();
      else if (e.key === "ArrowLeft") goPrev();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [goNext, goPrev]);

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
      const pct =
        (touchDeltaX.current / trackRef.current.parentElement!.clientWidth) *
        100;
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

  const isConclusion =
    story.whatWeLearned && currentScene === allScenes.length - 1;

  return (
    <article className="story-viewer">
      {/* Header */}
      <header className="story-header">
        <div className="story-title-row">
          <h1>{story.title}</h1>
          {story.titleAudioBase64 && (
            <audio
              controls
              src={`data:audio/mpeg;base64,${story.titleAudioBase64}`}
              className="title-audio-inline"
            >
              Your browser does not support the audio element.
            </audio>
          )}
        </div>
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
          <p className="story-paper-title">
            {story.sourceUrl ? (
              <a href={story.sourceUrl} target="_blank" rel="noopener noreferrer">
                {story.paperTitle}
              </a>
            ) : (
              story.paperTitle
            )}
          </p>
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

      {/* Storybook page */}
      <div
        ref={stageRef}
        className="book-stage"
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        {/* Side arrows */}
        <button
          className="book-arrow book-arrow-left"
          onClick={goPrev}
          disabled={currentScene === 0}
          aria-label="Previous page"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path
              d="M12.5 15L7.5 10L12.5 5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>

        <div className="book-page-area">
          <div
            ref={trackRef}
            className="book-track"
            style={{ transform: `translateX(-${currentScene * 100}%)` }}
          >
            {allScenes.map((s, i) => {
              const isConcl =
                story.whatWeLearned && i === allScenes.length - 1;
              return (
                <div key={i} className="book-page-slide">
                  <div className={`book-page${isConcl ? " book-page-conclusion" : ""}`}>
                    {/* Image */}
                    {(s.imageBase64 || s.imageUrl) && (
                      <div className="book-illustration">
                        <img
                          src={
                            s.imageBase64
                              ? `data:image/png;base64,${s.imageBase64}`
                              : s.imageUrl
                          }
                          alt={isConcl ? "What we learned" : `Scene ${i + 1}`}
                          loading={Math.abs(i - currentScene) > 1 ? "lazy" : "eager"}
                        />
                      </div>
                    )}

                    {/* Text */}
                    <div className="book-text-block">
                      {isConcl && (
                        <div className="book-conclusion-badge">What We Learned</div>
                      )}
                      <p className="book-text">
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
                          className="book-audio"
                        >
                          Your browser does not support the audio element.
                        </audio>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <button
          className="book-arrow book-arrow-right"
          onClick={goNext}
          disabled={currentScene === total - 1}
          aria-label="Next page"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path
              d="M7.5 5L12.5 10L7.5 15"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      {/* Page indicator */}
      <div className="book-footer">
        <span className="book-page-num">
          {isConclusion
            ? "The End"
            : `Page ${currentScene + 1} of ${total}`}
        </span>
        <div className="book-dots">
          {allScenes.map((_, i) => (
            <button
              key={i}
              className={`book-dot${i === currentScene ? " active" : ""}${
                story.whatWeLearned && i === allScenes.length - 1
                  ? " book-dot-end"
                  : ""
              }`}
              onClick={() => goTo(i)}
              aria-label={
                story.whatWeLearned && i === allScenes.length - 1
                  ? "Go to conclusion"
                  : `Go to page ${i + 1}`
              }
            />
          ))}
        </div>
      </div>
    </article>
  );
}
