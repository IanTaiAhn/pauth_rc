# Shared Text Utilities
# Why it exists
# Without this file:
# regexes end up duplicated
# text cleanup becomes inconsistent

# MVP-level helpers
import re

def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# Now every detection function can rely on normalized input.