"""Tools for story generation support — templates for 4 styles x 3 age groups."""

# ---------------------------------------------------------------------------
# Style-specific templates
# ---------------------------------------------------------------------------

_STYLE_TEMPLATES = {
    "fairy_tale": {
        "structure": {
            "setup": (
                "Introduce the enchanted world and the young hero who discovers "
                "something mysterious. Establish a sense of wonder and a gentle "
                "call to adventure."
            ),
            "rising_action": (
                "The hero meets a wise mentor and faces magical trials. Each "
                "challenge teaches a core scientific concept through an "
                "enchantment or riddle — but the underlying science must be "
                "stated accurately within the narrative."
            ),
            "climax": (
                "The hero confronts the central mystery — the hardest concept — "
                "and must use everything they've learned. A magical transformation "
                "or revelation occurs."
            ),
            "resolution": (
                "The enchantment resolves, the hero returns home wiser, and the "
                "scientific truth behind the magic is gently revealed."
            ),
        },
        "style_guidelines": {
            "tone": "Warm, whimsical, and gently mysterious",
            "vocabulary_level": "Fairy-tale language with 'once upon a time' framing",
            "sentence_complexity": "Lyrical but clear; short paragraphs with rhythm",
            "visual_style": "Storybook watercolor illustrations with soft edges",
            "color_palette": "Warm golds, soft greens, gentle purples, starlight whites",
        },
        "character_archetypes": [
            {"name": "Curious Hero", "description": "A young, inquisitive protagonist who asks 'why?' and discovers truths"},
            {"name": "Wise Mentor", "description": "An elder figure (wizard, grandmother, talking animal) who guides through riddles"},
            {"name": "Magical Helper", "description": "A whimsical companion (fairy, enchanted creature) who embodies a key concept"},
        ],
        "illustration_style": (
            "Storybook watercolor with soft lighting, hand-drawn feel. Characters "
            "have expressive faces. Backgrounds feature enchanted forests, glowing "
            "objects, and gentle sparkles. Think classic fairy-tale picture book."
        ),
        "accuracy_note": (
            "Magic and enchantments frame the science but must not contradict it. "
            "When a concept is presented as 'magic', the story must also reveal "
            "the real science behind it before the scene ends."
        ),
    },
    "adventure": {
        "structure": {
            "setup": (
                "Introduce the brave explorer and a thrilling discovery — a map, "
                "a distress signal, or a hidden doorway. The stakes are clear: "
                "a problem that needs solving."
            ),
            "rising_action": (
                "The team embarks on a journey through challenging environments. "
                "Each obstacle requires understanding a scientific concept to "
                "overcome. Tension builds with each new challenge."
            ),
            "climax": (
                "The ultimate challenge arrives — the team must combine all "
                "their learned knowledge in a high-stakes moment. Quick thinking "
                "and teamwork save the day."
            ),
            "resolution": (
                "The team succeeds and reflects on what they learned. The "
                "scientific concepts are celebrated as the real treasure of "
                "the adventure."
            ),
        },
        "style_guidelines": {
            "tone": "Exciting, fast-paced, and empowering",
            "vocabulary_level": "Action-oriented with clear, punchy descriptions",
            "sentence_complexity": "Short, dynamic sentences during action; longer for exposition",
            "visual_style": "Bold, dynamic compositions with strong perspective",
            "color_palette": "Vibrant blues, jungle greens, sunset oranges, earth tones",
        },
        "character_archetypes": [
            {"name": "Bold Explorer", "description": "A courageous leader who charges into the unknown with determination"},
            {"name": "Clever Inventor", "description": "A resourceful thinker who builds solutions from scientific knowledge"},
            {"name": "Loyal Companion", "description": "A steadfast friend who provides humor and heart during tough moments"},
        ],
        "illustration_style": (
            "Dynamic adventure-book style with bold lines and vivid colors. "
            "Action poses, dramatic angles, and sweeping landscapes. Characters "
            "have gear and expressive body language. Think Indiana Jones meets "
            "Magic School Bus."
        ),
        "accuracy_note": (
            "Obstacles must be solved using real science, not genre shortcuts. "
            "The scientific method or principle must be correctly applied in the "
            "solution — no 'it just works' hand-waving."
        ),
    },
    "sci_fi": {
        "structure": {
            "setup": (
                "Introduce a futuristic or alien setting where a young scientist "
                "discovers an anomaly. Technology is woven into daily life, and "
                "the anomaly threatens to disrupt it."
            ),
            "rising_action": (
                "The protagonist investigates using advanced tools, each revealing "
                "a layer of the scientific concept. They encounter alien phenomena "
                "or malfunctioning tech that requires deeper understanding."
            ),
            "climax": (
                "A critical system failure or cosmic event forces the protagonist "
                "to apply their full understanding. The science isn't just knowledge — "
                "it's survival."
            ),
            "resolution": (
                "The anomaly is resolved through scientific insight. The protagonist "
                "records their findings in a log, connecting the fictional science "
                "to real-world concepts."
            ),
        },
        "style_guidelines": {
            "tone": "Curious, awe-inspiring, and intellectually stimulating",
            "vocabulary_level": "Technical terms introduced naturally with in-context definitions",
            "sentence_complexity": "Varied; precise language with vivid sensory descriptions of tech",
            "visual_style": "Sleek digital art with glowing interfaces and cosmic vistas",
            "color_palette": "Deep space blues, neon cyans, holographic purples, starfield whites",
        },
        "character_archetypes": [
            {"name": "Young Scientist", "description": "A brilliant, curious mind navigating a world shaped by science and technology"},
            {"name": "AI Companion", "description": "A helpful but sometimes puzzled AI that learns alongside the reader"},
            {"name": "Alien Observer", "description": "A being from another world whose perspective reveals surprising truths"},
        ],
        "illustration_style": (
            "Sleek sci-fi digital art with glowing interfaces, holographic displays, "
            "and cosmic backgrounds. Clean lines, luminous effects. Characters wear "
            "futuristic gear. Think space station interiors and alien landscapes."
        ),
        "accuracy_note": (
            "Futuristic technology must be grounded in the real science from the paper. "
            "Alien phenomena should parallel, not contradict, the actual findings. "
            "The 'captain's log' should state the real-world science clearly."
        ),
    },
    "comic_book": {
        "structure": {
            "setup": (
                "Open with a dramatic splash panel introducing the hero and "
                "the problem. A villain, disaster, or mystery sets the action "
                "in motion with a bang."
            ),
            "rising_action": (
                "Paneled sequences show the hero gathering clues and allies. "
                "Each panel sequence teaches a concept through visual action "
                "and snappy dialogue. POW! ZAP! EUREKA!"
            ),
            "climax": (
                "Full-page spread: the hero faces the villain/problem head-on. "
                "The winning move requires applying the core scientific concept "
                "in a visually spectacular way. The 'science saves the day' moment "
                "must reflect how the science actually works — no made-up powers."
            ),
            "resolution": (
                "Wrap-up panels show the aftermath. The hero explains what they "
                "learned in a 'science corner' panel, connecting the story back "
                "to real science."
            ),
        },
        "style_guidelines": {
            "tone": "Energetic, humorous, and visually driven",
            "vocabulary_level": "Punchy dialogue, onomatopoeia, exclamations",
            "sentence_complexity": "Short bursts in speech bubbles; captions for narration",
            "visual_style": "Bold comic panels with thick outlines and halftone dots",
            "color_palette": "Primary colors (red, blue, yellow), bold blacks, action-line whites",
        },
        "character_archetypes": [
            {"name": "Science Hero", "description": "A kid with a special power tied to a scientific concept — knowledge is their superpower"},
            {"name": "Comic Sidekick", "description": "A funny, loyal friend who asks the questions readers are thinking"},
            {"name": "Concept Villain", "description": "An antagonist who embodies a misconception or misuse of science"},
        ],
        "illustration_style": (
            "Bold comic book style with thick black outlines, dynamic panel layouts, "
            "and halftone shading. Speech bubbles, sound effects (POW! ZAP!), and "
            "motion lines. Bright primary colors. Think Marvel meets Bill Nye."
        ),
        "accuracy_note": (
            "Superpowers and villains frame the science but must not distort it. "
            "The 'science corner' panel must state the real findings accurately. "
            "The hero's powers must reflect how the science actually works."
        ),
    },
}

