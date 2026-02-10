import os

class Settings:
    ENV = os.getenv("ENV", "dev")
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
    ALLOWED_FILE_TYPES = {"application/pdf", "text/plain"}

settings = Settings()

# Why it exists

# You do not want:
# API keys hardcoded in service files
# environment toggles scattered everywhere
# MVP-appropriate contents

# That’s it.
# No Pydantic. No dotenv magic unless you want it.

# Later:
# swap in pydantic-settings
# add logging levels
# add feature flags