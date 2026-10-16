#!/usr/bin/env python3
"""Drive a running Blender through the blender-mcp add-on's socket (127.0.0.1:9876).

Same protocol as Blender Lab's MCP server (blmcp): one request per connection,
{"type": "execute", "code": "...", "strict_json": false} + NUL  →  {"status": "ok"|"error", "result", "stdout", ...} + NUL.
Code runs in Blender's main thread; assign a dict to `result` to return data.

    python tools/blender_live.py info
    python tools/blender_live.py exec path/to/script.py [args]  # runs inside Blender (bpy available)

Scripts see `sys.argv = ['blender_live', *args]` and `HW_REPO`, this checkout's absolute path.
    python tools/blender_live.py screenshot out.png
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

HOST, PORT = "127.0.0.1", 9876
REPO = Path(__file__).resolve().parents[1]
NUL = bytes([0])


def execute(code: str, timeout: float = 3600.0) -> dict:
    with socket.create_connection((HOST, PORT), timeout=timeout) as s:
        s.sendall(json.dumps({"type": "execute", "code": code, "strict_json": False}).encode("utf-8") + NUL)
        buf = b""
        while NUL not in buf:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf.split(NUL, 1)[0].decode("utf-8"))


INFO = """
import bpy
result = {"version": bpy.app.version_string, "file": bpy.data.filepath, "scene": bpy.context.scene.name,
          "scenes": [s.name for s in bpy.data.scenes], "objects": len(bpy.context.scene.objects)}
"""

SCREENSHOT = """
import bpy
path = {path!r}
bpy.ops.screen.screenshot(filepath=path)
result = {{"saved": path}}
"""


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "info"
    if cmd == "info":
        r = execute(INFO)
    elif cmd == "exec":
        argv = sys.argv[3:]
        code = Path(sys.argv[2]).read_text(encoding="utf-8")
        r = execute(f"import sys\nsys.argv = ['blender_live'] + {argv!r}\nHW_REPO = {str(REPO)!r}\n" + code)
    elif cmd == "screenshot":
        r = execute(SCREENSHOT.format(path=str(Path(sys.argv[2]).resolve())))
    else:
        raise SystemExit(__doc__)
    print(json.dumps(r, indent=1)[:6000])


if __name__ == "__main__":
    main()
