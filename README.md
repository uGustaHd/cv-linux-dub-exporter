# CV Dub Exporter for Linux

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A Linux GUI tool for exporting dubbing sessions from **ChoicerVoicer**.

CV Dub Exporter automatically finds recorded dubbing sessions, synchronizes the voice recordings using their metadata timestamps, mixes them with the original backing track, and exports the result as both WAV audio and MP4 video.

---

## Features

- Automatically detects the ChoicerVoicer installation inside Wine
- Finds available dubbing sessions
- Supports `.ini` and `.txt` metadata formats
- Synchronizes voice recordings using `dub_timestamps`
- Detects the backing track and original video automatically
- Mixes original backing track with recorded voices using FFmpeg
- Exports final audio as `.wav` and video as `.mp4`
- Displays session info and progress bar in the GUI
- Generates clean filenames based on the pack name

---

## Requirements

- **OS:** Linux
- **Python:** 3.10+
- **Wine** (with ChoicerVoicer installed)
- **FFmpeg** & **FFprobe**

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/ugustahd/cv-linux-dub-exporter.git](https://github.com/ugustahd/cv-linux-dub-exporter.git)
   cd cv-linux-dub-exporter
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Ensure system dependencies are installed:**

   *Ubuntu/Debian:*
   ```bash
   sudo apt install ffmpeg wine
   ```

   *Arch Linux:*
   ```bash
   sudo pacman -S ffmpeg wine
   ```

---

## Usage

Run the application:

```bash
python3 main.py
```

The application automatically searches for the ChoicerVoicer installation inside:
```text
~/.wine/drive_c/users/
```

**Workflow:**
1. Select a dubbing session from the list.
2. Review the session details.
3. Click **Export selected session**.
4. Track export progress directly in the GUI.

---

## Output

The exporter saves generated files in the current working directory.

**Example for pack:** `Family Guy - Good Morning`

```text
Family_Guy_Good_Morning.wav  # Mixed backing track and recorded voices
Family_Guy_Good_Morning.mp4  # Original video combined with new audio
```

---

## How It Works

1. **Metadata Parsing:** Reads `.ini` or `.txt` metadata files associated with each voice line to extract timestamps and character roles.
2. **Audio Mixing:** Aligns audio tracks using `dub_timestamps` and mixes recorded voices with the pack's backing track using FFmpeg.
3. **Video Encoding:** Combines the original video stream with the newly rendered audio track into an MP4 container.

---

## Notes

- Designed specifically for Linux installations running ChoicerVoicer via Wine.
- Requires standard ChoicerVoicer directory structures for packs and recordings.

---

## License

Distributed under the MIT License. See `LICENSE` for more information.