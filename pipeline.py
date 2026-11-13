"""YouTube link -> scored vertical shorts. 100% free stack:
yt-dlp (download + 'most replayed' heatmap), faster-whisper (transcript),
numpy (audio energy), FFmpeg (cut/9:16/captions), optional Gemini free tier (hook rerank).

CLI:  python pipeline.py "https://youtube.com/watch?v=..." --top 5
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import wave

import numpy as np

import scoring

HOP = 0.5  # seconds per audio-energy sample
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
FONT_URLS = [
    "https://github.com/notofonts/devanagari/raw/main/fonts/NotoSansDevanagari/hinted/ttf/NotoSansDevanagari-Bold.ttf",
    "https://github.com/google/fonts/raw/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf",
]


def _find_ffmpeg():
    """System ffmpeg if present, else the one bundled via pip (imageio-ffmpeg). No manual install needed."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


FFMPEG = _find_ffmpeg()


def ensure_font(log=None):
    """Hindi captions need a Devanagari font. Download once (free, OFL licence); skip silently if offline."""
    import urllib.request

    os.makedirs(FONT_DIR, exist_ok=True)
    if any(f.lower().endswith(".ttf") for f in os.listdir(FONT_DIR)):
        return
    for i, url in enumerate(FONT_URLS):
        try:
            urllib.request.urlretrieve(url, os.path.join(FONT_DIR, f"NotoSansDevanagari{i}.ttf"))
            return
        except Exception:
            continue
    if log:
        log("Hindi font download nahi hua; Hindi captions mein boxes aa sakte hain (English theek rahega)")


def log_default(msg):
    print(msg, flush=True)


MAX_MINUTES = int(os.environ.get("MAX_MINUTES", "60"))


def check_duration(seconds):
    if seconds and seconds > MAX_MINUTES * 60:
        raise RuntimeError(f"Video bahut lamba hai ({int(seconds // 60)} min). Max {MAX_MINUTES} minute ka video chalega.")


def file_duration(path):
    import re
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0


