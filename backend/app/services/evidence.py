import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from pathlib import Path
import re
from typing import Optional, Dict, Any
import logging
import os
from groq import Groq

# Set up logging for debugging hallucinations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_PATH = r"C:\Users\n0308g\Git_Repos\pauth_rc\backend\app\rag_pipeline\models\qwen2.5"

class EvidenceExtractor:
    def __init__(self, model_path: str = MODEL_PATH, use_groq: bool = False, groq_api_key: Optional[str] = None):
        """Initialize model once - avoid reloading on every call"""
        self.use_groq = use_groq
        
        if self.use_groq:
            api_key = groq_api_key or os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY must be provided or set in environment")
            self.groq_client = Groq(api_key=api_key)
            self.groq_model = "llama-3.3-70b-versatile"
            logger.info(f"Using Groq API with {self.groq_model}")
        else:
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

    def _generate_with_groq(self, prompt: str) -> str:
        """Generate response using Groq API"""
        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                model=self.groq_model,
                temperature=0.0,
                max_tokens=800,
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

    def _generate_with_local_model(self, prompt: str) -> str:
        """Generate response using local model"""
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

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=800,
                temperature=0.0,
                do_sample=False,
                repetition_penalty=1.1,
                pad_token_id=self.tokenizer.eos_token_id
            )

        raw_output = self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[-1]:],
            skip_special_tokens=True
        ).strip()

        return raw_output

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
        
        prompt = f"""You are a medical chart data extractor. Extract ONLY information explicitly written in the chart note below.

CRITICAL RULES:
1. Extract facts word-for-word from the chart - do NOT interpret or infer
2. If information is absent or unclear, use null or false
3. Do NOT make clinical assumptions
4. Do NOT fill in missing data
5. Output ONLY valid JSON - no other text

EXTRACTION SCHEMA:
{{
  "patient_name": null,
  "symptom_duration_months": null,
  "affected_body_part": null,
  "laterality": null,
  "clinical_notes_date": null,
  "conservative_therapy": {{
    "physical_therapy": {{
      "attempted": false,
      "duration_weeks": null,
      "outcome": null
    }},
    "nsaids": {{
      "documented": false,
      "outcome": null
    }},
    "injections": {{
      "documented": false,
      "type": null,
      "outcome": null
    }},
    "other_treatments": {{
      "documented": false,
      "description": null,
      "outcome": null
    }}
  }},
  "imaging": {{
    "documented": false,
    "type": null,
    "body_part": null,
    "laterality": null,
    "months_ago": null,
    "findings": null
  }},
  "functional_impairment": {{
    "documented": false,
    "description": null
  }},
  "neurological_symptoms": {{
    "documented": false,
    "description": null
  }},
  "pain_characteristics": {{
    "documented": false,
    "severity": null,
    "quality": null,
    "radiation": null
  }},
  "red_flags": {{
    "documented": false,
    "description": null
  }},
  "evidence_notes": []
}}

FIELD INSTRUCTIONS:
- patient_name: Extract the full patient name if present in the chart (e.g., "Patient Name: John Doe"). If not present, use null.
- symptom_duration_months: Extract only if explicitly stated (e.g., "3 months of pain" = 3)
- affected_body_part: knee, shoulder, lumbar spine, cervical spine, brain, etc.
- laterality: "right", "left", "bilateral", or null
- clinical_notes_date: Extract the visit date or date of clinical note in YYYY-MM-DD format (e.g., "Date of Visit: January 15, 2025" = "2025-01-15")
- attempted: true ONLY if chart says therapy was done/tried/completed
- outcome: Use "failed", "partial", or "successful" ONLY if chart uses these terms or clear equivalents ("no relief"="failed", "minimal improvement"="partial", "improved"="partial", "resolved"="successful")
- imaging.type: MRI, CT, X-ray, etc.
- neurological_symptoms: numbness, tingling, weakness, radiculopathy, etc.
- pain_characteristics.radiation: where pain radiates to (e.g., "down leg", "into arm")
- red_flags: fever, weight loss, trauma, bowel/bladder dysfunction, progressive neurological deficits
- evidence_notes: Quote exact phrases from chart that support your extractions (max 10 words each)

CHART NOTE:
\"\"\"
{chart_text}
\"\"\"

OUTPUT (valid JSON only):"""

        try:
            if self.use_groq:
                raw_output = self._generate_with_groq(prompt)
            else:
                raw_output = self._generate_with_local_model(prompt)

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

def get_extractor(use_groq: bool = False, groq_api_key: Optional[str] = None) -> EvidenceExtractor:
    """Get or create extractor instance - avoid reloading model"""
    global _extractor
    if _extractor is None:
        _extractor = EvidenceExtractor(use_groq=use_groq, groq_api_key=groq_api_key)
    return _extractor


def extract_evidence(chart_text: str, use_groq: bool = False, groq_api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Backward-compatible function wrapper"""
    extractor = get_extractor(use_groq=use_groq, groq_api_key=groq_api_key)
    return extractor.extract_evidence(chart_text)