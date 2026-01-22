# Supposedly my most important file. This determines what clinical facts are worth it.

# def detect_conservative_therapy(text: str) -> dict:
#     keywords = ["physical therapy", "pt", "chiropractic", "home exercise"]
#     for kw in keywords:
#         if kw in text.lower():
#             return {
#                 "found": True,
#                 "evidence_text": kw,
#                 "confidence": 0.85
#             }
#     return {
#         "found": False,
#         "confidence": 0.9
#     }
# You can later replace this with:
# LLM classification
# embeddings + retrieval
# hybrid rules
# But start simple and deterministic.


# # Aggregator
# def extract_evidence(text: str) -> dict:
#     return {
#         "conservative_therapy": detect_conservative_therapy(text),
#         "duration_documented": detect_duration(text),
#         "failed_treatments": detect_failed_treatments(text),
#         "symptom_severity": detect_severity(text),
#         "recent_imaging": detect_imaging(text)
#     }

# def extract_evidence(chart_text: str) -> dict:
#     """
#     Output example:
#     {
#       "symptom_duration_months": 6,
#       "failed_pt": True,
#       "pt_duration_weeks": 8,
#       "failed_nsaids": True,
#       "imaging": {
#         "type": "MRI",
#         "date": "2024-11-01"
#       }
#     }
#     """

import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from pathlib import Path
import json
import re

MODEL_PATH = r"C:\Users\n0308g\Git_Repos\pauth_rc\backend\app\services\models\qwen2.5"

# print('MODEL_PATH', MODEL_PATH)

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    # device_map="auto",
    dtype=torch.float16,
    trust_remote_code=True
)

model.eval()

def extract_json_object(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output")
    return match.group(0)

def extract_evidence(chart_text: str) -> dict:
    prompt = f"""
You are a clinical documentation extraction assistant.

Your task is to extract ONLY facts that are explicitly stated in the chart note.
Do NOT infer, assume, or guess.

If information is not clearly present, set the value to null or false.

Return valid JSON only. No explanations.

Use this schema exactly:

{{
  "symptom_duration_months": number or null,

  "failed_conservative_therapy": boolean,
  "conservative_therapy_details": {{
    "physical_therapy": {{
      "attempted": boolean,
      "duration_weeks": number or null
    }},
    "nsaids": {{
      "attempted": boolean
    }},
    "injections": {{
      "attempted": boolean
    }}
  }},

  "imaging": {{
    "performed": boolean,
    "type": string or null,
    "body_part": string or null,
    "months_ago": number or null
  }},

  "functional_impairment": boolean,

  "confidence_notes": array of strings
}}

Chart note:
\"\"\"
{chart_text}
\"\"\"
"""

    messages = [
        {"role": "system", "content": "You output JSON only."},
        {"role": "user", "content": prompt}
    ]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=600,
            temperature=0.0,
            do_sample=False
        )

    raw_output = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[-1]:],
        skip_special_tokens=True
    ).strip()

    try:
        cleaned = extract_json_object(raw_output)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON from model:\n{cleaned}")


if __name__ == "__main__":


    chart = """
Patient presents with chronic right knee pain for 6 months.
Completed 8 weeks of physical therapy with minimal improvement.
Failed NSAIDs.
MRI of the right knee obtained 3 months ago.
Pain interferes with daily activities.
"""

evidence = extract_evidence(chart)
print(json.dumps(evidence, indent=2))