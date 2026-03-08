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

# Maps common subcategory names (lowercase) to their parent field in FIELD_TAXONOMY.
# Used as a safety net when the LLM outputs a subcategory instead of the parent field.
FIELD_SYNONYMS: dict[str, str] = {
    "machine learning": "Computer Science",
    "artificial intelligence": "Computer Science",
    "deep learning": "Computer Science",
    "natural language processing": "Computer Science",
    "nlp": "Computer Science",
    "computer vision": "Computer Science",
    "robotics": "Computer Science",
    "data science": "Computer Science",
    "cybersecurity": "Computer Science",
    "information theory": "Computer Science",
    "generative ai": "Computer Science",
    "video generation": "Computer Science",
    "image generation": "Computer Science",
    "diffusion models": "Computer Science",
    "neural networks": "Computer Science",
    "reinforcement learning": "Computer Science",
    "software engineering": "Computer Science",
    "ai": "Computer Science",
    "genetics": "Biology",
    "genomics": "Biology",
    "ecology": "Biology",
    "evolutionary biology": "Biology",
    "microbiology": "Biology",
    "molecular biology": "Biology",
    "bioinformatics": "Biology",
    "cell biology": "Biology",
    "epidemiology": "Medicine",
    "oncology": "Medicine",
    "immunology": "Medicine",
    "pharmacology": "Medicine",
    "public health": "Medicine",
    "clinical medicine": "Medicine",
    "pathology": "Medicine",
    "quantum physics": "Physics",
    "quantum mechanics": "Physics",
    "astrophysics": "Physics",
    "cosmology": "Physics",
    "particle physics": "Physics",
    "condensed matter": "Physics",
    "optics": "Physics",
    "biochemistry": "Chemistry",
    "organic chemistry": "Chemistry",
    "materials science": "Chemistry",
    "nanotechnology": "Chemistry",
    "statistics": "Mathematics",
    "probability": "Mathematics",
    "algebra": "Mathematics",
    "geometry": "Mathematics",
    "cognitive science": "Neuroscience",
    "neuroimaging": "Neuroscience",
    "electrical engineering": "Engineering",
    "mechanical engineering": "Engineering",
    "biomedical engineering": "Engineering",
    "finance": "Economics",
    "econometrics": "Economics",
    "climate science": "Environmental Science",
    "sustainability": "Environmental Science",
    "behavioral science": "Psychology",
    "cognitive psychology": "Psychology",
    "geology": "Earth Science",
    "oceanography": "Earth Science",
    "meteorology": "Earth Science",
    "sociology": "Social Science",
    "political science": "Social Science",
    "linguistics": "Social Science",
    "anthropology": "Social Science",
}
