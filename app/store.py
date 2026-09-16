import json
import sqlite3
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.db = directory / "studio.sqlite3"
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            con.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, project_id TEXT, body TEXT NOT NULL)")

    def connect(self):
        con = sqlite3.connect(self.db, timeout=15)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def projects(self):
        with self.connect() as con:
            rows = con.execute("SELECT body FROM projects").fetchall()
        return sorted((json.loads(r[0]) for r in rows), key=lambda p: p["updated_at"], reverse=True)

    def get_project(self, pid):
        with self.connect() as con:
            row = con.execute("SELECT body FROM projects WHERE id=?", (pid,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_project(self, project, expected_version=None):
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            if expected_version is not None:
                row = con.execute("SELECT body FROM projects WHERE id=?", (project["id"],)).fetchone()
                if not row or json.loads(row[0])["version"] != expected_version:
                    return False
            con.execute("INSERT OR REPLACE INTO projects VALUES (?, ?)", (project["id"], json.dumps(project)))
        return True

    def save_job(self, job):
        with self.connect() as con:
            con.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?, ?)", (job["id"], job["project_id"], json.dumps(job)))

    def get_job(self, jid):
        with self.connect() as con:
            row = con.execute("SELECT body FROM jobs WHERE id=?", (jid,)).fetchone()
        return json.loads(row[0]) if row else None

    def jobs(self, pid=None):
        with self.connect() as con:
            rows = con.execute("SELECT body FROM jobs WHERE project_id=?", (pid,)).fetchall() if pid else con.execute("SELECT body FROM jobs").fetchall()
        return sorted((json.loads(r[0]) for r in rows), key=lambda j: j["created_at"], reverse=True)

    def recover_jobs(self):
        for job in self.jobs():
            if job["status"] in ("queued", "rendering"):
                job.update(status="failed", error="服务已重启，上次导出中断。请重新导出。")
                self.save_job(job)
