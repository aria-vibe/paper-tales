import { useState, useRef, useCallback, useEffect } from "react";
import type { Story, StoryScene } from "../types";
import { useAuthMedia } from "../hooks/useAuthMedia";
import { VoteButtons } from "./VoteButtons";

interface StoryViewerProps {
  story: Story;
  getToken?: () => Promise<string>;
  isAdmin?: boolean;
  onRegenerate?: () => void;
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

function AuthImage({
  getToken,
  imageUrl,
  imageBase64,
  alt,
  loading,
}: {
  getToken?: () => Promise<string>;
  imageUrl?: string;
  imageBase64?: string;
  alt: string;
  loading?: "lazy" | "eager";
}) {
  const src = useAuthMedia(getToken, imageUrl, imageBase64, "image/png");
  const isLoading = !src && !!(imageUrl || imageBase64);
  if (!src && !isLoading) return null;
  if (isLoading) {
    return (
      <div className="media-placeholder media-placeholder-image">
        <div className="media-placeholder-shimmer" />
        <svg className="media-placeholder-icon" width="48" height="48" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="8.5" cy="8.5" r="1.5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M3 16l5-5 4 4 3-3 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    );
  }
  return <img src={src} alt={alt} loading={loading} />;
}

function AuthAudio({
  getToken,
  audioUrl,
  audioBase64,
  className,
}: {
  getToken?: () => Promise<string>;
  audioUrl?: string;
  audioBase64?: string;
  className?: string;
}) {
  const src = useAuthMedia(getToken, audioUrl, audioBase64, "audio/mpeg");
  const isLoading = !src && !!(audioUrl || audioBase64);
  if (!src && !isLoading) return null;
  if (isLoading) {
    return (
      <div className={`media-placeholder media-placeholder-audio ${className ?? ""}`}>
        <div className="media-placeholder-shimmer" />
        <svg className="media-placeholder-icon" width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M9 18V5l12-2v13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="6" cy="18" r="3" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="18" cy="16" r="3" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        <span className="media-placeholder-label">Loading audio...</span>
      </div>
    );
  }
  return (
    <audio controls src={src} className={className}>
      Your browser does not support the audio element.
    </audio>
  );
}

function ScenePage({
  scene,
  index,
  isConclusion,
  currentScene,
  glossary,
  getToken,
  onReadAgain,
}: {
  scene: StoryScene;
  index: number;
  isConclusion: boolean;
  currentScene: number;
  glossary: Record<string, string>;
  getToken?: () => Promise<string>;
  onReadAgain?: () => void;
}) {
  const hasImage = !!(scene.imageBase64 || scene.imageUrl);
  const hasAudio = !!(scene.audioBase64 || scene.audioUrl);
  const glossaryEntries = Object.entries(glossary);

  return (
    <div className="book-page-slide">
      <div className={`book-page${isConclusion ? " book-page-conclusion" : ""}`}>
        {hasImage && (
          <div className="book-illustration">
            <AuthImage
              getToken={getToken}
              imageUrl={scene.imageUrl}
              imageBase64={scene.imageBase64}
              alt={isConclusion ? "What we learned" : `Scene ${index + 1}`}
              loading={Math.abs(index - currentScene) > 1 ? "lazy" : "eager"}
            />
          </div>
        )}
        <div className="book-text-block">
          {isConclusion && (
            <div className="book-conclusion-badge">What We Learned</div>
          )}
          <p className="book-text">
            <GlossaryText text={scene.text} glossary={glossary} />
          </p>
          {hasAudio && (
            <AuthAudio
              getToken={getToken}
              audioUrl={scene.audioUrl}
              audioBase64={scene.audioBase64}
              className="book-audio"
            />
          )}
          {isConclusion && glossaryEntries.length > 0 && (
            <div className="book-glossary">
              <div className="book-glossary-badge">Glossary</div>
              <dl className="book-glossary-list">
                {glossaryEntries.map(([term, definition]) => (
                  <div key={term} className="book-glossary-entry">
                    <dt>{term}</dt>
                    <dd>{definition}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
          {isConclusion && onReadAgain && (
            <button className="book-read-again" onClick={onReadAgain}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M1 4v6h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Read Again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function StoryViewer({ story, getToken, isAdmin, onRegenerate }: StoryViewerProps) {
  const [regenerating, setRegenerating] = useState(false);
  const [showRegenConfirm, setShowRegenConfirm] = useState(false);
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
      ? [{ text: story.whatWeLearned, audioBase64: story.conclusionAudioBase64, audioUrl: story.conclusionAudioUrl }]
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
          <AuthAudio
            getToken={getToken}
            audioUrl={story.titleAudioUrl}
            audioBase64={story.titleAudioBase64}
            className="title-audio-inline"
          />
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
        <div className="story-actions-row">
          {getToken && (
            <VoteButtons
              storyId={story.id}
              initialUpvotes={story.upvotes ?? 0}
              initialDownvotes={story.downvotes ?? 0}
              initialUserVote={story.userVote}
              getToken={getToken}
            />
          )}
          {isAdmin && onRegenerate && (
            <button
              className="vote-btn regen-btn"
              disabled={regenerating}
              onClick={() => setShowRegenConfirm(true)}
              aria-label="Regenerate story"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M1 4v6h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {regenerating ? "Regenerating..." : "Regenerate"}
            </button>
          )}
        </div>
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
            {allScenes.map((s, i) => (
              <ScenePage
                key={i}
                scene={s}
                index={i}
                isConclusion={!!(story.whatWeLearned && i === allScenes.length - 1)}
                currentScene={currentScene}
                glossary={glossary}
                getToken={getToken}
                onReadAgain={() => goTo(0)}
              />
            ))}
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

      {/* Regeneration confirmation modal */}
      {showRegenConfirm && (
        <div className="regen-overlay" onClick={() => setShowRegenConfirm(false)}>
          <div className="regen-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="regen-modal-title">Regenerate this story?</h3>
            <p className="regen-modal-desc">
              This will create a new version of the story with fresh illustrations and narration.
            </p>
            <dl className="regen-modal-meta">
              <div className="regen-meta-row">
                <dt>Story</dt>
                <dd>{story.title}</dd>
              </div>
              {story.paperTitle && (
                <div className="regen-meta-row">
                  <dt>Paper</dt>
                  <dd>{story.paperTitle}</dd>
                </div>
              )}
              <div className="regen-meta-row">
                <dt>Age Group</dt>
                <dd>{story.ageGroup}</dd>
              </div>
              <div className="regen-meta-row">
                <dt>Style</dt>
                <dd>{story.style.replace("_", " ")}</dd>
              </div>
              {story.fieldOfStudy && (
                <div className="regen-meta-row">
                  <dt>Field</dt>
                  <dd>{story.fieldOfStudy}</dd>
                </div>
              )}
              {story.version !== undefined && (
                <div className="regen-meta-row">
                  <dt>Current Version</dt>
                  <dd>v{story.version}</dd>
                </div>
              )}
            </dl>
            <div className="regen-modal-actions">
              <button
                className="vote-btn"
                onClick={() => setShowRegenConfirm(false)}
              >
                Cancel
              </button>
              <button
                className="vote-btn regen-confirm-btn"
                onClick={() => {
                  setShowRegenConfirm(false);
                  setRegenerating(true);
                  onRegenerate!();
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M1 4v6h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Regenerate
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
