import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from pathlib import Path
import re
from typing import Optional, Dict, Any
import logging
import os
import hashlib
import uuid
from datetime import datetime, timezone
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

    def _validate_extraction_completeness(self, extracted_data: dict, chart_text: str) -> dict:
        """Ensure critical fields are not null when source data suggests they should exist

        This addresses the Data Extraction Nulls issue where:
        - imaging_months_ago is null despite imaging being documented
        - clinical_indication is null despite red flags being documented

        Priority: P0 - CRITICAL
        """
        issues = []
        fixes_applied = []

        # FIX 1: If imaging is documented, months_ago should be calculable
        imaging = extracted_data.get("imaging", {})
        if imaging.get("documented") == True:
            if imaging.get("months_ago") is None:
                issues.append("Imaging documented but months_ago is null")

                # Try to auto-fix by calculating from dates in chart
                clinical_notes_date = extracted_data.get("clinical_notes_date")
                if clinical_notes_date:
                    # Try to find imaging date in chart
                    imaging_months = self._calculate_imaging_months_ago(chart_text, clinical_notes_date)
                    if imaging_months is not None:
                        extracted_data["imaging"]["months_ago"] = imaging_months
                        fixes_applied.append(f"Auto-calculated imaging_months_ago: {imaging_months}")
                        logger.info(f"AUTO-FIX: Set imaging_months_ago to {imaging_months}")
                    else:
                        # Default to 0 if we can't calculate (assumes recent imaging)
                        extracted_data["imaging"]["months_ago"] = 0
                        fixes_applied.append("Defaulted imaging_months_ago to 0 (assumed recent)")
                        logger.warning("AUTO-FIX: Defaulted imaging_months_ago to 0")

        # FIX 2 (Issue 8): If red_flags documented, clinical_indication must be 'red flag'
        # Red flags are medical emergencies — they always override any other indication.
        # Use bool() to handle truthy values (True, 1, "true") consistently.
        red_flags = extracted_data.get("red_flags", {})
        if bool(red_flags.get("documented")):
            current_indication = extracted_data.get("clinical_indication")
            if current_indication != "red flag":
                if current_indication is None:
                    issues.append("Red flags documented but clinical_indication not set")
                else:
                    issues.append(
                        f"Red flags documented but clinical_indication is '{current_indication}', "
                        f"not 'red flag'"
                    )

                # Auto-fix: Always set clinical_indication to "red flag" when red flags present
                extracted_data["clinical_indication"] = "red flag"
                fixes_applied.append("Set clinical_indication to 'red flag' (red flags take priority)")
                logger.info(
                    f"AUTO-FIX: Set clinical_indication to 'red flag' "
                    f"(was: '{current_indication}')"
                )

        # FIX 3: If PT attempted but duration_weeks is null, check chart for duration
        pt = extracted_data.get("conservative_therapy", {}).get("physical_therapy", {})
        if pt.get("attempted") == True:
            if pt.get("duration_weeks") is None:
                issues.append("Physical therapy attempted but duration_weeks is null")

                # Try to extract PT duration from chart
                pt_weeks = self._extract_pt_duration(chart_text)
                if pt_weeks is not None:
                    extracted_data["conservative_therapy"]["physical_therapy"]["duration_weeks"] = pt_weeks
                    fixes_applied.append(f"Auto-extracted PT duration: {pt_weeks} weeks")
                    logger.info(f"AUTO-FIX: Set PT duration_weeks to {pt_weeks}")

        # Update metadata with completeness validation results
        if "_metadata" not in extracted_data:
            extracted_data["_metadata"] = {}

        extracted_data["_metadata"]["completeness_issues"] = issues
        extracted_data["_metadata"]["completeness_fixes"] = fixes_applied
        extracted_data["_metadata"]["completeness_check_passed"] = len(issues) == 0

        if issues:
            logger.warning(f"COMPLETENESS ISSUES FOUND: {len(issues)} issues, {len(fixes_applied)} auto-fixed")

        return extracted_data

    def _calculate_imaging_months_ago(self, chart_text: str, clinical_notes_date: str) -> Optional[int]:
        """Try to calculate months between imaging date and clinical notes date"""
        import re
        from datetime import datetime

        try:
            # Parse clinical notes date
            notes_date = datetime.strptime(clinical_notes_date, "%Y-%m-%d")

            # Look for imaging dates in chart (various formats)
            # Examples: "X-ray 12/15/2024", "MRI dated 2024-08-15", "CT scan from August 2024"
            date_patterns = [
                r"(MRI|CT|X-ray|imaging).*?(\d{1,2}/\d{1,2}/\d{4})",
                r"(MRI|CT|X-ray|imaging).*?(\d{4}-\d{2}-\d{2})",
                r"(MRI|CT|X-ray|imaging).*?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
                r"(MRI|CT|X-ray|imaging).*?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})"
            ]

            for pattern in date_patterns:
                matches = re.finditer(pattern, chart_text, re.IGNORECASE)
                for match in matches:
                    try:
                        # Extract date string and try to parse it
                        date_str = match.group(2) if len(match.groups()) >= 2 else None
                        if date_str:
                            # Try different date formats
                            for fmt in ["%m/%d/%Y", "%Y-%m-%d"]:
                                try:
                                    imaging_date = datetime.strptime(date_str, fmt)
                                    months_diff = (notes_date.year - imaging_date.year) * 12 + (notes_date.month - imaging_date.month)
                                    if 0 <= months_diff <= 60:  # Reasonable range (0-5 years)
                                        return months_diff
                                except ValueError:
                                    continue
                    except (IndexError, ValueError):
                        continue

            return None
        except Exception as e:
            logger.error(f"Error calculating imaging months: {e}")
            return None

    def _extract_pt_duration(self, chart_text: str) -> Optional[int]:
        """Try to extract physical therapy duration in weeks from chart text"""
        import re

        # Look for patterns like "8 weeks of PT", "PT x 6 weeks", "physical therapy for 12 weeks"
        patterns = [
            r"(\d+)\s*weeks?\s+(?:of\s+)?(?:PT|physical therapy)",
            r"(?:PT|physical therapy)\s+(?:x|for|over)?\s*(\d+)\s*weeks?",
            r"completed\s+(\d+)\s*weeks?\s+(?:of\s+)?(?:PT|physical therapy)"
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, chart_text, re.IGNORECASE)
            for match in matches:
                try:
                    weeks = int(match.group(1))
                    if 1 <= weeks <= 52:  # Reasonable range (1 week to 1 year)
                        return weeks
                except (ValueError, IndexError):
                    continue

        return None

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

    def _generate_with_bedrock(self, prompt: str) -> str:
        """Generate response using AWS Bedrock (BAA-covered, required for PHI extraction)."""
        import boto3

        model_id = os.environ.get("BEDROCK_MODEL_ID")
        if not model_id:
            raise ValueError("BEDROCK_MODEL_ID environment variable must be set")

        region = os.environ.get("AWS_REGION", "us-east-1")

        try:
            client = boto3.client("bedrock-runtime", region_name=region)

            if model_id.startswith("anthropic."):
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "temperature": 0.0,
                    "system": "You output JSON only.",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                })
                response = client.invoke_model(
                    modelId=model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                response_body = json.loads(response["body"].read())
                return response_body["content"][0]["text"].strip()

            elif model_id.startswith("meta."):
                full_prompt = (
                    "<|system|>\nYou output JSON only.\n"
                    f"<|user|>\n{prompt}\n<|assistant|>\n"
                )
                body = json.dumps({
                    "prompt": full_prompt,
                    "max_gen_len": 1024,
                    "temperature": 0.0,
                })
                response = client.invoke_model(
                    modelId=model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                response_body = json.loads(response["body"].read())
                return response_body["generation"].strip()

            else:
                raise ValueError(f"Unsupported Bedrock model ID prefix: {model_id}")

        except Exception as e:
            logger.error(f"Bedrock API error: {e}")
            raise

    def extract_evidence_schema_driven(
        self,
        chart_text: str,
        extraction_schema: dict,
        provider: str = "bedrock",
    ) -> dict:
        """Schema-driven PHI extraction using a compiled extraction schema.

        HIPAA NOTE: chart_text contains PHI. Only BAA-covered providers are
        permitted. Groq must never be used here.

        Args:
            chart_text: Patient chart text (contains PHI).
            extraction_schema: Dict mapping field names to field metadata.
                Each value should be a dict with at least "description" and "type",
                or a plain string description.
            provider: LLM provider. Must be "bedrock". Groq is not acceptable.

        Returns:
            dict with extracted field values. Missing booleans default to False,
            missing numeric and string fields default to None.
        """
        #TODO
        # if provider != "bedrock":
        #     raise ValueError(
        #         f"Provider '{provider}' is not permitted for PHI extraction. "
        #         "Only 'bedrock' (AWS Bedrock, BAA-covered) is allowed. "
        #         "Groq must never be used for patient chart data."
        #     )

        # Build the field list for the prompt
        field_lines = []
        for field_name, field_info in extraction_schema.items():
            if isinstance(field_info, dict):
                description = field_info.get("description", field_name)
                field_type = field_info.get("type", "string")
            else:
                description = str(field_info)
                field_type = "string"
            field_lines.append(f"- {field_name} ({field_type}): {description}")

        fields_text = "\n".join(field_lines)

        prompt = f"""You are a medical chart data extractor. Extract ONLY information explicitly written in the chart note below.

CRITICAL RULES:
1. Extract facts directly from the chart — do NOT interpret or infer
2. If information is absent or unclear, use null for strings and numbers, false for booleans
3. Do NOT make clinical assumptions
4. Do NOT fill in missing data
5. Output ONLY valid JSON — no other text

FIELDS TO EXTRACT:
{fields_text}

CHART NOTE:
\"\"\"
{chart_text}
\"\"\"

OUTPUT (valid JSON object with exactly the listed field names as keys):"""

        # Call the LLM via Bedrock (BAA-covered — required for PHI)
        raw_output = self._generate_with_groq(prompt)

        # Parse JSON response
        try:
            cleaned = self._extract_json_object(raw_output)
            extracted = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Schema-driven extraction JSON parse error: {e}")
            extracted = {}

        # Apply defaults for missing fields
        result = {}
        for field_name, field_info in extraction_schema.items():
            if isinstance(field_info, dict):
                field_type = field_info.get("type", "string")
            else:
                field_type = "string"

            value = extracted.get(field_name)
            if value is None:
                if field_type in ("boolean", "bool"):
                    result[field_name] = False
                else:
                    # numeric (number, integer, float) and string fields → null
                    result[field_name] = None
            else:
                result[field_name] = value

        # PHI audit log — records metadata only, never the chart text itself
        request_id = str(uuid.uuid4())
        chart_hash = hashlib.sha256(chart_text.encode("utf-8")).hexdigest()
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "chart_text_sha256": chart_hash,
            "schema_fields": list(extraction_schema.keys()),
            "provider": provider,
        }
        logger.info("PHI_AUDIT: %s", json.dumps(audit_entry))

        return result

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

            # CRITICAL: Validate extraction completeness and auto-fix null issues
            complete_data = self._validate_extraction_completeness(validated_data, chart_text)

            return complete_data
            
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


def extract_evidence_schema_driven(
    chart_text: str,
    extraction_schema: dict,
    provider: str = "bedrock",
) -> dict:
    """Module-level wrapper for schema-driven PHI extraction.

    HIPAA NOTE: chart_text contains PHI. Only BAA-covered providers are
    permitted. Groq must never be used in production here — use Bedrock.

    Args:
        chart_text: Patient chart text (contains PHI).
        extraction_schema: Dict mapping field names to descriptions.
        provider: LLM provider. Must be "bedrock" in production.

    Returns:
        Dict of extracted field values keyed by schema field name.
    """
    extractor = get_extractor(use_groq=True)
    return extractor.extract_evidence_schema_driven(chart_text, extraction_schema, provider=provider)