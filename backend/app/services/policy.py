# Put rag in here?
#embeds payer policy PDFs
#retrieves relevant chunks
#optionally asks LLM to normalize them
#👉 This is your only RAG dependency

# I think this is supposed to build my index from cpt, payer policy stuff.

def get_policy_criteria(payer: str, cpt: str) -> dict:
    """
    Uses vector search over payer PDFs.
    
    Output:
    {
      "required_symptom_duration_months": 3,
      "required_pt_weeks": 6,
      "imaging_required": True,
      "imaging_recency_months": 6,
      "raw_policy_text": "..."
    }
    """
