"""
Vector Store Inspector (FILE OUTPUT — NO TRUNCATION)
Dumps COMPLETE contents of FAISS indices and pickle files to disk
"""

import pickle
import faiss
import numpy as np
from pathlib import Path
import json
import sys

np.set_printoptions(threshold=np.inf)
sys.setrecursionlimit(10000)


# ---------- Helpers ----------

def make_serializable(obj):
    """Recursively convert EVERYTHING to JSON-serializable WITHOUT truncation"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()

    elif isinstance(obj, (list, tuple)):
        return [make_serializable(item) for item in obj]

    elif isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}

    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj

    else:
        return str(obj)


# ---------- Pickle Inspector ----------

def inspect_pickle_file(pickle_path, output_dir):
    print(f"Processing pickle: {pickle_path.name}")

    try:
        with open(pickle_path, 'rb') as f:
            data = pickle.load(f)

        base_name = pickle_path.stem

        # 1️⃣ Save full JSON
        json_path = output_dir / f"{base_name}_FULL.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(make_serializable(data), f, indent=2, ensure_ascii=False)

        # 2️⃣ Save readable TXT dump
        txt_path = output_dir / f"{base_name}_FULL.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"FULL INSPECTION OF: {pickle_path}\n")
            f.write("=" * 80 + "\n\n")
            f.write(repr(data))

        print(f"  → Saved JSON + TXT")

    except Exception as e:
        print(f"  ⚠ Error reading pickle: {e}")


# ---------- FAISS Inspector ----------

def inspect_faiss_index(faiss_path, output_dir):
    print(f"Processing FAISS index: {faiss_path.name}")

    try:
        index = faiss.read_index(str(faiss_path))
        base_name = faiss_path.stem

        # Save index metadata
        meta_path = output_dir / f"{base_name}_faiss_info.txt"
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(f"FAISS INDEX REPORT: {faiss_path}\n")
            f.write("=" * 80 + "\n")
            f.write(f"Type: {type(index)}\n")
            f.write(f"Total vectors: {index.ntotal}\n")
            f.write(f"Dimension: {index.d}\n")
            f.write(f"Is trained: {index.is_trained}\n")

        # Reconstruct ALL vectors and save as numpy file
        if index.ntotal > 0:
            vectors = np.zeros((index.ntotal, index.d), dtype=np.float32)
            for i in range(index.ntotal):
                index.reconstruct(i, vectors[i])

            vec_path = output_dir / f"{base_name}_vectors_FULL.npy"
            np.save(vec_path, vectors)

            print(f"  → Saved vectors ({index.ntotal})")

    except Exception as e:
        print(f"  ⚠ Error reading FAISS index: {e}")


# ---------- File Discovery ----------

def find_vectorstore_files(base_path):
    base_path = Path(base_path)
    faiss_files = list(base_path.glob("**/*.faiss"))
    pkl_files = list(base_path.glob("**/*.pkl"))
    return faiss_files, pkl_files


# ---------- Main ----------

def main():
    vectorstore_path = input(
        "Enter vectorstore directory (Enter for default): "
    ).strip()

    if not vectorstore_path:
        vectorstore_path = r"C:\Users\n0308g\Git_Repos\pauth_rc\backend\app\rag_pipeline\vectorstore"

    base_path = Path(vectorstore_path)
    output_dir = base_path / "VECTORSTORE_FULL_DUMP"
    output_dir.mkdir(exist_ok=True)

    print(f"\nDumping FULL vectorstore contents to: {output_dir}\n")

    faiss_files, pkl_files = find_vectorstore_files(base_path)

    print(f"Found {len(faiss_files)} FAISS files")
    print(f"Found {len(pkl_files)} pickle files\n")

    for pkl_file in pkl_files:
        inspect_pickle_file(pkl_file, output_dir)

    for faiss_file in faiss_files:
        inspect_faiss_index(faiss_file, output_dir)

    print("\n" + "=" * 80)
    print(" FULL VECTORSTORE DUMP COMPLETE ")
    print("=" * 80)


if __name__ == "__main__":
    main()