# ---------------------------------------------------------------------------
# Age-group guidelines
# ---------------------------------------------------------------------------

_AGE_GUIDELINES = {
    "6-9": {
        "vocabulary_level": "Simple, everyday words; max 2-syllable vocabulary preferred",
        "sentence_length": "5-10 words per sentence",
        "paragraph_length": "2-3 sentences per paragraph",
        "concepts_per_scene": 1,
        "scene_count": 4,
        "reading_level": "Grades 1-4",
        "content_notes": (
            "Use familiar comparisons (animals, food, playground). Avoid abstract "
            "ideas without concrete anchors. Characters should feel like friends."
        ),
    },
    "10-13": {
        "vocabulary_level": "Moderate vocabulary; scientific terms okay with definitions",
        "sentence_length": "10-18 words per sentence",
        "paragraph_length": "3-5 sentences per paragraph",
        "concepts_per_scene": 2,
        "scene_count": 4,
        "reading_level": "Grades 5-8",
        "content_notes": (
            "Can handle cause-and-effect reasoning. Introduce real scientific terms "
            "with analogies. Characters can face moral choices and teamwork challenges."
        ),
    },
    "14-17": {
        "vocabulary_level": "Near-adult vocabulary; technical terms with brief context",
        "sentence_length": "15-25 words per sentence",
        "paragraph_length": "4-6 sentences per paragraph",
        "concepts_per_scene": 2,
        "scene_count": 4,
        "reading_level": "Grades 9-12",
        "content_notes": (
            "Can handle nuance, ambiguity, and ethical dimensions of science. "
            "Characters can grapple with complexity. Connect to real-world implications."
        ),
    },
}

