from __future__ import annotations

AUTO_QUEUE_FILTERS = ("all", "daily", "weekly_review", "longread", "humor", "other")
MANUAL_QUEUE_FILTERS = ("due", "all")
REVIEW_SOURCE_FILTERS = ("all", "ai", "manual")
QUEUE_THEME_FILTERS = ("all", "regulation", "case", "implementation", "tools", "market")
BATCH_PUBLISH_MODES = ("page", "top3", "top5")

CALENDAR_CALLBACK_PREFIXES = ("cal:", "cav:", "cap:", "cpc:", "cpn:", "cas:", "car:")
CREATE_CALLBACK_PREFIXES = ("cn:", "ck:", "ct:", "cm:", "cl:", "cd:", "cr:", "ce:", "cs:")
CONTROLS_CALLBACK_EXACT = frozenset({"noop", "refresh", "sections", "automation", "status", "workers", "resetstale"})
CONTROLS_CALLBACK_PREFIXES = (
    "sch:",
    "int:",
    "rdg:",
    "sec:",
    "reader:",
    "rca:",
    "miniapp:",
    "thm:",
    "aq:",
    "srd:",
    "srt:",
    "stc:",
    "scc:",
    "srcm:",
    "src:",
    "th:",
    "lt:",
    "gt:",
    "fa:",
    "gen:",
    "preset:",
    "uih:",
    "all:",
    "set:",
    "wrk:",
)
POSTS_CALLBACK_PREFIXES = (
    "mq:",
    "mbp:",
    "mbc:",
    "mbn:",
    "ba:",
    "pl:",
    "pv:",
    "pt:",
    "ppc:",
    "ppy:",
    "ppn:",
    "rr:",
    "pr:",
    "pa:",
    "pm:",
    "pf:",
    "pdd:",
    "pdy:",
    "pdn:",
    "rv:",
    "cal:",
)


def parse_post_list_callback(data: str) -> tuple[str, int]:
    # New format: pl:<status>:<offset>, legacy: pl:<offset>
    parts = data.split(":")
    if len(parts) == 2:
        return "scheduled", int(parts[1])
    if len(parts) >= 3:
        return parts[1], int(parts[2])
    return "scheduled", 0


def parse_review_filter_callback(data: str) -> tuple[str, str, str, int]:
    parts = data.split(":")
    review_filter = "all"
    kind_filter = "all"
    theme_filter = "all"
    offset = 0
    if len(parts) >= 2 and parts[1] in REVIEW_SOURCE_FILTERS:
        review_filter = parts[1]
    if len(parts) >= 3 and parts[2] in AUTO_QUEUE_FILTERS:
        kind_filter = parts[2]
    if len(parts) >= 4 and parts[3] in QUEUE_THEME_FILTERS:
        theme_filter = parts[3]
    if len(parts) >= 5:
        offset = int(parts[4])
    elif len(parts) >= 3 and parts[2].isdigit():
        offset = int(parts[2])
    return review_filter, kind_filter, theme_filter, offset


