# Karaoke Captions for Reels

**Word-by-word highlighted captions, burned into vertical video with ffmpeg — no player subtitle track, no external renderer.**

## Why this exists

The "karaoke" caption style — each word highlighting in sync with speech — is common on short-form video, but most tutorials render it in a heavyweight video editor. This is a from-scratch pipeline: transcribe with word-level timestamps, generate an `.ass` subtitle file with one dialogue line per word, and burn it in with ffmpeg's native `libass` support. No editor, no manual keyframing, runs headless on a Linux box.

## How it works

1. **Word-level transcription** — [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) (`base` model, `word_timestamps=True`, `vad_filter=True`). Each word comes out with its own `start`/`end`.
2. **`.ass` generation** (`build_ass()`) — words are grouped into chunks of up to 6 (or fewer if punctuation closes a chunk early), split across 2 centered lines. For each word in a chunk, one `Dialogue` line is emitted covering just that word's time range, with only that word in the accent color and the rest in white — stepping through the chunk word-by-word creates the highlight effect.
3. **Burn-in** — the `.ass` file is applied via ffmpeg's `ass=` filter, last in the `filter_complex` chain so captions always render above any other overlay.

```python
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")
segments, _ = model.transcribe("audio.wav", language="pt", word_timestamps=True, vad_filter=True)
words = [{"word": w.word.strip(), "start": w.start, "end": w.end} for seg in segments for w in seg.words]

build_ass(words, "captions.ass")
# ffmpeg -i video.mp4 -vf "ass=captions.ass" -c:a copy output.mp4
```

`pipeline_remoto.py` also includes the full production pipeline this was built for — an avatar-in-circle intro that cuts to full-screen at set timestamps, with face detection (OpenCV Haar cascade) to keep the crop centered, plus a rotating border and transition SFX. `build_ass()` is the reusable part; the rest is a worked example of composing it into a larger `filter_complex`.

## Setup

- ffmpeg with `libass` support (default in most builds — verify with `ffmpeg -filters | grep ass`)
- Python 3.10+, `pip install faster-whisper opencv-python-headless`
- The [Archivo Black](https://raw.githubusercontent.com/google/fonts/main/ofl/archivoblack/ArchivoBlack-Regular.ttf) font (OFL license) installed system-wide — not just present in the project folder, or `ass=` silently falls back to a default font with no error

## Gotchas

- **Line breaks in the `.ass` string**: never write a literal `\N` in a normal Python string — `\N{...}` is Unicode escape syntax and breaks. Build the backslash with `chr(92) + "N"` instead.
- **Color order**: ASS colors are `&HAABBGGRR` — blue/green/red, reversed from normal hex, no `#`. Always test on a short clip before rendering the full video.
- **Silent font fallback**: if the font isn't installed at the OS level, `ass=` falls back to a default font with zero warning. Confirm with `fc-list | grep -i archivo` (Linux).
- **Overlay order**: apply the `ass=` filter last in the chain — anything overlaid after it (circle avatar, full-screen cuts) will cover the captions.

## License

MIT — see [LICENSE](LICENSE).
