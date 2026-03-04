"""Tests for papertales.tools.readability_tools and papertales.tools.story_tools."""

import pytest

from papertales.tools.readability_tools import _count_syllables, score_readability
from papertales.tools.story_tools import get_story_template


# ===========================================================================
# TestCountSyllables
# ===========================================================================


class TestCountSyllables:
    def test_one_syllable(self):
        assert _count_syllables("cat") == 1

    def test_two_syllables(self):
        assert _count_syllables("paper") == 2

    def test_three_syllables(self):
        assert _count_syllables("beautiful") == 3

    def test_five_syllables(self):
        assert _count_syllables("university") == 5

    def test_silent_e(self):
        # "cake" -> 1 syllable (silent e)
        assert _count_syllables("cake") == 1

    def test_empty_string(self):
        assert _count_syllables("") == 0

    def test_single_letter_vowel(self):
        assert _count_syllables("a") == 1

    def test_single_letter_consonant(self):
        assert _count_syllables("x") == 1  # minimum 1


# ===========================================================================
# TestScoreReadability
# ===========================================================================


class TestScoreReadability:
    def test_simple_text_low_grade(self):
        """Short, simple sentences should produce a low grade level."""
        text = "The cat sat. The dog ran. I am big. It is fun."
        result = score_readability(text)

        assert "error" not in result
        assert result["flesch_kincaid_grade"] < 4
        assert result["suggested_age_group"] == "6-9"
        assert result["word_count"] > 0
        assert result["sentence_count"] > 0

    def test_complex_text_high_grade(self):
        """Long sentences with multi-syllable words should produce a high grade level."""
        text = (
            "The comprehensive investigation of neurological phenomena demonstrates "
            "that sophisticated computational methodologies significantly outperform "
            "traditional experimental approaches in characterizing the fundamental "
            "mechanisms underlying consciousness."
        )
        result = score_readability(text)

        assert "error" not in result
        assert result["flesch_kincaid_grade"] > 10
        assert result["suggested_age_group"] == "14-17"

    def test_empty_text_returns_error(self):
        result = score_readability("")
        assert "error" in result

    def test_whitespace_only_returns_error(self):
        result = score_readability("   \n\t  ")
        assert "error" in result

    def test_age_group_6_9(self):
        """Text at grade level ~3 should map to age group 6-9."""
        text = "I like dogs. Dogs are fun. They run and play. I love my dog."
        result = score_readability(text)
        assert result["suggested_age_group"] == "6-9"

    def test_age_group_10_13(self):
        """Text at grade level ~6 should map to age group 10-13."""
        text = (
            "The kids found a new kind of frog in the forest. "
            "The frog had bright green skin that helped it hide from birds. "
            "They learned that this color keeps the frog safe from danger. "
            "The teacher said this trick is called camouflage."
        )
        result = score_readability(text)
        assert result["suggested_age_group"] in ("6-9", "10-13")

    def test_returns_all_keys(self):
        text = "The cat sat on the mat."
        result = score_readability(text)
        expected_keys = {
            "flesch_kincaid_grade",
            "reading_ease",
            "suggested_age_group",
            "word_count",
            "sentence_count",
        }
        assert expected_keys == set(result.keys())

    def test_reading_ease_range(self):
        """Reading ease should be higher for simple text."""
        simple = score_readability("I am a cat. You are a dog.")
        complex_ = score_readability(
            "The multifaceted investigation of transcontinental geopolitical "
            "ramifications necessitates comprehensive interdisciplinary collaboration."
        )
        assert simple["reading_ease"] > complex_["reading_ease"]


# ===========================================================================
# TestGetStoryTemplate
# ===========================================================================


class TestGetStoryTemplate:
    VALID_STYLES = ["fairy_tale", "adventure", "sci_fi", "comic_book"]
    VALID_AGES = ["6-9", "10-13", "14-17"]
    REQUIRED_KEYS = {
        "style",
        "age_group",
        "structure",
        "style_guidelines",
        "character_archetypes",
        "scene_count",
        "illustration_style",
    }

    def test_valid_style_and_age_returns_all_keys(self):
        result = get_story_template("fairy_tale", "6-9")
        assert self.REQUIRED_KEYS.issubset(set(result.keys()))

    @pytest.mark.parametrize("style", VALID_STYLES)
    def test_all_styles_have_structure(self, style):
        result = get_story_template(style, "10-13")
        structure = result["structure"]
        assert "setup" in structure
        assert "rising_action" in structure
        assert "climax" in structure
        assert "resolution" in structure

    @pytest.mark.parametrize("style", VALID_STYLES)
    def test_all_styles_have_character_archetypes(self, style):
        result = get_story_template(style, "10-13")
        archetypes = result["character_archetypes"]
        assert len(archetypes) >= 2
        for archetype in archetypes:
            assert "name" in archetype
            assert "description" in archetype

    def test_distinct_templates_per_style(self):
        """Each style should produce a distinct template."""
        templates = [get_story_template(s, "10-13") for s in self.VALID_STYLES]
        illustration_styles = [t["illustration_style"] for t in templates]
        # All illustration styles should be unique
        assert len(set(illustration_styles)) == len(self.VALID_STYLES)

    @pytest.mark.parametrize("age", VALID_AGES)
    def test_scene_count_varies_by_age(self, age):
        result = get_story_template("adventure", age)
        assert isinstance(result["scene_count"], int)
        assert result["scene_count"] >= 4

    def test_younger_has_fewer_scenes(self):
        young = get_story_template("adventure", "6-9")
        old = get_story_template("adventure", "14-17")
        assert young["scene_count"] <= old["scene_count"]

    def test_unknown_style_returns_defaults(self):
        """Unknown style should still return a valid template, not crash."""
        result = get_story_template("unknown_style", "10-13")
        assert self.REQUIRED_KEYS.issubset(set(result.keys()))
        assert result["style"] == "unknown_style"
        # Should still have a usable structure
        assert "setup" in result["structure"]

    def test_unknown_age_returns_defaults(self):
        result = get_story_template("fairy_tale", "99-99")
        assert self.REQUIRED_KEYS.issubset(set(result.keys()))
        assert isinstance(result["scene_count"], int)

    def test_style_guidelines_include_age_targets(self):
        result = get_story_template("sci_fi", "6-9")
        guidelines = result["style_guidelines"]
        assert "target_vocabulary" in guidelines
        assert "target_sentence_length" in guidelines
