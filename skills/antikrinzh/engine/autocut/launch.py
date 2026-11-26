# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
"""Start GRIN Reels: its own app window (Mac/Windows), or the browser as a fallback.

The phone keeps working too: the same page is served on the Wi-Fi address,
so iPhone → Safari → Share → «На экран Домой» gives a full-screen app icon.
"""
from .paths import app_root
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from .server import local_ip

PORT = 8765
ROOT = app_root()


def _serve() -> uvicorn.Server:
    from .server import app  # object, not an import string: works inside the packaged app too
    srv = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, workers=1, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(100):  # wait until it answers
        if srv.started:
            break
        time.sleep(0.1)
    return srv


def _mac_icon() -> None:
    try:
        from AppKit import NSApplication, NSImage
        img = NSImage.alloc().initWithContentsOfFile_(str(ROOT / "web" / "icon.png"))
        NSApplication.sharedApplication().setApplicationIconImage_(img)
    except Exception:
        pass


def main() -> None:
    ip = local_ip()
    print("\n  GRIN Reels запущен.")
    print(f"  С телефона (та же Wi-Fi сеть):  http://{ip}:{PORT}\n")
    srv = _serve()
    url = f"http://localhost:{PORT}"
    if "--browser" not in sys.argv:
        try:
            import webview  # pywebview: a real window, no browser bar
            if sys.platform == "darwin":
                _mac_icon()
            try:
                webview.settings["ALLOW_DOWNLOADS"] = True
            except Exception:
                pass
            webview.create_window("GRIN Reels", url, width=1240, height=880, min_size=(420, 640),
                                  background_color="#E6E5E0", text_select=True)
            webview.start()
            srv.should_exit = True
            return
        except Exception as e:  # no window toolkit -> browser
            print("  (окно приложения не открылось, открываю браузер:", e, ")")
    webbrowser.open(url)
    print("  Не закрывай это окно, пока монтируешь.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.should_exit = True


if __name__ == "__main__":
    main()
