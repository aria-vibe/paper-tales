"""Generate field-of-study icons using Gemini image generation.

Usage:
    cd backend && uv run python ../scripts/generate_field_icons.py
"""

import base64
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load .env from backend/
load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

FIELDS = {
    "biology": "a green leaf with a DNA helix",
    "chemistry": "a bubbling Erlenmeyer flask with colorful liquid",
    "computer-science": "a glowing terminal screen with angle brackets",
    "earth-science": "a globe showing continents with cloud swirls",
    "economics": "a rising bar chart with a coin",
    "engineering": "interlocking gears",
    "environmental-science": "a tree growing from a recycling symbol",
    "mathematics": "a pi symbol with geometric shapes",
    "medicine": "a stethoscope with a heart",
    "neuroscience": "a glowing brain with neural connections",
    "physics": "an atom with orbiting electrons",
    "psychology": "a head silhouette with a puzzle piece inside",
    "social-science": "connected people figures in a network",
    "other": "an open book with a magnifying glass",
}

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public" / "icons"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_icon(field_slug: str, subject: str) -> bool:
    output_path = OUTPUT_DIR / f"{field_slug}.png"
    if output_path.exists():
        print(f"  Skipping {field_slug} (already exists)")
        return True

    prompt = (
        f"Generate a single flat-design icon of {subject}. "
        "Style: minimal flat vector icon, solid colors, no gradients, no text, no labels, "
        "white background, centered composition, simple shapes, suitable as a small UI icon. "
        "The icon should be clean and recognizable at 64x64 pixels."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                temperature=0.8,
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                img_bytes = part.inline_data.data
                if isinstance(img_bytes, str):
                    img_bytes = base64.b64decode(img_bytes)
                output_path.write_bytes(img_bytes)
                print(f"  Saved {field_slug}.png ({len(img_bytes)} bytes)")
                return True

        print(f"  WARNING: No image in response for {field_slug}")
        return False

    except Exception as e:
        print(f"  ERROR generating {field_slug}: {e}")
        return False


def main():
    print(f"Generating {len(FIELDS)} field icons → {OUTPUT_DIR}\n")
    success = 0
    for slug, subject in FIELDS.items():
        print(f"[{slug}]")
        if generate_icon(slug, subject):
            success += 1
        # Rate limit: small delay between requests
        time.sleep(2)

    print(f"\nDone: {success}/{len(FIELDS)} icons generated.")
    if success < len(FIELDS):
        sys.exit(1)


if __name__ == "__main__":
    main()
