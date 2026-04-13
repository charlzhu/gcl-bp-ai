from datetime import datetime

from pydantic import BaseModel


class HealthData(BaseModel):
    status: str
    app_name: str
    version: str
    env: str
    demo_mode: bool
    checked_at: datetime


class SystemConfigData(BaseModel):
    app_name: str
    version: str
    env: str
    demo_mode: bool
    api_v1_prefix: str
    storage_root: str
    available_metrics: list[str]
    available_group_fields: list[str]
