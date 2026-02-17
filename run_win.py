"""
Run backend on Windows with ProactorEventLoop to avoid asyncio socket errors.

When using `uvicorn --reload` on Windows, uvicorn forces SelectorEventLoop, which
can trigger "Data should not be empty" and WinError 10038 when clients disconnect
during video streaming (e.g. user swipes clips, navigates away).

This script uses ProactorEventLoop instead, avoiding those errors.
Run: python run_win.py
"""
import asyncio
import os
import sys

if __name__ == "__main__":
    if sys.platform != "win32":
        print("run_win.py is for Windows only. Use: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
        sys.exit(1)

    # Use ProactorEventLoop to avoid SelectorEventLoop bugs with client disconnect during streaming
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Prevent uvicorn from overriding back to SelectorEventLoop when we pass reload
    import uvicorn.loops.asyncio as uv_asyncio
    _orig = uv_asyncio.asyncio_setup

    def _no_override(use_subprocess: bool = False) -> None:
        # Keep our ProactorEventLoop policy
        pass

    uv_asyncio.asyncio_setup = _no_override

    import uvicorn

    use_reload = os.environ.get("UVICORN_RELOAD", "0") == "1"  # TEMP: 0 for debug - reload subprocess may block requests on Windows
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("UVICORN_HOST", "0.0.0.0"),
        port=int(os.environ.get("UVICORN_PORT", "8000")),
        reload=use_reload,
    )
