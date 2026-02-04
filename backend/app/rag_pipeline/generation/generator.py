# generation/generator.py
import os
from pathlib import Path
from typing import Optional, Literal
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models" / "qwen2.5"

class MedicalGenerator:
    def __init__(
        self, 
        provider: Literal["local", "groq"] = "local",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize medical policy generator
        
        Args:
            provider: "local" for Qwen2.5, "groq" for Groq API
            model_name: Model to use (e.g., "llama-3.3-70b-versatile" for Groq)
            api_key: API key for Groq (or set GROQ_API_KEY env var)
        """
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        
        # Local model attributes
        self.model = None
        self.tokenizer = None
        
        # Groq client
        self.groq_client = None
        
        if provider == "local":
            self._load_local_model()
        elif provider == "groq":
            self._init_groq_client()
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    def _load_local_model(self):
        """Load Qwen2.5 model locally"""
        if self.model is None:
            print("Loading Qwen2.5 model for medical policy extraction...")
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
            self.model = AutoModelForCausalLM.from_pretrained(
                MODEL_DIR,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True
            )
            self.model.eval()
            print("Model loaded successfully")
    
    def _init_groq_client(self):
        """Initialize Groq API client"""
        try:
            from groq import Groq
        except ImportError:
            raise ImportError(
                "Groq library not installed. Run: pip install groq"
            )
        
        if not self.api_key:
            raise ValueError(
                "Groq API key required. Set GROQ_API_KEY env var or pass api_key parameter"
            )
        
        self.groq_client = Groq(api_key=self.api_key)
        
        # Set default model if not provided
        if not self.model_name:
            self.model_name = "llama-3.3-70b-versatile"
        
        print(f"Initialized Groq client with model: {self.model_name}")
    
    def generate_answer(
        self, 
        prompt: str, 
        max_tokens: int = 1024,
        temperature: float = 0.1
    ) -> Optional[str]:
        """
        Generate medical policy extraction
        
        Args:
            prompt: The extraction prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
        
        Returns:
            Generated response or None if failed
        """
        if self.provider == "local":
            return self._generate_local(prompt, max_tokens, temperature)
        elif self.provider == "groq":
            return self._generate_groq(prompt, max_tokens, temperature)
    
    def _generate_local(
        self, 
        prompt: str, 
        max_tokens: int,
        temperature: float
    ) -> Optional[str]:
        """Generate using local Qwen2.5 model"""
        try:
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=4096
            )
            
            generation_kwargs = {
                "max_new_tokens": max_tokens,
                "pad_token_id": self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "repetition_penalty": 1.1
            }
            
            # Add sampling parameters only if temperature > 0
            if temperature > 0:
                generation_kwargs.update({
                    "temperature": temperature,
                    "do_sample": True,
                    "top_p": 0.95
                })
            else:
                generation_kwargs["do_sample"] = False
            
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs.input_ids,
                    **generation_kwargs
                )
            
            # Decode only new tokens
            generated_ids = outputs[0][inputs.input_ids.shape[1]:]
            response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
            
            return response.strip()
            
        except Exception as e:
            print(f"❌ Local generation failed: {type(e).__name__}: {e}")
            return None
    
    def _generate_groq(
        self, 
        prompt: str, 
        max_tokens: int,
        temperature: float
    ) -> Optional[str]:
        """Generate using Groq API"""
        try:
            response = self.groq_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a medical policy analyst expert at extracting structured data from insurance documents."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.95,
                stream=False
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"❌ Groq generation failed: {type(e).__name__}: {e}")
            return None


# Global instance
_generator = None

def get_generator(
    provider: Literal["local", "groq"] = "local",
    model_name: Optional[str] = None,
    api_key: Optional[str] = None
) -> MedicalGenerator:
    """
    Get or create generator instance
    
    Args:
        provider: "local" or "groq"
        model_name: Model name (for Groq)
        api_key: API key (for Groq)
    """
    global _generator
    
    # Create new instance if doesn't exist or provider changed
    if _generator is None or _generator.provider != provider:
        _generator = MedicalGenerator(
            provider=provider,
            model_name=model_name,
            api_key=api_key
        )
    
    return _generator

def generate_with_context(
    prompt: str, 
    max_tokens: int = 1024,
    temperature: float = 0.1,
    provider: Literal["local", "groq"] = "local",
    model_name: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[str]:
    """
    Convenience function for generation
    
    Args:
        prompt: Extraction prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        provider: "local" or "groq"
        model_name: Model name for Groq (e.g., "llama-3.3-70b-versatile")
        api_key: Groq API key
    
    Returns:
        Generated text or None
    
    Example:
        # Use local Qwen2.5
        result = generate_with_context(prompt, provider="local")
        
        # Use Groq with Llama 3.3 70B
        result = generate_with_context(
            prompt, 
            provider="groq",
            model_name="llama-3.3-70b-versatile",
            api_key="your_api_key_here"
        )
    """
    generator = get_generator(provider, model_name, api_key)
    return generator.generate_answer(prompt, max_tokens, temperature)