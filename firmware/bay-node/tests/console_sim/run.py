"""Run the bay node's console on native_sim, with a fake DUT on its AUX UART.

Linux only (native_sim); web/screencast.py runs it in the Zephyr build image:

    python3 run.py [--workspace /ws] [--build /build]

Builds (west, incrementally) and starts two native_sim programs:

  * the node: this directory, i.e. the real aux_console.c, rfc2217.c and
    web.c with the hardware stubbed; HTTP on port 80, RFC 2217 on 4001;
  * the DUT: Zephyr's shell sample, a genuine Zephyr console.

The node's AUX UART is a PTY; the DUT's console is its stdin/stdout; this
script copies bytes between the two.  The node prints "SIM: dut reset" and
"SIM: dut power on|off" when the page presses RESET or the power buttons:
the DUT is restarted, stopped or started accordingly.  What you type goes
to the node's own shell (its UART pads on a real node): "bay access claim"
confirms a claim, as a short press on BOOT would.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import threading
import time
import tty
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(workspace: Path, out: Path, app: Path, *cmake_args: str) -> Path:
    cmd = ["west", "build", "-b", "native_sim/native/64", "-d", str(out), "-p", "auto", str(app)]
    if cmake_args:
        cmd += ["--", *cmake_args]
    subprocess.run(cmd, cwd=workspace, check=True)
    return out / "zephyr" / "zephyr.exe"


class Dut:
    """The fake board: restartable, its console wired to the node's AUX PTY."""

    def __init__(self, exe: Path, aux_fd: int):
        self.exe = exe
        self.aux_fd = aux_fd
        self.proc: subprocess.Popen | None = None
        self.lock = threading.Lock()

    def start(self) -> None:
        with self.lock:
            if self.proc is not None:
                return
            self.proc = subprocess.Popen([str(self.exe), "--uart_stdinout"],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
            threading.Thread(target=self._output, args=(self.proc,), daemon=True).start()

    def stop(self) -> None:
        with self.lock:
            proc, self.proc = self.proc, None
        if proc is not None:
            proc.kill()
            proc.wait()

    def write(self, data: bytes) -> None:
        proc = self.proc
        if proc is not None:
            try:
                proc.stdin.write(data)
            except OSError:
                pass

    def _output(self, proc: subprocess.Popen) -> None:
        fd = proc.stdout.fileno()
        while data := os.read(fd, 4096):
            os.write(self.aux_fd, data)


def keyboard(aux_fd: int, dut: Dut) -> None:
    """What the node sends on its AUX TX goes to the DUT's console."""
    while True:
        dut.write(os.read(aux_fd, 4096))


def node_shell(node: subprocess.Popen) -> None:
    """Lines typed here go to the node's shell (none when run detached)."""
    for line in sys.stdin:
        node.stdin.write(line.rstrip("\n").encode() + b"\r")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workspace", type=Path, default=Path("/ws"), help="west workspace")
    ap.add_argument("--build", type=Path, default=Path("/build"), help="build directories")
    ap.add_argument("--debug", action="store_true", help="node with debug.conf (logs, -O0)")
    args = ap.parse_args()

    if args.debug:
        node_exe = build(args.workspace, args.build / "simdbg", HERE,
                         f"-DEXTRA_CONF_FILE={HERE / 'debug.conf'}")
    else:
        node_exe = build(args.workspace, args.build / "sim", HERE)
    dut_exe = build(args.workspace, args.build / "dut", HERE / "dut")

    # The node's console (uart0) on stdout: its "SIM:" lines drive the DUT
    node = subprocess.Popen([str(node_exe), "--uart_stdinout"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, bufsize=0)
    threading.Thread(target=node_shell, args=(node,), daemon=True).start()
    dut = None
    # The node's shell shares its console: a "SIM:" line may follow a prompt
    for raw in iter(node.stdout.readline, b""):
        line = raw.decode(errors="replace").rstrip()
        print(f"node: {line}", flush=True)
        if dut is None and (m := re.search(r"uart_1 connected to pseudotty: (\S+)", line)):
            aux_fd = os.open(m.group(1), os.O_RDWR | os.O_NOCTTY)
            tty.setraw(aux_fd)
            dut = Dut(dut_exe, aux_fd)
            threading.Thread(target=keyboard, args=(aux_fd, dut), daemon=True).start()
        elif dut is not None and "SIM: ready" in line:
            dut.start()
        elif dut is not None and "SIM: dut reset" in line:
            dut.stop()
            time.sleep(0.2)
            dut.start()
        elif dut is not None and "SIM: dut power off" in line:
            dut.stop()
        elif dut is not None and "SIM: dut power on" in line:
            dut.start()
    sys.exit(node.wait())


if __name__ == "__main__":
    main()
