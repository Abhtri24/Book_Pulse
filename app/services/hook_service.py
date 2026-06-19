from app.schemas.hook import HookMetrics

CONFLICT_KEYWORDS = frozenset(
    {"fight", "war", "attack", "danger", "escape", "kill", "dead", "blood"}
)
MYSTERY_KEYWORDS = frozenset(
    {"strange", "unknown", "impossible", "missing", "disappeared", "suddenly", "mysterious"}
)
ACTION_VERBS = frozenset(
    {"ran", "sprinted", "jumped", "crashed", "fell", "charged", "dashed", "leaped", "struck"}
)
SETTING_KEYWORDS = frozenset(
    {
        "city",
        "kingdom",
        "world",
        "forest",
        "mountain",
        "sky",
        "tower",
        "village",
        "planet",
        "empire",
        "realm",
        "castle",
        "desert",
        "ocean",
        "valley",
    }
)
SENTENCE_START_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "it",
        "he",
        "she",
        "they",
        "we",
        "i",
        "this",
        "that",
        "there",
        "when",
        "what",
        "where",
        "how",
        "why",
        "if",
        "but",
        "and",
        "or",
        "so",
        "as",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "to",
        "of",
    }
)
TITLE_PREFIXES = frozenset({"mr", "mrs", "ms", "dr", "sir", "lady", "lord", "captain", "general"})
OPENING_STYLES = {
    "question": "question_lead",
    "dialogue": "quoted_dialogue",
    "conflict": "conflict_forward",
    "mystery": "mysterious",
    "action": "action_burst",
    "character": "character_focus",
    "worldbuilding": "setting_first",
}
HOOK_TYPE_PRIORITY = (
    "question",
    "dialogue",
    "conflict",
    "mystery",
    "action",
    "character",
    "worldbuilding",
)


def check_hook_strength(text: str) -> HookMetrics:
    opening = _first_n_words(text)
    dialogue_opening = _has_dialogue_opening(opening)
    question_hook = _has_question_hook(opening)
    curiosity_gap = _detect_curiosity_gap(opening)
    conflict_present = _detect_conflict_present(opening)
    hook_type = _determine_hook_type(
        opening,
        dialogue_opening=dialogue_opening,
        question_hook=question_hook,
        conflict_present=conflict_present,
    )
    opening_style = OPENING_STYLES.get(hook_type, "neutral")
    hook_score, reasoning = _compute_score(
        curiosity_gap=curiosity_gap,
        conflict_present=conflict_present,
        dialogue_opening=dialogue_opening,
        question_hook=question_hook,
        hook_type=hook_type,
    )

    return HookMetrics(
        hook_score=hook_score,
        hook_type=hook_type,
        opening_style=opening_style,
        curiosity_gap=curiosity_gap,
        conflict_present=conflict_present,
        dialogue_opening=dialogue_opening,
        reasoning=reasoning,
    )


def _first_n_words(text: str, n: int = 50) -> str:
    stripped = text.strip()
    if not stripped:
        raise ValueError("text must not be empty")
    return " ".join(stripped.split()[:n])


def _normalize_word(word: str) -> str:
    return word.strip(".,!?;:'\"()[]{}“”‘’").lower()


def _has_dialogue_opening(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith(('"', "'", "“", "‘"))


def _has_question_hook(text: str) -> bool:
    return "?" in text


def _contains_keywords(text: str, keywords: frozenset[str]) -> bool:
    words = {_normalize_word(word) for word in text.split()}
    return any(keyword in words for keyword in keywords)


def _starts_with_action_verb(text: str) -> bool:
    words = text.split()
    if not words:
        return False
    return _normalize_word(words[0]) in ACTION_VERBS


def _has_named_character(text: str) -> bool:
    words = text.split()[:15]
    for index, word in enumerate(words):
        clean = word.strip(".,!?;:'\"()[]{}“”‘’")
        if not clean:
            continue
        lower = _normalize_word(clean)
        if lower in TITLE_PREFIXES and index + 1 < len(words):
            return True
        if (
            len(clean) > 1
            and clean[0].isupper()
            and clean[1:].islower()
            and lower not in SENTENCE_START_WORDS
            and index > 0
        ):
            return True
    return False


def _has_worldbuilding_signal(text: str) -> bool:
    return _contains_keywords(text, SETTING_KEYWORDS) and not _starts_with_action_verb(text)


def _detect_curiosity_gap(text: str) -> bool:
    return _contains_keywords(text, MYSTERY_KEYWORDS) or _has_question_hook(text)


def _detect_conflict_present(text: str) -> bool:
    return _contains_keywords(text, CONFLICT_KEYWORDS)


def _determine_hook_type(
    text: str,
    *,
    dialogue_opening: bool,
    question_hook: bool,
    conflict_present: bool,
) -> str:
    signals = {
        "question": question_hook,
        "dialogue": dialogue_opening,
        "conflict": conflict_present,
        "mystery": _contains_keywords(text, MYSTERY_KEYWORDS),
        "action": _starts_with_action_verb(text),
        "character": _has_named_character(text),
        "worldbuilding": _has_worldbuilding_signal(text),
    }
    for hook_type in HOOK_TYPE_PRIORITY:
        if signals[hook_type]:
            return hook_type
    return "character"


def _compute_score(
    *,
    curiosity_gap: bool,
    conflict_present: bool,
    dialogue_opening: bool,
    question_hook: bool,
    hook_type: str,
) -> tuple[int, list[str]]:
    score = 50
    reasoning = ["Base hook score starts at 50."]

    if curiosity_gap:
        score += 20
        reasoning.append("+20 curiosity gap detected (mystery keywords or unanswered question).")
    if conflict_present:
        score += 15
        reasoning.append("+15 conflict signals present in opening.")
    if dialogue_opening:
        score += 10
        reasoning.append("+10 dialogue opening detected.")
    if question_hook:
        score += 10
        reasoning.append("+10 question hook detected.")

    if hook_type == "character" and score == 50:
        reasoning.append("Opening lacks strong hook signals; score remains at baseline.")

    score = max(0, min(100, score))
    reasoning.append(f"Final hook score clamped to {score}.")
    return score, reasoning
