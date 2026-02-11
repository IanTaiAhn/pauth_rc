import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from pathlib import Path
import re
from typing import Optional, Dict, Any, List, Tuple
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
  "symptom_duration_months": null,
  "affected_body_part": null,
  "laterality": null,
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
- symptom_duration_months: Extract only if explicitly stated (e.g., "3 months of pain" = 3)
- affected_body_part: knee, shoulder, lumbar spine, cervical spine, brain, etc.
- laterality: "right", "left", "bilateral", or null
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

    def extract_evidence_multi(
        self,
        chart_texts: List[Tuple[str, Optional[str]]]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract and merge evidence from multiple patient charts for the same patient.

        Args:
            chart_texts: List of tuples (chart_text, source_identifier)
                        where source_identifier can be filename, timestamp, etc.

        Returns:
            Merged evidence dictionary with source tracking metadata

        Merge Strategy:
            - Conservative therapy: ANY documented attempt = documented
            - Duration values: Use MAXIMUM across all charts
            - Evidence notes: Accumulate ALL notes from all charts
            - Conflicting values: Most recent (last in list) wins
            - Metadata: Track which source contributed which data
        """
        if not chart_texts:
            logger.error("No chart texts provided")
            return None

        all_extractions = []
        sources = []

        # Extract from each chart independently
        for idx, (chart_text, source_id) in enumerate(chart_texts):
            source_name = source_id or f"chart_{idx}"
            logger.info(f"Extracting from {source_name}")

            extracted = self.extract_evidence(chart_text)
            if extracted:
                all_extractions.append(extracted)
                sources.append(source_name)
            else:
                logger.warning(f"Failed to extract from {source_name}")

        if not all_extractions:
            logger.error("All extractions failed")
            return None

        # If only one successful extraction, return it with source info
        if len(all_extractions) == 1:
            all_extractions[0]["_multi_source_metadata"] = {
                "total_charts": len(chart_texts),
                "successful_extractions": 1,
                "sources": sources
            }
            return all_extractions[0]

        # Merge multiple extractions
        merged = self._merge_extractions(all_extractions, sources)
        return merged

    def _merge_extractions(
        self,
        extractions: List[Dict[str, Any]],
        sources: List[str]
    ) -> Dict[str, Any]:
        """
        Merge multiple evidence extractions into a single unified structure.

        Merge rules:
        1. Scalar values (duration, body_part, laterality): Last non-null wins
        2. Boolean 'documented'/'attempted' flags: True if ANY is True
        3. Nested therapy objects: Merge with priority to documented attempts
        4. Evidence notes: Concatenate all unique notes
        5. Metadata: Track sources and merge hallucination counts
        """
        merged = {
            "symptom_duration_months": None,
            "affected_body_part": None,
            "laterality": None,
            "conservative_therapy": {
                "physical_therapy": {
                    "attempted": False,
                    "duration_weeks": None,
                    "outcome": None
                },
                "nsaids": {
                    "documented": False,
                    "outcome": None
                },
                "injections": {
                    "documented": False,
                    "type": None,
                    "outcome": None
                },
                "other_treatments": {
                    "documented": False,
                    "description": None,
                    "outcome": None
                }
            },
            "imaging": {
                "documented": False,
                "type": None,
                "body_part": None,
                "laterality": None,
                "months_ago": None,
                "findings": None
            },
            "functional_impairment": {
                "documented": False,
                "description": None
            },
            "neurological_symptoms": {
                "documented": False,
                "description": None
            },
            "pain_characteristics": {
                "documented": False,
                "severity": None,
                "quality": None,
                "radiation": None
            },
            "red_flags": {
                "documented": False,
                "description": None
            },
            "evidence_notes": []
        }

        all_evidence_notes = []
        total_hallucinations = 0
        all_hallucinated_notes = []
        source_contributions = {}

        for idx, extraction in enumerate(extractions):
            source = sources[idx]
            source_contributions[source] = []

            # Merge scalar fields (max for durations, last non-null for others)
            if extraction.get("symptom_duration_months"):
                if merged["symptom_duration_months"] is None:
                    merged["symptom_duration_months"] = extraction["symptom_duration_months"]
                    source_contributions[source].append("symptom_duration_months")
                else:
                    # Use maximum duration
                    if extraction["symptom_duration_months"] > merged["symptom_duration_months"]:
                        merged["symptom_duration_months"] = extraction["symptom_duration_months"]
                        source_contributions[source].append("symptom_duration_months (max)")

            # Last non-null wins for body part and laterality
            if extraction.get("affected_body_part"):
                merged["affected_body_part"] = extraction["affected_body_part"]
                source_contributions[source].append("affected_body_part")

            if extraction.get("laterality"):
                merged["laterality"] = extraction["laterality"]
                source_contributions[source].append("laterality")

            # Merge conservative therapy (ANY documented = True, max duration)
            ct = extraction.get("conservative_therapy", {})

            # Physical therapy
            pt = ct.get("physical_therapy", {})
            if pt.get("attempted"):
                merged["conservative_therapy"]["physical_therapy"]["attempted"] = True
                source_contributions[source].append("PT attempted")
                if pt.get("duration_weeks"):
                    if merged["conservative_therapy"]["physical_therapy"]["duration_weeks"] is None:
                        merged["conservative_therapy"]["physical_therapy"]["duration_weeks"] = pt["duration_weeks"]
                    else:
                        merged["conservative_therapy"]["physical_therapy"]["duration_weeks"] = max(
                            merged["conservative_therapy"]["physical_therapy"]["duration_weeks"],
                            pt["duration_weeks"]
                        )
                if pt.get("outcome"):
                    merged["conservative_therapy"]["physical_therapy"]["outcome"] = pt["outcome"]

            # NSAIDs
            nsaids = ct.get("nsaids", {})
            if nsaids.get("documented"):
                merged["conservative_therapy"]["nsaids"]["documented"] = True
                source_contributions[source].append("NSAIDs documented")
                if nsaids.get("outcome"):
                    merged["conservative_therapy"]["nsaids"]["outcome"] = nsaids["outcome"]

            # Injections
            inj = ct.get("injections", {})
            if inj.get("documented"):
                merged["conservative_therapy"]["injections"]["documented"] = True
                source_contributions[source].append("Injections documented")
                if inj.get("type"):
                    merged["conservative_therapy"]["injections"]["type"] = inj["type"]
                if inj.get("outcome"):
                    merged["conservative_therapy"]["injections"]["outcome"] = inj["outcome"]

            # Other treatments
            other = ct.get("other_treatments", {})
            if other.get("documented"):
                merged["conservative_therapy"]["other_treatments"]["documented"] = True
                source_contributions[source].append("Other treatments documented")
                if other.get("description"):
                    merged["conservative_therapy"]["other_treatments"]["description"] = other["description"]
                if other.get("outcome"):
                    merged["conservative_therapy"]["other_treatments"]["outcome"] = other["outcome"]

            # Merge imaging (ANY documented = True)
            img = extraction.get("imaging", {})
            if img.get("documented"):
                merged["imaging"]["documented"] = True
                source_contributions[source].append("Imaging documented")
                for field in ["type", "body_part", "laterality", "findings"]:
                    if img.get(field):
                        merged["imaging"][field] = img[field]
                # Use most recent imaging (minimum months_ago)
                if img.get("months_ago") is not None:
                    if merged["imaging"]["months_ago"] is None:
                        merged["imaging"]["months_ago"] = img["months_ago"]
                    else:
                        merged["imaging"]["months_ago"] = min(
                            merged["imaging"]["months_ago"],
                            img["months_ago"]
                        )

            # Merge functional impairment
            fi = extraction.get("functional_impairment", {})
            if fi.get("documented"):
                merged["functional_impairment"]["documented"] = True
                source_contributions[source].append("Functional impairment documented")
                if fi.get("description"):
                    merged["functional_impairment"]["description"] = fi["description"]

            # Merge neurological symptoms
            neuro = extraction.get("neurological_symptoms", {})
            if neuro.get("documented"):
                merged["neurological_symptoms"]["documented"] = True
                source_contributions[source].append("Neurological symptoms documented")
                if neuro.get("description"):
                    merged["neurological_symptoms"]["description"] = neuro["description"]

            # Merge pain characteristics
            pain = extraction.get("pain_characteristics", {})
            if pain.get("documented"):
                merged["pain_characteristics"]["documented"] = True
                source_contributions[source].append("Pain characteristics documented")
                for field in ["severity", "quality", "radiation"]:
                    if pain.get(field):
                        merged["pain_characteristics"][field] = pain[field]

            # Merge red flags
            rf = extraction.get("red_flags", {})
            if rf.get("documented"):
                merged["red_flags"]["documented"] = True
                source_contributions[source].append("Red flags documented")
                if rf.get("description"):
                    merged["red_flags"]["description"] = rf["description"]

            # Accumulate evidence notes
            notes = extraction.get("evidence_notes", [])
            all_evidence_notes.extend(notes)

            # Accumulate hallucination metadata
            metadata = extraction.get("_metadata", {})
            total_hallucinations += metadata.get("hallucinations_detected", 0)
            all_hallucinated_notes.extend(metadata.get("hallucinated_notes", []))

        # Deduplicate evidence notes while preserving order
        seen = set()
        unique_notes = []
        for note in all_evidence_notes:
            if note.lower() not in seen:
                seen.add(note.lower())
                unique_notes.append(note)

        merged["evidence_notes"] = unique_notes

        # Add comprehensive metadata
        merged["_multi_source_metadata"] = {
            "total_charts": len(extractions),
            "sources": sources,
            "source_contributions": source_contributions,
            "total_hallucinations": total_hallucinations,
            "hallucinated_notes": all_hallucinated_notes,
            "validation_passed": total_hallucinations == 0
        }

        return merged


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


def extract_evidence_multi(
    chart_texts: List[Tuple[str, Optional[str]]],
    use_groq: bool = False,
    groq_api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Extract and merge evidence from multiple patient charts.

    Args:
        chart_texts: List of (chart_text, source_identifier) tuples
        use_groq: Whether to use Groq API or local model
        groq_api_key: Optional Groq API key

    Returns:
        Merged evidence dictionary with source tracking metadata
    """
    extractor = get_extractor(use_groq=use_groq, groq_api_key=groq_api_key)
    return extractor.extract_evidence_multi(chart_texts)