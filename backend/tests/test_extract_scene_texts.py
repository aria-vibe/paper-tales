"""Tests for _extract_scene_texts in audio_narrator."""

import pytest

from papertales.agents.audio_narrator import _extract_scene_texts


# ---------------------------------------------------------------------------
# Standard story markdown used across multiple tests
# ---------------------------------------------------------------------------

STANDARD_STORY = """\
# The Quantum Garden
**A fairy tale story for ages 10-13**

## Scene 1: The Discovery
Once upon a time, a young scientist found a glowing seed.

## Scene 2: The Challenge
The seed began to grow in strange, quantum ways.

## Scene 3: The Resolution
She learned to nurture the quantum plant with patience.

## The End
And so, the garden bloomed with impossible colors.

**What We Learned:** Quantum mechanics describes how tiny particles behave differently from everyday objects.

### GLOSSARY
| Term | Meaning |
|------|---------|
| Quantum | Very small scale physics |
"""


class TestBasicExtraction:
    def test_extracts_title(self):
        items = _extract_scene_texts(STANDARD_STORY)
        title = next(i for i in items if i["label"] == "title")
        assert "Quantum Garden" in title["text"]

    def test_extracts_all_scenes(self):
        items = _extract_scene_texts(STANDARD_STORY)
        scene_labels = [i["label"] for i in items if i["label"].startswith("scene_")]
        assert scene_labels == ["scene_0", "scene_1", "scene_2"]

    def test_extracts_conclusion(self):
        items = _extract_scene_texts(STANDARD_STORY)
        conclusion = next(i for i in items if i["label"] == "conclusion")
        assert "garden bloomed" in conclusion["text"]
        assert "What We Learned" in conclusion["text"]

    def test_glossary_excluded_from_conclusion(self):
        items = _extract_scene_texts(STANDARD_STORY)
        conclusion = next(i for i in items if i["label"] == "conclusion")
        assert "Quantum" not in conclusion["text"] or "Very small" not in conclusion["text"]

    def test_empty_input(self):
        assert _extract_scene_texts("") == []
        assert _extract_scene_texts("   ") == []
        assert _extract_scene_texts(None) == []


class TestTitlePreambleFiltering:
    """Bug fix: model preamble before the # header should be excluded."""

    def test_preamble_before_title_is_stripped(self):
        story = """\
I'll create a fairy tale story about quantum physics for you.

# The Quantum Garden
**A fairy tale story for ages 10-13**

## Scene 1: The Discovery
Once upon a time.

## The End
The end of the story.
"""
        items = _extract_scene_texts(story)
        title = next(i for i in items if i["label"] == "title")
        assert "I'll create" not in title["text"]
        assert "Quantum Garden" in title["text"]

    def test_error_text_before_title_is_stripped(self):
        story = """\
I apologize, but I encountered an issue generating the illustration.
Let me continue with the story text.

# The Magic Seed
**An adventure story for ages 6-9**

## Scene 1: Begin
The hero set off.

## The End
Happily ever after.
"""
        items = _extract_scene_texts(story)
        title = next(i for i in items if i["label"] == "title")
        assert "apologize" not in title["text"]
        assert "Magic Seed" in title["text"]

    def test_image_marker_in_title_is_filtered(self):
        story = """\
# The Sun Story
**A fairy tale for ages 6-9**
[Generate title illustration here]

## Scene 1: Dawn
The sun rose.

## The End
Goodbye.
"""
        items = _extract_scene_texts(story)
        title = next(i for i in items if i["label"] == "title")
        assert "Generate" not in title["text"]
        assert "Sun Story" in title["text"]


