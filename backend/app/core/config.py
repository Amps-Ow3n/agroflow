import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() == "true"


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://agroflow-frontend-sigma.vercel.app").split(",") if x.strip()]
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
    ENABLE_AUDIT_LOGS = _bool("ENABLE_AUDIT_LOGS", True)
    ENABLE_DECISION_LOGS = _bool("ENABLE_DECISION_LOGS", True)
    EVIDENCE_STORAGE_DIR = os.getenv("EVIDENCE_STORAGE_DIR", "storage/evidence")
    MAX_EVIDENCE_FILE_SIZE = int(os.getenv("MAX_EVIDENCE_FILE_SIZE", str(10 * 1024 * 1024)))
    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "agroflow_access_token")
    CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "agroflow_csrf")
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "none")
    SESSION_COOKIE_SECURE = _bool(
    "SESSION_COOKIE_SECURE",
    ENVIRONMENT == "production"
)
    SESSION_COOKIE_MAX_AGE = int(
    os.getenv("SESSION_COOKIE_MAX_AGE", str(30 * 60))
)
    RATE_LIMIT_LOGIN_MAX = int(os.getenv("RATE_LIMIT_LOGIN_MAX", "10"))
    RATE_LIMIT_LOGIN_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_LOGIN_WINDOW_SECONDS", "300"))
    RATE_LIMIT_REGISTER_MAX = int(os.getenv("RATE_LIMIT_REGISTER_MAX", "5"))
    RATE_LIMIT_REGISTER_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_REGISTER_WINDOW_SECONDS", "900"))
    PRIVACY_CONTACT_EMAIL = os.getenv("PRIVACY_CONTACT_EMAIL", "privacy@example.com")
    PRIVACY_POLICY_VERSION = os.getenv("PRIVACY_POLICY_VERSION", "2026-09-11")

    def validate(self):
        if not self.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is required.")
        if not self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
            raise RuntimeError("JWT_SECRET_KEY must be configured with at least 32 characters.")
        if self.ENVIRONMENT == "production":
            if not self.CORS_ORIGINS or any(x == "*" for x in self.CORS_ORIGINS):
                raise RuntimeError("Production CORS_ORIGINS must explicitly list trusted origins.")
            if self.SESSION_COOKIE_SAMESITE == "none":
                # Secure cookies are enforced by the auth route in production.
                pass


settings = Settings()
