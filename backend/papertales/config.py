"""Centralized configuration for PaperTales agents."""

from google.adk.models import Gemini
from google.genai import types

# Retry config for transient Gemini API errors (408, 429, 5xx)
RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=5,
    initial_delay=2.0,
    max_delay=60.0,
    exp_base=2.0,
    http_status_codes=[408, 429, 500, 502, 503, 504],
)

# Model objects with retry support
MODEL_GEMINI_FLASH = Gemini(model="gemini-2.5-flash", retry_options=RETRY_OPTIONS)
MODEL_GEMINI_FLASH_LITE = Gemini(model="gemini-2.5-flash-lite", retry_options=RETRY_OPTIONS)
MODEL_GEMINI_FLASH_IMAGE = Gemini(model="gemini-2.5-flash-image", retry_options=RETRY_OPTIONS)

# State keys — each agent writes to its output_key, next agent reads via template
STATE_PAPER_TEXT = "parsed_paper"
STATE_CONCEPTS = "extracted_concepts"
STATE_SIMPLIFIED = "simplified_content"
STATE_NARRATIVE = "narrative_design"
STATE_STORY = "generated_story"
STATE_AUDIO = "audio_urls"
STATE_FACTCHECK = "fact_check_result"
STATE_FINAL = "final_story"
STATE_STORY_TEMPLATE = "story_template"

# Scene count (extracted from story template for quality gates)
STATE_SCENE_COUNT = "scene_count"

# Correlation keys
STATE_SESSION_ID = "session_id"

# Paper cache key (set to "true" when parsed content is pre-loaded from cache)
STATE_PAPER_CACHED = "paper_cached"

# User-provided input keys
STATE_USER_PAPER_URL = "user_paper_url"
STATE_USER_AGE_GROUP = "age_group"
STATE_USER_STYLE = "story_style"

# Field of study classification
STATE_FIELD_OF_STUDY = "field_of_study"

FIELD_TAXONOMY = [
    "Biology",
    "Chemistry",
    "Computer Science",
    "Earth Science",
    "Economics",
    "Engineering",
    "Environmental Science",
    "Mathematics",
    "Medicine",
    "Neuroscience",
    "Physics",
    "Psychology",
    "Social Science",
    "Other",
]
