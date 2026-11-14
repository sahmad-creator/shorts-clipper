"""Shorts Clipper website. Run: python app.py  (opens http://localhost:5000)
Hosting: works on any server (see Dockerfile / README). One video is processed at a time; others wait in line."""
import os
import shutil
import threading
import time
import traceback
import uuid

from flask import Flask, jsonify, request, send_from_directory

import pipeline

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
KEEP_HOURS = float(os.environ.get("KEEP_HOURS", "6"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "500"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
JOBS = {}
QUEUE = []
LOCK = threading.Lock()   # only one heavy job at a time
QLOCK = threading.Lock()


def friendly(e):
    m = str(e)
    low = m.lower()
    if "sign in to confirm" in low or "not a bot" in low or "player response" in low or "http error 403" in low or "http error 429" in low:
        return "YouTube ne server ko block kiya. Is video ko apne PC se chalao ya 'Upload' tab mein video file daalo."
    if "private" in low or "unavailable" in low:
        return "Ye video private ya unavailable hai."
    if "unsupported url" in low or "is not a valid url" in low:
        return "Ye link sahi nahi lag raha. Poora YouTube link paste karo."
    if "no such file" in low and "ffmpeg" in low:
        return "FFmpeg nahi mila. Server setup check karo."
    return m[:300]


def worker(job_id, url, top, lang, captions, local_file, title=None):
    job = JOBS[job_id]
    with QLOCK:
        QUEUE.append(job_id)
    with LOCK:
        with QLOCK:
            QUEUE.remove(job_id)
        job["status"] = "running"
        job["log"].append("Shuru ho gaya...")
        try:
            job["result"] = pipeline.run(url, os.path.join(OUT, job_id), top, lang, captions,
                                         lambda m: job["log"].append(m), local_file)
            if title and job["result"]:
                job["result"]["title"] = title
            job["status"] = "done"
        except Exception as e:
            traceback.print_exc()
            job["status"] = "error"
            job["error"] = friendly(e)
        finally:
            if local_file and os.path.exists(local_file):
                try:
                    os.remove(local_file)
                except OSError:
                    pass


def cleanup_loop():
    while True:
        time.sleep(600)
        cutoff = time.time() - KEEP_HOURS * 3600
        if os.path.isdir(OUT):
            for d in os.listdir(OUT):
                p = os.path.join(OUT, d)
                if os.path.isdir(p) and os.path.getmtime(p) < cutoff:
                    shutil.rmtree(p, ignore_errors=True)
                    JOBS.pop(d, None)


def new_job(url, top, lang, captions, local_file=None, title=None):
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {"status": "queued", "log": [], "result": None}
    threading.Thread(target=worker, args=(job_id, url, top, lang, captions, local_file, title), daemon=True).start()
    return job_id


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.post("/api/start")
def start():
    d = request.get_json(force=True)
    url = (d.get("url") or "").strip()
    if "youtu" not in url:
        return jsonify(error="Valid YouTube link daalo (youtube.com ya youtu.be)"), 400
    top = max(1, min(12, int(d.get("top", 5))))
    return jsonify(id=new_job(url, top, d.get("lang") or None, bool(d.get("captions", True))))


@app.post("/api/upload")
def upload():
    f = request.files.get("video")
    if not f or not f.filename:
        return jsonify(error="Video file chuno"), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mp3", ".wav", ".m4a"}:
        return jsonify(error="Sirf mp4, mov, mkv, webm jaisi video files chalengi"), 400
    job_dir = os.path.join(OUT, "_uploads")
    os.makedirs(job_dir, exist_ok=True)
    path = os.path.join(job_dir, uuid.uuid4().hex[:8] + ext)
    f.save(path)
    top = max(1, min(12, int(request.form.get("top", 5))))
    return jsonify(id=new_job(None, top, request.form.get("lang") or None,
                              request.form.get("captions", "1") == "1", path, f.filename))


@app.errorhandler(413)
def too_big(_):
    return jsonify(error=f"File bahut badi hai. Max {MAX_UPLOAD_MB} MB."), 413


@app.get("/api/status/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify(error="Ye job nahi mila (shayad purana ho gaya). Dobara try karo."), 404
    with QLOCK:
        pos = QUEUE.index(job_id) + 1 if job_id in QUEUE else 0
    return jsonify(**job, queue_position=pos)


@app.get("/clips/<job_id>/<path:fn>")
def clips(job_id, fn):
    if not fn.endswith(".mp4") or fn.startswith("source"):
        return "", 404
    return send_from_directory(os.path.join(OUT, job_id), fn)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    threading.Thread(target=cleanup_loop, daemon=True).start()
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "127.0.0.1")
    if not os.environ.get("NO_BROWSER") and host == "127.0.0.1":
        threading.Timer(1.5, lambda: __import__("webbrowser").open(f"http://localhost:{port}")).start()
    print(f"Browser mein kholo: http://localhost:{port}  (band karne ke liye Ctrl+C)")
    app.run(host=host, port=port, debug=False, threaded=True)
