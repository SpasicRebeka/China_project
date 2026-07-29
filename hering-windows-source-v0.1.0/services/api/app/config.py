from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HERING_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    database_path: Path = Field(default=PROJECT_ROOT / "data" / "hering.db")
    static_root: Path = Field(default=API_ROOT / "static")
    knowledge_base_path: Path = Field(
        default=PROJECT_ROOT / "现病史追问知识库" / "knowledge_base.json"
    )
    session_ttl_minutes: int = 240
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://localhost:5174",
    )
