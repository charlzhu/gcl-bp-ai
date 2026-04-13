from datetime import datetime, timezone

from backend.app.core.config import Settings
from backend.app.domains.logistics.constants import AVAILABLE_GROUP_FIELDS, AVAILABLE_METRICS
from backend.app.schemas.health import HealthData, SystemConfigData


class HealthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def check(self) -> HealthData:
        return HealthData(
            status="ok",
            app_name=self.settings.app_name,
            version=self.settings.app_version,
            env=self.settings.app_env,
            demo_mode=self.settings.demo_mode,
            checked_at=datetime.now(timezone.utc),
        )

    def system_config(self) -> SystemConfigData:
        return SystemConfigData(
            app_name=self.settings.app_name,
            version=self.settings.app_version,
            env=self.settings.app_env,
            demo_mode=self.settings.demo_mode,
            api_v1_prefix=self.settings.API_V1_PREFIX,
            storage_root=str(self.settings.file_storage_root),
            available_metrics=list(AVAILABLE_METRICS),
            available_group_fields=list(AVAILABLE_GROUP_FIELDS),
        )
