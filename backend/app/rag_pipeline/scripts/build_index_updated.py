import os
from app.rag_pipeline.ingestion.pdf_loader import load_pdf_text
from app.rag_pipeline.ingestion.text_loader import load_text_file

# NEW: Import the improved chunker instead of the old one
from app.rag_pipeline.chunking.improved_chunker import InsurancePolicyChunker

from app.rag_pipeline.embeddings.embedder import get_embedder
from app.rag_pipeline.embeddings.vectorstore import FaissStore
from transformers import AutoTokenizer

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/rag_pipeline
FRONTEND_BASE_DIR = Path(__file__).resolve().parents[3]
# DATA_DIR is for local file usage
DATA_DIR = BASE_DIR / "data" / "raw_docs"
# For frontend file uploads
FRONTEND_DATA_DIR = FRONTEND_BASE_DIR / "uploaded_docs"

INDEX_DIR = BASE_DIR / "vectorstore"
CURRENT_DIR = Path(__file__).resolve().parent
MODEL_DIR = CURRENT_DIR.parent / "models" / "qwen2.5"

def load_all_documents():
    print('load docs portion: ', os.getcwd())
    docs = []
    print('build_index load_all_documents function FRONTEND_DATA_DIR: ', FRONTEND_DATA_DIR)
    # Switch DATA_DIR w/ FRONTEND_DATA_DIR for local or frontend usage
    for file in FRONTEND_DATA_DIR.iterdir():
        ext = file.suffix.lower()

        if ext == ".pdf":
            print(f"Loading PDF: {file}")
            text = load_pdf_text(file)

        elif ext in [".txt", ".md"]:
            print(f"Loading text file: {file}")
            text = load_text_file(file)

        else:
            print(f"Skipping unsupported file: {file}")
            continue

        docs.append((file, text))

    return docs

# no building of index in prod for now.
# def build_index():
#     INDEX_DIR.mkdir(exist_ok=True)

#     print("Loading embedding model to build index...")
#     embed = get_embedder()
#     print("embed model:", embed)

#     # local path
#     # model_path = "../models/qwen2.5"   # your local Qwen2.5 folder
#     model_path = str(MODEL_DIR)
#     tokenizer = AutoTokenizer.from_pretrained(model_path)
    
#     # NEW: Initialize the improved chunker with your tokenizer
#     chunker = InsurancePolicyChunker(
#         tokenizer=tokenizer,
#         max_tokens=400,      # Adjust based on your embedding model's context window
#         min_chunk_tokens=100 # Minimum chunk size to avoid tiny fragments
#     )
    
#     store = None

#     docs = load_all_documents()
#     index_name = docs[0][0].stem

#     print(f"Loaded {len(docs)} documents.")

#     for doc_name, text in docs:
#         print(f"\nChunking {doc_name}...")

#         # NEW: Use the improved chunker's chunk_document method
#         # This returns a list of dicts with rich metadata
#         chunks = chunker.chunk_document(text)
        
#         # Extract just the text for embedding
#         chunk_texts = [c["text"] for c in chunks]

#         print(f"Embedding {len(chunk_texts)} chunks...")
#         print(f"  - {sum(1 for c in chunks if c['is_requirement'])} requirement chunks")
#         print(f"  - {sum(1 for c in chunks if c['is_exception'])} exception chunks")
#         print(f"  - {sum(1 for c in chunks if c['logical_operator'])} chunks with logical operators")

#         vectors = embed.embed(chunk_texts)
#         print("vectors type:", type(vectors))

#         if store is None:
#             dim = len(vectors[0])
#             store = FaissStore(dim)

#         # NEW: Store ALL the rich metadata from improved chunker
#         # This is critical for retrieval enhancement
#         metadatas = [
#             {
#                 # Original metadata
#                 "doc_name": str(doc_name),
#                 "chunk_id": c["chunk_id"],
#                 "text": c["text"],
                
#                 # NEW: Rich metadata from improved chunker
#                 "rule_type": c["rule_type"],
#                 "section_header": c["section_header"],
#                 "parent_context": c.get("parent_context"),
#                 "logical_operator": c.get("logical_operator"),
#                 "is_exception": c["is_exception"],
#                 "is_requirement": c["is_requirement"],
#                 "is_definition": c["is_definition"],
#                 "cpt_codes": c["cpt_codes"],
#                 "icd_codes": c["icd_codes"],
#             }
#             for c in chunks
#         ]

#         store.add(vectors, metadatas)

#     print("\nSaving FAISS store... from build_index into: ", INDEX_DIR)
#     store.save(INDEX_DIR, index_name)

#     print("\nIndex build complete!")
#     print(f"Total vectors stored: {store.index.ntotal}")

# Global cache
STORE = None
EMBEDDER = None
CURRENT_INDEX = None

def load_index(index_name="default"):
    global STORE, EMBEDDER, CURRENT_INDEX
    print('INDEX PATHS DIR : ',INDEX_DIR)
    # index_dir = INDEX_ROOT  # all files live directly in vectorstore/

    # Load embedder
    EMBEDDER = get_embedder()

    # Load FAISS + metadata
    dim = len(EMBEDDER.embed(["test"])[0])
    STORE = FaissStore.load(dim, path=str(INDEX_DIR), name=index_name)
    CURRENT_INDEX = index_name
    print('current index build_index: ', CURRENT_INDEX)
    print(f"Loaded index build_index: {index_name}")

if __name__ == "__main__":
    print('build_index passed')
    # build_index()