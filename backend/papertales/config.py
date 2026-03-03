"""Centralized configuration for PaperTales agents."""

# Model names
MODEL_GEMINI_FLASH = "gemini-2.5-flash"
MODEL_GEMINI_FLASH_IMAGE = "gemini-2.5-flash-preview-image-generation"

# State keys — each agent writes to its output_key, next agent reads via template
STATE_PAPER_TEXT = "parsed_paper"
STATE_CONCEPTS = "extracted_concepts"
STATE_SIMPLIFIED = "simplified_content"
STATE_NARRATIVE = "narrative_design"
STATE_STORY = "generated_story"
STATE_AUDIO = "audio_urls"
STATE_FACTCHECK = "fact_check_result"
STATE_FINAL = "final_story"

# User-provided input keys
STATE_USER_PDF = "user_pdf_path"
STATE_USER_AGE_GROUP = "age_group"
STATE_USER_STYLE = "story_style"
