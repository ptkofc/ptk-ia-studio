"""Ponte JSON-lines (stdin/stdout) entre a interface Tauri e o motor. Um comando por linha."""
import json, os, sys, threading
from pathlib import Path
from . import tools, silence
from .ffmpeg_core import probe
from .db import DB
from .jobs import JobQueue

_out = threading.Lock()
def emit(obj):
    with _out:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n"); sys.stdout.flush()

JOB_TOOLS = {"cut": tools.cut, "extract_audio": tools.extract_audio, "speed": tools.change_speed,
             "resize": tools.resize, "compress": tools.compress, "gif": tools.to_gif,
             "concat": tools.concat, "export": tools.export, "remove_silence": silence.remove_silence}

def main():
    data_dir = Path(os.environ.get("PTK_DATA_DIR", Path.home() / ".ptk-ai-studio"))
    db = DB(data_dir / "ptk.db")
    q = JobQueue(on_update=lambda j: emit({"event": "job", "job": j.as_dict()}))
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        rid = None
        try:
            req = json.loads(line); rid = req.get("id"); cmd = req["cmd"]; a = req.get("args", {})
            if cmd == "ping": res = "pong"
            elif cmd == "probe": res = probe(**a)
            elif cmd == "thumbnail": res = tools.thumbnail(**a)
            elif cmd == "detect_silences": res = silence.detect_silences(**a)
            elif cmd == "silence_preview": res = silence.remove_silence(dst="", dry_run=True, **a)
            elif cmd == "job": res = q.submit(a["tool"], JOB_TOOLS[a["tool"]], **a["params"])
            elif cmd == "jobs": res = q.list()
            elif cmd == "cancel": q.cancel(a["job"]); res = True
            elif cmd == "retry": res = q.retry(a["job"])
            elif cmd == "pause_queue": q.pause_queue(); res = True
            elif cmd == "resume_queue": q.resume_queue(); res = True
            elif cmd == "new_project": res = db.new_project(a["name"])
            elif cmd == "projects": res = db.list_projects()
            elif cmd == "import_media":
                info = probe(a["path"]); kind = "video" if info["has_video"] else "audio"
                res = db.add_media(a["project"], info["path"], kind, info)
            elif cmd == "media": res = db.list_media(a["project"])
            elif cmd == "history": res = db.history(a["project"])
            else: raise ValueError(f"Comando desconhecido: {cmd}")
            emit({"id": rid, "ok": True, "result": res})
        except Exception as e:  # nenhum erro derruba o processo
            emit({"id": rid, "ok": False, "error": f"{type(e).__name__}: {e}"})

if __name__ == "__main__": main()
