"""经营分析 API 包。

说明：
    当前只注册产销存经营分析问答入口，后续其他经营分析子域应继续挂在本包下。
"""

from backend.app.domains.business_analysis.api.router import router

__all__ = ["router"]
