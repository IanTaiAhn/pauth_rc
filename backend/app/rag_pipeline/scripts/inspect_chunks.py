"""
Chunk Quality Analyzer
Specifically analyzes the text chunks and their metadata to diagnose retrieval issues
"""

import pickle
import faiss
from pathlib import Path
import pandas as pd

def analyze_chunks(vectorstore_path, index_name="mocked_insurance_policy"):
    """Analyze chunks from a specific index"""
    
    vectorstore_path = Path(vectorstore_path)
    
    # Common file patterns to look for
    possible_files = [
        vectorstore_path / index_name / "index.pkl",
        vectorstore_path / index_name / "metadata.pkl",
        vectorstore_path / index_name / "chunks.pkl",
        vectorstore_path / index_name / "documents.pkl",
        vectorstore_path / f"{index_name}.pkl",
        vectorstore_path / f"{index_name}_metadata.pkl",
        vectorstore_path / f"{index_name}_chunks.pkl",
    ]
    
    print(f"\n{'='*80}")
    print(f"CHUNK QUALITY ANALYSIS FOR: {index_name}")
    print('='*80)
    
    # Try to find and load the pickle files
    loaded_data = {}
    for file_path in possible_files:
        if file_path.exists():
            print(f"\n✓ Found: {file_path}")
            try:
                with open(file_path, 'rb') as f:
                    data = pickle.load(f)
                    loaded_data[file_path.name] = data
                    print(f"  Loaded successfully, type: {type(data)}")
            except Exception as e:
                print(f"  ⚠ Error loading: {e}")
    
    if not loaded_data:
        print(f"\n⚠ No pickle files found. Searching entire directory...")
        all_pkl = list(vectorstore_path.glob("**/*.pkl"))
        print(f"Found {len(all_pkl)} pickle files:")
        for f in all_pkl:
            print(f"  - {f}")
        return
    
    # Analyze each loaded file
    print(f"\n{'='*80}")
    print("DETAILED CHUNK ANALYSIS")
    print('='*80)
    
    for filename, data in loaded_data.items():
        print(f"\n{'─'*80}")
        print(f"FILE: {filename}")
        print('─'*80)
        
        # Handle different data structures
        if isinstance(data, dict):
            analyze_dict_structure(data)
        elif isinstance(data, list):
            analyze_list_structure(data)
        else:
            print(f"Unknown data structure: {type(data)}")

def analyze_dict_structure(data):
    """Analyze dictionary-based chunk storage"""
    print(f"\nDictionary with {len(data)} keys:")
    
    # Common keys to look for
    important_keys = ['chunks', 'texts', 'documents', 'metadata', 'metadatas', 
                     'ids', 'embeddings', 'content', 'text']
    
    for key in data.keys():
        print(f"\n  Key: '{key}'")
        value = data[key]
        
        if isinstance(value, list):
            print(f"    Type: list, Length: {len(value)}")
            
            if len(value) > 0:
                print(f"    First item type: {type(value[0])}")
                
                # Analyze first few items
                print(f"\n    📋 SAMPLE ITEMS (first 3):")
                for i, item in enumerate(value[:3]):
                    print(f"\n    --- Item {i} ---")
                    
                    if isinstance(item, str):
                        print(f"    Length: {len(item)} characters")
                        print(f"    Content: '{item[:200]}'")
                        if len(item) < 5:
                            print(f"    ⚠️ WARNING: Very short chunk!")
                    
                    elif isinstance(item, dict):
                        print(f"    Keys: {list(item.keys())}")
                        for k, v in item.items():
                            if isinstance(v, str):
                                print(f"      {k}: '{v[:100]}{'...' if len(v) > 100 else ''}'")
                            else:
                                print(f"      {k}: {type(v)}")
                    else:
                        print(f"    Value: {str(item)[:200]}")
                
                # Statistics
                if isinstance(value[0], str):
                    lengths = [len(s) for s in value]
                    print(f"\n    📊 CHUNK LENGTH STATISTICS:")
                    print(f"    Min length: {min(lengths)}")
                    print(f"    Max length: {max(lengths)}")
                    print(f"    Average length: {sum(lengths)/len(lengths):.1f}")
                    print(f"    Chunks < 10 chars: {sum(1 for l in lengths if l < 10)}")
                    print(f"    Chunks < 50 chars: {sum(1 for l in lengths if l < 50)}")
                    
                    # Show problematic chunks
                    short_chunks = [(i, s) for i, s in enumerate(value) if len(s) < 10]
                    if short_chunks:
                        print(f"\n    ⚠️ PROBLEMATIC SHORT CHUNKS:")
                        for idx, chunk in short_chunks[:10]:
                            print(f"    Chunk {idx}: '{chunk}'")

def analyze_list_structure(data):
    """Analyze list-based chunk storage"""
    print(f"\nList with {len(data)} items")
    
    if len(data) == 0:
        print("  ⚠️ Empty list!")
        return
    
    print(f"First item type: {type(data[0])}")
    
    # Sample first items
    print(f"\n📋 SAMPLE ITEMS (first 5):")
    for i, item in enumerate(data[:5]):
        print(f"\n--- Item {i} ---")
        
        if isinstance(item, str):
            print(f"Length: {len(item)} characters")
            print(f"Content: '{item[:200]}'")
            if len(item) < 5:
                print(f"⚠️ WARNING: Very short chunk!")
        
        elif isinstance(item, dict):
            print(f"Keys: {list(item.keys())}")
            for k, v in item.items():
                if isinstance(v, str):
                    print(f"  {k}: '{v[:100]}{'...' if len(v) > 100 else ''}'")
                else:
                    print(f"  {k}: {type(v)}")
        else:
            print(f"Value: {str(item)[:200]}")
    
    # Statistics if string chunks
    if isinstance(data[0], str):
        lengths = [len(s) for s in data]
        print(f"\n📊 CHUNK LENGTH STATISTICS:")
        print(f"Min length: {min(lengths)}")
        print(f"Max length: {max(lengths)}")
        print(f"Average length: {sum(lengths)/len(lengths):.1f}")
        print(f"Chunks < 10 chars: {sum(1 for l in lengths if l < 10)}")
        print(f"Chunks < 50 chars: {sum(1 for l in lengths if l < 50)}")
        
        # Show problematic chunks
        short_chunks = [(i, s) for i, s in enumerate(data) if len(s) < 10]
        if short_chunks:
            print(f"\n⚠️ PROBLEMATIC SHORT CHUNKS:")
            for idx, chunk in short_chunks[:10]:
                print(f"Chunk {idx}: '{chunk}'")

def main():
    vectorstore_path = input("Enter vectorstore path (or press Enter for default): ").strip()
    
    if not vectorstore_path:
        vectorstore_path = r"C:\Users\n0308g\Git_Repos\pauth_rc\backend\app\rag_pipeline\vectorstore"
    
    index_name = input("Enter index name (default: mocked_insurance_policy): ").strip()
    if not index_name:
        index_name = "mocked_insurance_policy"
    
    analyze_chunks(vectorstore_path, index_name)

if __name__ == "__main__":
    main()