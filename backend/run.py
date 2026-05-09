import sys

import uvicorn

from backend.app.core.config import settings


if __name__ == "__main__":
    # IDE 调试器附加时若继续开启 uvicorn reload，会派生 reloader/worker 两个进程，
    # PyCharm/VSCode 等调试器会分别输出 Connected to socket 提示；调试态关闭 reload，普通运行仍按 APP_DEBUG 热重载。
    debugger_attached = sys.gettrace() is not None
    reload_enabled = bool(settings.APP_DEBUG and not debugger_attached)
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=reload_enabled,
    )