def callback_payload_text(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    return ""


def callback_prefix_matcher(
    payload: object,
    *,
    prefixes: tuple[str, ...] = (),
    exact: frozenset[str] | None = None,
) -> bool:
    data = callback_payload_text(payload)
    if not data:
        return False
    if exact and data in exact:
        return True
    return any(data.startswith(prefix) for prefix in prefixes)


def is_calendar_callback(payload: object) -> bool:
    return callback_prefix_matcher(payload, prefixes=CALENDAR_CALLBACK_PREFIXES)


def is_create_callback(payload: object) -> bool:
    return callback_prefix_matcher(payload, prefixes=CREATE_CALLBACK_PREFIXES)


def is_controls_callback(payload: object) -> bool:
    return callback_prefix_matcher(
        payload,
        prefixes=CONTROLS_CALLBACK_PREFIXES,
        exact=CONTROLS_CALLBACK_EXACT,
    )


def is_posts_callback(payload: object) -> bool:
    return callback_prefix_matcher(payload, prefixes=POSTS_CALLBACK_PREFIXES)


def parse_manual_queue_callback(data: str) -> tuple[str, str, int]:
    # Format: mq:<filter>:<theme>:<offset>, fallback: mq:<filter>:<offset>, legacy: mq:<offset>
    parts = data.split(":")
    if len(parts) == 2:
        return "due", "all", int(parts[1])
    if len(parts) >= 4:
        queue_filter = parts[1]
        if queue_filter not in MANUAL_QUEUE_FILTERS:
            queue_filter = "due"
        theme_filter = parts[2]
        if theme_filter not in QUEUE_THEME_FILTERS:
            theme_filter = "all"
        return queue_filter, theme_filter, int(parts[3])
    if len(parts) >= 3:
        queue_filter = parts[1]
        if queue_filter not in MANUAL_QUEUE_FILTERS:
            queue_filter = "due"
        return queue_filter, "all", int(parts[2])
    return "due", "all", 0


def parse_batch_publish_callback(data: str) -> tuple[str, int, str]:
    # Format: mbp|mbc|mbn:<filter>:<offset>[:mode]
    parts = data.split(":")
    queue_filter = "due"
    offset = 0
    mode = "page"
    if len(parts) >= 2 and parts[1] in MANUAL_QUEUE_FILTERS:
        queue_filter = parts[1]
    if len(parts) >= 3:
        offset = int(parts[2])
    if len(parts) >= 4 and parts[3] in BATCH_PUBLISH_MODES:
        mode = parts[3]
    return queue_filter, offset, mode


def queue_context_from_filter(queue_filter: str, theme_filter: str = "all") -> str:
    normalized_queue = "all" if queue_filter == "all" else "due"
    normalized_theme = theme_filter if theme_filter in QUEUE_THEME_FILTERS else "all"
    return f"mq_{normalized_queue}_{normalized_theme}"


def queue_filters_from_context(context: str) -> tuple[str, str]:
    normalized = context.removeprefix("mq_")
    parts = normalized.split("_", 1)
    queue_filter = parts[0] if parts and parts[0] in MANUAL_QUEUE_FILTERS else "due"
    theme_filter = parts[1] if len(parts) == 2 and parts[1] in QUEUE_THEME_FILTERS else "all"
    return queue_filter, theme_filter


def queue_filter_from_context(context: str) -> str:
    return queue_filters_from_context(context)[0]


def is_manual_queue_context(context: str) -> bool:
    return context.startswith("mq_")


def auto_queue_context(queue_filter: str, theme_filter: str = "all") -> str:
    normalized = queue_filter if queue_filter in AUTO_QUEUE_FILTERS else "all"
    normalized_theme = theme_filter if theme_filter in QUEUE_THEME_FILTERS else "all"
    return f"aq_{normalized}_{normalized_theme}"


def auto_queue_filters_from_context(context: str) -> tuple[str, str]:
    normalized = context.removeprefix("aq_")
    parts = normalized.split("_", 1)
    queue_filter = parts[0] if parts and parts[0] in AUTO_QUEUE_FILTERS else "all"
    theme_filter = parts[1] if len(parts) == 2 and parts[1] in QUEUE_THEME_FILTERS else "all"
    return queue_filter, theme_filter


def auto_queue_filter_from_context(context: str) -> str:
    return auto_queue_filters_from_context(context)[0]


def is_auto_queue_context(context: str) -> bool:
    return context.startswith("aq_")


def parse_auto_queue_callback(data: str) -> tuple[str, str, int]:
    parts = data.split(":")
    if len(parts) == 2:
        return "all", "all", int(parts[1])
    if len(parts) >= 4:
        queue_filter = parts[1]
        if queue_filter not in AUTO_QUEUE_FILTERS:
            queue_filter = "all"
        theme_filter = parts[2]
        if theme_filter not in QUEUE_THEME_FILTERS:
            theme_filter = "all"
        return queue_filter, theme_filter, int(parts[3])
    if len(parts) >= 3:
        queue_filter = parts[1]
        if queue_filter not in AUTO_QUEUE_FILTERS:
            queue_filter = "all"
        return queue_filter, "all", int(parts[2])
    return "all", "all", 0


def theme_context(pillar: str) -> str:
    return f"th_{pillar}"


def is_theme_context(context: str) -> bool:
    return context.startswith("th_")


def theme_from_context(context: str) -> str:
    return context.removeprefix("th_")


def source_context(domain: str) -> str:
    return f"src_{domain}"


def is_source_context(context: str) -> bool:
    return context.startswith("src_")


def source_from_context(context: str) -> str:
    return context.removeprefix("src_")


def calendar_context(date_iso: str) -> str:
    return f"cal_{date_iso.replace('-', '')}"


def is_calendar_context(context: str) -> bool:
    return context.startswith("cal_") and len(context) == 12


def calendar_date_from_context(context: str) -> str:
    raw = context.removeprefix("cal_")
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def slot_token(hour: int, minute: int) -> str:
    return f"{hour:02d}{minute:02d}"


def slot_from_token(token: str) -> tuple[int, int]:
    return int(token[:2]), int(token[2:4])
