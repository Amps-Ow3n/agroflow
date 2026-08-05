import os
from dotenv import load_dotenv

load_dotenv()


class Settings:

    DATABASE_URL = os.getenv("DATABASE_URL")

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    JWT_ALGORITHM = os.getenv(
        "JWT_ALGORITHM",
        "HS256"
    )

    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "60"
        )
    )

    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")

    ENVIRONMENT = os.getenv(
        "ENVIRONMENT",
        "development"
    )

    ENABLE_AUDIT_LOGS = (
        os.getenv(
            "ENABLE_AUDIT_LOGS",
            "true"
        ).lower() == "true"
    )

    ENABLE_DECISION_LOGS = (
        os.getenv(
            "ENABLE_DECISION_LOGS",
            "true"
        ).lower() == "true"
    )


settings = Settings()