#!/usr/bin/env python3
"""Demo script for the PaperTales pipeline.

Usage:
    # Quick demo — Agents 5 & 6 only with mock state (no PDF needed)
    cd backend && uv run python demo_pipeline.py --quick

    # Full pipeline with arXiv URL
    cd backend && uv run python demo_pipeline.py --arxiv https://arxiv.org/abs/2301.00001

    # Full pipeline with local PDF
    cd backend && uv run python demo_pipeline.py --pdf path/to/paper.pdf

Options:
    --age    Target age group (default: 10-13)
    --style  Story style (default: fairy_tale)
"""

import argparse
import asyncio
import base64
import os
import sys
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.adk.agents import SequentialAgent
from google.genai import types

OUTPUT_DIR = Path("demo_output")

# ---------------------------------------------------------------------------
# Mock data for --quick mode (Agents 5-6 only)
# ---------------------------------------------------------------------------

MOCK_NARRATIVE_DESIGN = """\
## NARRATIVE DESIGN

### Story Metadata
- **Source paper**: "Quantum Efficiency of Photosystem II in Arabidopsis Under Variable Light"
- **Core concept**: Photosynthesis — how plants convert sunlight into energy using special molecular machines called photosystems
- **Target age group**: {age_group}
- **Story style**: {story_style}
- **Number of scenes**: 5

### Characters
1. **Lily** — A curious 10-year-old girl with curly red hair, green overalls, and muddy boots. She loves her grandmother's garden.
2. **Professor Chloro** — A talking chloroplast (tiny green oval with friendly eyes and a lab coat). He is wise, patient, and enthusiastic about science.
3. **Sunny** — A playful photon of light, depicted as a small glowing golden orb with a cheerful face.

### Scene Outlines

#### Scene 1: The Wilting Garden
- **Setting**: Grandma's garden on a cloudy day. Flowers are drooping.
- **Plot**: Lily notices the garden looks sad without sunlight. She wonders why plants need the sun.
- **Key concept**: Plants depend on light energy to survive.
- **Illustration prompt**: A girl with curly red hair in green overalls kneeling in a garden of drooping flowers under grey clouds.

#### Scene 2: Shrinking Down
- **Setting**: Inside a leaf — a vast green landscape of cells.
- **Plot**: Professor Chloro appears and shrinks Lily to microscopic size. They enter a leaf cell and see towering green structures (chloroplasts).
- **Key concept**: Photosynthesis happens inside chloroplasts in leaf cells.
- **Illustration prompt**: A tiny girl and a green oval character with a lab coat standing inside a giant leaf cell, surrounded by enormous green oval chloroplasts.

#### Scene 3: The Light Harvest
- **Setting**: Inside a chloroplast — the thylakoid membrane, visualized as a glowing green factory floor.
- **Plot**: Sunny the photon arrives and gets captured by antenna pigments. Lily watches as Sunny's energy is passed along a chain of molecules like a relay race.
- **Key concept**: Photosystem II captures light energy and passes it through an electron transport chain.
- **Illustration prompt**: A glowing golden orb being caught by green cup-shaped molecules on a glowing membrane, with the girl and green character watching excitedly.

#### Scene 4: Water Splitting
- **Setting**: The oxygen-evolving complex, visualized as a sparkling fountain.
- **Plot**: Professor Chloro shows Lily how water molecules are split apart, releasing oxygen bubbles that float up and out of the leaf. Lily realizes this is the oxygen she breathes!
- **Key concept**: Photosystem II splits water into oxygen, protons, and electrons.
- **Illustration prompt**: Sparkling water molecules breaking apart into glowing blue oxygen bubbles floating upward, with the girl gasping in wonder.

#### Scene 5: Back to the Garden
- **Setting**: Grandma's garden, now bathed in warm sunlight.
- **Plot**: Lily returns to normal size. The clouds part, sunlight streams down, and the flowers perk up. Lily understands what's happening inside every leaf.
- **Key concept**: Sunlight drives the whole process — healthy plants = working photosystems.
- **Illustration prompt**: The girl smiling in a sunlit garden of vibrant, upright flowers, holding a green leaf up to the light with a knowing smile.

### Emotional Arc
Setup (wonder) → Discovery (excitement) → Awe (the molecular world) → Understanding (connection to breathing) → Resolution (appreciation)
"""


