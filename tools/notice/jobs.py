"""The drawings on another machine within its memory (run.py's NOTICE_REMOTE step, Linux or
macOS): one freecadcmd process per job, started when the job's peak, plus what the running jobs
may still take, fits in the memory available.  A whole-rack drawing peaks at about 5.5 GB, a parts
card at about 1 GB.

    cd <run dir with notice.py, jobs.py and build/>; python jobs.py <freecadcmd> <job,job,...>

Peaks (MB: VmHWM on Linux, the largest sampled RSS on macOS) are kept in ../peaks.json for the
next run; a job without one counts as STEP_MB (a step drawing) or CARD_MB (thumb:, hw:).
Stdlib only.
"""
import json
import os
import re
import subprocess
import sys
import time

STEP_MB, CARD_MB, MARGIN_MB = 5500, 1500, 600
FC, names = sys.argv[1], [n for n in sys.argv[2].split(",") if n]
PEAKS = os.path.join("..", "peaks.json")
peaks = json.load(open(PEAKS)) if os.path.exists(PEAKS) else {}


def need(n):
    return 1.1 * peaks.get(n, CARD_MB if ":" in n else STEP_MB)


def available():
    """MB a new process can take: MemAvailable on Linux; free, inactive and speculative pages on macOS."""
    if os.path.exists("/proc/meminfo"):
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
        return 0
    vm = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    pages = dict(re.findall(r"^Pages (free|inactive|speculative):\s+(\d+)", vm, re.M))
    return sum(map(int, pages.values())) * int(re.search(r"page size of (\d+)", vm).group(1)) // 2**20


def peak(pid):
    """A running job's peak resident memory so far (MB): VmHWM on Linux, its RSS now on macOS."""
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    rss = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return int(rss) // 1024 if rss.isdigit() else 0


todo, running = list(names), {}            # names heaviest first (run.py's order); name -> [process, peak seen]
while todo or running:
    for n, r in list(running.items()):
        r[1] = max(r[1], peak(r[0].pid))
        if r[0].poll() is not None:
            if r[1]:                       # 0: done before its first sample
                peaks[n] = r[1]
            del running[n]
    owed = sum(max(need(n) - r[1], 0) for n, r in running.items())
    free = available() - owed - MARGIN_MB
    n = next((n for n in todo if need(n) <= free), None) or (todo[0] if todo and not running else None)
    if n:
        running[n] = [subprocess.Popen([FC, "notice.py"], env=dict(os.environ, NOTICE=n),
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL), 0]
        todo.remove(n)
    time.sleep(1)
json.dump(peaks, open(PEAKS, "w"), indent=1, sort_keys=True)
