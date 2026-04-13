from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


class LogisticsTemplateLoader:
    """物流模板加载器（V5）。

    设计目标：
    1. 兼容 V3/V4 的单文件模板；
    2. 支持 V5 的“多域模板分层”；
    3. 让后续 BOM / 经营分析 / 物料管理 能共用同一套加载逻辑。

    当前默认目录结构：
    config/
      global/
        domain_keywords.yaml
      domains/
        logistics/query_templates.yaml
        plan_bom/query_templates.yaml
        business_analysis/query_templates.yaml
        material_management/query_templates.yaml

    如果多域结构不存在，则自动回退到旧版 query_templates.yaml。
    """

    def __init__(self, template_path: str | None = None, base_dir: str | None = None) -> None:
        default_base_dir = Path(__file__).resolve().parent.parent / 'config'
        self.base_dir = Path(base_dir) if base_dir else default_base_dir
        # 旧版兼容：如果调用方仍传单个模板文件，则优先使用该文件。
        self.template_path = Path(template_path) if template_path else self.base_dir / 'query_templates.yaml'

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding='utf-8')) or {}

    @staticmethod
    def _normalize_templates(items: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
        """统一给模板补上 domain 字段，便于后续做命中解释。"""
        result: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict) and item.get('id'):
                copied = dict(item)
                copied.setdefault('domain', domain)
                result.append(copied)
        return result

    def load(self, domain: str = 'logistics') -> list[dict[str, Any]]:
        """按指定业务域加载模板。

        - 如果存在 V5 多域目录，则优先走多域目录；
        - 否则回退到旧版单文件模板。
        """
        catalog = self.load_catalog()
        # 全局模板 + 当前域模板 共同组成候选集合。
        global_templates = catalog.get('global_templates', []) or []
        domain_templates = catalog.get('domains', {}).get(domain, []) or []
        if global_templates or domain_templates:
            return [*global_templates, *domain_templates]

        # 旧版兼容：只加载单个模板文件。
        data = self._read_yaml(self.template_path)
        return self._normalize_templates(data.get('templates', []) or [], domain='logistics')

    def load_catalog(self) -> dict[str, Any]:
        """加载整套模板目录，返回模板目录快照。"""
        domains_dir = self.base_dir / 'domains'
        if not domains_dir.exists():
            # 回退兼容。
            data = self._read_yaml(self.template_path)
            return {
                'global_templates': [],
                'domains': {
                    'logistics': self._normalize_templates(data.get('templates', []) or [], domain='logistics')
                },
            }

        catalog: dict[str, Any] = {
            'global_templates': [],
            'domains': {},
        }

        # 这里预留全局模板文件。如果后面真的有跨域通用模板，可以放在根目录。
        root_templates = self._read_yaml(self.base_dir / 'query_templates.yaml').get('templates', []) or []
        catalog['global_templates'] = self._normalize_templates(root_templates, domain='global')

        for domain_dir in sorted(domains_dir.iterdir()):
            if not domain_dir.is_dir():
                continue
            template_path = domain_dir / 'query_templates.yaml'
            data = self._read_yaml(template_path)
            catalog['domains'][domain_dir.name] = self._normalize_templates(
                data.get('templates', []) or [],
                domain=domain_dir.name,
            )
        return catalog

    def list_config_files(self) -> list[Path]:
        """列出模板相关配置文件，供热更新监测使用。"""
        files: list[Path] = []
        if self.template_path.exists():
            files.append(self.template_path)
        if self.base_dir.exists():
            for path in self.base_dir.rglob('*.yaml'):
                files.append(path)
        # 去重 + 排序，保证版本计算稳定。
        uniq = sorted({p.resolve() for p in files})
        return uniq


@lru_cache(maxsize=4)
def get_default_template_loader(template_path: str | None = None, base_dir: str | None = None) -> LogisticsTemplateLoader:
    """获取默认的物流模板加载器。"""
    return LogisticsTemplateLoader(template_path=template_path, base_dir=base_dir)
