# 🧪→📖 PaperTales: Research-to-Story Creative Storyteller Agent

## Project Plan for the Gemini Live Agent Challenge — Creative Storyteller Track

---

## 1. Vision & Problem Statement

**The Problem:** Research papers are the frontier of human knowledge, but they are locked behind jargon, dense notation, and academic conventions. A child curious about black holes, CRISPR, or climate change has no bridge between a published paper and their understanding.

**The Solution — PaperTales:** An AI agent that ingests any research paper and transforms it into a rich, multimodal, age-appropriate story — weaving together simplified narration, AI-generated illustrations, and optional audio — all produced in a single, fluid interleaved output stream powered by Gemini.

**Target Users:** Children (6–9), tweens (10–13), and teens (14–17), along with teachers and parents who want to make science accessible.

---

## 2. Challenge Category Alignment

| Requirement | How PaperTales Meets It |
|---|---|
| **Creative Storyteller focus** | Transforms papers into narrative stories with interleaved text + images + audio |
| **Multimodal interleaved output** | Uses Gemini's native interleaved text & image generation in a single API call |
| **Built with Google GenAI SDK or ADK** | Multi-agent system built entirely on **Google ADK (Python)** |
| **Leverages a Gemini model** | Uses `gemini-2.5-flash` for reasoning and `gemini-2.5-flash-image` for interleaved generation |
| **At least one Google Cloud service** | Cloud Run (hosting), Cloud Storage (papers/assets), Firestore (sessions), Vertex AI, Cloud TTS |
| **Hosted on Google Cloud** | Backend deployed as a containerized service on **Cloud Run** |

---

## 3. Multi-Agent Architecture (ADK)

PaperTales uses the **Google Agent Development Kit (ADK)** to orchestrate a pipeline of specialized agents. Each agent has a single responsibility, and the Root Orchestrator sequences them using ADK's `SequentialAgent` workflow.

### Agent Roster

| # | Agent Name | Role | Gemini Model | Key Tools |
|---|---|---|---|---|
| 0 | **Root Orchestrator** | Routes input, manages session state, sequences sub-agents | `gemini-2.5-flash` | ADK SequentialAgent |
| 1 | **Paper Parser** | Extracts raw text, figures, tables, and metadata from uploaded PDF/URL | `gemini-2.5-flash` | PDF extraction tool, URL fetcher |
| 2 | **Concept Extractor** | Identifies core concepts, jargon terms, key findings, and their relationships | `gemini-2.5-flash` | Custom concept-map tool |
| 3 | **Language Simplifier** | Rewrites extracted content to the target reading level (age group) | `gemini-2.5-flash` | Readability scorer tool |
| 4 | **Narrative Designer** | Converts simplified concepts into a story arc with characters, metaphors, and scenes | `gemini-2.5-flash` | Story template tool |
| 5 | **Story Writer + Illustrator** | Generates the final interleaved text + image output using Gemini's native capabilities | `gemini-2.5-flash-image` | Gemini interleaved output (responseModalities: TEXT + IMAGE) |
| 6 | **Audio Narrator** | Produces voiceover narration for the story | Cloud TTS / Gemini Live API | Cloud Text-to-Speech |
| 7 | **Fact-Check Agent** | Validates that simplified story remains scientifically accurate vs. the source | `gemini-2.5-flash` | Semantic comparison tool |
| 8 | **Story Assembler** | Combines all modalities into the final deliverable and saves to Firestore | `gemini-2.5-flash` | Firestore write tool, GCS upload |

---

## 4. End-to-End Flow

### Step-by-step Walkthrough

**Step 1 — User Input**
The user uploads a research paper (PDF, pasted text, or arXiv URL), selects an age group (6–9 / 10–13 / 14–17), and optionally picks a story style (fairy tale, adventure, sci-fi, comic book).

**Step 2 — Paper Parsing (Agent 1)**
The Paper Parser agent extracts the full text, identifies sections (Abstract, Methods, Results, Discussion), pulls out any embedded figures, and structures the content into a machine-readable format stored in Cloud Storage.

**Step 3 — Concept Extraction (Agent 2)**
The Concept Extractor analyzes the parsed content and produces a concept map: a ranked list of key ideas, technical terms with plain-language definitions, cause-effect relationships, and the paper's core contribution in one sentence.

