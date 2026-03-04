"""Tools for scoring text readability using Flesch-Kincaid metrics."""

import re


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _count_syllables(word: str) -> int:
    """Count syllables in a word using a vowel-group heuristic.

    Rules:
    1. Count groups of consecutive vowels as one syllable each.
    2. Subtract 1 if the word ends with a silent 'e' (but not "le").
    3. Every word has at least 1 syllable.
    """
    word = word.lower().strip()
    if not word:
        return 0

    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False

    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel

    # Silent-e: subtract if word ends with 'e' but not 'le' (like "candle")
    if word.endswith("e") and not word.endswith("le") and count > 1:
        count -= 1

    return max(1, count)


# ---------------------------------------------------------------------------
# Public tool function (called by ADK FunctionTool)
# ---------------------------------------------------------------------------


def score_readability(text: str) -> dict:
    """Score the readability of text using Flesch-Kincaid metrics.

    Args:
        text: The text to analyze for readability.

    Returns:
        A dict with Flesch-Kincaid grade level, reading ease score,
        suggested age group, word count, and sentence count.
        Returns a dict with 'error' key on invalid input.
    """
    if not text or not text.strip():
        return {"error": "Empty or whitespace-only text provided."}

    # Split sentences on .!? (filter out empty)
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    sentence_count = len(sentences)

    if sentence_count == 0:
        return {"error": "No sentences detected in text."}

    # Split words on whitespace, strip punctuation
    words = [w for w in re.findall(r"[a-zA-Z']+", text) if len(w) > 0]
    word_count = len(words)

    if word_count == 0:
        return {"error": "No words detected in text."}

    # Count syllables
    total_syllables = sum(_count_syllables(w) for w in words)

    # Flesch-Kincaid Grade Level
    avg_words_per_sentence = word_count / sentence_count
    avg_syllables_per_word = total_syllables / word_count

    fk_grade = (
        0.39 * avg_words_per_sentence
        + 11.8 * avg_syllables_per_word
        - 15.59
    )

    # Flesch Reading Ease
    reading_ease = (
        206.835
        - 1.015 * avg_words_per_sentence
        - 84.6 * avg_syllables_per_word
    )

    # Map grade level to age group
    if fk_grade <= 4:
        suggested_age_group = "6-9"
    elif fk_grade <= 8:
        suggested_age_group = "10-13"
    else:
        suggested_age_group = "14-17"

    return {
        "flesch_kincaid_grade": round(fk_grade, 2),
        "reading_ease": round(reading_ease, 2),
        "suggested_age_group": suggested_age_group,
        "word_count": word_count,
        "sentence_count": sentence_count,
    }
