import os
from dotenv import load_dotenv

load_dotenv()


def load_config():
    cors_origins = os.getenv("CORS_ORIGINS", "")
    origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
    return {
        "APP_PORT": int(os.getenv("APP_PORT", 5001)),
        "JWT_SECRET": os.getenv("JWT_SECRET", "secret"),
        "CORS_ORIGINS": origins,
    }
