from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ai_provider: str = "groq"
    groq_api_key: str = ""
    model_name: str = "llama-3.3-70b-versatile"
    database_url: str = "sqlite:///./ps22.db"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
