"""Tools for story generation support."""


def get_story_template(style: str, age_group: str) -> dict:
    """Get a story template based on style and target age group.

    Args:
        style: Story style — one of 'fairy_tale', 'adventure', 'sci_fi', 'comic_book'.
        age_group: Target age group — one of '6-9', '10-13', '14-17'.

    Returns:
        A dict with story structure template and style guidelines.
    """
    # TODO: Implement story template lookup
    return {
        "style": style,
        "age_group": age_group,
        "structure": {
            "opening": "Once upon a time...",
            "rising_action": "",
            "climax": "",
            "resolution": "",
        },
        "guidelines": {
            "vocabulary_level": "intermediate",
            "sentence_length": "medium",
            "illustration_style": style,
        },
    }
