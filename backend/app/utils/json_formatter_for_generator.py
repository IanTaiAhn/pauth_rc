import json
import re
from typing import Dict, List, Optional


class JSONFormatter:
    """
    Handles JSON extraction, cleaning, and validation.
    Separate from generation logic.
    """
    
    @staticmethod
    def extract_json(text: str) -> dict:
        """
        Extract and parse JSON from text that may contain markdown, preamble, etc.
        
        Args:
            text: Raw text that contains JSON
        
        Returns:
            Parsed JSON as dict
        
        Raises:
            ValueError: If JSON cannot be extracted or parsed
        """
        # Remove markdown code fences
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Find JSON boundaries
        start = text.find('{')
        end = text.rfind('}')
        
        if start == -1 or end == -1 or start >= end:
            raise ValueError(f"No valid JSON found in response. Text preview: {text[:200]}")
        
        # Extract JSON string
        json_str = text[start:end+1]
        
        try:
            # Parse JSON
            parsed = json.loads(json_str)
            return parsed
        
        except json.JSONDecodeError as e:
            # Attempt automatic repairs
            print(f"⚠️  JSON parse error, attempting repairs...")
            repaired = JSONFormatter._repair_json(json_str)
            
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                raise ValueError(
                    f"Could not parse JSON even after repairs: {e}\n\n"
                    f"Extracted JSON: {json_str[:500]}"
                )
    
    @staticmethod
    def _repair_json(json_str: str) -> str:
        """
        Attempt common JSON repairs for LLM output.
        
        Args:
            json_str: Potentially malformed JSON string
        
        Returns:
            Repaired JSON string
        """
        # Fix single quotes to double quotes
        json_str = json_str.replace("'", '"')
        
        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Fix unescaped newlines in strings (common LLM issue)
        # This is a simple heuristic - may not catch all cases
        json_str = re.sub(r'(?<!\\)\n(?=[^"]*"[^"]*:)', r'\\n', json_str)
        
        return json_str
    
    @staticmethod
    def validate_policy_structure(data: dict, strict: bool = False) -> Dict[str, List[str]]:
        """
        Validate medical policy JSON structure.
        
        Args:
            data: Parsed JSON data
            strict: If True, raise ValueError on missing fields. 
                   If False, return validation report.
        
        Returns:
            Dict with 'missing_required' and 'missing_optional' keys
        
        Raises:
            ValueError: If strict=True and validation fails
        """
        # Required top-level fields
        required_keys = [
            "payer",
            "cpt_code",
            "coverage_criteria",
            "source_references"
        ]
        
        # Optional but expected coverage criteria
        expected_criteria = [
            "clinical_indications",
            "prerequisites",
            "exclusion_criteria",
            "documentation_requirements",
            "quantity_limits"
        ]
        
        # Check required keys
        missing_required = [k for k in required_keys if k not in data]
        
        # Check coverage criteria structure
        missing_criteria = []
        if "coverage_criteria" in data:
            criteria = data["coverage_criteria"]
            missing_criteria = [c for c in expected_criteria if c not in criteria]
        
        validation_report = {
            "missing_required": missing_required,
            "missing_optional": missing_criteria
        }
        
        # Strict mode raises on missing required fields
        if strict and missing_required:
            raise ValueError(f"Missing required fields: {missing_required}")
        
        return validation_report
    
    @staticmethod
    def extract_and_validate_policy(
        text: str,
        strict: bool = False
    ) -> Dict:
        """
        Combined extraction and validation for medical policies.
        
        Args:
            text: Raw text containing JSON
            strict: If True, raise on validation errors
        
        Returns:
            Parsed and validated policy dict
        """
        # Extract JSON
        policy_data = JSONFormatter.extract_json(text)
        
        # Validate structure
        validation = JSONFormatter.validate_policy_structure(policy_data, strict=strict)
        
        # Log warnings for optional missing fields
        if validation["missing_optional"]:
            print(f"⚠️  Warning: Missing optional fields: {validation['missing_optional']}")
        
        return policy_data


# Convenience function
def extract_policy_json(text: str, strict: bool = False) -> dict:
    """
    Extract and validate medical policy JSON from text.
    
    Args:
        text: Raw text containing JSON
        strict: If True, raise on missing required fields
    
    Returns:
        Parsed policy dict
    
    Example:
        raw_output = generate(prompt)
        policy_data = extract_policy_json(raw_output)
    """
    return JSONFormatter.extract_and_validate_policy(text, strict=strict)