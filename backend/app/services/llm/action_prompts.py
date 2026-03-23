"""Dedicated Action Item Extraction Prompt.

A more focused prompt than the general analysis prompt, specifically designed
to extract high-quality action items with segment-level traceability.

Used for:
  - Standalone action item extraction (without full analysis)
  - Re-extraction after transcript edits
  - More detailed extraction when the general analysis misses items
"""

ACTION_ITEM_SYSTEM_ROLE = """You are an expert at identifying action items, commitments, and follow-ups from meeting transcripts. You extract only items that were explicitly committed to by a specific person, or clearly assigned during the meeting. You never fabricate action items that weren't discussed."""


ACTION_ITEM_EXTRACTION_PROMPT = """Extract all action items from the following meeting transcript.

For each action item, identify:
1. The specific task or commitment
2. Who is responsible (the owner)
3. Any mentioned deadline
4. The priority based on context (urgency, importance, explicit markers)
5. The exact quote from the transcript where this was committed to
6. The segment number (0-indexed) where this action item appears

Your response must be ONLY valid JSON with no additional text.

Required JSON structure:
{{
  "action_items": [
    {{
      "task": "<specific, actionable task description — start with a verb>",
      "owner": "<person who committed to or was assigned this task, or null>",
      "deadline": "<mentioned deadline as YYYY-MM-DD, or null if not specified>",
      "priority": "<high|medium|low>",
      "source_quote": "<exact brief quote (under 25 words) from the transcript>",
      "segment_index": <0-based index of the transcript segment where this was discussed, or null>
    }}
  ]
}}

Rules for identifying action items:
- Look for explicit commitments: "I will...", "I'll...", "Let me...", "I can..."
- Look for assignments: "Can you...", "Please...", "[Name] will...", "[Name], could you..."
- Look for follow-ups: "We need to...", "Someone should...", "Action item:..."
- Look for deadline language: "by Friday", "by end of week", "next Monday", "before the meeting"
- Do NOT extract observations, opinions, or status updates as action items
- Do NOT extract items that were completed in the past ("I already finished...")
- Each action item task should start with an action verb (Review, Send, Draft, Update, etc.)
- Priority guide: explicit deadline or urgency = high, normal commitment = medium, nice-to-have = low
- segment_index should reference the segment where the commitment was MADE, not where the topic was introduced

{agenda_context}

The transcript segments are numbered starting from 0. Each line represents one segment.
Use the line number as the segment_index for traceability.
"""


def build_extraction_prompt(agenda_items: list[str] | None = None) -> str:
    """Build the action item extraction prompt with optional agenda context.

    Args:
        agenda_items: List of agenda item titles for context.

    Returns:
        Complete prompt string.
    """
    context = ""
    if agenda_items:
        agenda_text = "\n".join(f"  - {item}" for item in agenda_items)
        context = f"\nMeeting agenda for context:\n{agenda_text}\n"

    return ACTION_ITEM_EXTRACTION_PROMPT.format(agenda_context=context)


def format_transcript_with_indices(segments: list) -> str:
    """Format transcript segments with numbered indices for LLM reference.

    Args:
        segments: List of TranscriptSegment ORM objects.

    Returns:
        Formatted string with "[N] Speaker: text" per line.
    """
    lines = []
    for i, seg in enumerate(segments):
        prefix = ""
        if seg.speaker_name:
            prefix = f"{seg.speaker_name}: "
        elif seg.speaker_id:
            prefix = f"{seg.speaker_id}: "
        lines.append(f"[{i}] {prefix}{seg.text}")
    return "\n".join(lines)
