#!/usr/bin/env python3
"""Route one placement many ways at once and keep the best: a Freerouting portfolio.

    python tools/route_farm.py bay-node                  # prepare, route the portfolio, score, report
    python tools/route_farm.py bay-node --runs single    # only the pipeline's own run (tools/kicad.sh --route's)
    python tools/route_farm.py bay-node --step score     # re-score what has been routed
    python tools/route_farm.py bay-node --apply          # + install the best routing in electronics/bay-node

Freerouting's autorouter runs on one core and is deterministic: the same DSN and settings give the same
board on any machine.  So the cores go to runs that differ, each a complete Freerouting job: pass counts,
via and rip-up costs, fan-out and optimizer on or off, and the order of the nets (the DSN's nets and
components permuted with a seed, electronics/tools/dsn.py).  Each run's session is imported into its own
copy of the project, as tools/kicad.sh --ses would, and ranked by KiCad's verdict: unconnected items,
copper DRC errors, then copper length plus 2 mm a via (VIA_MM).

Steps (--step, default all):
  prepare  tools/kicad.sh <board> --dsn on the committed design, kept in build/farm/base (the board's own
           files are put back as they were)
  route    every run of the portfolio on the hosts, several at once; a run that has its session is skipped,
           one still running on its host is waited for (resumable)
  score    each session imported into build/farm/runs/<run>/project (tools/kicad.sh --ses --outdir=...)
  report   build/farm/report.json and a ranked table; --apply copies the best into the board

Hosts (--hosts FILE, or ROUTE_FARM_HOSTS): a JSON list, by default one local Docker host:
  [{"name": "mac", "ssh": ["user@host"], "kind": "java", "slots": 5},
   {"name": "box", "ssh": ["user@host", "box"], "kind": "docker", "slots": 8, "docker": "docker --context default"}]
  "ssh": the hops (each one ssh'd from the previous), [] for this machine; "kind": java (a JRE on PATH) or
  docker (eclipse-temurin); "slots": runs at once; "dir": where the runs go (~/route-farm); "threads": the
  optimizer's threads per run (default 1: with more, its result changes from one run to the next); "env": a
  prefix for its commands (e.g. "PATH=/usr/local/bin:$PATH" for Docker Desktop on a Mac over ssh).
  --score-on HOST runs the KiCad imports there (tools/kicad.sh in Docker, on a copy of the files they need)
  instead of on this machine.  The jar is copied to each host once.  Containers are named
  rf-<board>-<farm>-<run>, so they can be told from other jobs on a shared machine.  --run-timeout stops a run
  that grinds on (Freerouting keeps passing on a board it sees almost complete).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "electronics" / "tools"))
import dsn as dsnlib  # noqa: E402

FR_VER = "2.5.0"
FR_JAR = REPO / ".cache" / "freerouting" / f"freerouting-{FR_VER}.jar"
JRE_IMAGE = os.environ.get("JRE_IMAGE", "eclipse-temurin:25-jre")
# tools/kicad.sh --route's Freerouting call (here with one optimizer thread, FR_OPT_THREADS=1 there: runs must
# be repeatable): the reference every portfolio is measured against
BASE_ARGS = ["--gui.enabled=false", "-da", "--router.autorouter.max_passes=60"]

# The default portfolio.  Each entry: Freerouting's own settings on top of BASE_ARGS, and an optional net
# order (the seed of dsn.shuffle).  "single" is exactly the pipeline's run.
PORTFOLIO = {
    "single": {},
    "via10": {"args": ["--router.scoring.via_costs=10"]},
    "via150": {"args": ["--router.scoring.via_costs=150"]},
    "ripup30": {"args": ["--router.scoring.start_ripup_costs=30"]},
    "ripup300": {"args": ["--router.scoring.start_ripup_costs=300"]},
    "nofanout": {"args": ["--router.fanout.enabled=false"]},
    "noopt": {"args": ["--router.optimizer.enabled=false"]},
    "planevia50": {"args": ["--router.scoring.plane_via_costs=50"]},
    # its automatic neck-down narrows tracks at crowded pads under the board's minimum (0.076 mm on a 0.09 one)
    "noneck": {"args": ["--router.automatic_neckdown=false"]},
    "noneck-order2": {"args": ["--router.automatic_neckdown=false"], "order": 2},
    "order1": {"order": 1},
    "order2": {"order": 2},
    "order3": {"order": 3},
    "order4": {"order": 4},
    "order5": {"order": 5},
    "via10-order1": {"args": ["--router.scoring.via_costs=10"], "order": 1},
    "ripup30-order2": {"args": ["--router.scoring.start_ripup_costs=30"], "order": 2},
}
# Also possible ("planes": "signals", dsn.split_planes_as_signals): a split power layer's nets routed as
# signals.  Left out: on the DATA x4 v2 it leaves 171-212 links open where the default leaves 12-14.

_print_lock = threading.Lock()
# full paths: on Windows, CreateProcess looks in System32 (WSL's bash) before PATH (Git's)
BASH = shutil.which("bash") or "bash"
SH = shutil.which("sh") or "sh"
SSH = shutil.which("ssh") or "ssh"


def log(*a):
    with _print_lock:
        print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------ hosts

class Host:
    def __init__(self, spec: dict):
        self.name = spec["name"]
        self.hops = list(spec.get("ssh", []))
        self.kind = spec.get("kind", "docker")
        self.slots = int(spec.get("slots", 2))
        self.dir = spec.get("dir", "~/route-farm")
        self.docker = spec.get("docker", "docker")
        self.java = spec.get("java", "java")
        self.threads = int(spec.get("threads", 0)) or None
        self.xmx = spec.get("xmx", "3g")
        self.env = spec.get("env", "")
        self.jar = f"{self.dir}/freerouting-{FR_VER}.jar"
        self._jar_ok = False
        self._lock = threading.Lock()

    @property
    def local(self) -> bool:
        return not self.hops

    def argv(self, cmd: str) -> list[str]:
        """The command line that runs `cmd` (a POSIX shell command) on this host."""
        if self.local:
            return [SH, "-c", cmd]
        for hop in reversed(self.hops[1:]):
            cmd = f"ssh -o BatchMode=yes {hop} {shlex.quote(cmd)}"
        return [SSH, "-o", "BatchMode=yes", "-o", "ServerAliveInterval=30", self.hops[0], cmd]

    def sh(self, cmd: str, stdin: bytes | None = None, check: bool = True, timeout: float = 600) -> bytes:
        for attempt in range(3):
            r = subprocess.run(self.argv(cmd), input=stdin, capture_output=True, timeout=timeout)
            if r.returncode == 0 or not check:
                return r.stdout
            if r.returncode != 255:          # 255: ssh itself failed; worth another try
                break
            time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"{self.name}: {cmd[:120]}: exit {r.returncode}: {r.stderr.decode(errors='replace')[-400:]}")

    def put(self, data: bytes, path: str):
        self.sh(f"mkdir -p {_q(os.path.dirname(path))} && cat > {_q(path)}", stdin=data)

    def get(self, path: str) -> bytes | None:
        out = self.sh(f"cat {_q(path)} 2>/dev/null || true", check=False)
        return out or None

    def ensure_jar(self):
        with self._lock:
            if self._jar_ok:
                return
            have = self.sh(f"test -s {_q(self.jar)} && echo yes || true", check=False).strip()
            if have != b"yes":
                log(f"{self.name}: copying Freerouting {FR_VER}")
                self.put(FR_JAR.read_bytes(), self.jar)
            self._jar_ok = True


def _q(path: str) -> str:
    """Quote a remote path, leaving a leading ~/ to the remote shell."""
    if path.startswith("~/"):
        return "~/" + shlex.quote(path[2:])
    return shlex.quote(path)


def load_hosts(path: str | None) -> list[Host]:
    path = path or os.environ.get("ROUTE_FARM_HOSTS")
    if path:
        return [Host(h) for h in json.loads(Path(path).read_text(encoding="utf-8"))]
    return [Host({"name": "local", "ssh": [], "kind": "docker", "slots": max(1, (os.cpu_count() or 4) // 4),
                  "dir": str(REPO / ".cache" / "route-farm").replace("\\", "/")})]


# ------------------------------------------------------------------ the board's files

FARM = "farm"          # --farm: another set of runs for the same board (a variant's base, made by hand)


def farm_dir(board: str) -> Path:
    return REPO / "electronics" / board / "build" / FARM


def board_name(board: str) -> str:
    """The KiCad project name of a board folder (its .kicad_pro, or its farm base's)."""
    for d in (REPO / "electronics" / board, farm_dir(board) / "base"):
        pros = [p for p in sorted(d.glob("*.kicad_pro")) if not p.stem.endswith("-panel")]
        if pros:
            return pros[0].stem
    return board


PROJECT_SUFFIXES = (".kicad_pcb", ".kicad_pro", ".kicad_sch", ".kicad_dru")
LIB_TABLES = ("fp-lib-table", "sym-lib-table")


def kicad(args: list[str], name: str | None = None, quiet: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if name:
        env["KICAD_NAME"] = name
    r = subprocess.run([BASH, "tools/kicad.sh", *args], cwd=REPO, env=env, capture_output=quiet, text=True)
    if r.returncode:
        raise RuntimeError(f"tools/kicad.sh {' '.join(args)}: exit {r.returncode}\n{(r.stdout or '')[-2000:]}"
                           f"\n{(r.stderr or '')[-2000:]}")
    return r


def copy_project(src: Path, dst: Path):
    """A board's KiCad project (pcb, project, sheets, rules) from src to dst, the library tables pointed at
    the repository's libraries (a copy sits deeper than the board's folder: ${KIPRJMOD}/../lib won't do)."""
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file() and f.suffix in PROJECT_SUFFIXES and "-panel" not in f.stem:
            shutil.copy2(f, dst / f.name)
    for t in LIB_TABLES:
        if (src / t).exists():
            text = (src / t).read_text(encoding="utf-8")
            (dst / t).write_text(text.replace("${KIPRJMOD}/../lib/", "/work/electronics/lib/"), encoding="utf-8",
                                 newline="\n")


def prepare(board: str, force: bool = False) -> Path:
    """build/farm/base: the unrouted project and its DSN, from the committed design.py."""
    base = farm_dir(board) / "base"
    if base.exists() and list((base / "build").glob("*.dsn")) and not force:
        return base
    bdir = REPO / "electronics" / board
    saved = {f.name: f.read_bytes() for f in bdir.iterdir() if f.is_file()}
    log(f"{board}: building the placed board and its DSN")
    t0 = time.time()
    try:
        kicad([board, "--dsn"], name=f"rf-{board}-{FARM}-prepare")
        name = board_name(board)            # the design's own name (a scratch copy's folder may differ)
        if base.exists():
            shutil.rmtree(base)
        copy_project(bdir, base)
        (base / "build").mkdir(parents=True, exist_ok=True)
        for f in (f"{name}.dsn", "erc-summary.json", "summary.json"):
            if (bdir / "build" / f).exists():
                shutil.copy2(bdir / "build" / f, base / "build" / f)
    finally:
        # the board's own files as they were (the routed, committed board)
        for f in bdir.iterdir():
            if f.is_file() and f.name not in saved:
                f.unlink()
        for fname, data in saved.items():
            if (bdir / fname).read_bytes() != data:
                (bdir / fname).write_bytes(data)
    log(f"{board}: base ready in {time.time() - t0:.0f} s")
    return base


# ------------------------------------------------------------------ runs

def run_id_hash(dsn_text: str, spec: dict) -> str:
    h = hashlib.sha256(dsn_text.encode())
    h.update(json.dumps(spec, sort_keys=True).encode())
    return h.hexdigest()[:12]


def run_dsn(base_dsn: str, spec: dict) -> str:
    """A run's DSN: the base, its nets in another order ("order": seed), its split planes routed as signals
    ("planes": "signals")."""
    text = dsnlib.shuffle(base_dsn, spec["order"]) if spec.get("order") else base_dsn
    if spec.get("planes") == "signals":
        text = dsnlib.split_planes_as_signals(text)[0]
    return text


def fr_args(spec: dict, threads: int | None) -> list[str]:
    # the optimizer (it runs once Freerouting thinks the board complete) is deterministic on one thread only
    return BASE_ARGS + list(spec.get("args", [])) + [f"--router.optimizer.max_threads={threads or 1}"]


def wrapper(java: str, jar: str, args: list[str], xmx: str = "3g") -> str:
    """The shell line a run executes in its folder: Freerouting, its exit code, start and end times."""
    fr = " ".join([java, f"-Xmx{xmx}", "-jar", jar, *map(shlex.quote, args), "-de", "board.dsn", "-do", "board.ses"])
    return f"echo $$ > pid; date +%s > start; {fr} > freerouting.log 2>&1; echo $? > exit; date +%s > end"


def start_remote(host: Host, rdir: str, board: str, rid: str, spec: dict):
    threads = host.threads or None
    if host.kind == "java":
        line = wrapper(host.java, host.jar, fr_args(spec, threads), host.xmx)
        host.sh(f"cd {_q(rdir)} && rm -f exit end && (nohup sh -c {shlex.quote(line)} > /dev/null 2>&1 < /dev/null &)")
    else:
        line = wrapper("java", "/fr.jar", fr_args(spec, threads), host.xmx)
        cname = f"rf-{board}-{FARM}-{rid}"
        host.sh(f"cd {_q(rdir)} && rm -f exit end && ({host.docker} rm -f {cname} > /dev/null 2>&1 || true) && "
                f"{host.docker} run -d --rm --name {cname} --user $(id -u):$(id -g) -v \"$PWD\":/w "
                f"-v {_q(host.jar)}:/fr.jar:ro -w /w {JRE_IMAGE} sh -c {shlex.quote(line)} > /dev/null")


def start_local_docker(host: Host, rdir: Path, board: str, rid: str, spec: dict):
    line = wrapper("java", "/fr.jar", fr_args(spec, host.threads), host.xmx)
    cname = f"rf-{board}-{FARM}-{rid}"
    mount = lambda p: subprocess.run(["cygpath", "-m", str(p)], capture_output=True, text=True).stdout.strip() \
        if shutil.which("cygpath") else str(p)
    subprocess.run(["docker", "rm", "-f", cname], capture_output=True)
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    subprocess.run(["docker", "run", "-d", "--rm", "--name", cname, "-v", f"{mount(rdir)}:/w",
                    "-v", f"{mount(FR_JAR)}:/fr.jar:ro", "-w", "/w", JRE_IMAGE, "sh", "-c", line],
                   check=True, capture_output=True, env=env)


def alive(host: Host, rdir: str, cname: str) -> bool:
    """Is a run that has started but not finished still going (its container, or its shell's pid)?"""
    if host.kind == "docker":
        docker = "docker" if host.local else host.docker
        out = host.sh(f"{docker} ps -q -f name=^{cname}$", check=False).strip()
        return bool(out)
    out = host.sh(f"kill -0 $(cat {_q(rdir)}/pid 2>/dev/null) 2>/dev/null && echo y || true", check=False).strip()
    return out == b"y"


RUN_TIMEOUT = 0          # --run-timeout: seconds before a run is stopped (its exit code then 124); 0: none


def stop(host: Host, rdir: str, cname: str):
    """Stop a run (its container, or its shell and that shell's children) and mark it finished, exit 124."""
    if host.kind == "docker":
        docker = "docker" if host.local else host.docker
        host.sh(f"{docker} rm -f {cname} > /dev/null 2>&1 || true", check=False)
    else:
        host.sh(f"p=$(cat {_q(rdir)}/pid); for c in $(pgrep -P $p); do kill -9 $c; done; kill -9 $p || true",
                check=False)
    host.sh(f"cd {_q(rdir)} && echo 124 > exit && date +%s > end", check=False)


def route_one(host: Host, board: str, rid: str, spec: dict, base_dsn: str, poll: float = 20.0) -> dict:
    """One run on one host, from upload to its session back in build/farm/runs/<rid>.  Resumable: a run that
    already finished there is only fetched, one still running is waited for."""
    out = farm_dir(board) / "runs" / rid
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "run.json"
    text = run_dsn(base_dsn, spec)
    key = run_id_hash(text, {k: v for k, v in spec.items()})
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    if meta.get("key") == key and meta.get("status") == "done" and (out / "board.ses").exists():
        return meta
    (out / "board.dsn").write_text(text, encoding="utf-8", newline="\n")
    rdir = f"{host.dir}/{board}/{FARM}-{rid}-{key}"
    if host.local:
        Path(rdir).mkdir(parents=True, exist_ok=True)
    meta = {"run": rid, "key": key, "spec": spec, "host": host.name, "args": fr_args(spec, host.threads),
            "status": "running"}
    if not host.local:
        host.ensure_jar()
    state = host.sh(f"cd {_q(rdir)} 2>/dev/null && (test -f exit && echo done || (test -f start && echo running)) || true",
                    check=False).strip().decode()
    if state == "running" and not alive(host, rdir, f"rf-{board}-{FARM}-{rid}"):
        log(f"{board} {rid}: its run on {host.name} died, starting it again")
        host.sh(f"cd {_q(rdir)} && rm -f start pid freerouting.log board.ses", check=False)
        state = ""
    if state == "":
        if host.local:
            shutil.copy2(out / "board.dsn", Path(rdir) / "board.dsn")
            start_local_docker(host, Path(rdir), board, rid, spec)
        else:
            host.put(text.encode(), f"{rdir}/board.dsn")
            start_remote(host, rdir, board, rid, spec)
        log(f"{board} {rid}: started on {host.name}")
    else:
        log(f"{board} {rid}: {state} on {host.name} already")
    meta_path.write_text(json.dumps(meta, indent=1))
    t_wait = time.time()
    while True:
        if host.sh(f"test -f {_q(rdir)}/exit && echo y || true", check=False).strip() == b"y":
            break
        if RUN_TIMEOUT and time.time() - t_wait > RUN_TIMEOUT:
            stop(host, rdir, f"rf-{board}-{FARM}-{rid}")
            log(f"{board} {rid}: stopped on {host.name} after {RUN_TIMEOUT} s (--run-timeout)")
            continue
        time.sleep(min(poll, max(2.0, (time.time() - t_wait) / 8)))     # often at first: small boards take seconds
    t = host.sh(f"cd {_q(rdir)} && cat exit start end", check=False).decode().split()
    exit_code, t0, t1 = (int(x) for x in t[:3]) if len(t) >= 3 else (-1, 0, 0)
    for f in ("freerouting.log", "board.ses"):
        data = host.get(f"{rdir}/{f}")
        if data:
            (out / f).write_bytes(data)
    meta.update(status="done" if (out / "board.ses").exists() else "failed", exit=exit_code, wall_s=t1 - t0,
                **fr_log_summary(out / "freerouting.log"))
    meta_path.write_text(json.dumps(meta, indent=1))
    log(f"{board} {rid}: {meta['status']} on {host.name} in {meta['wall_s']} s, Freerouting says "
        f"{meta.get('fr_unrouted')} unrouted")
    return meta


def fr_log_summary(path: Path) -> dict:
    """Freerouting's own account of a run: its last unrouted count, passes, CPU seconds."""
    import re
    out = {}
    if not path.exists():
        return out
    text = path.read_text(encoding="utf-8", errors="replace")
    passes = re.findall(r"Auto-routing pass #(\d+)", text)
    out["fr_passes"] = int(passes[-1]) if passes else 0
    m = re.findall(r"Auto-routing stage completed:.*?final score: ([\d.]+) \((\d+) unrouted and (\d+) violations\), "
                   r"using ([\d.]+) total CPU seconds", text)
    if m:
        out.update(fr_score=float(m[-1][0]), fr_unrouted=int(m[-1][1]), fr_violations=int(m[-1][2]),
                   fr_cpu_s=float(m[-1][3]))
    m = re.findall(r"Optimization stage completed.*?using ([\d.]+) total CPU seconds", text)
    if m:
        out["fr_opt_cpu_s"] = float(m[-1])
    return out


def route_all(board: str, runs: dict, hosts: list[Host], base_dsn: str, on_done=None) -> dict:
    """Every run on the first free slot of any host (the slower hosts' slots are just fewer); `on_done(rid)`
    as each one finishes (its scoring starts while the others route)."""
    import queue
    todo: queue.Queue = queue.Queue()
    # runs that come to the same DSN and settings (a split-plane variant on a board without one) run once
    first: dict[str, str] = {}
    twins: dict[str, str] = {}
    for rid, spec in runs.items():
        key = run_id_hash(run_dsn(base_dsn, spec), {"args": spec.get("args", [])})
        if key in first:
            twins[rid] = first[key]
        else:
            first[key] = rid
            todo.put((rid, spec))
    results, errors = {}, []
    # a run already started on a host (an earlier invocation stopped) goes back to that host
    pinned: dict[str, queue.Queue] = {h.name: queue.Queue() for h in hosts}
    rest: queue.Queue = queue.Queue()
    have = {}
    for h in hosts:
        try:
            listing = h.sh(f"ls {_q(h.dir)}/{board} 2>/dev/null || true", check=False).decode().split()
        except Exception:      # noqa: BLE001 - a host we can't list just gets no pinned runs
            listing = []
        for d in listing:
            have.setdefault(d, h.name)
    while not todo.empty():
        rid, spec = todo.get()
        key = run_id_hash(run_dsn(base_dsn, spec), spec)
        h = have.get(f"{FARM}-{rid}-{key}")
        (pinned[h] if h in pinned else rest).put((rid, spec))

    def worker(host: Host):
        while True:
            try:
                rid, spec = pinned[host.name].get_nowait()
            except queue.Empty:
                try:
                    rid, spec = rest.get_nowait()
                except queue.Empty:
                    return
            try:
                results[rid] = route_one(host, board, rid, spec, base_dsn)
                if on_done and results[rid].get("status") == "done":
                    on_done(rid)
            except Exception as e:      # noqa: BLE001 - one host failing must not stop the others
                errors.append(f"{rid} on {host.name}: {e}")
                log(f"{board} {rid}: FAILED on {host.name}: {e}")

    slots = [h for h in hosts for _ in range(h.slots)]
    t0 = time.time()
    with cf.ThreadPoolExecutor(len(slots)) as ex:
        list(ex.map(worker, slots))
    for rid, twin in twins.items():
        if twin in results:
            out = farm_dir(board) / "runs" / rid
            out.mkdir(parents=True, exist_ok=True)
            for f in ("board.ses", "freerouting.log", "board.dsn"):
                if (farm_dir(board) / "runs" / twin / f).exists():
                    shutil.copy2(farm_dir(board) / "runs" / twin / f, out / f)
            results[rid] = {**results[twin], "run": rid, "same_as": twin}
            (out / "run.json").write_text(json.dumps(results[rid], indent=1))
            if on_done:
                on_done(rid)
    log(f"{board}: {len(results)} runs in {time.time() - t0:.0f} s, {len(errors)} failed")
    (farm_dir(board) / "route.json").write_text(json.dumps({"wall_s": round(time.time() - t0), "errors": errors,
                                                            "hosts": [h.name for h in hosts]}, indent=1))
    return results


# ------------------------------------------------------------------ scoring

def score_one(board: str, rid: str, routed: Path | None = None) -> dict:
    """Import a run's session (or a board another router routed) into its own copy of the project, as
    tools/kicad.sh --ses does, and keep KiCad's verdict: build/farm/runs/<rid>/score.json."""
    run = farm_dir(board) / "runs" / rid
    proj = run / "project"
    name = board_name(board)
    ses = run / "board.ses"
    if routed is None and not ses.exists():
        return {}
    stamp = hashlib.sha256((routed or ses).read_bytes()).hexdigest()[:12]
    score_path = run / "score.json"
    if score_path.exists():
        old = json.loads(score_path.read_text())
        if old.get("stamp") == stamp:
            return {**old, "cached": True}
    if proj.exists():
        shutil.rmtree(proj)
    copy_project(farm_dir(board) / "base", proj)
    (proj / "build").mkdir(exist_ok=True)
    for f in ("erc-summary.json",):
        if (farm_dir(board) / "base" / "build" / f).exists():
            shutil.copy2(farm_dir(board) / "base" / "build" / f, proj / "build" / f)
    args = [board, "--ses", f"--outdir={proj.relative_to(REPO).as_posix()}"]
    if routed is None:
        shutil.copy2(ses, proj / "build" / f"{name}.ses")
    else:
        dst = run / "routed.kicad_pcb"
        if routed.resolve() != dst.resolve():
            shutil.copy2(routed, dst)
        args.append(f"--routed={dst.relative_to(REPO).as_posix()}")
    t0 = time.time()
    try:
        if SCORE_HOST is not None:
            kicad_remote(SCORE_HOST, args, proj, run, name=f"rf-{board}-{FARM}-{rid}-score")
        else:
            kicad(args, name=f"rf-{board}-{FARM}-{rid}-score")
    except RuntimeError as e:
        return {"stamp": stamp, "error": str(e)[-1500:]}         # not kept: the next --step score tries again
    s = json.loads((proj / "build" / "summary.json").read_text())
    res = {"stamp": stamp, "import_s": round(time.time() - t0), "drc": s["drc"], "routing": s.get("routing", {})}
    score_path.write_text(json.dumps(res, indent=1))
    return res


SCORE_HOST: Host | None = None          # --score-on
# what tools/kicad.sh needs from the repository to import a session (design.py, the libraries, rackcfg's data)
SNAPSHOT = ("electronics", "config", "mechanical/boards", "tools")
_synced: dict[str, str] = {}
_sync_lock = threading.Lock()


def _tar(root: Path, files) -> bytes:
    import io
    import tarfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        for f in files:
            t.add(root / f, arcname=str(f), recursive=False)
    return buf.getvalue()


def sync_repo(host: Host) -> str:
    """{host.dir}/repo: this checkout's files the imports need (tracked, as they are on disk), sent again
    whenever one changes.  Returns the remote folder."""
    rrepo = f"{host.dir}/repo"
    with _sync_lock:
        files = subprocess.run(["git", "ls-files", "-z", *SNAPSHOT], cwd=REPO, capture_output=True,
                               check=True).stdout.decode().split("\0")
        files = [f for f in files if f and (REPO / f).is_file()]
        h = hashlib.sha256()
        for f in files:
            h.update(f.encode() + (REPO / f).read_bytes())
        stamp = h.hexdigest()[:16]
        if _synced.get(host.name) == stamp:
            return rrepo
        if host.sh(f"cat {_q(rrepo)}/.stamp 2>/dev/null || true", check=False).decode().strip() != stamp:
            log(f"{host.name}: sending the repository's files ({len(files)})")
            host.sh(f"rm -rf {_q(rrepo)} && mkdir -p {_q(rrepo)} && tar xf - -C {_q(rrepo)} && echo {stamp} > "
                    f"{_q(rrepo)}/.stamp", stdin=_tar(REPO, files), timeout=1800)
        _synced[host.name] = stamp
        return rrepo


def kicad_remote(host: Host, args: list[str], proj: Path, run: Path, name: str):
    """tools/kicad.sh `args` on `host`: the candidate's project (and a routed board) go there, the imported
    project comes back into `proj`."""
    rrepo = sync_repo(host)
    rrun = f"{rrepo}/{run.relative_to(REPO).as_posix()}"
    files = [f.relative_to(run) for f in run.rglob("*") if f.is_file() and (f.is_relative_to(proj)
                                                                          or f.name == "routed.kicad_pcb")]
    host.sh(f"rm -rf {_q(rrun)} && mkdir -p {_q(rrun)} && tar xf - -C {_q(rrun)}", stdin=_tar(run, files))
    cmd = f"cd {_q(rrepo)} && {host.env} KICAD_NAME={name} bash tools/kicad.sh {' '.join(map(shlex.quote, args))}"
    r = subprocess.run(host.argv(cmd), capture_output=True, timeout=3600)
    if r.returncode:
        raise RuntimeError(f"{host.name}: tools/kicad.sh {' '.join(args)}: exit {r.returncode}\n"
                           f"{r.stdout.decode(errors='replace')[-1500:]}\n{r.stderr.decode(errors='replace')[-1000:]}")
    import io
    import tarfile
    data = host.sh(f"cd {_q(rrun)}/project && tar cf - .", timeout=600)
    shutil.rmtree(proj)
    proj.mkdir()
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        t.extractall(proj, filter="data")


# a via counts as this much track in a run's cost (copper length + VIA_MM × vias): 2 mm, about what a via
# adds to a route in drilling, its two pads' clearance and the turn into it
VIA_MM = 2.0


def cost(score: dict) -> float:
    r = score.get("routing", {})
    return round(r.get("length_mm", 0) + VIA_MM * r.get("vias", 0), 1)


def rank_key(score: dict) -> tuple:
    """Fewest unconnected items, then copper DRC errors and parity, then the cost (length and vias)."""
    if not score or "drc" not in score:
        return (10 ** 9,)
    d = score["drc"]
    return (d["unconnected"], sum(d.get("copper", {}).values()) + d["parity"], cost(score))


def score_logged(board: str, rid: str) -> dict:
    try:
        r = score_one(board, rid)
    except Exception as e:      # noqa: BLE001
        r = {"error": str(e)}
    if "drc" in r and not r.get("cached"):
        log(f"{board} {rid}: unconnected {r['drc']['unconnected']}, copper {r['drc'].get('copper')}, "
            f"vias {r['routing'].get('vias')}, {r['routing'].get('length_mm')} mm")
    elif r:
        log(f"{board} {rid}: scoring failed: {r.get('error', '')[-300:]}")
    return r


def score_all(board: str, rids: list[str], jobs: int) -> dict:
    with cf.ThreadPoolExecutor(jobs) as ex:
        futs = {rid: ex.submit(score_logged, board, rid) for rid in rids}
    return {rid: f.result() for rid, f in futs.items()}


# ------------------------------------------------------------------ report

def report(board: str, rids: list[str]) -> dict:
    rows = []
    for rid in rids:
        run = farm_dir(board) / "runs" / rid
        meta = json.loads((run / "run.json").read_text()) if (run / "run.json").exists() else {}
        score = json.loads((run / "score.json").read_text()) if (run / "score.json").exists() else {}
        rows.append({"run": rid, "host": meta.get("host"), "wall_s": meta.get("wall_s"),
                     "fr_unrouted": meta.get("fr_unrouted"), "fr_passes": meta.get("fr_passes"),
                     "fr_cpu_s": meta.get("fr_cpu_s"), "key": rank_key(score),
                     "unconnected": score.get("drc", {}).get("unconnected"),
                     "copper": score.get("drc", {}).get("copper"), "vias": score.get("routing", {}).get("vias"),
                     "length_mm": score.get("routing", {}).get("length_mm"), "cost": cost(score) if score else None,
                     "error": score.get("error") or ("stopped (--run-timeout)" if meta.get("exit") == 124 else None)})
    rows.sort(key=lambda r: r["key"])
    walls = [r["wall_s"] for r in rows if r["wall_s"]]
    rep = {"board": board, "runs": rows, "best": rows[0]["run"] if rows else None,
           "longest_run_s": max(walls) if walls else None}
    (farm_dir(board) / "report.json").write_text(json.dumps(rep, indent=1))
    print(f"\n{board}: {len(rows)} runs, best {rep['best']}")
    print(f"{'run':18} {'host':6} {'wall':>6} {'FR':>4} {'unconn':>6} {'copper':>6} {'vias':>5} {'mm':>8} {'cost':>8}")
    for r in rows:
        cu = sum((r["copper"] or {}).values()) if r["copper"] is not None else "-"
        print(f"{r['run']:18} {str(r['host'] or '-'):6} {str(r['wall_s'] or '-'):>6} {str(r['fr_unrouted']):>4} "
              f"{str(r['unconnected']):>6} {str(cu):>6} {str(r['vias']):>5} {str(r['length_mm']):>8} {str(r['cost']):>8}"
              + (f"  error: {r['error'][:60]}" if r["error"] else ""))
    return rep


def apply_best(board: str, rid: str):
    """Install a run's routed board in electronics/<board> (the session too), as tools/kicad.sh --ses would
    have left it.  Check it with tools/kicad.sh <board> --check --fab before committing."""
    name = board_name(board)
    run = farm_dir(board) / "runs" / rid
    proj = run / "project"
    shutil.copy2(proj / f"{name}.kicad_pcb", REPO / "electronics" / board / f"{name}.kicad_pcb")
    if (run / "board.ses").exists():
        shutil.copy2(run / "board.ses", REPO / "electronics" / board / "build" / f"{name}.ses")
    log(f"{board}: installed {rid}; now tools/kicad.sh {board} --check --fab")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("boards", nargs="+")
    ap.add_argument("--step", choices=["all", "prepare", "route", "score", "report"], default="all")
    ap.add_argument("--runs", help="comma-separated runs of the portfolio (default: all of them)")
    ap.add_argument("--portfolio", help="a JSON file of runs ({name: {args: [...], order: seed}}) instead")
    ap.add_argument("--hosts", help="hosts JSON file (default: ROUTE_FARM_HOSTS, else local Docker)")
    ap.add_argument("--score-jobs", type=int, default=6, help="KiCad imports at once (local Docker)")
    ap.add_argument("--fresh", action="store_true", help="rebuild the base (design.py changed)")
    ap.add_argument("--apply", action="store_true", help="install the best run's board in electronics/<board>")
    ap.add_argument("--farm", default="farm", help="build/<farm>: another set of runs (its base/ made by hand)")
    ap.add_argument("--score-on", help="a host (by name) to run the KiCad imports on, in Docker")
    ap.add_argument("--run-timeout", type=int, default=0, help="stop a run after this many seconds (0: never)")
    a = ap.parse_args()
    global FARM, SCORE_HOST, RUN_TIMEOUT
    RUN_TIMEOUT = a.run_timeout
    FARM = a.farm
    runs = json.loads(Path(a.portfolio).read_text()) if a.portfolio else dict(PORTFOLIO)
    if a.runs:
        runs = {k: runs[k] for k in a.runs.split(",")}
    hosts = load_hosts(a.hosts)
    if a.score_on:
        SCORE_HOST = next(h for h in hosts if h.name == a.score_on)
    if not FR_JAR.exists():
        FR_JAR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sSL", "-o", str(FR_JAR), "https://github.com/freerouting/freerouting/releases/"
                        f"download/v{FR_VER}/freerouting-{FR_VER}.jar"], check=True)
    for board in a.boards:
        if a.step in ("all", "prepare"):
            prepare(board, force=a.fresh)
        base_dsn = (farm_dir(board) / "base" / "build" / f"{board_name(board)}.dsn").read_text(encoding="utf-8")
        if a.step == "all":
            with cf.ThreadPoolExecutor(a.score_jobs) as scorer:
                route_all(board, runs, hosts, base_dsn, on_done=lambda rid: scorer.submit(score_logged, board, rid))
        elif a.step == "route":
            route_all(board, runs, hosts, base_dsn)
        if a.step in ("all", "score"):
            score_all(board, list(runs), a.score_jobs)      # the ones not scored yet (the rest are cached)
        if a.step in ("all", "report", "score"):
            rep = report(board, list(runs))
            if a.apply and rep["best"]:
                apply_best(board, rep["best"])


if __name__ == "__main__":
    main()
