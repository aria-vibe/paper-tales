# How I Built a 9-Agent AI Pipeline That Turns Research Papers Into Children's Stories

*This post was created for the purposes of entering the [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/) on DevPost. #GeminiLiveAgentChallenge*

---

A curious 8-year-old asks: "How do black holes work?" The answer exists — buried in a 30-page PDF full of equations, jargon, and dense prose no child could parse. What if an AI could read that paper and retell it as an illustrated fairy tale?

That's **PaperTales** — a 9-agent pipeline built with Google's Agent Development Kit (ADK) and Gemini that transforms any research paper into an illustrated, narrated story tailored to a child's age.

## The Pipeline: 9 Agents, One Story

PaperTales uses ADK's `SequentialAgent` to chain eight specialized agents (plus a validation gate):

1. **Paper Parser** — Downloads the PDF and extracts structured text via PyMuPDF
2. **Concept Extractor** — Gemini Flash identifies 3–5 core science concepts and classifies the paper's field
3. **Language Simplifier** — Reduces vocabulary complexity for the target age group (6–9, 10–13, or 14–17), verified with Flesch-Kincaid scoring
4. **Narrative Designer** — Gemini creates a plot outline with characters, conflict, and scene structure
5. **Story Illustrator** — The creative core. Gemini 2.5 Flash Image writes the full story with **interleaved text and illustrations** in a single call
6. **Audio Narrator** — Gemini TTS generates age-appropriate voice narration for every scene
7. **Fact Checker** — Embedding-based semantic verification against the source paper
8. **Story Assembler** — Packages everything into a final story and persists it to Cloud Storage

Agents 6 and 7 run **in parallel** via ADK's `ParallelAgent` — they share no data dependencies, which saves 30–60 seconds per run.

## The Core Trick: Interleaved Text + Image Generation

The Creative Storyteller track requires interleaved multimodal output — text and images generated together, not separately. This is what makes PaperTales work:

```python
generate_content_config = types.GenerateContentConfig(
    response_modalities=["TEXT", "IMAGE"],
    max_output_tokens=65536,
    temperature=0.8,
)
```

With `gemini-2.5-flash-image` and `response_modalities=["TEXT", "IMAGE"]`, the Story Illustrator agent produces scene text and matching illustrations in a single streaming response. No separate image generation API calls. No post-hoc image stitching. One model, one call, coherent output.

The tradeoff: this single call takes 90–180 seconds and accounts for ~50% of total pipeline time. The model doesn't support function calling in this mode, so there's no way to break it into smaller steps. We mitigate this with aggressive caching — story IDs are deterministic (`sha256(paper_id + age_group + style)`), so repeat requests return instantly.

## Fact-Checking With Embeddings

A children's story about science is worse than useless if it's wrong. PaperTales doesn't just generate — it verifies. The Fact Checker agent uses `gemini-embedding-001` to:

1. Extract key claims from the generated story
2. Chunk the source paper into passages
3. Compute cosine similarity between each claim and the most relevant paper chunk
4. Produce an overall accuracy score

This is semantic verification, not keyword matching. If the story says "cells use sunlight to make food" and the paper says "photosynthetic organisms convert solar radiation into chemical energy," the embedding similarity catches that these are the same claim.

## Running on Google Cloud

The full stack runs on GCP:

- **Cloud Run** — FastAPI backend (4Gi RAM, 600s timeout for long pipeline runs)
- **Firebase Hosting** — React frontend
- **Firebase Auth** — Google, email, and anonymous sign-in
- **Cloud Firestore** — Story metadata, voting, leaderboard
- **Cloud Storage** — Images, audio, and full story JSON (Firestore has a 1MB document limit — stories with base64 images exceed that)
- **Cloud Build** — CI/CD via `cloudbuild.yaml` that builds and deploys both backend and frontend
- **Secret Manager** — API keys

Everything is infrastructure as code. A single `gcloud builds submit` deploys the entire stack.

## What I Learned

**State contracts are essential.** With 9 agents passing data through shared session state, I documented exactly which keys each agent reads and writes. Without this, debugging was impossible — with it, adding new agents became straightforward.

**ADK's ParallelAgent is a free optimization.** Audio narration and fact-checking are completely independent. Wrapping them in a `ParallelAgent` saved 30–60 seconds with zero additional complexity.

**Deterministic caching changes everything.** Without it, every page refresh triggers a 3–8 minute pipeline run. With `sha256(paper_id:age:style)` as the story ID, the app feels instant for repeat requests.

**Image generation models have hard constraints.** `gemini-2.5-flash-image` doesn't support tool use. You can't break the generation into smaller calls. You design around the model's limitations, not against them.

## Try It

PaperTales supports 8 paper archives (arXiv, bioRxiv, medRxiv, and more), 3 age groups, and 4 story styles. You can paste a paper URL or just ask a question like "What is a transformer?" — Gemini-powered search finds the best matching paper automatically.

The code is open source at [github.com/aria-vibe/paper-tales](https://github.com/aria-vibe/paper-tales).

---

*Built for the Gemini Live Agent Challenge — Creative Storyteller Track. #GeminiLiveAgentChallenge*
