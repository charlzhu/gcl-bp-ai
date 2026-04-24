"""ORM 模型注册包。

说明：
1. 这里集中导入需要挂到 Base.metadata 的模型；
2. 计划 BOM 模型已用于 ORM 映射和 Alembic 迁移元数据，不属于可删除的过渡代码。
"""

from backend.app.domains.plan_bom.models import (
    PlanBomExportFile,
    PlanBomExportTask,
    PlanBomHeader,
    PlanBomImportBatch,
    PlanBomMaterialLine,
    PlanBomRevision,
)
from backend.app.models.sys_query_log import SysQueryLog
from backend.app.models.sys_task_error_log import SysTaskErrorLog
from backend.app.models.sys_task_log import SysTaskLog

__all__ = [
    "SysQueryLog",
    "SysTaskLog",
    "SysTaskErrorLog",
    "PlanBomImportBatch",
    "PlanBomHeader",
    "PlanBomMaterialLine",
    "PlanBomRevision",
    "PlanBomExportTask",
    "PlanBomExportFile",
]
