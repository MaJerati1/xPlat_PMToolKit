"""Prompt Templates for LLM Transcript Analysis.

Carefully engineered prompts for extracting structured meeting data.
Each prompt produces JSON output that maps directly to our database schema.

Design principles:
  - Explicit JSON schema in every prompt (the LLM sees exactly what to produce)
  - Role-setting preamble for consistent tone
  - Transcript injected as a delimited block
  - Temperature 0.2-0.3 for factual extraction (set in the service layer)
"""

SYSTEM_ROLE = """You are an expert meeting analyst. You produce structured, factual analysis of meeting transcripts. You never fabricate information — if something is unclear from the transcript, say so. You extract only what is explicitly stated or clearly implied."""


ANALYSIS_PROMPT = """Analyze the following meeting transcript and produce a structured JSON response.

Your response must be ONLY valid JSON with no additional text, markdown, or explanation.

Required JSON structure:
{{
  "summary": "<2-4 paragraph executive summary of the meeting covering purpose, key discussions, and outcomes>",
  "decisions": [
    {{
      "decision": "<what was decided>",
      "context": "<brief context or reasoning>",
      "made_by": "<person who made/announced the decision, or null>"
    }}
  ],
  "action_items": [
    {{
      "task": "<specific, actionable task description>",
      "owner": "<person assigned, or null if unassigned>",
      "deadline": "<mentioned deadline as YYYY-MM-DD, or null>",
      "priority": "<high|medium|low based on urgency/importance expressed>",
      "source_quote": "<brief direct quote from transcript where this was discussed>"
    }}
  ],
  "topics": [
    {{
      "topic": "<discussion topic name>",
      "summary": "<1-2 sentence summary of what was discussed>",
      "time_spent_estimate": "<rough estimate like '5 minutes' or 'brief mention', or null>"
    }}
  ],
  "speakers": [
    {{
      "name": "<speaker name as it appears in transcript>",
      "role": "<inferred role like 'facilitator', 'presenter', 'participant', or null>",
      "contribution_summary": "<1 sentence about their main contributions>",
      "segment_count": <number of times they spoke, or null>
    }}
  ]
}}

Rules:
- Extract ONLY information that is explicitly stated or clearly implied in the transcript
- For action items, be specific and actionable — "Review Q2 budget" not "Look at stuff"
- Priority should reflect urgency expressed in the meeting (explicit deadlines = high, general tasks = medium)
- If no decisions were made, return an empty array — do not invent decisions
- If no clear action items exist, return an empty array
- Include ALL speakers found in the transcript
- source_quote should be a brief excerpt (under 20 words) showing where the action item came from
- Do not wrap your response in markdown code blocks

{agenda_context}"""


AGENDA_CONTEXT_TEMPLATE = """
Additional context — this meeting had the following agenda items:
{agenda_items}

Use these to help organize your topic analysis and identify which agenda items were covered vs. skipped."""


NO_AGENDA_CONTEXT = ""


def build_analysis_prompt(agenda_items: list[str] | None = None) -> str:
    """Build the complete analysis prompt, optionally with agenda context.

    Args:
        agenda_items: List of agenda item titles, or None if no agenda exists.

    Returns:
        Complete prompt string ready to send to the LLM.
    """
    if agenda_items:
        agenda_text = "\n".join(f"  - {item}" for item in agenda_items)
        context = AGENDA_CONTEXT_TEMPLATE.format(agenda_items=agenda_text)
    else:
        context = NO_AGENDA_CONTEXT

    return ANALYSIS_PROMPT.format(agenda_context=context)
