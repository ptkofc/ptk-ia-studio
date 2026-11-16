"""Ferramentas de video/audio sobre FFmpeg. Todas retornam o caminho de saida."""
import re, subprocess
from typing import Callable, List, Optional, Tuple
from .ffmpeg_core import Runner, probe, safe_input, safe_output, find_binary, FFmpegError

Progress = Optional[Callable[[float], None]]

ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
HEIGHTS = {"480p": 480, "720p": 720, "1080p": 1080, "1440p": 1440, "4k": 2160}
CODECS = {"mp4": ("libx264", "aac"), "mov": ("libx264", "aac"), "webm": ("libvpx-vp9", "libopus")}

def _runner(r: Optional[Runner]) -> Runner:
    return r or Runner()

def cut(src, dst, start: float, end: float, runner=None, on_progress: Progress = None, overwrite=False):
    src, dst = safe_input(src), safe_output(dst, overwrite)
    if end <= start:
        raise ValueError("Fim deve ser maior que inicio.")
    _runner(runner).run(["-ss", str(start), "-to", str(end), "-i", src,
                         "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", dst],
                        end - start, on_progress)
    return dst

def extract_audio(src, dst, runner=None, on_progress: Progress = None, overwrite=False):
    src, dst = safe_input(src), safe_output(dst, overwrite)
    info = probe(src)
    if not info["has_audio"]:
        raise FFmpegError("O arquivo nao possui trilha de audio.")
    ext = dst.lower().rsplit(".", 1)[-1]
    codec = {"mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac", "m4a": "aac"}.get(ext, "aac")
    _runner(runner).run(["-i", src, "-vn", "-c:a", codec, dst], info["duration"], on_progress)
    return dst

def change_speed(src, dst, factor: float, runner=None, on_progress: Progress = None, overwrite=False):
    if not 0.25 <= factor <= 4:
        raise ValueError("Velocidade deve estar entre 0.25x e 4x.")
    src, dst = safe_input(src), safe_output(dst, overwrite)
    info = probe(src)
    # atempo aceita 0.5..2 por filtro; encadeia quando necessario
    chain, f = [], factor
    while f > 2.0: chain.append(2.0); f /= 2.0
    while f < 0.5: chain.append(0.5); f /= 0.5
    chain.append(f)
    atempo = ",".join(f"atempo={x:.4f}" for x in chain)
    args = ["-i", src, "-filter:v", f"setpts=PTS/{factor}"]
    args += (["-filter:a", atempo] if info["has_audio"] else ["-an"])
    args += ["-c:v", "libx264", "-preset", "veryfast", dst]
    _runner(runner).run(args, info["duration"] / factor, on_progress)
    return dst

def resize(src, dst, aspect: str = "16:9", height: str = "1080p", runner=None,
           on_progress: Progress = None, overwrite=False):
    """Redimensiona para proporcao alvo com barras (pad) preservando o conteudo."""
    src, dst = safe_input(src), safe_output(dst, overwrite)
    if aspect not in ASPECTS: raise ValueError(f"Proporcao invalida: {aspect}")
    if height not in HEIGHTS: raise ValueError(f"Resolucao invalida: {height}")
    aw, ah = (int(x) for x in aspect.split(":"))
    h = HEIGHTS[height]
    w = int(round(h * aw / ah / 2) * 2); h = int(h // 2 * 2)
    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    info = probe(src)
    _runner(runner).run(["-i", src, "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                         "-c:a", "aac", dst], info["duration"], on_progress)
    return dst

def compress(src, dst, crf: int = 28, runner=None, on_progress: Progress = None, overwrite=False):
    src, dst = safe_input(src), safe_output(dst, overwrite)
    info = probe(src)
    _runner(runner).run(["-i", src, "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
                         "-c:a", "aac", "-b:a", "96k", dst], info["duration"], on_progress)
    return dst

def to_gif(src, dst, start=0.0, duration=5.0, width=480, fps=12, runner=None,
           on_progress: Progress = None, overwrite=False):
    src, dst = safe_input(src), safe_output(dst, overwrite)
    vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"
    _runner(runner).run(["-ss", str(start), "-t", str(duration), "-i", src, "-vf", vf, dst],
                        duration, on_progress)
    return dst

def thumbnail(src, dst, at: float = 1.0, overwrite=False):
    src, dst = safe_input(src), safe_output(dst, overwrite)
    _runner(None).run(["-ss", str(at), "-i", src, "-frames:v", "1", "-q:v", "2", dst])
    return dst

def extract_frames(src, out_pattern, fps: float = 1.0, runner=None, overwrite=False):
    """out_pattern ex.: pasta/frame_%04d.png"""
    src = safe_input(src)
    if "%" not in out_pattern: raise ValueError("Use um padrao como frame_%04d.png")
    safe_output(out_pattern.replace("%04d", "0001"), True)  # so garante a pasta
    _runner(runner).run(["-i", src, "-vf", f"fps={fps}", out_pattern])
    return out_pattern

def concat(sources: List[str], dst, width=1280, height=720, runner=None,
           on_progress: Progress = None, overwrite=False):
    """Une videos reencodando para tamanho comum (funciona mesmo com codecs diferentes)."""
    if len(sources) < 2: raise ValueError("Informe ao menos 2 arquivos.")
    srcs = [safe_input(s) for s in sources]
    dst = safe_output(dst, overwrite)
    infos = [probe(s) for s in srcs]
    total = sum(i["duration"] for i in infos)
    args, parts = [], []
    for n, (s, i) in enumerate(zip(srcs, infos)):
        args += ["-i", s]
        parts.append(f"[{n}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                     f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{n}]")
        if i["has_audio"]:
            parts.append(f"[{n}:a]aresample=44100,aformat=channel_layouts=stereo[a{n}]")
        else:
            parts.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={i['duration']}[a{n}]")
    seq = "".join(f"[v{n}][a{n}]" for n in range(len(srcs)))
    fc = ";".join(parts) + f";{seq}concat=n={len(srcs)}:v=1:a=1[v][a]"
    args += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", dst]
    _runner(runner).run(args, total, on_progress)
    return dst

def export(src, dst, fmt="mp4", height="1080p", fps: Optional[int] = None, crf=23,
           burn_srt: Optional[str] = None, runner=None, on_progress: Progress = None, overwrite=False):
    """Exportacao final com formato, codec, resolucao, FPS, qualidade e legendas opcionais."""
    src, dst = safe_input(src), safe_output(dst, overwrite)
    if fmt not in CODECS: raise ValueError(f"Formato nao suportado: {fmt}")
    if height not in HEIGHTS: raise ValueError(f"Resolucao invalida: {height}")
    vc, ac = CODECS[fmt]
    vf = [f"scale=-2:{HEIGHTS[height]}"]
    if burn_srt:
        srt = safe_input(burn_srt).replace("\\", "/").replace(":", "\\:").replace("'", r"\'")
        vf.append(f"subtitles='{srt}'")
    args = ["-i", src, "-vf", ",".join(vf), "-c:v", vc, "-crf", str(crf)]
    if vc == "libvpx-vp9": args += ["-b:v", "0", "-row-mt", "1"]
    else: args += ["-preset", "veryfast"]
    if fps: args += ["-r", str(fps)]
    args += ["-c:a", ac, dst]
    _runner(runner).run(args, probe(src)["duration"], on_progress)
    return dst
