# generation/generator.py
import os
from pathlib import Path
from transformers import pipeline
from transformers import AutoModelForCausalLM, AutoTokenizer
# OPENAI = os.getenv("OPENAI_API_KEY") is not None

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/rag_pipeline
MODEL_DIR = BASE_DIR / "models" / "qwen2.5"

def generate_answer(prompt: str, max_tokens: int = 256):
    try:
        print("I'm using a locally loaded model")

        model_path = MODEL_DIR  # make sure this exists

        # Load tokenizer + model
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForCausalLM.from_pretrained(model_path)

        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            device=-1  # CPU
        )

        out = pipe(
            prompt,
            max_length=max_tokens,   # use function arg instead of hardcoded 512
            do_sample=False
        )

        return out[0]["generated_text"]

    except Exception as e:
        print("❌ Local model generation failed.")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")
        return "Sorry, I couldn't generate a response due to a local model error."
