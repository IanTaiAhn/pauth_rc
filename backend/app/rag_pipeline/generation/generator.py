# generation/generator.py
import os
from pathlib import Path
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models" / "qwen2.5"

class MedicalGenerator:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self._load_model()
    
    def _load_model(self):
        """Load model once and reuse"""
        if self.model is None:
            print("Loading Qwen2.5 model for medical policy extraction...")
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
            self.model = AutoModelForCausalLM.from_pretrained(
                MODEL_DIR,
                torch_dtype=torch.float32,  # or torch.float16 if supported
                low_cpu_mem_usage=True
            )
            self.model.eval()
            print("Model loaded successfully")
    
    def generate_answer(self, prompt: str, max_new_tokens: int = 512):
        """
        Generate medical policy extraction with proper tokenization
        """
        try:
            # Tokenize input
            inputs = self.tokenizer(
                prompt, 
                return_tensors="pt",
                truncation=True,
                max_length=2048  # Adjust based on your model's context window
            )
            
            # Generate with medical-appropriate parameters
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs.input_ids,
                    max_new_tokens=max_new_tokens,  # Only NEW tokens, not total
                    temperature=0.1,  # Low temperature for factual extraction
                    do_sample=False,  # Greedy decoding for consistency
                    pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    repetition_penalty=1.1  # Reduce repetition
                )
            
            # Decode ONLY the new tokens (exclude prompt)
            generated_ids = outputs[0][inputs.input_ids.shape[1]:]
            response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
            
            return response.strip()
            
        except Exception as e:
            print(f"❌ Generation failed: {type(e).__name__}: {e}")
            return None

# Global instance
_generator = None

def get_generator():
    global _generator
    if _generator is None:
        _generator = MedicalGenerator()
    return _generator

def generate_with_context(prompt: str, max_new_tokens: int = 512):
    """Wrapper for backward compatibility"""
    generator = get_generator()
    return generator.generate_answer(prompt, max_new_tokens)