#!/usr/bin/env python3
"""
Pipeline completo: fundo (captura de tela) + avatar (circulo + tela cheia
nos ultimos 6s + 2 cortes no meio) + legenda karaoke + borda girando.
Roda no servidor (Linux), sem depender do Windows local.

Uso: python3 pipeline_remoto.py <bg.mp4> <avatar.mp4> <nome_saida_sem_ext>
"""
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
FONT = "Archivo Black"


def run(cmd):
    subprocess.run(cmd, shell=True, check=True)


WORD_FIXES = {
    "envidia": "Nvidia",
    "envidia,": "Nvidia,",
    "envidia.": "Nvidia.",
    "nvidia": "Nvidia",
    "dipsik": "DeepSeek",
    "dipsik,": "DeepSeek,",
    "dipsick": "DeepSeek",
}


def transcribe(avatar_wav):
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(avatar_wav, language="pt", word_timestamps=True, vad_filter=True)
    words = []
    for seg in segments:
        for w in seg.words:
            text = w.word.strip()
            fixed = WORD_FIXES.get(text.lower())
            words.append({"word": fixed if fixed else text, "start": w.start, "end": w.end})
    return words


def fix_word_sequence(words):
    for i in range(len(words) - 1):
        a, b = words[i]["word"], words[i + 1]["word"]
        if a.strip(".,").lower() == "i" and b.lower().lstrip("-").startswith("agigante"):
            words[i]["word"] = "IA"
            words[i + 1]["word"] = "GIGANTE." if b.endswith(".") else "GIGANTE"
    return words


def detect_face(frame_png):
    import cv2
    img = cv2.imread(frame_png)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = sorted(cascade.detectMultiScale(gray, 1.1, 5), key=lambda f: -f[2])
    x, y, w, h = faces[0]
    return x + w / 2, y + h / 2


def build_ass(words, out_path):
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 6 or (w["word"].endswith((".", ",", "!", "?")) and len(cur) >= 3):
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)

    def ts(t):
        h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{FONT},72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,3,5,50,50,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    PURPLE, WHITE, CX, CY, BS = "&H00EA3393", "&H00FFFFFF", 540, 1345, chr(92)
    lines = []
    for chunk in chunks:
        n = len(chunk)
        split_at = (n + 1) // 2 if n > 4 else n
        for i, w in enumerate(chunk):
            p1, p2 = [], []
            for j, w2 in enumerate(chunk):
                color = PURPLE if j == i else WHITE
                piece = "{" + BS + "c" + color + "}" + w2["word"].upper()
                (p1 if j < split_at else p2).append(piece)
            body = " ".join(p1) + ((BS + "N" + " ".join(p2)) if p2 else "")
            text = "{" + BS + f"pos({CX},{CY})" + "}" + body
            lines.append(f"Dialogue: 0,{ts(w['start'])},{ts(w['end'])},Cap,,0,0,0,,{text}")
    open(out_path, "w", encoding="utf-8").write(header + "\n".join(lines))
    return len(lines)


CIRCLE_POS = {
    "capture": {"face": (759, 130), "ring": (751, 122)},
    "remodel": {"face": (758, 58), "ring": (750, 50)},
}


