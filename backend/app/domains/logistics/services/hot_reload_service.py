from __future__ import annotations

from typing import Any

from backend.app.domains.logistics.services.config_watcher import LogisticsConfigWatcher
from backend.app.domains.logistics.services.template_loader import LogisticsTemplateLoader
from backend.app.domains.logistics.services.version_manager import LogisticsConfigVersionManager, LogisticsConfigVersionSnapshot


class LogisticsHotReloadService:
    """模板与字典配置热更新服务（V6）。

    当前策略：
    - 每次请求前快速检查配置文件快照；
    - 如果文件修改时间发生变化，则重新加载模板目录；
    - 如果没有变化，则直接复用内存中的上一次结果；
    - 在 V6 中新增版本快照细节，便于解释“当前到底生效的是哪一套配置”。
    """

    def __init__(self, template_loader: LogisticsTemplateLoader) -> None:
        self.template_loader = template_loader
        self.watcher = LogisticsConfigWatcher()
        self.version_manager = LogisticsConfigVersionManager()
        self._snapshot: dict[str, int] = {}
        self._version: str = 'not-loaded'
        self._version_detail: LogisticsConfigVersionSnapshot | None = None
        self._catalog: dict[str, Any] = {'global_templates': [], 'domains': {}}

    def get_catalog(self) -> dict[str, Any]:
        """获取最新模板目录；如果发现配置有变化，则自动重载。"""
        files = self.template_loader.list_config_files()
        snapshot = self.watcher.build_snapshot(files)
        if self.watcher.has_changed(self._snapshot, snapshot):
            self._catalog = self.template_loader.load_catalog()
            self._snapshot = snapshot
            self._version = self.watcher.build_version(snapshot)
            self._version_detail = self.version_manager.build_snapshot(self._version, files)
        return self._catalog

    def get_version(self) -> str:
        """获取当前生效的配置版本号。"""
        if self._version == 'not-loaded':
            self.get_catalog()
        return self._version

    def get_version_detail(self) -> dict[str, Any]:
        """获取配置版本详细信息。"""
        if self._version_detail is None:
            self.get_catalog()
        detail = self._version_detail
        if detail is None:
            return {'version': self.get_version(), 'file_count': 0, 'files': []}
        return {
            'version': detail.version,
            'file_count': detail.file_count,
            'files': detail.files,
        }
