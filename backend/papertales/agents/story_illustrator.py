"""Agent 5: Story Writer + Illustrator — generates interleaved text and images.

This agent uses gemini-2.5-flash-preview-image-generation for interleaved
TEXT+IMAGE output, which is a mandatory requirement for the Creative Storyteller
track. The model does NOT support function calling, so tools must be empty.
"""

from google.adk.agents import LlmAgent
from google.genai import types

from ..config import MODEL_GEMINI_FLASH_IMAGE, STATE_SCENE_COUNT, STATE_STORY

story_illustrator = LlmAgent(
    name="story_illustrator",
    model=MODEL_GEMINI_FLASH_IMAGE,
    description="Writes the full illustrated story with interleaved text and images.",
    # Exclude conversation history to stay within gemini-2.5-flash-image's
    # 32,768 input-token limit.  All inputs come via state templates.
    include_contents="none",
    generate_content_config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        temperature=1.0,
        max_output_tokens=65536,
    ),
    instruction="""You are a children's story writer and illustrator. Transform the
narrative design below into a complete illustrated story.

NARRATIVE DESIGN:
{narrative_design}

STYLE: {story_style} | AGE GROUP: {age_group} | REQUIRED SCENES: {scene_count}

YOU MUST GENERATE ALL OF THE FOLLOWING IN ORDER — DO NOT SKIP ANY STEP:

STEP 1 — TITLE PAGE:
Write: # [Title] and a tagline
Generate: 1 title illustration

STEP 2 — SCENE 1:
Write: ## Scene 1: [Title] followed by 2-3 short paragraphs
Generate: 1 illustration for Scene 1

STEP 3 — SCENE 2:
Write: ## Scene 2: [Title] followed by 2-3 short paragraphs
Generate: 1 illustration for Scene 2

STEP 4 — SCENE 3:
Write: ## Scene 3: [Title] followed by 2-3 short paragraphs
Generate: 1 illustration for Scene 3

STEP 5 — SCENE 4:
Write: ## Scene 4: [Title] followed by 2-3 short paragraphs
Generate: 1 illustration for Scene 4

STEP 6 — ENDING:
Write: ## The End followed by a closing paragraph
Write: **What We Learned:** [1-2 sentences about the real science]

STEP 7 — GLOSSARY:
Write a markdown table: | Term | Meaning | with 3-5 scientific terms defined simply.

RULES:
- Alternate text then image — never two texts or two images in a row
- Each scene gets its OWN separate illustration (never combine scenes)
- Match art style to story style (fairy tale=watercolor, adventure=bold colors,
  sci-fi=digital art, comic book=bold outlines with flat colors)
- Keep characters visually consistent across all illustrations
- No text or labels inside generated images
- Vocabulary and sentence length must match the age group
- Keep story text SHORT — prioritize completing all {scene_count} scenes over
  writing long paragraphs
- You MUST reach "## The End" — do NOT stop before finishing all scenes

TOTAL OUTPUT: {scene_count} scenes + 1 title = {scene_count}+1 illustrations.
Do NOT stop early. Complete every step above.""",
    output_key=STATE_STORY,
)