# ---------- 1. download ----------
def download(url, workdir, log=log_default):
    import yt_dlp

    os.makedirs(workdir, exist_ok=True)
    opts = {
        "format": "bv*[height<=720]+ba/b[height<=720]/b",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(workdir, "source.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "ffmpeg_location": FFMPEG,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        pre = ydl.extract_info(url, download=False)
        check_duration(pre.get("duration") or 0)
        info = ydl.extract_info(url, download=True)
    files = [f for f in glob.glob(os.path.join(workdir, "source.*")) if not f.endswith((".part", ".wav", ".json"))]
    if not files:
        raise RuntimeError("Download failed: no video file found")
    meta = {
        "title": info.get("title", ""),
        "duration": info.get("duration") or 0,
        "heatmap": info.get("heatmap"),  # None if video has too few views
    }
    log(f"Downloaded: {meta['title']} ({meta['duration']}s), heatmap={'yes' if meta['heatmap'] else 'no'}")
    return files[0], meta


# ---------- 2. transcript ----------
def transcribe(video_path, language=None, log=log_default):
    from faster_whisper import WhisperModel

    size = os.environ.get("WHISPER_MODEL", "small")
    log(f"Transcribing with faster-whisper ({size})... pehli baar model download hoga")
    model = WhisperModel(size, device="auto", compute_type="auto")
    segs, info = model.transcribe(video_path, language=language, vad_filter=True)
    out = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segs]
    log(f"Transcript ready: {len(out)} segments, language={info.language}")
    return out


# ---------- 3. audio energy ----------
def audio_envelope(video_path, workdir):
    wav = os.path.join(workdir, "audio.wav")
    subprocess.run(
        [FFMPEG, "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", wav],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    with wave.open(wav) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    step = int(sr * HOP)
    n = len(data) // step
    if n == 0:
        return np.zeros(1)
    frames = data[: n * step].reshape(n, step)
    return np.sqrt((frames ** 2).mean(axis=1))


# ---------- 4. candidates + scoring ----------
def make_candidates(segments, min_len=20, max_len=55):
    cands = []
    n = len(segments)
    for i in range(n):
        start = segments[i]["start"]
        fallback = None
        for j in range(i, n):
            d = segments[j]["end"] - start
            if d < min_len:
                continue
            if d > max_len:
                break
            if fallback is None:
                fallback = j
            if segments[j]["text"].rstrip()[-1:] in ".?!।":
                cands.append((i, j))
        if fallback is not None and not any(c[0] == i for c in cands):
            cands.append((i, fallback))
    return cands


def overlap(a, b):
    inter = max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    return inter / min(a["end"] - a["start"], b["end"] - b["start"])


def gemini_hook_scores(texts, log=log_default):
    """Optional: free Gemini API key in env GEMINI_API_KEY. Returns list of 0..1 or None."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    import requests

    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    listing = "\n".join(f"{i}: {t[:400]}" for i, t in enumerate(texts))
    prompt = (
        "You rate short-video clips for virality (Hindi/Hinglish/English). For each numbered clip "
        "give a hook score 0-10 (strong first line, curiosity, emotion, self-contained). "
        'Reply ONLY with JSON: {"scores":[...]} in the same order.\n\n' + listing
    )
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=60,
        )
        r.raise_for_status()
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        scores = json.loads(txt)["scores"]
        if len(scores) != len(texts):
            return None
        return [max(0.0, min(1.0, float(s) / 10)) for s in scores]
    except Exception as e:  # never break the pipeline for the optional LLM
        log(f"Gemini skipped: {e}")
        return None


def pick_clips(segments, meta, env, top=5, log=log_default):
    cands = []
    for i, j in make_candidates(segments):
        start, end = segments[i]["start"], segments[j]["end"]
        text = " ".join(s["text"] for s in segments[i : j + 1])
        comp = scoring.components(text, start, end, meta.get("heatmap"), env, HOP)
        cands.append({"start": start, "end": end, "text": text, "comp": comp, "score": scoring.combine(comp)})
    cands.sort(key=lambda c: c["score"], reverse=True)

    # optional LLM rerank of the best 20
    head = cands[:20]
    llm = gemini_hook_scores([c["text"] for c in head], log) if head else None
    if llm:
        log("Gemini hook rerank applied")
        for c, h in zip(head, llm):
            c["comp"]["hook"] = 0.5 * c["comp"]["hook"] + 0.5 * h
            c["score"] = scoring.combine(c["comp"])
        cands.sort(key=lambda c: c["score"], reverse=True)

    chosen = []
    for c in cands:
        if all(overlap(c, k) < 0.3 for k in chosen):
            chosen.append(c)
        if len(chosen) >= top:
            break
    return chosen


# ---------- 5. render ----------
def _ts(t):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_ass(path, segments, start, end):
    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,"
        "Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,"
        "MarginL,MarginR,MarginV,Encoding\n"
        "Style: Default,Noto Sans Devanagari,68,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,5,1,2,60,60,420,1\n\n"
        "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )
    lines = []
    for s in segments:
        if s["end"] <= start or s["start"] >= end:
            continue
        a, b = max(s["start"], start) - start, min(s["end"], end) - start
        text = s["text"].replace("\n", " ")
        # wrap every ~4 words so captions stay readable on a phone
        w = text.split()
        text = "\\N".join(" ".join(w[k : k + 4]) for k in range(0, len(w), 4))
        lines.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},Default,,0,0,0,,{text}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(lines) + "\n")


def render_clip(video, segments, clip, outdir, idx, captions=True):
    name = f"clip_{idx:02d}"
    ass = f"{name}.ass"
    write_ass(os.path.join(outdir, ass), segments, clip["start"], clip["end"])
    vf = (
        "[0:v]split[a][b];"
        "[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=6:2,scale=1080:1920[bg];"
        "[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )
    for f in glob.glob(os.path.join(FONT_DIR, "*.ttf")):
        shutil.copy(f, outdir)
    vf += f",subtitles={ass}:fontsdir=.[v]" if captions else "[v]"
    out = f"{name}.mp4"
    cmd = [
        FFMPEG, "-y", "-ss", f"{clip['start']:.2f}", "-i", os.path.abspath(video),
        "-t", f"{clip['end'] - clip['start']:.2f}", "-filter_complex", vf, "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-movflags", "+faststart", out,
    ]
    subprocess.run(cmd, cwd=outdir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return out


# ---------- orchestrator ----------
def run(url, outdir, top=5, language=None, captions=True, log=log_default, local_file=None):
    """url = YouTube link, or pass local_file= path of an uploaded video."""
    os.makedirs(outdir, exist_ok=True)
    if captions:
        ensure_font(log)
    if local_file:
        dur = file_duration(local_file)
        check_duration(dur)
        video, meta = local_file, {"title": os.path.basename(local_file), "duration": dur, "heatmap": None}
        log("Video mil gaya (upload). Most replayed data upload par nahi milta, baaki signals se score banega.")
    else:
        video, meta = download(url, outdir, log)
    segments = transcribe(video, language, log)
    log("Audio energy nikal raha hu...")
    env = audio_envelope(video, outdir)
    log("Clips chun aur score kar raha hu...")
    chosen = pick_clips(segments, meta, env, top, log)
    results = []
    for n, c in enumerate(chosen, 1):
        log(f"Clip {n}/{len(chosen)} render ho raha hai...")
        f = render_clip(video, segments, c, outdir, n, captions)
        results.append({
            "file": f, "start": round(c["start"], 1), "end": round(c["end"], 1),
            "score": c["score"], "text": c["text"],
            "breakdown": {k: (None if v is None else round(v * 100)) for k, v in c["comp"].items()},
        })
    with open(os.path.join(outdir, "results.json"), "w", encoding="utf-8") as f:
        json.dump({"title": meta["title"], "clips": results}, f, ensure_ascii=False, indent=2)
    log("Done!")
    return {"title": meta["title"], "clips": results}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--lang", default=None, help="hi, en ... (default auto)")
    ap.add_argument("--out", default="output/cli")
    ap.add_argument("--no-captions", action="store_true")
    a = ap.parse_args()
    res = run(a.url, a.out, a.top, a.lang, not a.no_captions)
    for c in res["clips"]:
        print(f"[{c['score']:5.1f}] {c['start']}-{c['end']}s  {c['file']}  {c['breakdown']}")
