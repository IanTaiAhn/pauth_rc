# Put rag in here?
#embeds payer policy PDFs
#retrieves relevant chunks
#optionally asks LLM to normalize them
#👉 This is your only RAG dependency

# I think this is supposed to build my index from cpt, payer policy stuff.
# OKAY! It is finally coming together better in my brain.
# This needs to be hooked up to a rag pipeline and the vector database has a bunch of bcbs, cpt codes embedded... It would be best if I can select which code they want to use.

def get_policy_criteria(payer: str, cpt: str) -> dict:
    """
    Uses vector search over payer PDFs.
    
"""



# Example of the output I'd probably want. It needs to be transformed twice, so the out put of the RAG is text, and then we have some structured JSON
[
  {
    "text": "Lumbar epidural steroid injections are medically necessary when radicular pain persists ≥6 weeks despite conservative therapy.",
    "source": "BCBS_Lumbar_ESI_Policy.pdf",
    "section": "Medical Necessity Criteria"
  },
  {
    "text": "MRI or CT must demonstrate nerve root compression correlating with symptoms.",
    "source": "BCBS_Lumbar_ESI_Policy.pdf",
    "section": "Imaging Requirements"
  }
]

# ⚙️ Important: RAG Is Only for Policies
# Do NOT put chart notes into this vector DB.
# Your vector DB should ONLY contain:
# Payer medical policies
# Coverage determination documents
# Clinical criteria bullet lists
# If you mix charts in, you’ll get garbage retrieval.
