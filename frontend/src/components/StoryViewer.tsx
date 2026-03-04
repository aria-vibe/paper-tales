import type { Story } from "../types";
import { VoteButtons } from "./VoteButtons";

interface StoryViewerProps {
  story: Story;
  getToken?: () => Promise<string>;
}

export function StoryViewer({ story, getToken }: StoryViewerProps) {
  return (
    <article className="story-viewer">
      <header>
        <h1>{story.title}</h1>
        <p className="story-meta">
          {story.style.replace("_", " ")} | Ages {story.ageGroup}
          {story.paperTitle && <> | Source: {story.paperTitle}</>}
          {story.version && <> | v{story.version}</>}
        </p>
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

      <div className="story-scenes">
        {story.scenes.map((scene, i) => (
          <section key={i} className="story-scene">
            {scene.imageBase64 && (
              <img
                src={`data:image/png;base64,${scene.imageBase64}`}
                alt={`Scene ${i + 1}`}
                className="scene-image"
              />
            )}
            {scene.imageUrl && !scene.imageBase64 && (
              <img
                src={scene.imageUrl}
                alt={`Scene ${i + 1}`}
                className="scene-image"
              />
            )}
            <p className="scene-text">{scene.text}</p>
            {scene.audioBase64 && (
              <audio
                controls
                src={`data:audio/mpeg;base64,${scene.audioBase64}`}
                className="scene-audio"
              >
                Your browser does not support the audio element.
              </audio>
            )}
            {scene.audioUrl && !scene.audioBase64 && (
              <audio controls src={scene.audioUrl} className="scene-audio">
                Your browser does not support the audio element.
              </audio>
            )}
          </section>
        ))}
      </div>

      {story.glossary && Object.keys(story.glossary).length > 0 && (
        <section className="story-glossary">
          <h2>Glossary</h2>
          <dl>
            {Object.entries(story.glossary).map(([term, definition]) => (
              <div key={term}>
                <dt>{term}</dt>
                <dd>{definition}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </article>
  );
}
