"""Armazenamento local em SQLite: projetos, midias, historico de edicao e tarefas."""
import json, sqlite3, time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, name TEXT NOT NULL, created REAL, updated REAL, settings TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS media(id INTEGER PRIMARY KEY, project_id INTEGER, path TEXT, kind TEXT, info TEXT, added REAL);
CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY, project_id INTEGER, action TEXT, detail TEXT, at REAL);
CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, project_id INTEGER, kind TEXT, params TEXT, status TEXT, progress REAL DEFAULT 0, error TEXT, output TEXT, created REAL, finished REAL);
"""

class DB:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.executescript(SCHEMA); self.c.commit()

    def new_project(self, name):
        t = time.time()
        cur = self.c.execute("INSERT INTO projects(name,created,updated) VALUES(?,?,?)", (name, t, t))
        self.c.commit(); self.log(cur.lastrowid, "criado", name)
        return cur.lastrowid

    def list_projects(self):
        return [dict(r) for r in self.c.execute("SELECT * FROM projects ORDER BY updated DESC")]

    def add_media(self, project_id, path, kind, info):
        cur = self.c.execute("INSERT INTO media(project_id,path,kind,info,added) VALUES(?,?,?,?,?)",
                             (project_id, path, kind, json.dumps(info), time.time()))
        self.c.execute("UPDATE projects SET updated=? WHERE id=?", (time.time(), project_id))
        self.c.commit(); self.log(project_id, "midia_importada", path)
        return cur.lastrowid

    def list_media(self, project_id):
        return [dict(r) for r in self.c.execute("SELECT * FROM media WHERE project_id=?", (project_id,))]

    def log(self, project_id, action, detail=""):
        self.c.execute("INSERT INTO history(project_id,action,detail,at) VALUES(?,?,?,?)",
                       (project_id, action, detail, time.time())); self.c.commit()

    def history(self, project_id):
        return [dict(r) for r in self.c.execute("SELECT * FROM history WHERE project_id=? ORDER BY id", (project_id,))]

    def save_settings(self, project_id, settings: dict):
        self.c.execute("UPDATE projects SET settings=?, updated=? WHERE id=?",
                       (json.dumps(settings), time.time(), project_id)); self.c.commit()