def build_video(bg_path, avatar_path, out_name, work_dir, mode="capture"):
    os.makedirs(work_dir, exist_ok=True)
    wav = os.path.join(work_dir, "audio.wav")
    run(f'ffmpeg -v error -y -i "{avatar_path}" -vn -ar 16000 -ac 1 "{wav}"')

    words = fix_word_sequence(transcribe(wav))
    duration = words[-1]["end"] if words else 40.0
    print("duracao avatar:", duration, flush=True)

    ass_path = os.path.join(work_dir, "captions.ass")
    n = build_ass(words, ass_path)
    print("legendas:", n, flush=True)

    frame_png = os.path.join(work_dir, "frame.png")
    run(f'ffmpeg -v error -y -ss 5 -i "{avatar_path}" -frames:v 1 "{frame_png}"')
    fx, fy = detect_face(frame_png)
    print("rosto centro:", fx, fy, flush=True)

    face_x = int(fx - 300)
    face_y = int(fy - 300)
    box_x = int(fx - 430)
    box_y_target = 0.57
    box_y = int(fy - box_y_target * 1700)
    box_y = max(0, min(box_y, 1920 - 1700))
    box_x = max(0, min(box_x, 1080 - 860))

    d = duration
    cut1 = "between(t\\,8\\,10.2)"
    cut2 = "between(t\\,20\\,22.2)" if d > 30 else "between(t\\,15\\,17.2)"
    cut3 = f"gte(t\\,{max(d-6,10):.1f})"
    cuts = f"{cut1}+{cut2}+{cut3}"

    face_pos = CIRCLE_POS[mode]["face"]
    ring_pos = CIRCLE_POS[mode]["ring"]
    cover_input = f'-i "{BASE}/caption_cover.png" \\\n' if mode == "remodel" else ""
    cover_step = (
        f"[s2][7:v]overlay=0:0:enable='eq({cuts},0)'[s2c];\n" if mode == "remodel" else ""
    )
    bg_label = "s2c" if mode == "remodel" else "s2"

    out_path = os.path.join(work_dir, f"{out_name}.mp4")
    cmd = f'''ffmpeg -y \
-i "{bg_path}" \
-i "{avatar_path}" \
-i "{BASE}/circle_mask.png" \
-i "{BASE}/circle_ring.png" \
-i "{BASE}/transition_whoosh.wav" \
-i "{BASE}/gradient_bg.png" \
-loop 1 -framerate 30 -t {d+1:.1f} -i "{BASE}/avatar_box_border.png" \
{cover_input}-filter_complex "
[0:v]scale=1080:1920,setpts=PTS-STARTPTS[bgraw];
[1:v]split=2[av1][av2];
[av1]crop=600:600:{face_x}:{face_y},scale=283:283:flags=lanczos,unsharp=5:5:1.2:5:5:0.6[facecrop];
[2:v]format=gray[maskg];
[facecrop][maskg]alphamerge[facea];
[av2]crop=860:1700:{box_x}:{box_y},unsharp=5:5:1.2:5:5:0.6[avatarbox];
[6:v]hue=h='t*140':s=1.2[spinborder];
[bgraw]tpad=stop_mode=clone:stop_duration=10[bgmain];
[bgmain][facea]overlay={face_pos[0]}:{face_pos[1]}:enable='eq({cuts},0)'[s1];
[s1][3:v]overlay={ring_pos[0]}:{ring_pos[1]}:enable='eq({cuts},0)'[s2];
{cover_step}[{bg_label}][5:v]overlay=0:0:enable='{cuts}'[s3];
[s3][avatarbox]overlay=110:110:enable='{cuts}'[s4];
[s4][spinborder]overlay=100:100:enable='{cuts}'[s5];
[s5]trim=duration={d:.2f},ass={ass_path}[outv];
[4:a]adelay=7850|7850[sfx1];
[4:a]adelay=19850|19850[sfx2];
[4:a]adelay=31850|31850[sfx3];
[1:a]loudnorm=I=-16:TP=-1.5:LRA=6,alimiter=limit=0.9:attack=5:release=60[avnorm];
[avnorm][sfx1][sfx2][sfx3]amix=inputs=4:duration=first:dropout_transition=0[outa]
" -map "[outv]" -map "[outa]" -c:v libx264 -preset slow -crf 14 -pix_fmt yuv420p -c:a aac -b:a 192k "{out_path}"'''
    run(cmd)
    print("VIDEO_PRONTO:", out_path, flush=True)
    return out_path


if __name__ == "__main__":
    bg, avatar, name = sys.argv[1], sys.argv[2], sys.argv[3]
    mode = sys.argv[4] if len(sys.argv) > 4 else "capture"
    work_dir = os.path.join(BASE, "saida_" + name)
    build_video(bg, avatar, name, work_dir, mode=mode)
