#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chapter_queue  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = chapter_queue.db_path_from(REPO_ROOT)
WORKER_RE = re.compile(r"--worker-id\s+(\S+)")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(cmd: list[str], cwd: pathlib.Path | None = None) -> str:
    return subprocess.check_output(cmd, cwd=str(cwd) if cwd else None, text=True).strip()


def active_processes() -> dict[str, Any]:
    workers: dict[str, dict[str, Any]] = {}
    merge_loops: list[dict[str, Any]] = []

    def collect(pattern: str) -> list[str]:
        try:
            raw = subprocess.check_output(["pgrep", "-af", pattern], text=True)
            return [line.strip() for line in raw.splitlines() if line.strip()]
        except subprocess.CalledProcessError:
            return []

    for line in collect("chapter_worker.py"):
        parts = line.split(" ", 1)
        pid = int(parts[0])
        cmd = parts[1] if len(parts) > 1 else ""
        match = WORKER_RE.search(cmd)
        worker_id = match.group(1) if match else f"pid-{pid}"
        workers[worker_id] = {"pid": pid, "command": cmd}

    for line in collect("chapter_merge.py") + collect("cob_phase2_merge_loop.sh"):
        parts = line.split(" ", 1)
        pid = int(parts[0])
        cmd = parts[1] if len(parts) > 1 else ""
        merge_loops.append({"pid": pid, "command": cmd})

    return {"workers": workers, "merge_loops": merge_loops}


def chapter_progress(job: dict[str, Any]) -> dict[str, Any]:
    worktree = job.get("worktree_path")
    if not worktree:
        return {"written": 0, "percent": 0.0, "latest_file": None, "latest_mtime": None}
    chapter_dir = pathlib.Path(worktree) / "translation" / job["testament"] / job["book_slug"] / f"{int(job['chapter']):03d}"
    if not chapter_dir.exists():
        return {"written": 0, "percent": 0.0, "latest_file": None, "latest_mtime": None}
    files = sorted(chapter_dir.glob("*.yaml"))
    written = len(files)
    latest_file = None
    latest_mtime = None
    if files:
        latest = max(files, key=lambda p: p.stat().st_mtime)
        latest_file = latest.name
        latest_mtime = dt.datetime.fromtimestamp(latest.stat().st_mtime).isoformat(timespec="seconds")
    verse_count = int(job.get("verse_count") or 0) or 1
    percent = round((written / verse_count) * 100, 1)
    return {
        "written": written,
        "percent": percent,
        "latest_file": latest_file,
        "latest_mtime": latest_mtime,
    }


def recent_main_commits(limit: int = 12) -> list[dict[str, str]]:
    raw = run(["git", "log", "--oneline", f"-{limit}"], cwd=REPO_ROOT)
    commits: list[dict[str, str]] = []
    for line in raw.splitlines():
        sha, _, msg = line.partition(" ")
        commits.append({"sha": sha, "message": msg})
    return commits


def queue_jobs(limit_ready: int = 20) -> dict[str, Any]:
    with chapter_queue.connect(DB_PATH) as conn:
        chapter_queue.ensure_schema(conn)
        summary_rows = [dict(r) for r in conn.execute(
            "SELECT phase, status, COUNT(*) AS count FROM jobs GROUP BY phase, status ORDER BY phase_order, status"
        ).fetchall()]
        running_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM jobs WHERE status='running' ORDER BY phase_order, book_order, chapter"
        ).fetchall()]
        ready_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM jobs WHERE status='completed' AND commit_sha IS NOT NULL AND merged_at IS NULL ORDER BY phase_order, book_order, chapter LIMIT ?",
            (limit_ready,),
        ).fetchall()]
        failed_rows = [dict(r) for r in conn.execute(
            "SELECT * FROM jobs WHERE status='failed' ORDER BY updated_at DESC LIMIT 20"
        ).fetchall()]
    return {
        "summary": summary_rows,
        "running": running_rows,
        "ready": ready_rows,
        "failed": failed_rows,
    }


def build_status() -> dict[str, Any]:
    proc = active_processes()
    queue = queue_jobs()
    running = []
    for job in queue["running"]:
        progress = chapter_progress(job)
        worker_meta = proc["workers"].get(job.get("worker_id") or "")
        running.append({
            **job,
            **progress,
            "worker_process": worker_meta,
        })
    return {
        "generated_at": now_iso(),
        "repo_root": str(REPO_ROOT),
        "main_branch": run(["git", "branch", "--show-current"], cwd=REPO_ROOT),
        "main_head": run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT),
        "queue": {
            "summary": queue["summary"],
            "running": running,
            "ready": queue["ready"],
            "failed": queue["failed"],
        },
        "merge_loops": proc["merge_loops"],
        "recent_commits": recent_main_commits(),
    }


