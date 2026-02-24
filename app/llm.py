"""
Groq API wrapper — the only file that calls Groq.
"""

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)


class GroqClient:
    def __init__(self) -> None:
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("groq library not installed. Run: pip install groq")

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")

        self.model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        self._client = Groq(api_key=api_key)

    def generate(self, prompt: str, max_tokens: int = 4096) -> Optional[str]:
        """Call Groq and return raw text. Retries up to 3 times on failure."""
        for attempt in range(1, 4):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a medical policy analyst expert at extracting "
                                "structured data from insurance prior authorization documents."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    max_tokens=max_tokens,
                    stream=False,
                )
                return response.choices[0].message.content.strip()
            except Exception as exc:
                logger.warning("Groq attempt %d failed: %s", attempt, exc)
                if attempt == 3:
                    logger.error("All 3 Groq attempts failed")
                    return None
        return None

    def generate_json(self, prompt: str, max_tokens: int = 4096) -> Optional[dict]:
        """Call generate(), strip markdown fences, parse JSON."""
        import json

        raw = self.generate(prompt, max_tokens=max_tokens)
        if not raw:
            return None

        cleaned = re.sub(r"```(?:json)?", "", raw).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1

        if start < 0 or end <= start:
            logger.warning("No JSON object found in LLM response")
            return None

        try:
            return json.loads(cleaned[start:end])
        except Exception as exc:
            logger.warning("JSON parse failed: %s", exc)
            return None
