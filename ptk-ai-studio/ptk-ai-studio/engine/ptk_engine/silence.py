"""Deteccao e remocao de silencios."""
import re, subprocess
from typing import List, Tuple
from .ffmpeg_core import Runner, probe, safe_input, safe_output, find_binary, FFmpegError

def detect_silences(src, noise_db=-35.0, min_dur=0.5) -> List[Tuple[float, float]]:
    src = safe_input(src)
    r = subprocess.run([find_binary("ffmpeg"), "-hide_banner", "-nostdin", "-i", src, "-af",
                        f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    total = probe(src)["duration"]
    if len(starts) > len(ends): ends.append(total)
    return list(zip(starts, ends))

def keep_segments(silences, total, pad=0.08) -> List[Tuple[float, float]]:
    segs, cur = [], 0.0
    for s, e in silences:
        s2 = max(cur, s + pad)
        if s2 - cur > 0.05: segs.append((cur, s2))
        cur = max(cur, e - pad)
    if total - cur > 0.05: segs.append((cur, total))
    return segs

def remove_silence(src, dst, noise_db=-35.0, min_dur=0.5, runner=None, on_progress=None,
                   overwrite=False, dry_run=False):
    """dry_run=True devolve apenas os trechos que seriam mantidos (previa para aprovar/rejeitar)."""
    src = safe_input(src)
    info = probe(src)
    if not info["has_audio"]: raise FFmpegError("Sem trilha de audio para detectar silencio.")
    keep = keep_segments(detect_silences(src, noise_db, min_dur), info["duration"])
    if dry_run: return keep
    dst = safe_output(dst, overwrite)
    if not keep: raise FFmpegError("Todo o audio foi considerado silencio; ajuste o limiar.")
    parts, labels = [], ""
    for n, (a, b) in enumerate(keep):
        if info["has_video"]:
            parts.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{n}]")
            labels += f"[v{n}]"
        parts.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{n}]")
        labels += f"[a{n}]"
    v = 1 if info["has_video"] else 0
    fc = ";".join(parts) + f";{labels}concat=n={len(keep)}:v={v}:a=1" + ("[v][a]" if v else "[a]")
    args = ["-i", src, "-filter_complex", fc] + (["-map", "[v]"] if v else []) + ["-map", "[a]"]
    if v: args += ["-c:v", "libx264", "-preset", "veryfast"]
    args += ["-c:a", "aac", dst]
    (runner or Runner()).run(args, sum(b - a for a, b in keep), on_progress)
    return dst
