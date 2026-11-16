"""Nucleo FFmpeg: localizacao de binarios, probe e execucao com progresso/cancelamento."""
import json, os, shutil, subprocess, threading
from pathlib import Path
from typing import Callable, Optional

class FFmpegError(RuntimeError):
    pass

class Cancelled(Exception):
    pass

def find_binary(name: str) -> str:
    """Procura primeiro em PTK_FFMPEG_DIR (binario embutido no instalador), depois no PATH."""
    d = os.environ.get("PTK_FFMPEG_DIR")
    if d:
        for ext in ("", ".exe"):
            p = Path(d) / (name + ext)
            if p.exists():
                return str(p)
    p = shutil.which(name)
    if not p:
        raise FFmpegError(f"{name} nao encontrado. Instale o FFmpeg ou defina PTK_FFMPEG_DIR.")
    return p

def safe_input(path: str) -> str:
    """Valida caminho de entrada: precisa existir, ser arquivo e nao conter bytes nulos."""
    if "\x00" in path:
        raise ValueError("Caminho invalido.")
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")
    return str(p)

def safe_output(path: str, overwrite: bool = False) -> str:
    """Valida saida: nunca sobrescreve arquivo existente sem autorizacao explicita."""
    if "\x00" in path:
        raise ValueError("Caminho invalido.")
    p = Path(path).expanduser().resolve()
    if p.exists() and not overwrite:
        raise FileExistsError(f"Arquivo ja existe (nao sera sobrescrito): {p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)

def probe(path: str) -> dict:
    path = safe_input(path)
    r = subprocess.run([find_binary("ffprobe"), "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise FFmpegError(r.stderr.strip() or "ffprobe falhou")
    data = json.loads(r.stdout)
    v = next((s for s in data.get("streams", []) if s["codec_type"] == "video"), None)
    a = next((s for s in data.get("streams", []) if s["codec_type"] == "audio"), None)
    fps = None
    if v and v.get("avg_frame_rate", "0/0") not in ("0/0", "0"):
        n, d = v["avg_frame_rate"].split("/")
        fps = round(int(n) / int(d), 3) if int(d) else None
    return {
        "path": path,
        "duration": float(data["format"].get("duration", 0) or 0),
        "size": int(data["format"].get("size", 0) or 0),
        "has_video": v is not None, "has_audio": a is not None,
        "width": v.get("width") if v else None, "height": v.get("height") if v else None,
        "fps": fps, "video_codec": v.get("codec_name") if v else None,
        "audio_codec": a.get("codec_name") if a else None,
    }

class Runner:
    """Executa ffmpeg em subprocesso, le progresso e permite cancelar com seguranca."""
    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def run(self, args: list, duration: float = 0.0,
            on_progress: Optional[Callable[[float], None]] = None):
        cmd = [find_binary("ffmpeg"), "-hide_banner", "-nostdin", "-y",
               "-progress", "pipe:1", "-nostats"] + args
        out_path = args[-1]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        err_lines = []
        t = threading.Thread(target=lambda: err_lines.extend(self.proc.stderr), daemon=True)
        t.start()
        for line in self.proc.stdout:
            if line.startswith("out_time_us=") and duration > 0 and on_progress:
                try:
                    sec = int(line.split("=")[1]) / 1_000_000
                    on_progress(max(0.0, min(1.0, sec / duration)))
                except ValueError:
                    pass
        rc = self.proc.wait()
        t.join(timeout=2)
        for stream in (self.proc.stdout, self.proc.stderr):
            try: stream.close()
            except Exception: pass
        if self._cancel.is_set():
            try:
                if os.path.exists(out_path):
                    os.remove(out_path)  # remove apenas o arquivo parcial que nos criamos
            except OSError:
                pass
            raise Cancelled()
        if rc != 0:
            raise FFmpegError("".join(err_lines[-15:]).strip() or f"ffmpeg falhou ({rc})")
        if on_progress:
            on_progress(1.0)
