#!/usr/bin/env python3
"""Query the JLC/LCSC parts library through the `@jlcpcb/mcp` MCP server.

    python tools/jlc_mcp.py "S2P-VH" "SMBJ33A" --limit 5

Runs the server in Docker (node:22-alpine) over stdio, so no local Node is
needed.  Prints LCSC id, MPN, package, stock, price and basic/extended.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

CMD = ["docker", "run", "-i", "--rm", "node:22-alpine", "npx", "-y", "@jlcpcb/mcp@0.5.0"]


class Mcp:
    def __init__(self):
        self.p = subprocess.Popen(CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, encoding="utf-8", bufsize=1)
        self.n = 0
        self.call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "hw-testing-rack", "version": "0"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, msg):
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()

    def call(self, method, params):
        self.n += 1
        self._send({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("MCP server exited")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    def tool(self, name, args):
        res = self.call("tools/call", {"name": name, "arguments": args})
        texts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
        joined = "\n".join(texts)
        try:
            return json.loads(joined)
        except json.JSONDecodeError:
            return joined

    def close(self):
        self.p.stdin.close()
        self.p.terminate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queries", nargs="+")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--raw", action="store_true")
    a = ap.parse_args()
    m = Mcp()
    try:
        for q in a.queries:
            r = m.tool("component_search", {"query": q, "limit": a.limit})
            print(f"=== {q}")
            if a.raw or not isinstance(r, (dict, list)):
                print(r if isinstance(r, str) else json.dumps(r, indent=1)[:4000])
                continue
            rows = r.get("results") or r.get("components") or r if isinstance(r, dict) else r
            for c in rows if isinstance(rows, list) else []:
                print("  {lcsc:>10}  {mpn:30.30}  {mfr:14.14}  {pkg:22.22}  stock={stock:<8} ${price:<8} {lib}".format(
                    lcsc=c.get("lcsc_id") or c.get("id", ""), mpn=str(c.get("name", "")),
                    mfr=str(c.get("manufacturer", "")), pkg=str(c.get("package", "")), stock=c.get("stock", ""),
                    price=c.get("price", ""), lib=c.get("library_type", "")))
    finally:
        m.close()


if __name__ == "__main__":
    sys.exit(main())