# ---------------------------------------------------------------------------
# Default fallbacks
# ---------------------------------------------------------------------------

_DEFAULT_STYLE = {
    "structure": {
        "setup": "Introduce the main character and the scientific mystery they encounter.",
        "rising_action": "The character investigates and learns key concepts through challenges.",
        "climax": "The character must apply their knowledge to solve the central problem.",
        "resolution": "The problem is solved and the character reflects on what they learned.",
    },
    "style_guidelines": {
        "tone": "Engaging and educational",
        "vocabulary_level": "Age-appropriate with clear explanations",
        "sentence_complexity": "Varied sentence structure",
        "visual_style": "Colorful and expressive illustrations",
        "color_palette": "Bright, inviting colors",
    },
    "character_archetypes": [
        {"name": "Curious Learner", "description": "A relatable protagonist who discovers science through exploration"},
        {"name": "Helpful Guide", "description": "A mentor figure who provides key insights at critical moments"},
    ],
    "illustration_style": (
        "Colorful, expressive illustrations with clear character designs "
        "and engaging backgrounds. Suitable for the target age group."
    ),
    "accuracy_note": (
        "Genre framing must not contradict the science from the paper. "
        "Every scene must accurately represent the scientific concepts it teaches."
    ),
}

_DEFAULT_AGE = {
    "vocabulary_level": "Moderate vocabulary",
    "sentence_length": "10-18 words per sentence",
    "paragraph_length": "3-5 sentences per paragraph",
    "concepts_per_scene": 1,
    "scene_count": 4,
    "reading_level": "General",
    "content_notes": "Keep language clear and concepts grounded with examples.",
}


# ---------------------------------------------------------------------------
# Public tool function (called by ADK FunctionTool)
# ---------------------------------------------------------------------------


def get_story_template(style: str, age_group: str) -> dict:
    """Get a story template based on style and target age group.

    Args:
        style: Story style — one of 'fairy_tale', 'adventure', 'sci_fi', 'comic_book'.
        age_group: Target age group — one of '6-9', '10-13', '14-17'.

    Returns:
        A dict with story structure template, style guidelines,
        character archetypes, scene count, illustration style,
        and age-group-specific guidelines.
    """
    style_template = _STYLE_TEMPLATES.get(style, _DEFAULT_STYLE)
    age_guidelines = _AGE_GUIDELINES.get(age_group, _DEFAULT_AGE)

    return {
        "style": style,
        "age_group": age_group,
        "structure": style_template["structure"],
        "style_guidelines": {
            **style_template["style_guidelines"],
            **{
                "target_vocabulary": age_guidelines["vocabulary_level"],
                "target_sentence_length": age_guidelines["sentence_length"],
                "target_paragraph_length": age_guidelines["paragraph_length"],
            },
        },
        "character_archetypes": style_template["character_archetypes"],
        "scene_count": age_guidelines["scene_count"],
        "concepts_per_scene": age_guidelines["concepts_per_scene"],
        "illustration_style": style_template["illustration_style"],
        "age_guidelines": {
            "reading_level": age_guidelines["reading_level"],
            "content_notes": age_guidelines["content_notes"],
        },
        "accuracy_note": style_template.get("accuracy_note", "Genre framing must not contradict the science."),
    }
