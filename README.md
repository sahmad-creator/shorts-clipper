# Shorts Clipper

Ek website jahan YouTube link paste karo (ya video upload karo), aur tool lambe video se sabse popular hisse chun ke **vertical Shorts** bana deta hai, captions ke saath. Har clip ko **0-100 popularity score** milta hai, score ke hisaab se sorted. Free, koi login ya paid API nahi.

## Apne PC par chalao (sabse aasan)

1. **Python install karo** (ek baar): https://www.python.org/downloads/  
   Windows par install karte waqt **"Add Python to PATH"** tick karna.
2. Upar green **Code > Download ZIP** dabao aur extract karo.
3. **Windows:** `start.bat` par double-click.  
   **Mac:** `start.command` par double-click (na khule to Terminal mein `bash start.sh`).  
   **Linux:** `bash start.sh`
4. Pehli baar sab apne aap install hoga (5-10 minute, FFmpeg aur Hindi font bhi). Phir website browser mein khul jayegi.

## Website ko online karo (kuch download/upload nahi, sab browser mein)

GitHub Pages par ye nahi chalega (video process karne ke liye server chahiye). Do free tareeke:

**1. Render (ek click)**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/sahmad-creator/shorts-clipper)

Button dabao, GitHub se login karo, **Apply** dabao. 5-10 minute mein tera link ban jata hai. Free server kam RAM wala hai, isliye `tiny` Whisper model laga hai (Hindi ki accuracy kam, English theek). Memory error aaye to video chhota rakho.

**2. Hugging Face Spaces (zyada RAM, behtar)**

1. https://huggingface.co/new-space par jao: SDK **Docker**, Blank, Public, Create.
2. Space mein **Files > Add file > Create a new file**, naam `Dockerfile`, aur is repo ki `Dockerfile.hf` ka text paste karo, Commit.
3. Space ki `README.md` ke sabse upar ye daalo:
   ```
   ---
   title: Shorts Clipper
   sdk: docker
   app_port: 7860
   ---
   ```
4. Build hone do (5-10 min), link ban jayega.

**Tez banane ke liye (1 minute ka kaam, free):**
Bina key ke transcript free server par bahut dheema hota hai. Groq ki free Whisper API se wo kuch second mein ho jata hai:
1. https://console.groq.com par Google se login karo, **API Keys > Create API Key**, key copy karo.
2. Render mein apni service kholo: **Environment > Add Environment Variable**: Key `GROQ_API_KEY`, Value wo key. **Save**, service apne aap dobara chalegi.

Phir video chuno, aur kuch hi second mein clips aur score mil jate hain. Download dabane par us clip ka asli 9:16 video ~10 second mein banta hai.

**Free server ki sachchai:**
- Server 15 minute idle rehne par so jata hai, pehla page khulne mein ~50 second lag sakte hain.
- **YouTube aksar server (datacenter) wale IP ko block kar deta hai.** Tab website saaf message dikhati hai aur "Video upload" tab chalta rehta hai (wahi sabse pakka tareeka).
- Limits (`MAX_MINUTES`, `MAX_UPLOAD_MB`, `KEEP_HOURS`) environment variables se badal sakte ho. Clips 6 ghante baad delete hote hain.

## Score kaise banta hai (0-100)

| Cheez | Weight | Matlab |
|---|---|---|
| Most replayed | 40% | YouTube par log sabse zyada kahan rewind karte hain |
| Hook | 30% | Pehli line mein sawaal, number, strong shabd (Hindi + English) |
| Energy | 20% | Awaaz ki jaan aur bolne ki speed |
| Length | 10% | 20-45 second sabse best |

Jis video par "Most replayed" data nahi hota (kam views, ya upload), uska score baaki teen se banta hai.

## Settings (optional)

- **Groq key ke bina** (apne PC par) local model chalta hai: tez ke liye `WHISPER_MODEL=base`, behtar Hindi ke liye `medium` (slow).
- **Better hook scoring:** free Gemini key (https://aistudio.google.com/apikey) ko `GEMINI_API_KEY` mein daalo.
- `MAX_MINUTES`, `MAX_UPLOAD_MB`, `KEEP_HOURS` se limits badlo.
- Bina website ke: `python pipeline.py "LINK" --top 5 --lang hi`
- Google Colab: `Shorts_Clipper_Colab.ipynb` (pehle cell mein repo link already set hai).

## Dhyan rakho

- **Copyright:** sirf apne videos ya jinki permission ho unhi ke clips upload karo, warna strike aa sakta hai.
- Face tracking abhi nahi hai: video blurred background ke beech mein fit hota hai.

Banaya gaya: yt-dlp, faster-whisper, FFmpeg, Flask. License: MIT.
