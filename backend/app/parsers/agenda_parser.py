"""Agenda Text Parser - rule-based and LLM-assisted parsing.

Parses freeform agenda text (pasted from emails, calendar descriptions,
shared documents, etc.) into structured AgendaItem records.

Supported formats:
  - Numbered lists: "1. Topic Name", "1) Topic Name"
  - Bullet lists: "- Topic", "* Topic", "• Topic"
  - Time-stamped: "9:00 AM - Topic Name", "09:00-09:15 Topic"
  - Indented sub-items: "  - Sub-topic" (merged into parent description)
  - Presenter markers: "(John Smith)", "[Jane Doe]", "Presenter: Alice"
  - Time allocation markers: "(10 min)", "[15 minutes]", "~20m"
"""

import re
from typing import List, Optional, Tuple

from app.schemas.meeting import AgendaItemCreate


# Regex patterns for agenda line detection
NUMBERED_PATTERN = re.compile(
    r"^\s*(\d{1,3})\s*[.)]\s+(.+)$"
)
BULLET_PATTERN = re.compile(
    r"^\s*[-*•]\s+(.+)$"
)
TIME_RANGE_PATTERN = re.compile(
    r"^\s*(\d{1,2}:\d{2})\s*(?:AM|PM|am|pm)?\s*[-–—]\s*(\d{1,2}:\d{2})\s*(?:AM|PM|am|pm)?\s*[-–—:\s]\s*(.+)$"
)
TIME_SINGLE_PATTERN = re.compile(
    r"^\s*(\d{1,2}:\d{2})\s*(?:AM|PM|am|pm)?\s*[-–—:]\s*(.+)$"
)
SUBITEM_PATTERN = re.compile(
    r"^\s{2,}[-*•]\s+(.+)$"
)

# Inline metadata extraction
TIME_ALLOC_PATTERN = re.compile(
    r"[\(\[~](\d{1,3})\s*(?:min(?:utes?)?|m)[\)\]]?"
)
PRESENTER_PATTERN = re.compile(
    r"(?:(?:presenter|lead|owner|speaker)\s*:\s*(.+?)(?:\s*[-|,]|$))"
    r"|(?:[\(\[]([A-Z][a-z]+ [A-Z][a-z]+)[\)\]])",
    re.IGNORECASE,
)


def _extract_time_allocation(text: str) -> Tuple[Optional[int], str]:
    """Extract time allocation from text and return (minutes, cleaned_text)."""
    match = TIME_ALLOC_PATTERN.search(text)
    if match:
        minutes = int(match.group(1))
        cleaned = TIME_ALLOC_PATTERN.sub("", text).strip().rstrip("-–—,;: ")
        return minutes, cleaned
    return None, text


def _extract_presenter(text: str) -> Tuple[Optional[str], str]:
    """Extract presenter name from text and return (name, cleaned_text)."""
    match = PRESENTER_PATTERN.search(text)
    if match:
        name = match.group(1) or match.group(2)
        cleaned = PRESENTER_PATTERN.sub("", text).strip().rstrip("-–—,;: ")
        return name.strip(), cleaned
    return None, text


def _calculate_duration_from_range(start: str, end: str) -> Optional[int]:
    """Calculate duration in minutes from two time strings like '9:00' and '9:30'."""
    try:
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
        start_mins = sh * 60 + sm
        end_mins = eh * 60 + em
        if end_mins > start_mins:
            return end_mins - start_mins
    except (ValueError, AttributeError):
        pass
    return None


def parse_agenda_text(text: str) -> List[AgendaItemCreate]:
    """Parse freeform agenda text into structured agenda items.

    Uses rule-based pattern matching to detect agenda items from common
    formatting patterns found in emails, calendar events, and documents.

    Args:
        text: Freeform text containing agenda items.

    Returns:
        List of AgendaItemCreate schemas ready for database insertion.
    """
    lines = text.strip().splitlines()
    items: List[AgendaItemCreate] = []
    current_item: Optional[dict] = None
    sub_descriptions: List[str] = []
    order = 0

    for line in lines:
        stripped = line.strip()

        # Skip empty lines and common headers
        if not stripped:
            continue
        lower = stripped.lower()
        if lower in ("agenda", "agenda:", "meeting agenda", "meeting agenda:",
                      "topics", "topics:", "discussion items", "discussion items:"):
            continue

        # Check if this is a sub-item (indented bullet under a parent)
        if SUBITEM_PATTERN.match(line) and current_item is not None:
            sub_text = SUBITEM_PATTERN.match(line).group(1).strip()
            sub_descriptions.append(sub_text)
            continue

        # If we have a pending item, finalize it before processing new line
        if current_item is not None:
            if sub_descriptions:
                desc_parts = []
                if current_item.get("description"):
                    desc_parts.append(current_item["description"])
                desc_parts.extend(f"• {s}" for s in sub_descriptions)
                current_item["description"] = "\n".join(desc_parts)
                sub_descriptions = []
            items.append(AgendaItemCreate(**current_item))
            current_item = None

        title = None
        time_alloc = None
        description = None

        # Try time-range format: "9:00 AM - 9:30 AM - Topic"
        m = TIME_RANGE_PATTERN.match(stripped)
        if m:
            time_alloc = _calculate_duration_from_range(m.group(1), m.group(2))
            title = m.group(3).strip()
        else:
            # Try single-time format: "9:00 AM - Topic"
            m = TIME_SINGLE_PATTERN.match(stripped)
            if m:
                title = m.group(2).strip()
            else:
                # Try numbered format: "1. Topic" or "1) Topic"
                m = NUMBERED_PATTERN.match(stripped)
                if m:
                    title = m.group(2).strip()
                else:
                    # Try bullet format: "- Topic" or "* Topic"
                    m = BULLET_PATTERN.match(stripped)
                    if m:
                        title = m.group(1).strip()
                    else:
                        # Fallback: treat non-empty lines as agenda items
                        # only if they look substantial (>3 chars, not just punctuation)
                        if len(stripped) > 3 and re.search(r"[a-zA-Z]", stripped):
                            title = stripped

        if title:
            # Extract inline metadata
            alloc, title = _extract_time_allocation(title)
            presenter_name, title = _extract_presenter(title)

            if alloc:
                time_alloc = alloc

            # Split "Title - Description" or "Title: Description" patterns
            for sep in (" - ", " – ", " — ", ": "):
                if sep in title and len(title.split(sep, 1)[0]) > 3:
                    parts = title.split(sep, 1)
                    title = parts[0].strip()
                    description = parts[1].strip()
                    break

            current_item = {
                "title": title,
                "description": description,
                "time_allocation_minutes": time_alloc,
                "item_order": order,
            }
            order += 1

    # Don't forget the last item
    if current_item is not None:
        if sub_descriptions:
            desc_parts = []
            if current_item.get("description"):
                desc_parts.append(current_item["description"])
            desc_parts.extend(f"• {s}" for s in sub_descriptions)
            current_item["description"] = "\n".join(desc_parts)
        items.append(AgendaItemCreate(**current_item))

    return items
