"""
Inspect metadata pickle and FAISS index structure
"""

import pickle
import faiss
from pathlib import Path
import json

def inspect_metadata_file(pkl_path):
    """Deep inspection of the metadata pickle file"""
    print(f"\n{'='*80}")
    print(f"INSPECTING: {pkl_path}")
    print('='*80)
    
    try:
        with open(pkl_path, 'rb') as f:
            metadata = pickle.load(f)
        
        print(f"\nLoaded successfully!")
        print(f"Data type: {type(metadata)}")
        
        if isinstance(metadata, dict):
            print(f"\n📋 Dictionary Keys: {list(metadata.keys())}")
            
            for key, value in metadata.items():
                print(f"\n{'─'*60}")
                print(f"KEY: '{key}'")
                print(f"Type: {type(value)}")
                
                if isinstance(value, list):
                    print(f"Length: {len(value)}")
                    
                    if len(value) > 0:
                        print(f"First item type: {type(value[0])}")
                        
                        # Show first 5 items in detail
                        print(f"\n🔍 First 5 items:")
                        for i, item in enumerate(value[:5]):
                            print(f"\n  [{i}]:")
                            if isinstance(item, dict):
                                print(f"    Keys: {list(item.keys())}")
                                for k, v in item.items():
                                    if isinstance(v, str):
                                        display_text = v[:150] + ('...' if len(v) > 150 else '')
                                        print(f"    {k}: '{display_text}'")
                                    else:
                                        print(f"    {k}: {type(v)} = {str(v)[:100]}")
                            elif isinstance(item, str):
                                print(f"    Text ({len(item)} chars): '{item[:200]}'")
                                if len(item) < 5:
                                    print(f"    ⚠️ VERY SHORT!")
                            else:
                                print(f"    {str(item)[:200]}")
                        
                        # Statistics for string lists
                        if isinstance(value[0], str):
                            lengths = [len(s) for s in value]
                            print(f"\n📊 CHUNK LENGTH STATISTICS:")
                            print(f"  Total chunks: {len(value)}")
                            print(f"  Min length: {min(lengths)}")
                            print(f"  Max length: {max(lengths)}")
                            print(f"  Average length: {sum(lengths)/len(lengths):.1f}")
                            print(f"  Median length: {sorted(lengths)[len(lengths)//2]}")
                            
                            # Count problematic chunks
                            very_short = sum(1 for l in lengths if l < 5)
                            short = sum(1 for l in lengths if l < 50)
                            
                            print(f"\n⚠️ PROBLEM DETECTION:")
                            print(f"  Chunks < 5 chars: {very_short} ({very_short/len(value)*100:.1f}%)")
                            print(f"  Chunks < 50 chars: {short} ({short/len(value)*100:.1f}%)")
                            
                            if very_short > 0:
                                print(f"\n🔴 SHOWING ALL CHUNKS < 5 CHARACTERS:")
                                for i, s in enumerate(value):
                                    if len(s) < 5:
                                        print(f"    Index {i}: '{s}' (length={len(s)})")
                                        if i > 20:  # Limit output
                                            print(f"    ... and {very_short - i - 1} more")
                                            break
                        
                        # Statistics for dict lists (metadata)
                        elif isinstance(value[0], dict):
                            print(f"\n📊 METADATA STATISTICS:")
                            print(f"  Total metadata items: {len(value)}")
                            
                            # Analyze common keys
                            all_keys = set()
                            for item in value:
                                if isinstance(item, dict):
                                    all_keys.update(item.keys())
                            
                            print(f"  Common keys across all items: {list(all_keys)}")
                            
                            # Check for 'text' or 'content' fields
                            if any('text' in item or 'content' in item for item in value if isinstance(item, dict)):
                                print(f"\n🔍 Checking text/content in metadata:")
                                for i, item in enumerate(value[:5]):
                                    if isinstance(item, dict):
                                        text = item.get('text') or item.get('content', '')
                                        if text:
                                            print(f"    Item {i} text length: {len(text)}")
                                            print(f"    Preview: '{text[:100]}'")
                
                elif isinstance(value, str):
                    print(f"String length: {len(value)}")
                    print(f"Preview: {value[:200]}")
                
                else:
                    print(f"Value: {str(value)[:200]}")
        
        elif isinstance(metadata, list):
            print(f"\nList with {len(metadata)} items")
            analyze_list_items(metadata)
        
        else:
            print(f"\nUnexpected data structure: {type(metadata)}")
            print(f"Content: {str(metadata)[:500]}")
        
        return metadata
        
    except Exception as e:
        print(f"\n❌ Error loading file: {e}")
        import traceback
        traceback.print_exc()
        return None

