"""Application settings loaded from environment variables.

This module centralizes configuration and ensures that all required
environment variables are validated at startup.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Typed application configuration loaded from the environment."""

    api_id: int = Field(..., alias="API_ID")
    api_hash: str = Field(..., alias="API_HASH")
    tg_session: str = Field("pf_session", alias="TG_SESSION")
    
    # Storage configuration
    sheet_id: str | None = Field(None, alias="SHEET_ID")
    credentials_path: str | None = Field(None, alias="GOOGLE_CREDENTIALS_PATH")
    excel_path: str | None = Field(None, alias="EXCEL_PATH")
    
    # Storage backend enablement
    enable_excel: bool = Field(False, alias="ENABLE_EXCEL")
    enable_sheets: bool = Field(False, alias="ENABLE_SHEETS")

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
        "populate_by_name": True
    }


settings = Settings()
