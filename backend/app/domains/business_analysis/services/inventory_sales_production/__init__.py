"""产销存服务包。

说明：
    子模块之间存在 parser -> repository -> import_service 的分层依赖，
    因此包初始化不预导入具体类，避免循环导入。
"""

__all__ = []
