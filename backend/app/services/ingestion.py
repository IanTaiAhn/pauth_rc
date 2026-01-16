# One Job: Turn Files into Text

# Why it exists
# This logic:
# grows fast
# changes often
# is painful to refactor later

# MVP implementation
import io

def extract_text(file_bytes: bytes) -> str:
    try:
        text = file_bytes.decode("utf-8")
        return text
    except UnicodeDecodeError:
        # Placeholder for PDF extraction later
        return ""

# This lets you:
# start with .txt uploads
# add PDF parsing later without touching your API or logic