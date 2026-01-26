import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from pathlib import Path
import re
from typing import Optional, Dict, Any
import logging

# Set up logging for debugging hallucinations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_PATH = r"C:\Users\n0308g\Git_Repos\pauth_rc\backend\app\rag_pipeline\models\qwen2.5"

class EvidenceExtractor:
    def __init__(self, model_path: str = MODEL_PATH):
        """Initialize model once - avoid reloading on every call"""
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True
        )
        
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            dtype=torch.float16,
            trust_remote_code=True
        )
        
        # Move to GPU if available
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        self.model.eval()
        
        logger.info(f"Model loaded on {self.device}")

    def _validate_evidence(self, extracted_data: dict, chart_text: str) -> dict:
        """Check if evidence_notes actually exist in chart - FLAG HALLUCINATIONS"""
        chart_lower = chart_text.lower()
        validated_notes = []
        hallucinations = []
        
        for note in extracted_data.get("evidence_notes", []):
            note_lower = note.lower().strip()
            # Allow fuzzy matching for minor variations
            if note_lower in chart_lower or any(
                word in chart_lower for word in note_lower.split() if len(word) > 4
            ):
                validated_notes.append(note)
            else:
                hallucinations.append(note)
                logger.warning(f"HALLUCINATION DETECTED: '{note}' not in chart")
        
        extracted_data["evidence_notes"] = validated_notes
        
        # Add metadata about extraction quality
        extracted_data["_metadata"] = {
            "hallucinations_detected": len(hallucinations),
            "hallucinated_notes": hallucinations,
            "validation_passed": len(hallucinations) == 0
        }
        
        return extracted_data

    def _extract_json_object(self, text: str) -> str:
        """Extract JSON with better error handling"""
        # Try to find JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            logger.error(f"No JSON found in output: {text[:200]}")
            raise ValueError("No JSON object found in model output")
        return match.group(0)

    def extract_evidence(self, chart_text: str) -> Optional[Dict[str, Any]]:
        """Main extraction function with validation"""
        
        # Input validation
        if not chart_text or len(chart_text.strip()) < 10:
            logger.error("Chart text too short or empty")
            return None
        
        # Truncate very long notes (Qwen context limit ~32k tokens)
        max_chars = 8000  # ~2k tokens with safety margin
        if len(chart_text) > max_chars:
            logger.warning(f"Chart truncated from {len(chart_text)} to {max_chars} chars")
            chart_text = chart_text[:max_chars] + "\n[NOTE TRUNCATED]"
        
        # this prompt is most fitting for an orthopedics chart...(imaging + failed conservative therapy)
        prompt = f"""You are a medical chart data extractor. Extract ONLY information explicitly written in the chart note below.

CRITICAL RULES:
1. Extract facts word-for-word from the chart - do NOT interpret or infer
2. If information is absent or unclear, use null or false
3. Do NOT make clinical assumptions
4. Do NOT fill in missing data
5. Output ONLY valid JSON - no other text

EXTRACTION SCHEMA:
{{
  "symptom_duration_months": null,
  "conservative_therapy": {{
    "physical_therapy": {{
      "attempted": false,
      "duration_weeks": null
    }},
    "nsaids": {{
      "documented": false,
      "outcome": null
    }},
    "injections": {{
      "documented": false,
      "outcome": null
    }}
  }},
  "imaging": {{
    "documented": false,
    "type": null,
    "body_part": null,
    "months_ago": null
  }},
  "functional_impairment": {{
    "documented": false,
    "description": null
  }},
  "evidence_notes": []
}}

FIELD INSTRUCTIONS:
- symptom_duration_months: Extract only if explicitly stated (e.g., "3 months of pain" = 3)
- attempted: true ONLY if chart says therapy was done/tried/completed
- outcome: Use "failed", "partial", or "successful" ONLY if chart uses these exact terms or clear equivalents ("no relief"="failed", "improved"="partial", "resolved"="successful")
- evidence_notes: Quote exact phrases from chart that support your extractions (max 10 words each)

CHART NOTE:
\"\"\"
{chart_text}
\"\"\"

OUTPUT (valid JSON only):"""

        messages = [
            {"role": "system", "content": "You output JSON only."},
            {"role": "user", "content": prompt}
        ]

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)

        try:
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=600,
                    temperature=0.0,
                    do_sample=False,
                    repetition_penalty=1.1,  # Reduce repetitive hallucinations
                    pad_token_id=self.tokenizer.eos_token_id
                )

            raw_output = self.tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[-1]:],
                skip_special_tokens=True
            ).strip()

            # Extract and parse JSON
            cleaned = self._extract_json_object(raw_output)
            extracted_data = json.loads(cleaned)
            
            # CRITICAL: Validate evidence against source
            validated_data = self._validate_evidence(extracted_data, chart_text)
            
            return validated_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}\nOutput: {raw_output[:500]}")
            return None
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return None


# Singleton instance for reuse
_extractor = None

def get_extractor() -> EvidenceExtractor:
    """Get or create extractor instance - avoid reloading model"""
    global _extractor
    if _extractor is None:
        _extractor = EvidenceExtractor()
    return _extractor


def extract_evidence(chart_text: str) -> Optional[Dict[str, Any]]:
    """Backward-compatible function wrapper"""
    extractor = get_extractor()
    return extractor.extract_evidence(chart_text)


# Example usage with validation
if __name__ == "__main__":
    test_chart = """
    Patient reports 4 months of right knee pain.
    Tried physical therapy for 8 weeks with minimal improvement.
    NSAIDs provided no relief.
    MRI of right knee 2 months ago shows meniscal tear.
    Patient unable to climb stairs or walk more than 10 minutes.
    """
    
    result = extract_evidence(test_chart)
    
    if result:
        print(json.dumps(result, indent=2))
        
        # Check validation
        if not result["_metadata"]["validation_passed"]:
            print("\n⚠️ HALLUCINATIONS DETECTED:")
            for note in result["_metadata"]["hallucinated_notes"]:
                print(f"  - {note}")

                
# This is what the extracted test json looks like.
# {
#   "symptom_duration_months": 4,
#   "conservative_therapy": {
#     "physical_therapy": {
#       "attempted": true,
#       "duration_weeks": 8
#     },
#     "nsaids": {
#       "documented": true,
#       "outcome": "no relief"
#     },
#     "injections": {
#       "documented": false,
#       "outcome": null
#     }
#   },
#   "imaging": {
#     "documented": true,
#     "type": "MRI",
#     "body_part": "right knee",
#     "months_ago": 2
#   },
#   "functional_impairment": {
#     "documented": true,
#     "description": "unable to climb stairs or walk more than 10 minutes"
#   },
#   "evidence_notes": [
#     "Patient reports 4 months of right knee pain.",
#     "Tried physical therapy for 8 weeks with minimal improvement.",
#     "NSAIDs provided no relief.",
#     "MRI of right knee 2 months ago shows meniscal tear."
#   ],
#   "_metadata": {
#     "hallucinations_detected": 0,
#     "hallucinated_notes": [],
#     "validation_passed": true
#   }
# }
