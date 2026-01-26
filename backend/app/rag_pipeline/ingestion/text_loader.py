from pathlib import Path

def load_text_file(path: Path) -> str:
    print('path of question: ', type(path))
    return path.read_text(encoding="utf-8", errors="ignore")

if __name__ == "__main__":
    p = Path(__file__).parent.parent / "data" / "raw_docs"
    for f in p.glob("*.txt"):
        print(f, len(load_text_file(f)))