def html_page() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Cartha Bible Worker Dashboard</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; margin: 0; background: #0b1020; color: #eef2ff; }
    .wrap { max-width: 1400px; margin: 0 auto; padding: 24px; }
    .muted { color: #a5b4fc; }
    .grid { display: grid; gap: 16px; }
    .cards { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
    .card { background: #111833; border: 1px solid #273469; border-radius: 14px; padding: 16px; box-shadow: 0 4px 20px rgba(0,0,0,.22); }
    h1, h2, h3 { margin: 0 0 10px 0; }
    h2 { margin-top: 18px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid #23305f; vertical-align: top; }
    th { color: #c7d2fe; font-weight: 600; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .badge { display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
    .running { background: #1d4ed8; color: white; }
    .completed { background: #065f46; color: white; }
    .pending { background: #374151; color: white; }
    .failed { background: #991b1b; color: white; }
    .bar { width: 220px; height: 10px; background: #1f2a53; border-radius: 999px; overflow: hidden; }
    .bar > span { display: block; height: 100%; background: linear-gradient(90deg, #22c55e, #10b981); }
    .small { font-size: 12px; color: #cbd5e1; }
    .section { margin-top: 24px; }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1>📖 Cartha Bible Worker Dashboard</h1>
    <p class=\"muted\">Local live view of queue workers, claimed chapters, and merge status.</p>
    <div id=\"app\">Loading…</div>
  </div>
<script>
async function refresh() {
  const res = await fetch('/api/status');
  const data = await res.json();
  const summaryMap = Object.fromEntries((data.queue.summary || []).map(r => [r.status, r.count]));
  const running = data.queue.running || [];
  const ready = data.queue.ready || [];
  const failed = data.queue.failed || [];
  const commits = data.recent_commits || [];
  const mergeLoops = data.merge_loops || [];

  const cards = `
    <div class=\"grid cards\">
      <div class=\"card\"><h3>Main</h3><div class=\"mono\">${data.main_branch}@${data.main_head}</div><div class=\"small\">Updated ${data.generated_at}</div></div>
      <div class=\"card\"><h3>Running jobs</h3><div class=\"mono\">${summaryMap.running || 0}</div></div>
      <div class=\"card\"><h3>Completed jobs</h3><div class=\"mono\">${summaryMap.completed || 0}</div></div>
      <div class=\"card\"><h3>Pending jobs</h3><div class=\"mono\">${summaryMap.pending || 0}</div></div>
      <div class=\"card\"><h3>Ready to merge</h3><div class=\"mono\">${ready.length}</div></div>
      <div class=\"card\"><h3>Failed jobs</h3><div class=\"mono\">${failed.length}</div></div>
      <div class=\"card\"><h3>Merge loops</h3><div class=\"mono\">${mergeLoops.length}</div></div>
    </div>`;

  const runningRows = running.map(job => `
    <tr>
      <td><span class=\"badge running\">${job.worker_id || 'worker'}</span><div class=\"small mono\">${job.worker_process ? 'pid ' + job.worker_process.pid : 'no live pid seen'}</div></td>
      <td class=\"mono\">${job.phase}</td>
      <td class=\"mono\">${job.book_code} ${job.chapter}</td>
      <td>
        <div>${job.written || 0}/${job.verse_count}</div>
        <div class=\"bar\"><span style=\"width:${job.percent || 0}%\"></span></div>
        <div class=\"small\">${job.percent || 0}%</div>
      </td>
      <td class=\"small mono\">${job.latest_file || ''}<br>${job.latest_mtime || ''}</td>
      <td class=\"small mono\">${job.claimed_at || ''}</td>
    </tr>`).join('') || '<tr><td colspan=\"6\" class=\"small\">No running jobs.</td></tr>';

  const readyRows = ready.map(job => `
    <tr>
      <td class=\"mono\">${job.book_code} ${job.chapter}</td>
      <td class=\"mono\">${job.commit_sha ? job.commit_sha.slice(0,7) : ''}</td>
      <td class=\"small mono\">${job.completed_at || ''}</td>
    </tr>`).join('') || '<tr><td colspan=\"3\" class=\"small\">No ready jobs.</td></tr>';

  const failedRows = failed.map(job => `
    <tr>
      <td class=\"mono\">${job.book_code} ${job.chapter}</td>
      <td class=\"small mono\">${(job.last_error || '').slice(0,220)}</td>
    </tr>`).join('') || '<tr><td colspan=\"2\" class=\"small\">No failed jobs.</td></tr>';

  const commitRows = commits.map(c => `<tr><td class=\"mono\">${c.sha}</td><td>${c.message}</td></tr>`).join('');

  document.getElementById('app').innerHTML = `
    ${cards}
    <div class=\"section card\">
      <h2>🏃 Running workers</h2>
      <table><thead><tr><th>Worker</th><th>Phase</th><th>Chapter</th><th>Progress</th><th>Latest file</th><th>Claimed</th></tr></thead><tbody>${runningRows}</tbody></table>
    </div>
    <div class=\"section grid cards\">
      <div class=\"card\">
        <h2>📥 Ready to merge</h2>
        <table><thead><tr><th>Job</th><th>Commit</th><th>Completed</th></tr></thead><tbody>${readyRows}</tbody></table>
      </div>
      <div class=\"card\">
        <h2>⚠️ Failed jobs</h2>
        <table><thead><tr><th>Job</th><th>Error</th></tr></thead><tbody>${failedRows}</tbody></table>
      </div>
    </div>
    <div class=\"section card\">
      <h2>🧾 Recent main commits</h2>
      <table><thead><tr><th>SHA</th><th>Message</th></tr></thead><tbody>${commitRows}</tbody></table>
    </div>`;
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            payload = json.dumps(build_status(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path == "/" or path == "/index.html":
            payload = html_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Dashboard running at http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