**Step 4 — Language Simplification (Agent 3)**
The Language Simplifier rewrites each concept for the selected age group. For ages 6–9, it uses simple sentences and everyday analogies ("DNA is like an instruction book for your body"). For 14–17, it preserves more complexity while still removing unnecessary jargon. A readability scorer tool validates the output against target Flesch-Kincaid levels.

**Step 5 — Narrative Design (Agent 4)**
The Narrative Designer maps the simplified concepts onto a story structure. It creates characters (e.g., "Captain Neuron" for a neuroscience paper), builds a three-act arc (Setup → Conflict/Discovery → Resolution), and assigns each concept to a scene. It also generates image-prompt briefs for each scene.

**Step 6 — Interleaved Multimodal Generation (Agent 5) ⭐ CORE**
This is the heart of the project and the mandatory tech. The Story Writer + Illustrator agent calls Gemini with `responseModalities: [TEXT, IMAGE]` to produce a single, fluid output stream that interleaves narration paragraphs with generated illustrations. For example:

```
[TEXT] "Once upon a time, in the tiniest kingdom inside your body, lived a brave messenger named mRNA..."
[IMAGE] — A colorful illustration of a cartoon mRNA character walking through a cell
[TEXT] "mRNA carried an important letter from the King of the Nucleus to the Ribosome Factory..."
[IMAGE] — A whimsical factory scene with ribosomes assembling proteins
```

This uses Gemini's native image generation (Nano Banana) and does NOT require separate image model calls — it's all one cohesive generation.

**Step 7 — Audio Narration (Agent 6)**
The text portions are sent to Google Cloud Text-to-Speech (or Gemini Live API for more expressive voice) to create a child-friendly voiceover. Different character voices can be assigned to different story characters.

**Step 8 — Fact-Checking (Agent 7)**
The Fact-Check agent compares the generated story against the original paper's findings using semantic similarity. It flags any oversimplifications that distort the science and suggests corrections. This ensures we make things simple but never wrong.

**Step 9 — Assembly & Delivery (Agent 8)**
The Story Assembler compiles the interleaved text + images, audio tracks, and metadata into a final story object. It saves the result to Firestore for session persistence and uploads media assets to Cloud Storage. The frontend receives a structured story that it renders as a scrollable, interactive storybook.

---

## 5. Tech Stack

| Layer | Technology |
|---|---|
| **Agent Framework** | Google ADK (Python) — `SequentialAgent`, `LlmAgent`, `FunctionTool` |
| **LLM — Reasoning** | `gemini-2.5-flash` via Vertex AI |
| **LLM — Interleaved Output** | `gemini-2.5-flash-image` (Nano Banana) — text + image in one call |
| **Audio** | Google Cloud Text-to-Speech API |
| **Backend Hosting** | Google Cloud Run (containerized Python/FastAPI) |
| **Storage** | Google Cloud Storage (PDFs, images, audio files) |
| **Database** | Firestore (user sessions, generated stories, preferences) |
| **Frontend** | React web app (hosted on Firebase Hosting or Cloud Run) |
| **CI/CD** | Cloud Build → Cloud Run (bonus: Infrastructure as Code) |
| **PDF Processing** | PyMuPDF / pdfplumber (within Paper Parser agent tool) |

---

## 6. Key Code Pattern — Interleaved Output

The mandatory tech for the Creative Storyteller track is Gemini's interleaved output. Here is the core pattern used by the Story Writer + Illustrator agent:

```python
from google import genai
from google.genai.types import GenerateContentConfig, Modality

client = genai.Client()

response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=(
        "You are a children's story illustrator and narrator. "
        "Tell an engaging story for a 10-year-old about how mRNA vaccines work. "
        "For each scene, write a paragraph of narration followed by a matching "
        "colorful, child-friendly illustration. "
        "Use a whimsical adventure style with cartoon characters."
    ),
    config=GenerateContentConfig(
        response_modalities=[Modality.TEXT, Modality.IMAGE],
    ),
)

# Process the interleaved stream
for part in response.candidates[0].content.parts:
    if part.text:
        print(f"[NARRATION] {part.text}")
    elif part.inline_data:
        # Save the generated illustration
        save_image(part.inline_data.data, part.inline_data.mime_type)
```

---

## 7. ADK Agent Definition Pattern

