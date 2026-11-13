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

## Website ko sabke liye online karo (free)

GitHub Pages par ye nahi chalega, kyunki video process karne ke liye server chahiye. **Hugging Face Spaces** free hai:

1. https://huggingface.co/new-space par jao: SDK **Docker** chuno, Blank, Public.
2. Is repo ki saari files Space mein upload karo.
3. Space ki `README.md` ke sabse upar ye 5 lines daalo:
   ```
   ---
   title: Shorts Clipper
   sdk: docker
   app_port: 7860
   ---
   ```
4. Build hone do (5-10 min). Link ban jayega.

**Free server ki sachchai:**
- Free server dheema hota hai, 10 minute ke video mein 10-20 minute lag sakte hain. Server ek time par ek hi video karta hai, baaki line mein lagte hain.
- **YouTube aksar server (datacenter) wale IP ko block kar deta hai.** Aisa hua to website saaf message dikhati hai, aur "Video upload" tab chalta rahega. Apne PC par YouTube link hamesha chalta hai.
- Limits (`Dockerfile` mein badal sakte ho): video max 30 minute, upload max 500 MB, clips 6 ghante baad delete.

## Score kaise banta hai (0-100)

| Cheez | Weight | Matlab |
|---|---|---|
| Most replayed | 40% | YouTube par log sabse zyada kahan rewind karte hain |
| Hook | 30% | Pehli line mein sawaal, number, strong shabd (Hindi + English) |
| Energy | 20% | Awaaz ki jaan aur bolne ki speed |
| Length | 10% | 20-45 second sabse best |

Jis video par "Most replayed" data nahi hota (kam views, ya upload), uska score baaki teen se banta hai.

## Settings (optional)

- **Tez chalana:** `WHISPER_MODEL=base`. **Behtar Hindi:** `medium` (slow).
- **Better hook scoring:** free Gemini key (https://aistudio.google.com/apikey) ko `GEMINI_API_KEY` mein daalo.
- `MAX_MINUTES`, `MAX_UPLOAD_MB`, `KEEP_HOURS` se limits badlo.
- Bina website ke: `python pipeline.py "LINK" --top 5 --lang hi`
- Google Colab: `Shorts_Clipper_Colab.ipynb` (pehle cell mein repo link already set hai).

## Dhyan rakho

- **Copyright:** sirf apne videos ya jinki permission ho unhi ke clips upload karo, warna strike aa sakta hai.
- Face tracking abhi nahi hai: video blurred background ke beech mein fit hota hai.

Banaya gaya: yt-dlp, faster-whisper, FFmpeg, Flask. License: MIT.
