"""
Vector Store Inspector
Loads and displays contents of FAISS indices and associated pickle files
"""

import pickle
import faiss
import numpy as np
from pathlib import Path
import json

def inspect_pickle_file(pickle_path):
    """Load and inspect a pickle file"""
    print(f"\n{'='*80}")
    print(f"INSPECTING PICKLE FILE: {pickle_path}")
    print('='*80)
    
    try:
        with open(pickle_path, 'rb') as f:
            data = pickle.load(f)
        
        print(f"\nData Type: {type(data)}")
        
        # Handle different data structures
        if isinstance(data, dict):
            print(f"\nDictionary Keys: {list(data.keys())}")
            for key, value in data.items():
                print(f"\n--- Key: {key} ---")
                if isinstance(value, list):
                    print(f"  Type: list, Length: {len(value)}")
                    if len(value) > 0:
                        print(f"  First item type: {type(value[0])}")
                        print(f"  First 3 items: {value[:3]}")
                elif isinstance(value, np.ndarray):
                    print(f"  Type: numpy array, Shape: {value.shape}")
                elif isinstance(value, str):
                    print(f"  Type: string, Length: {len(value)}")
                    print(f"  Content preview: {value[:200]}...")
                else:
                    print(f"  Type: {type(value)}")
                    print(f"  Content: {str(value)[:200]}")
        
        elif isinstance(data, list):
            print(f"\nList Length: {len(data)}")
            if len(data) > 0:
                print(f"First item type: {type(data[0])}")
                print("\n--- First 5 Items ---")
                for i, item in enumerate(data[:5]):
                    print(f"\nItem {i}:")
                    if isinstance(item, dict):
                        print(f"  Keys: {list(item.keys())}")
                        for k, v in item.items():
                            if isinstance(v, str):
                                print(f"  {k}: {v[:100]}{'...' if len(v) > 100 else ''}")
                            else:
                                print(f"  {k}: {type(v)} - {str(v)[:100]}")
                    elif isinstance(item, str):
                        print(f"  Text: {item[:200]}...")
                    else:
                        print(f"  {item}")
        
        return data
        
    except Exception as e:
        print(f"Error loading pickle file: {e}")
        return None

def inspect_faiss_index(faiss_path):
    """Load and inspect a FAISS index"""
    print(f"\n{'='*80}")
    print(f"INSPECTING FAISS INDEX: {faiss_path}")
    print('='*80)
    
    try:
        index = faiss.read_index(str(faiss_path))
        
        print(f"\nIndex Type: {type(index)}")
        print(f"Total Vectors: {index.ntotal}")
        print(f"Vector Dimension: {index.d}")
        print(f"Is Trained: {index.is_trained}")
        
        # Try to get some sample vectors
        if index.ntotal > 0:
            print(f"\n--- Sample Vector Statistics ---")
            # Reconstruct first few vectors if possible
            try:
                n_samples = min(5, index.ntotal)
                vectors = np.zeros((n_samples, index.d), dtype=np.float32)
                for i in range(n_samples):
                    index.reconstruct(i, vectors[i])
                
                print(f"First {n_samples} vector norms:")
                for i, vec in enumerate(vectors):
                    norm = np.linalg.norm(vec)
                    print(f"  Vector {i}: norm = {norm:.4f}, non-zero elements = {np.count_nonzero(vec)}")
            except Exception as e:
                print(f"Cannot reconstruct vectors: {e}")
        
        return index
        
    except Exception as e:
        print(f"Error loading FAISS index: {e}")
        return None

def find_vectorstore_files(base_path):
    """Find all .faiss and .pkl files in the directory"""
    base_path = Path(base_path)
    
    faiss_files = list(base_path.glob("**/*.faiss"))
    pkl_files = list(base_path.glob("**/*.pkl"))
    
    return faiss_files, pkl_files

def main():
    # Update this path to your vectorstore directory
    vectorstore_path = input("Enter the path to your vectorstore directory (or press Enter for default): ").strip()
    
    if not vectorstore_path:
        # Default from your log
        vectorstore_path = r"C:\Users\n0308g\Git_Repos\pauth_rc\backend\app\rag_pipeline\vectorstore"
    
    print(f"\nSearching for vector store files in: {vectorstore_path}")
    
    faiss_files, pkl_files = find_vectorstore_files(vectorstore_path)
    
    print(f"\nFound {len(faiss_files)} FAISS files and {len(pkl_files)} pickle files")
    
    # Inspect all pickle files
    for pkl_file in pkl_files:
        data = inspect_pickle_file(pkl_file)
        
        # Save detailed output to JSON for analysis
        output_file = Path(f"pickle_inspection_{pkl_file.stem}.json")
        try:
            if isinstance(data, (dict, list)):
                # Convert to serializable format
                def make_serializable(obj):
                    if isinstance(obj, np.ndarray):
                        return f"<numpy array: shape={obj.shape}, dtype={obj.dtype}>"
                    elif isinstance(obj, (list, tuple)):
                        return [make_serializable(item) for item in obj[:100]]  # Limit to first 100 items
                    elif isinstance(obj, dict):
                        return {k: make_serializable(v) for k, v in obj.items()}
                    else:
                        return obj
                
                serializable_data = make_serializable(data)
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(serializable_data, f, indent=2, ensure_ascii=False)
                print(f"\n✓ Detailed output saved to: {output_file}")
        except Exception as e:
            print(f"\n⚠ Could not save to JSON: {e}")
    
    # Inspect all FAISS indices
    for faiss_file in faiss_files:
        inspect_faiss_index(faiss_file)
    
    print("\n" + "="*80)
    print("INSPECTION COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()