class TestConclusionCaseInsensitive:
    """Bug fix: ## The End matching should be case-insensitive."""

    def test_uppercase_the_end(self):
        story = """\
# Title

## Scene 1: Start
Hello world.

## THE END
This is the conclusion.

**What We Learned:** Science is cool.

### GLOSSARY
| Term | Meaning |
"""
        items = _extract_scene_texts(story)
        conclusion = next((i for i in items if i["label"] == "conclusion"), None)
        assert conclusion is not None
        assert "conclusion" in conclusion["text"].lower() or "Science is cool" in conclusion["text"]

    def test_bold_the_end(self):
        story = """\
# Title

## Scene 1: Start
Hello world.

## **The End**
This is the conclusion.

### GLOSSARY
| Term | Meaning |
"""
        items = _extract_scene_texts(story)
        conclusion = next((i for i in items if i["label"] == "conclusion"), None)
        assert conclusion is not None
        assert "conclusion" in conclusion["text"].lower() or "The End" not in conclusion["text"]

    def test_mixed_case_the_end(self):
        story = """\
# Title

## Scene 1: Start
Hello world.

## the end
Wrap up text here.
"""
        items = _extract_scene_texts(story)
        conclusion = next((i for i in items if i["label"] == "conclusion"), None)
        assert conclusion is not None
        assert "Wrap up" in conclusion["text"]


class TestSceneEndMarkerVariations:
    """The scene loop should also handle end marker case variations."""

    def test_uppercase_end_not_in_last_scene(self):
        story = """\
# Title

## Scene 1: Only Scene
Scene text here.

## THE END
Conclusion text.
"""
        items = _extract_scene_texts(story)
        scene = next(i for i in items if i["label"] == "scene_0")
        assert "Conclusion" not in scene["text"]
        assert "Scene text" in scene["text"]

    def test_bold_end_not_in_last_scene(self):
        story = """\
# Title

## Scene 1: Only Scene
Scene text here.

## **The End**
Conclusion text.
"""
        items = _extract_scene_texts(story)
        scene = next(i for i in items if i["label"] == "scene_0")
        assert "Conclusion" not in scene["text"]


class TestFallbackEndMarker:
    """Fallback: THE END without ## header, or What We Learned standalone."""

    def test_the_end_without_header(self):
        """Model writes 'THE END' on its own line without ## prefix."""
        story = """\
# Title

## Scene 1: Start
Story text here.

THE END

**What We Learned:** Plants need sunlight.

### GLOSSARY
| Term | Meaning |
"""
        items = _extract_scene_texts(story)
        scene = next(i for i in items if i["label"] == "scene_0")
        assert "THE END" not in scene["text"]
        conclusion = next((i for i in items if i["label"] == "conclusion"), None)
        assert conclusion is not None
        assert "Plants need sunlight" in conclusion["text"]

    def test_bold_the_end_without_header(self):
        """Model writes '**THE END**' on its own line without ## prefix."""
        story = """\
# Title

## Scene 1: Start
Story text here.

**THE END**

What We Learned: Science is fun.
"""
        items = _extract_scene_texts(story)
        conclusion = next((i for i in items if i["label"] == "conclusion"), None)
        assert conclusion is not None
        assert "Science is fun" in conclusion["text"]

    def test_what_we_learned_without_any_end_marker(self):
        """Model has no 'The End' at all but does have 'What We Learned'."""
        story = """\
# Title

## Scene 1: Start
Story text here.

## Scene 2: Finish
More story.

**What We Learned:** The ocean is deep.

### GLOSSARY
| Term | Meaning |
"""
        items = _extract_scene_texts(story)
        conclusion = next((i for i in items if i["label"] == "conclusion"), None)
        assert conclusion is not None
        assert "ocean is deep" in conclusion["text"]

    def test_inline_the_end_in_scene_does_not_false_trigger(self):
        """'The End' inside a sentence should not trigger the marker."""
        story = """\
# Title

## Scene 1: Start
They walked toward the end of the road.

## The End
Real conclusion here.
"""
        items = _extract_scene_texts(story)
        scene = next(i for i in items if i["label"] == "scene_0")
        # "the end" in a sentence should not be removed
        assert "walked toward" in scene["text"]


class TestNoiseLineFiltering:
    def test_table_rows_excluded(self):
        items = _extract_scene_texts(STANDARD_STORY)
        for item in items:
            assert "|" not in item["text"]

    def test_generate_markers_excluded_from_scenes(self):
        story = """\
# Title

## Scene 1: Start
Story text here.
[Generate illustration of the scene]

## The End
Done.
"""
        items = _extract_scene_texts(story)
        scene = next(i for i in items if i["label"] == "scene_0")
        assert "Generate" not in scene["text"]

    def test_markdown_formatting_stripped(self):
        items = _extract_scene_texts(STANDARD_STORY)
        for item in items:
            assert "#" not in item["text"]
            assert "**" not in item["text"]
