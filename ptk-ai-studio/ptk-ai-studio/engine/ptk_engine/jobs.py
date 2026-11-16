"""Fila de processamento em segundo plano: progresso, cancelar, pausar fila, repetir, historico."""
import threading, time, traceback, queue
from typing import Callable, Dict
from .ffmpeg_core import Runner, Cancelled

class Job:
    def __init__(self, jid, kind, fn, params):
        self.id, self.kind, self.fn, self.params = jid, kind, fn, params
        self.status, self.progress, self.error, self.output = "pendente", 0.0, None, None
        self.runner = Runner(); self.created = time.time()
    def as_dict(self):
        return {"id": self.id, "kind": self.kind, "status": self.status, "progress": self.progress,
                "error": self.error, "output": self.output}

class JobQueue:
    def __init__(self, workers=1, on_update: Callable = None):
        self.jobs: Dict[int, Job] = {}; self._q = queue.Queue(); self._n = 0
        self._lock = threading.Lock(); self._paused = threading.Event()
        self.on_update = on_update or (lambda j: None)
        for _ in range(workers):
            threading.Thread(target=self._work, daemon=True).start()

    def submit(self, kind, fn, **params) -> int:
        with self._lock:
            self._n += 1; job = Job(self._n, kind, fn, params); self.jobs[job.id] = job
        self._q.put(job.id); self.on_update(job); return job.id

    def _work(self):
        while True:
            jid = self._q.get(); job = self.jobs[jid]
            while self._paused.is_set(): time.sleep(0.1)
            if job.status == "cancelado": continue
            job.status = "processando"; self.on_update(job)
            def prog(p, j=job): j.progress = p; self.on_update(j)
            try:
                job.output = job.fn(runner=job.runner, on_progress=prog, **job.params)
                job.status, job.progress = "concluido", 1.0
            except Cancelled:
                job.status = "cancelado"
            except Exception as e:  # um erro nunca derruba o aplicativo
                job.status, job.error = "erro", f"{type(e).__name__}: {e}"
            self.on_update(job)

    def cancel(self, jid):
        job = self.jobs[jid]
        if job.status == "pendente": job.status = "cancelado"; self.on_update(job)
        elif job.status == "processando": job.runner.cancel()

    def retry(self, jid) -> int:
        j = self.jobs[jid]
        if j.status not in ("erro", "cancelado"): raise ValueError("So tarefas com erro/canceladas.")
        return self.submit(j.kind, j.fn, **j.params)

    def pause_queue(self): self._paused.set()      # nao inicia novas tarefas; a em curso termina
    def resume_queue(self): self._paused.clear()
    def list(self): return [j.as_dict() for j in self.jobs.values()]
