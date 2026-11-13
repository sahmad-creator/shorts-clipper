"""Virality scoring for candidate clips. Free, no paid APIs.

Each component is normalised to 0..1, then combined with weights into 0..100.
If a component is missing (e.g. no YouTube heatmap), weights are renormalised.
"""
import re
from statistics import mean

import numpy as np

WEIGHTS = {"heat": 0.40, "hook": 0.30, "energy": 0.20, "length": 0.10}

# English + Hinglish/Hindi trigger words that often signal a strong hook
HOOK_WORDS = {
    "secret", "mistake", "never", "always", "truth", "shocking", "crazy", "insane",
    "nobody", "everyone", "stop", "warning", "biggest", "worst", "best", "free",
    "how", "why", "what", "wait", "listen", "imagine", "money", "story",
    "raaz", "rahasya", "sach", "galti", "kabhi", "koi", "sabse", "bada", "pagal",
    "dhyan", "suno", "dekho", "kaise", "kyun", "kya", "paisa", "zindagi", "dard",
    "ishq", "mohabbat", "khabardar", "sirf", "bilkul", "jaanlo", "janlo",
    "राज", "सच", "गलती", "कभी", "सबसे", "सुनो", "देखो", "कैसे", "क्यों", "क्या", "पैसा", "ज़िंदगी",
}
YOU_WORDS = {"you", "your", "tum", "tumhe", "tumhara", "aap", "aapko", "aapka", "तुम", "आप", "तुम्हें", "आपको"}
_word_re = re.compile(r"[\w']+", re.UNICODE)


def words(text):
    return [w.lower() for w in _word_re.findall(text)]


def length_score(d):
    if 20 <= d <= 45:
        return 1.0
    if d < 20:
        return max(0.0, d / 20.0)
    return max(0.0, 1 - (d - 45) / 30.0)


def heatmap_score(heatmap, start, end):
    """YouTube 'Most replayed' data (list of {start_time,end_time,value 0..1})."""
    if not heatmap:
        return None
    vals = [h["value"] for h in heatmap if h["end_time"] > start and h["start_time"] < end]
    if not vals:
        return None
    top = max(h["value"] for h in heatmap) or 1e-6
    return 0.6 * max(vals) / top + 0.4 * mean(vals) / top


def hook_score(text):
    """Heuristic strength of the first ~2 sentences (what the viewer sees first)."""
    sentences = re.split(r"(?<=[.?!।])\s+", text.strip())
    head = " ".join(sentences[:2])
    first = sentences[0] if sentences else ""
    ws = words(head)
    if not ws:
        return 0.0
    s = 0.0
    if "?" in head or "؟" in head:
        s += 0.25
    if re.search(r"\d", head):
        s += 0.15
    if any(w in HOOK_WORDS for w in ws):
        s += 0.25
    if "!" in head:
        s += 0.10
    if any(w in YOU_WORDS for w in ws):
        s += 0.10
    if 0 < len(words(first)) <= 12:
        s += 0.15  # short punchy opener
    return min(1.0, s)


def pace_score(text, duration):
    if duration <= 0:
        return 0.0
    wps = len(words(text)) / duration
    if 2.0 <= wps <= 3.5:
        return 1.0
    if wps < 2.0:
        return max(0.0, wps / 2.0)
    return max(0.0, 1 - (wps - 3.5) / 3.0)


def energy_score(env, hop, start, end, text):
    """env: numpy array of RMS per `hop` seconds for the whole video."""
    if env is None or len(env) == 0:
        return pace_score(text, end - start)
    a, b = int(start / hop), max(int(end / hop), int(start / hop) + 1)
    seg = env[a:b]
    if len(seg) == 0:
        return pace_score(text, end - start)
    ref = float(np.percentile(env, 90)) or 1e-6
    loud = min(1.0, float(0.6 * seg.mean() + 0.4 * seg.max()) / ref)
    return float(0.7 * loud + 0.3 * pace_score(text, end - start))


def components(text, start, end, heatmap, env, hop):
    return {
        "heat": heatmap_score(heatmap, start, end),
        "hook": hook_score(text),
        "energy": energy_score(env, hop, start, end, text),
        "length": length_score(end - start),
    }


def combine(comp):
    used = {k: v for k, v in comp.items() if v is not None}
    total_w = sum(WEIGHTS[k] for k in used)
    score = sum(WEIGHTS[k] * v for k, v in used.items()) / total_w
    return round(score * 100, 1)
