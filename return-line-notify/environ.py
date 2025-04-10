from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environ(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    works_id: str = Field(alias="WORKS_ID")
    password: str = Field(alias="PASSWORD")

    log_path: Path = Field(
        default=Path(".log/debug.log"),
        alias="LOG_PATH",
    )

    def __init__(self):
        super().__init__()
