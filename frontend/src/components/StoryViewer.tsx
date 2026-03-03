import type { Story } from "../types";

interface StoryViewerProps {
  story: Story;
}

export function StoryViewer({ story }: StoryViewerProps) {
  return (
    <article className="story-viewer">
      <header>
        <h1>{story.title}</h1>
        <p className="story-meta">
          {story.style.replace("_", " ")} | Ages {story.ageGroup}
        </p>
      </header>

      <div className="story-scenes">
        {story.scenes.map((scene, i) => (
          <section key={i} className="story-scene">
            {scene.imageUrl && (
              <img
                src={scene.imageUrl}
                alt={`Scene ${i + 1}`}
                className="scene-image"
              />
            )}
            <p className="scene-text">{scene.text}</p>
            {scene.audioUrl && (
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