def analyze_list_items(items):
    """Analyze items in a list"""
    if len(items) == 0:
        print("Empty list!")
        return
    
    print(f"First item type: {type(items[0])}")
    
    print(f"\n🔍 First 5 items:")
    for i, item in enumerate(items[:5]):
        print(f"\n[{i}]:")
        if isinstance(item, dict):
            print(f"  Keys: {list(item.keys())}")
            for k, v in item.items():
                if isinstance(v, str):
                    display = v[:100] + ('...' if len(v) > 100 else '')
                    print(f"  {k}: '{display}'")
                else:
                    print(f"  {k}: {type(v)}")
        elif isinstance(item, str):
            print(f"  Text ({len(item)} chars): '{item[:150]}'")
        else:
            print(f"  {str(item)[:200]}")

def find_faiss_index(vectorstore_path, index_name):
    """Find and inspect FAISS index file"""
    vectorstore_path = Path(vectorstore_path)
    
    # Possible FAISS file locations
    possible_paths = [
        vectorstore_path / f"{index_name}.faiss",
        vectorstore_path / index_name / "index.faiss",
        vectorstore_path / "index.faiss",
    ]
    
    # Also search for any .faiss files
    all_faiss = list(vectorstore_path.glob("**/*.faiss"))
    
    print(f"\n{'='*80}")
    print(f"SEARCHING FOR FAISS INDEX")
    print('='*80)
    
    for path in possible_paths:
        if path.exists():
            print(f"\n✓ Found at expected location: {path}")
            inspect_faiss(path)
            return path
    
    if all_faiss:
        print(f"\nFound {len(all_faiss)} FAISS files:")
        for f in all_faiss:
            print(f"\n✓ {f}")
            inspect_faiss(f)
        return all_faiss[0]
    else:
        print("\n⚠️ No FAISS index files found!")
        return None

def inspect_faiss(faiss_path):
    """Inspect FAISS index"""
    try:
        index = faiss.read_index(str(faiss_path))
        print(f"\n  Index type: {type(index)}")
        print(f"  Total vectors: {index.ntotal}")
        print(f"  Dimension: {index.d}")
        print(f"  Is trained: {index.is_trained}")
        
        return index
    except Exception as e:
        print(f"\n  ❌ Error loading FAISS index: {e}")
        return None

def main():
    print("="*80)
    print("VECTORSTORE FORENSICS")
    print("="*80)
    
    vectorstore_path = input("\nEnter vectorstore path (or press Enter for default): ").strip()
    if not vectorstore_path:
        vectorstore_path = r"C:\Users\n0308g\Git_Repos\pauth_rc\backend\app\rag_pipeline\vectorstore"
    
    index_name = input("Enter index name (default: mocked_insurance_policy): ").strip()
    if not index_name:
        index_name = "mocked_insurance_policy"
    
    print(f"\nSearching in: {vectorstore_path}")
    print(f"Index name: {index_name}")
    
    # Find the metadata file
    meta_file = Path(vectorstore_path) / f"{index_name}_meta.pkl"
    
    if meta_file.exists():
        metadata = inspect_metadata_file(meta_file)
    else:
        print(f"\n⚠️ Metadata file not found at: {meta_file}")
        print("\nSearching for any pickle files...")
        all_pkl = list(Path(vectorstore_path).glob("**/*.pkl"))
        if all_pkl:
            print(f"\nFound {len(all_pkl)} pickle files:")
            for pkl in all_pkl:
                print(f"\n{pkl}")
                inspect_metadata_file(pkl)
    
    # Find FAISS index
    faiss_idx = find_faiss_index(vectorstore_path, index_name)
    
    print(f"\n{'='*80}")
    print("FORENSICS COMPLETE")
    print('='*80)
    
    # Summary
    if meta_file.exists() and faiss_idx:
        print("\n✅ Both metadata and FAISS index found")
        print("\n🔍 KEY FINDINGS:")
        print("Check above for:")
        print("  - Chunk lengths (should be 200-1000+ chars typically)")
        print("  - Any chunks that are just 1-2 characters")
        print("  - Whether 'text' is stored in metadata vs separate")
    else:
        print("\n⚠️ Missing files - check your ingestion pipeline")

if __name__ == "__main__":
    main()