# ---------------------------------------------------------------------------
# Quick demo: Agents 5-6 with mock state
# ---------------------------------------------------------------------------


async def run_quick_demo(age_group: str, style: str):
    from google.adk.agents import LlmAgent
    from google.adk.tools import FunctionTool
    from papertales.config import (
        MODEL_GEMINI_FLASH,
        MODEL_GEMINI_FLASH_IMAGE,
        STATE_AUDIO,
        STATE_STORY,
    )
    from papertales.agents.story_illustrator import story_illustrator as si_template
    from papertales.agents.audio_narrator import audio_narrator as an_template
    from papertales.tools.audio_tools import get_voice_for_age_group, synthesize_speech

    demo_story_illustrator = LlmAgent(
        name="story_illustrator",
        model=MODEL_GEMINI_FLASH_IMAGE,
        description=si_template.description,
        generate_content_config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            temperature=1.0,
        ),
        instruction=si_template.instruction,
        output_key=STATE_STORY,
    )

    demo_audio_narrator = LlmAgent(
        name="audio_narrator",
        model=MODEL_GEMINI_FLASH,
        description=an_template.description,
        instruction=an_template.instruction,
        tools=[
            FunctionTool(get_voice_for_age_group),
            FunctionTool(synthesize_speech),
        ],
        output_key=STATE_AUDIO,
    )

    demo_pipeline = SequentialAgent(
        name="demo_pipeline",
        description="Demo: story illustrator + audio narrator",
        sub_agents=[demo_story_illustrator, demo_audio_narrator],
    )

    runner = InMemoryRunner(agent=demo_pipeline, app_name="papertales_demo")

    narrative_text = MOCK_NARRATIVE_DESIGN.replace("{age_group}", age_group).replace(
        "{story_style}", style
    )

    user_id = "demo_user"
    session = await runner.session_service.create_session(
        app_name="papertales_demo",
        user_id=user_id,
        state={
            "narrative_design": narrative_text,
            "age_group": age_group,
            "story_style": style,
        },
    )

    print(f"Session {session.id} created with mock state.")
    print("Running Agent 5 (Story Illustrator) + Agent 6 (Audio Narrator)...")
    print("This may take 1-3 minutes (image generation is slow).\n")

    user_msg = types.Content(
        role="user",
        parts=[types.Part(text="Create the illustrated story and audio narration based on the narrative design.")],
    )

    story_text_parts = []
    image_count = 0

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=user_msg,
    ):
        if not event.content or not event.content.parts:
            continue

        for part in event.content.parts:
            if part.text:
                story_text_parts.append(part.text)
                snippet = part.text[:200].replace("\n", " ")
                print(f"  [TEXT] ({event.author}) {snippet}...")
            elif part.inline_data and part.inline_data.mime_type.startswith("image/"):
                image_count += 1
                ext = "png" if "png" in part.inline_data.mime_type else "jpg"
                img_path = OUTPUT_DIR / f"illustration_{image_count:02d}.{ext}"
                img_bytes = part.inline_data.data
                if isinstance(img_bytes, str):
                    img_bytes = base64.b64decode(img_bytes)
                img_path.write_bytes(img_bytes)
                print(f"  [IMAGE] Saved {img_path} ({len(img_bytes):,} bytes)")
                story_text_parts.append(f"\n[Illustration {image_count}: {img_path.name}]\n")

    full_text = "\n".join(story_text_parts)
    story_path = OUTPUT_DIR / "story.md"
    story_path.write_text(full_text)
    print(f"\nStory saved to {story_path}")
    print(f"Total illustrations: {image_count}")

    session = await runner.session_service.get_session(
        app_name="papertales_demo",
        user_id=user_id,
        session_id=session.id,
    )
    audio_output = session.state.get("audio_urls", "")
    if audio_output:
        audio_path = OUTPUT_DIR / "audio_narration.md"
        audio_path.write_text(str(audio_output))
        print(f"Audio narration saved to {audio_path}")
    else:
        print("Note: Audio narration state not found (TTS may require GCP credentials)")

    print(f"\nAll outputs in: {OUTPUT_DIR.resolve()}")


