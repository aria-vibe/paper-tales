#!/usr/bin/env python3
"""Test script: invoke the full story generation pipeline locally.

Calls the agentic flow directly (no FastAPI server needed).
Saves the generated story, images, and logs to test_output/.

Usage:
    cd backend
    export GOOGLE_API_KEY=your-key
    uv run python test_story_generation.py

    # With options:
    uv run python test_story_generation.py --url https://arxiv.org/abs/2301.00001 --age 6-9 --style adventure
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.genai import types

from papertales.agent import root_agent
from papertales.config import (
    STATE_CONCEPTS,
    STATE_FACTCHECK,
    STATE_FINAL,
    STATE_NARRATIVE,
    STATE_PAPER_TEXT,
    STATE_SIMPLIFIED,
    STATE_STORY,
    STATE_AUDIO,
    STATE_USER_AGE_GROUP,
    STATE_USER_PAPER_URL,
    STATE_USER_STYLE,
)

# Default test paper — a short, well-known arXiv paper
DEFAULT_URL = "https://arxiv.org/abs/2312.02813"

OUTPUT_DIR = Path("test_output")
APP_NAME = "papertales_test"


def print_banner(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


async def run_pipeline(paper_url: str, age_group: str, style: str):
    """Run the full 8-agent pipeline and collect all outputs."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)

    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id="test_user",
        state={
            STATE_USER_PAPER_URL: paper_url,
            STATE_USER_AGE_GROUP: age_group,
            STATE_USER_STYLE: style,
        },
    )

    print_banner("PaperTales Story Generation Test")
    print(f"Paper URL:  {paper_url}")
    print(f"Age group:  {age_group}")
    print(f"Style:      {style}")
    print(f"Session ID: {session.id}")
    print(f"Output dir: {OUTPUT_DIR.resolve()}")

    trigger = types.Content(
        role="user",
        parts=[
            types.Part(
                text=f"Transform this research paper into an illustrated story for age group {age_group} in {style} style."
            )
        ],
    )

    # Track events per agent
    agent_events: dict[str, list[str]] = {}
    image_count = 0
    audio_count = 0
    current_agent = None
    start_time = time.time()

    print_banner("Pipeline Running")

    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=trigger,
    ):
        # Track agent transitions
        if event.author and event.author != current_agent:
            current_agent = event.author
            elapsed = time.time() - start_time
            print(f"\n[{elapsed:6.1f}s] >>> Agent: {current_agent}")
            if current_agent not in agent_events:
                agent_events[current_agent] = []

        if not event.content or not event.content.parts:
            continue

        for part in event.content.parts:
            if part.text:
                snippet = part.text[:120].replace("\n", " ")
                print(f"  [TEXT] {snippet}...")
                if current_agent:
                    agent_events[current_agent].append(f"text: {snippet}")

            elif part.inline_data and part.inline_data.mime_type and part.inline_data.mime_type.startswith("image/"):
                image_count += 1
                ext = "png" if "png" in part.inline_data.mime_type else "jpg"
                img_path = OUTPUT_DIR / f"illustration_{image_count:02d}.{ext}"
                img_bytes = part.inline_data.data
                if isinstance(img_bytes, str):
                    img_bytes = base64.b64decode(img_bytes)
                img_path.write_bytes(img_bytes)
                size_kb = len(img_bytes) / 1024
                print(f"  [IMAGE] Saved {img_path.name} ({size_kb:.1f} KB)")
                if current_agent:
                    agent_events[current_agent].append(f"image: {img_path.name}")

            # Log tool calls
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                print(f"  [TOOL CALL] {fc.name}({json.dumps(dict(fc.args or {}))[:100]})")
                if current_agent:
                    agent_events[current_agent].append(f"tool_call: {fc.name}")

            if hasattr(part, "function_response") and part.function_response:
                fr = part.function_response
                resp = fr.response if isinstance(fr.response, dict) else {}
                print(f"  [TOOL RESP] {fr.name} -> {str(resp)[:100]}...")
                if current_agent:
                    agent_events[current_agent].append(f"tool_response: {fr.name}")

                # Extract TTS audio from synthesize_speech responses
                if fr.name == "synthesize_speech" and isinstance(resp, dict) and resp.get("audio_base64"):
                    audio_count += 1
                    audio_path = OUTPUT_DIR / f"narration_{audio_count:02d}.mp3"
                    audio_bytes = base64.b64decode(resp["audio_base64"])
                    audio_path.write_bytes(audio_bytes)
                    size_kb = len(audio_bytes) / 1024
                    print(f"  [AUDIO] Saved {audio_path.name} ({size_kb:.1f} KB)")
                    if current_agent:
                        agent_events[current_agent].append(f"audio: {audio_path.name}")

    total_time = time.time() - start_time

    # Retrieve final session state
    session = await runner.session_service.get_session(
        app_name=APP_NAME,
        user_id="test_user",
        session_id=session.id,
    )
    state = session.state

    print_banner("Saving Outputs")

    # Save each intermediate state key
    state_keys = [
        (STATE_PAPER_TEXT, "01_parsed_paper.txt"),
        (STATE_CONCEPTS, "02_concepts.txt"),
        (STATE_SIMPLIFIED, "03_simplified.txt"),
        (STATE_NARRATIVE, "04_narrative.txt"),
        (STATE_STORY, "05_story_raw.txt"),
        (STATE_AUDIO, "06_audio.txt"),
        (STATE_FACTCHECK, "07_factcheck.txt"),
        (STATE_FINAL, "08_final_story.json"),
    ]

    for key, filename in state_keys:
        value = state.get(key, "")
        if value:
            path = OUTPUT_DIR / filename
            content = str(value)

            # Try to pretty-print JSON for the final story
            if filename.endswith(".json"):
                try:
                    text = content.strip()
                    if text.startswith("```"):
                        text = text[text.index("\n") + 1:]
                    if text.endswith("```"):
                        text = text[:-3].rstrip()
                    parsed = json.loads(text)
                    content = json.dumps(parsed, indent=2, ensure_ascii=False)
                except (json.JSONDecodeError, ValueError):
                    pass

            path.write_text(content)
            print(f"  Saved {filename} ({len(content):,} chars)")
        else:
            print(f"  MISSING: {key} (no output from agent)")

    # Save test run summary
    summary = {
        "paper_url": paper_url,
        "age_group": age_group,
        "style": style,
        "total_time_seconds": round(total_time, 1),
        "image_count": image_count,
        "audio_count": audio_count,
        "timestamp": datetime.now().isoformat(),
        "agents_observed": list(agent_events.keys()),
        "state_keys_present": [k for k, _ in state_keys if state.get(k)],
        "state_keys_missing": [k for k, _ in state_keys if not state.get(k)],
    }
    summary_path = OUTPUT_DIR / "test_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"  Saved test_summary.json")

    # Print results
    print_banner("Results")
    print(f"Total time:     {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"Illustrations:  {image_count}")
    print(f"Audio clips:    {audio_count}")
    print(f"Agents run:     {len(agent_events)}")
    for agent, events in agent_events.items():
        print(f"  - {agent}: {len(events)} events")
    print(f"State keys OK:  {len(summary['state_keys_present'])}/{len(state_keys)}")
    if summary["state_keys_missing"]:
        print(f"  Missing: {summary['state_keys_missing']}")
    print(f"\nAll outputs in: {OUTPUT_DIR.resolve()}")

    # Basic assertions
    errors = []
    if not state.get(STATE_FINAL):
        errors.append("No final story produced (STATE_FINAL empty)")
    if not state.get(STATE_STORY):
        errors.append("No illustrated story produced (STATE_STORY empty)")
    if image_count == 0:
        errors.append("No illustrations generated")
    if len(agent_events) < 3:
        errors.append(f"Only {len(agent_events)} agents observed, expected ~8")

    if errors:
        print_banner("ISSUES DETECTED")
        for e in errors:
            print(f"  !! {e}")
        return False
    else:
        print_banner("ALL CHECKS PASSED")
        return True


def main():
    parser = argparse.ArgumentParser(description="Test PaperTales story generation pipeline")
    parser.add_argument("--url", type=str, default=DEFAULT_URL, help=f"Paper URL (default: {DEFAULT_URL})")
    parser.add_argument("--age", type=str, default="10-13", choices=["6-9", "10-13", "14-17"], help="Age group")
    parser.add_argument("--style", type=str, default="fairy_tale", choices=["fairy_tale", "adventure", "sci_fi", "comic_book"], help="Story style")
    args = parser.parse_args()

    if not os.environ.get("GOOGLE_API_KEY"):
        print("ERROR: Set GOOGLE_API_KEY first.")
        print("  export GOOGLE_API_KEY=your-key-here")
        sys.exit(1)

    success = asyncio.run(run_pipeline(args.url, args.age, args.style))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
