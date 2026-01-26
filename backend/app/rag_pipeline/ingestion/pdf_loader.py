import pdfplumber
from pathlib import Path

def load_pdf_text(path: str) -> str:
    text_chunks = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_chunks.append(text)
    return "\n\n".join(text_chunks)


if __name__ == "__main__":
    p = Path(__file__).parent.parent / "data" / "raw_docs"
    for f in p.glob("*.pdf"):
        print("Loading:", f)
        txt = load_pdf_text(str(f))
        out = f.with_suffix('.txt')
        out.write_text(txt)
        print("Wrote:", out)