# ---------------------------------------------------------------------------
# Full pipeline: all 8 agents
# ---------------------------------------------------------------------------


async def run_full_pipeline(pdf_source: str, age_group: str, style: str):
    from papertales.agent import root_agent
    from papertales.config import STATE_FINAL, STATE_USER_AGE_GROUP, STATE_USER_PAPER_URL, STATE_USER_STYLE

    runner = InMemoryRunner(agent=root_agent, app_name="papertales")

    user_id = "demo_user"
    session = await runner.session_service.create_session(
        app_name="papertales",
        user_id=user_id,
        state={
            STATE_USER_PAPER_URL: pdf_source,
            STATE_USER_AGE_GROUP: age_group,
            STATE_USER_STYLE: style,
        },
    )

    print(f"Session {session.id} created.")
    print(f"Source: {pdf_source}")
    print(f"Age group: {age_group}, Style: {style}")
    print("Running full 8-agent pipeline (this may take several minutes)...\n")

    trigger = types.Content(
        role="user",
        parts=[
            types.Part(
                text=f"Transform this research paper into an illustrated story for age group {age_group} in {style} style."
            )
        ],
    )

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=trigger,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    snippet = part.text[:150].replace("\n", " ")
                    print(f"  [{event.author}] {snippet}...")

    # Retrieve final story
    session = await runner.session_service.get_session(
        app_name="papertales",
        user_id=user_id,
        session_id=session.id,
    )
    final_story = session.state.get(STATE_FINAL, "")

    if final_story:
        story_path = OUTPUT_DIR / "final_story.json"
        story_path.write_text(str(final_story))
        print(f"\nFinal story saved to {story_path}")
    else:
        print("\nWarning: No final_story in session state.")

    print(f"All outputs in: {OUTPUT_DIR.resolve()}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="PaperTales demo pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--quick", action="store_true", help="Quick demo with Agents 5-6 and mock state")
    group.add_argument("--arxiv", type=str, metavar="URL", help="arXiv URL for full 8-agent pipeline")
    group.add_argument("--pdf", type=str, metavar="PATH", help="Local PDF path for full 8-agent pipeline")
    parser.add_argument("--age", type=str, default="10-13", help="Target age group (default: 10-13)")
    parser.add_argument("--style", type=str, default="fairy_tale", help="Story style (default: fairy_tale)")
    args = parser.parse_args()

    if not os.environ.get("GOOGLE_API_KEY"):
        print("ERROR: Set GOOGLE_API_KEY first.")
        print("  export GOOGLE_API_KEY=your-key-here")
        sys.exit(1)

    OUTPUT_DIR.mkdir(exist_ok=True)

    if args.quick:
        asyncio.run(run_quick_demo(args.age, args.style))
    elif args.arxiv:
        asyncio.run(run_full_pipeline(args.arxiv, args.age, args.style))
    elif args.pdf:
        pdf_path = str(Path(args.pdf).resolve())
        if not Path(pdf_path).exists():
            print(f"ERROR: PDF not found: {pdf_path}")
            sys.exit(1)
        asyncio.run(run_full_pipeline(pdf_path, args.age, args.style))


if __name__ == "__main__":
    main()