```python
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

# Define individual agents
concept_extractor = LlmAgent(
    name="concept_extractor",
    model="gemini-2.5-flash",
    instruction="""You are a scientific concept analyst. Given parsed 
    research paper text, extract: key concepts, jargon definitions, 
    cause-effect chains, and the core finding in one sentence.""",
    tools=[concept_map_tool],
)

narrative_designer = LlmAgent(
    name="narrative_designer",
    model="gemini-2.5-flash",
    instruction="""You are a children's story architect. Convert 
    scientific concepts into an engaging story arc with characters, 
    metaphors, and scenes appropriate for the target age group.""",
    tools=[story_template_tool],
)

# Orchestrate with SequentialAgent
root_agent = SequentialAgent(
    name="papertales_orchestrator",
    sub_agents=[
        paper_parser,
        concept_extractor,
        language_simplifier,
        narrative_designer,
        story_illustrator,   # Uses gemini-2.5-flash-image
        audio_narrator,
        fact_checker,
        story_assembler,
    ],
)
```

---

## 8. Judging Criteria Alignment

| Criteria (Weight) | How PaperTales Scores |
|---|---|
| **Innovation & Multimodal UX (40%)** | Breaks the text box — paper in, illustrated storybook out. Interleaved images + text + audio in one stream. Age-adaptive persona. |
| **Technical Implementation (30%)** | ADK multi-agent pipeline, Gemini interleaved output, Cloud Run deployment, Firestore persistence, fact-checking loop. |
| **Demo & Presentation (30%)** | Live demo: upload a real paper, watch the story generate scene-by-scene with illustrations appearing inline. Clear architecture diagram. |

---

## 9. Example Use Case

**Input:** A research paper on CRISPR-Cas9 gene editing  
**Age Group:** 10–13  
**Style:** Adventure  

**Output (interleaved):**

> 🔤 *"Deep inside every living thing, there's a secret library called DNA. Each book in this library holds instructions for building YOU — from the color of your eyes to how tall you'll grow..."*
>
> 🖼️ *[Generated illustration: A colorful library inside a cell, with tiny characters browsing bookshelves made of DNA strands]*
>
> 🔤 *"But sometimes, a typo sneaks into one of the books. That's where our hero comes in — meet CRISPR, the world's tiniest editor, armed with molecular scissors!"*
>
> 🖼️ *[Generated illustration: A cartoon character with scissors approaching a DNA strand, looking determined]*
>
> 🔊 *[Audio narration plays with an enthusiastic, age-appropriate voice]*

---

## 10. Submission Checklist

- [ ] **Text Description** — This plan + README in the repo
- [ ] **Public Code Repository** — GitHub with spin-up instructions
- [ ] **Proof of GCP Deployment** — Screen recording of Cloud Run console + logs
- [ ] **Architecture Diagram** — The Mermaid diagram (rendered) + PNG export
- [ ] **Demo Video** — < 4 min, showing live paper upload → story generation
- [ ] **Bonus: Blog post** — "Building PaperTales with Google ADK & Gemini" with #GeminiLiveAgentChallenge
- [ ] **Bonus: IaC deployment** — Terraform/Cloud Build scripts in repo
- [ ] **Bonus: GDG profile** — Link to Google Developer Group membership

---

## 11. Development Timeline (Suggested)

| Phase | Duration | Deliverables |
|---|---|---|
| **Setup & Scaffolding** | Day 1–2 | GCP project, ADK setup, Cloud Run hello-world, repo structure |
| **Core Agents (Parsing + Extraction)** | Day 3–5 | Paper Parser, Concept Extractor, basic pipeline working |
| **Simplification + Narrative** | Day 6–8 | Language Simplifier, Narrative Designer, age-adaptive prompts |
| **Interleaved Generation** | Day 9–12 | Story Writer + Illustrator with Gemini interleaved output (KEY MILESTONE) |
| **Audio + Fact-Check** | Day 13–14 | Cloud TTS integration, Fact-Check agent |
| **Frontend & Assembly** | Day 15–17 | React storybook viewer, Story Assembler, Firestore persistence |
| **Testing & Polish** | Day 18–19 | End-to-end testing, edge cases, UI polish |
| **Demo Video & Submission** | Day 20 | Record demo, write description, finalize README, submit |

---

*Built with ❤️ for the Gemini Live Agent Challenge — Creative Storyteller Track*
