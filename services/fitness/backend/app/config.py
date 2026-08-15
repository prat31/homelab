from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    fitness_data_dir: Path = Path("/data")
    fitness_tz: str = "Asia/Kolkata"
    fitness_api_key: str = ""
    fitness_domain: str = "fitness.homelab.pratcode.dev"
    public_fitness_domain: str = "hl-fitness.pratcode.dev"
    drive_folder_id: str = ""
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_refresh_token: str = ""
    google_service_account_json: str = ""
    drive_poll_hour: int = 6
    source_priority: str = (
        "com.garmin.android.apps.connectmobile,"
        "com.google.android.apps.fitness,"
        "com.sec.android.app.shealth"
    )

    @property
    def warehouse_path(self) -> Path:
        return self.fitness_data_dir / "fitness.db"

    @property
    def exports_dir(self) -> Path:
        return self.fitness_data_dir / "exports"

    @property
    def priority_packages(self) -> list[str]:
        return [item.strip() for item in self.source_priority.split(",") if item.strip()]


def get_settings() -> Settings:
    return Settings()
