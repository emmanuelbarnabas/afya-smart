"""
Application settings loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "Afya Smart API"
    environment: str = "development"

    # Database (PostgreSQL kwa dev/prod; SQLite ni fallback ya local dev bila docker)
    database_url: str = "sqlite:///./afyasmart.db"

    # CORS (dashboard origin)
    cors_origins: list[str] = ["http://localhost:5173"]

    # Africa's Talking
    at_username: str = "sandbox"
    at_api_key: str = ""
    at_phone_number: str = ""
    ussd_service_code: str = "*384*123#"

    # ML
    triage_model_path: str = "ml/artifacts/triage_model.joblib"
    demand_model_path: str = "ml/artifacts/demand_forecast.joblib"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
