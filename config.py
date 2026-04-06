import os
from dotenv import load_dotenv

load_dotenv(override=True)


def _normalize_database_url(raw_url):
    if not raw_url:
        return "sqlite:///career_success_tracker.db"
    if raw_url.startswith("mysql://"):
        return raw_url.replace("mysql://", "mysql+pymysql://", 1)
    return raw_url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(
        os.getenv(
            "DATABASE_URL",
            "sqlite:///career_success_tracker.db",
        )
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTO_INIT_DB = os.getenv("AUTO_INIT_DB", "true").lower() in {"1", "true", "yes", "on"}

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join("static", "uploads")
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
    ALLOWED_DOC_EXTENSIONS = {"pdf"}
