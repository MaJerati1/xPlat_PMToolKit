"""Mock LLM Provider for testing and development.

Returns realistic structured analysis output without making any API calls.
Analyzes the transcript text heuristically to produce plausible mock data
that exercises the full pipeline (parsing, storage, response building).

Usage:
    In tests or when no API keys are configured, the analysis service
    falls back to this provider automatically.
"""

import json
import re
from typing import Optional

from app.services.llm.abstraction import LLMProvider, LLMRequest, LLMResponse


class MockProvider(LLMProvider):
    """Mock LLM provider that generates structured analysis from transcript heuristics.

    Extracts real speaker names and produces contextually plausible output
    so the full pipeline can be tested end-to-end without API calls.
    """

    async def process(self, request: LLMRequest) -> LLMResponse:
        """Generate mock analysis based on the transcript content."""
        transcript = request.transcript_data
        speakers = self._extract_speakers(transcript)
        segments = self._split_segments(transcript)

        # Build realistic mock output
        analysis = {
            "summary": self._generate_summary(speakers, len(segments)),
            "decisions": self._extract_mock_decisions(segments),
            "action_items": self._extract_mock_action_items(segments, speakers),
            "topics": self._extract_mock_topics(segments),
            "speakers": self._build_speaker_analysis(speakers, segments),
        }

        content = json.dumps(analysis, indent=2)

        return LLMResponse(
            content=content,
            structured_data=analysis,
            provider="mock",
            model="mock-analysis-v1",
            tier=0,
            input_tokens=len(transcript.split()),
            output_tokens=len(content.split()),
            latency_ms=50.0,
        )

    def _extract_speakers(self, text: str) -> list[str]:
        """Extract unique speaker names from transcript."""
        speakers = set()
        for line in text.splitlines():
            # Match "Speaker Name: text" pattern
            m = re.match(r"^([A-Za-z][A-Za-z .',-]{0,58}):\s+", line.strip())
            if m:
                name = m.group(1).strip()
                words = name.split()
                if len(words) <= 4:
                    speakers.add(name)
        return sorted(speakers) if speakers else ["Speaker 1", "Speaker 2"]

    def _split_segments(self, text: str) -> list[str]:
        """Split transcript into rough segments."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return lines if lines else ["No transcript content"]

    def _generate_summary(self, speakers: list[str], segment_count: int) -> str:
        """Generate a plausible summary paragraph."""
        speaker_list = ", ".join(speakers[:3])
        if len(speakers) > 3:
            speaker_list += f" and {len(speakers) - 3} others"

        return (
            f"This meeting included contributions from {speaker_list} "
            f"across {segment_count} discussion segments. "
            f"The team covered key topics and reviewed progress on ongoing initiatives. "
            f"Several decisions were made and action items were assigned for follow-up."
        )

    def _extract_mock_decisions(self, segments: list[str]) -> list[dict]:
        """Generate mock decisions based on transcript content."""
        decisions = []
        decision_keywords = ["decided", "agreed", "approved", "confirmed", "will go with"]

        for seg in segments:
            lower = seg.lower()
            for kw in decision_keywords:
                if kw in lower:
                    # Extract the speaker if present
                    speaker = None
                    m = re.match(r"^([A-Za-z .',-]+?):\s+", seg)
                    if m:
                        speaker = m.group(1).strip()

                    decisions.append({
                        "decision": seg.split(":", 1)[-1].strip()[:200] if ":" in seg else seg[:200],
                        "context": "Discussed during the meeting",
                        "made_by": speaker,
                    })
                    break

        if not decisions:
            decisions.append({
                "decision": "Team aligned on next steps and priorities",
                "context": "General consensus reached during discussion",
                "made_by": None,
            })

        return decisions[:5]

    def _extract_mock_action_items(self, segments: list[str], speakers: list[str]) -> list[dict]:
        """Generate mock action items based on transcript content."""
        items = []
        action_keywords = [
            "will", "need to", "should", "action item", "follow up",
            "take care of", "responsible for", "deadline", "by next"
        ]

        for seg in segments:
            lower = seg.lower()
            for kw in action_keywords:
                if kw in lower:
                    speaker = None
                    m = re.match(r"^([A-Za-z .',-]+?):\s+", seg)
                    if m:
                        speaker = m.group(1).strip()

                    task_text = seg.split(":", 1)[-1].strip() if ":" in seg else seg.strip()
                    items.append({
                        "task": task_text[:300],
                        "owner": speaker or (speakers[0] if speakers else None),
                        "deadline": None,
                        "priority": "medium",
                        "source_quote": task_text[:80],
                    })
                    break

        if not items:
            items.append({
                "task": "Review meeting notes and confirm action items",
                "owner": speakers[0] if speakers else None,
                "deadline": None,
                "priority": "medium",
                "source_quote": "General follow-up from meeting discussion",
            })

        return items[:10]

    def _extract_mock_topics(self, segments: list[str]) -> list[dict]:
        """Generate mock topics from transcript content."""
        topics = []
        seen = set()

        for seg in segments[:20]:
            # Use first few words as topic proxy
            words = seg.split()
            if len(words) > 3:
                topic_name = " ".join(words[:5]).rstrip(":,.-")
                if ":" in seg:
                    topic_name = seg.split(":")[0].strip()
                # Deduplicate
                if topic_name.lower() not in seen and len(topic_name) > 5:
                    seen.add(topic_name.lower())
                    topics.append({
                        "topic": topic_name[:100],
                        "summary": "Discussion point covered during the meeting",
                        "time_spent_estimate": None,
                    })

        if not topics:
            topics.append({
                "topic": "General Discussion",
                "summary": "Open discussion among meeting participants",
                "time_spent_estimate": None,
            })

        return topics[:8]

    def _build_speaker_analysis(self, speakers: list[str], segments: list[str]) -> list[dict]:
        """Build speaker contribution analysis."""
        speaker_counts = {}
        for seg in segments:
            for sp in speakers:
                if seg.startswith(f"{sp}:"):
                    speaker_counts[sp] = speaker_counts.get(sp, 0) + 1

        result = []
        for i, sp in enumerate(speakers):
            count = speaker_counts.get(sp, 0)
            role = "facilitator" if i == 0 else "participant"
            result.append({
                "name": sp,
                "role": role,
                "contribution_summary": f"Contributed to the discussion with {count} segments",
                "segment_count": count or None,
            })

        return result
