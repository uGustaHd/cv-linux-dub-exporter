import sys
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QListWidget,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

def find_choicer_voicer():
    """Detects the ChoicerVoicer installation path inside the Wine prefix."""
    users_path = (
        Path.home()
        / ".wine"
        / "drive_c"
        / "users"
    )

    if not users_path.exists():
        return None

    for user_dir in users_path.iterdir():
        if not user_dir.is_dir():
            continue

        candidate = (
            user_dir
            / "AppData"
            / "Roaming"
            / "YeahMaybe"
            / "ChoicerVoicer"
        )

        if candidate.exists():
            return candidate

    return None

CHOICER_VOICER = find_choicer_voicer()

if CHOICER_VOICER is None:
    raise FileNotFoundError(
        "Could not find the ChoicerVoicer installation inside Wine."
    )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CV Dub Exporter")
        self.resize(800, 600)

        self.sessions = []

        # Export process state
        self.process = None
        self.export_stage = None
        self.stage_duration = 0.0

        self.audio_output = None
        self.video_output = None

        self.setup_ui()
        self.find_recordings()

    # =========================================================
    # User Interface
    # =========================================================

    def setup_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        title = QLabel("CV Dub Exporter — Linux")
        title.setStyleSheet(
            "font-size: 24px; font-weight: bold;"
        )

        self.status = QLabel(
            "Scanning for recordings..."
        )

        self.recordings_list = QListWidget()

        self.session_info = QLabel(
            "Select a session to view details."
        )

        self.session_info.setWordWrap(True)

        self.session_info.setStyleSheet(
            """
            QLabel {
                padding: 10px;
                border: 1px solid #555;
                border-radius: 6px;
            }
            """
        )

        self.progress_label = QLabel(
            "Progress: 0%"
        )

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(
            0,
            100,
        )

        self.progress_bar.setValue(0)

        self.export_button = QPushButton(
            "Export selected session"
        )

        self.export_button.setEnabled(False)

        layout.addWidget(title)
        layout.addWidget(self.status)
        layout.addWidget(self.recordings_list)
        layout.addWidget(self.session_info)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.export_button)

        self.setCentralWidget(central)

        self.recordings_list.currentRowChanged.connect(
            self.session_selected
        )

        self.export_button.clicked.connect(
            self.export_selected
        )

    # =========================================================
    # Session Discovery
    # =========================================================

    def find_recordings(self):
        """Scans the dub_recordings directory for valid recording sessions."""
        recordings_path = (
            CHOICER_VOICER
            / "game"
            / "recordings"
            / "dub_recordings"
        )

        if not recordings_path.exists():
            self.status.setText(
                "Recordings directory not found."
            )
            return

        self.sessions.clear()
        self.recordings_list.clear()

        for project in sorted(
            recordings_path.iterdir()
        ):
            if not project.is_dir():
                continue

            for session in sorted(
                project.iterdir()
            ):
                if not session.is_dir():
                    continue

                wav_files = list(
                    session.glob("*.wav")
                )

                if not wav_files:
                    continue

                pack_path = (
                    CHOICER_VOICER
                    / "game"
                    / "packs_voice"
                    / project.name
                )

                self.sessions.append(
                    (
                        pack_path,
                        session,
                    )
                )

                self.recordings_list.addItem(
                    f"{project.name} — "
                    f"{session.name} "
                    f"({len(wav_files)} recordings)"
                )

        self.status.setText(
            f"Found {len(self.sessions)} session(s)."
        )

    # =========================================================
    # Metadata Parsing
    # =========================================================

    def find_metadata(
        self,
        pack: Path,
        wav: Path,
    ):
        """
        Locates the corresponding metadata file (.ini or .txt) for a given audio file.

        Supported mappings:
        _dubrecord_01_Vader.wav -> 01_Vader.ini
        _dubrecord_01_Joe.wav   -> 01_Joe.txt
        """

        name = wav.stem

        if name.startswith(
            "_dubrecord_"
        ):
            name = name[
                len("_dubrecord_"):
            ]

        # INI metadata format
        ini = pack / f"{name}.ini"

        if ini.exists():
            return ini

        # TXT metadata format
        txt = pack / f"{name}.txt"

        if txt.exists():
            return txt

        return None

    def get_timestamp(
        self,
        metadata: Path,
    ):
        """Extracts the start timestamp from the metadata file."""
        text = metadata.read_text(
            encoding="utf-8"
        )

        match = re.search(
            r"dub_timestamps=\[([0-9.]+)\]",
            text,
        )

        if not match:
            raise ValueError(
                f"Timestamp not found in:\n"
                f"{metadata.name}"
            )

        return float(
            match.group(1)
        )

    def get_character(
        self,
        metadata: Path,
    ):
        """Extracts character names from the metadata file if present."""
        text = metadata.read_text(
            encoding="utf-8"
        )

        match = re.search(
            r'dub_characters=\["([^"]+)"\]',
            text,
        )

        if match:
            return match.group(1)

        return None

    # =========================================================
    # Pack Assets
    # =========================================================

    def find_backing_track(
        self,
        pack: Path,
    ):
        """Finds the background audio file within the voice pack."""
        candidates = [
            pack / "_backing_track.wav",
            pack / "_backing_track.mp3",
        ]

        for path in candidates:
            if path.is_file():
                return path

        raise FileNotFoundError(
            "Backing track not found in pack:\n\n"
            f"{pack}"
        )

    def find_video(
        self,
        pack: Path,
    ):
        """Finds the source video file within the voice pack."""
        video = pack / "dub_video.ogv"

        if video.is_file():
            return video

        raise FileNotFoundError(
            "Source video not found in pack:\n\n"
            f"{video}"
        )

    # =========================================================
    # Export Naming
    # =========================================================

    def get_export_name(
        self,
        pack: Path,
    ):
        """Sanitizes the voice pack name to create a clean output filename."""
        name = pack.name

        name = re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            name,
        )

        return name.strip("_")

    # =========================================================
    # Media Duration
    # =========================================================

    def get_media_duration(
        self,
        media: Path,
    ):
        """Retrieves total duration in seconds of a media file using ffprobe."""
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(media),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        return float(
            result.stdout.strip()
        )

    # =========================================================
    # Session Selection
    # =========================================================

    def session_selected(
        self,
        row,
    ):
        """Handles selection changes in the list widget and updates information view."""
        if row < 0:
            self.export_button.setEnabled(
                False
            )

            self.session_info.setText(
                "Select a session to view details."
            )

            return

        if row >= len(
            self.sessions
        ):
            self.export_button.setEnabled(
                False
            )

            return

        pack_path, session_path = (
            self.sessions[row]
        )

        wavs = sorted(
            session_path.glob("*.wav")
        )

        # -------------------------
        # Backing Track Check
        # -------------------------

        backing_track = None

        for filename in (
            "_backing_track.wav",
            "_backing_track.mp3",
        ):
            candidate = (
                pack_path / filename
            )

            if candidate.is_file():
                backing_track = candidate
                break

        # -------------------------
        # Video Check
        # -------------------------

        video = (
            pack_path
            / "dub_video.ogv"
        )

        # -------------------------
        # Metadata Check
        # -------------------------

        metadata_txt = 0
        metadata_ini = 0
        metadata_missing = 0

        characters = set()

        for wav in wavs:
            metadata = self.find_metadata(
                pack_path,
                wav,
            )

            if metadata is None:
                metadata_missing += 1
                continue

            if (
                metadata.suffix.lower()
                == ".txt"
            ):
                metadata_txt += 1

            elif (
                metadata.suffix.lower()
                == ".ini"
            ):
                metadata_ini += 1

            try:
                character = (
                    self.get_character(
                        metadata
                    )
                )

                if character:
                    characters.add(
                        character
                    )

            except Exception:
                pass

        # -------------------------
        # Status Label Construction
        # -------------------------

        backing_status = (
            backing_track.name
            if backing_track
            else "❌ Not found"
        )

        video_status = (
            video.name
            if video.is_file()
            else "❌ Not found"
        )

        if metadata_missing:
            metadata_status = (
                f"⚠️ {metadata_missing} "
                f"missing metadata"
            )
        else:
            metadata_status = (
                "✓ All found"
            )

        if characters:
            characters_text = ", ".join(
                sorted(characters)
            )
        else:
            characters_text = (
                "Not specified"
            )

        info = (
            f"<b>Pack:</b> "
            f"{pack_path.name}<br>"

            f"<b>Session:</b> "
            f"{session_path.name}<br>"

            f"<b>Recordings:</b> "
            f"{len(wavs)}<br>"

            f"<b>Characters:</b> "
            f"{characters_text}<br>"

            f"<br>"

            f"<b>Backing Track:</b> "
            f"{backing_status}<br>"

            f"<b>Video:</b> "
            f"{video_status}<br>"

            f"<b>Metadata:</b> "
            f"{metadata_status}<br>"

            f"<br>"

            f"<b>Formats:</b> "
            f"{metadata_txt} TXT / "
            f"{metadata_ini} INI"
        )

        self.session_info.setText(
            info
        )

        self.status.setText(
            f"Selected: "
            f"{pack_path.name} — "
            f"{session_path.name}"
        )

        self.export_button.setEnabled(
            True
        )

    # =========================================================
    # Progress Display
    # =========================================================

    def set_progress(
        self,
        value,
        text=None,
    ):
        """Updates UI progress bar and progress text label."""
        value = max(
            0,
            min(
                100,
                int(value),
            ),
        )

        self.progress_bar.setValue(
            value
        )

        if text is None:
            text = (
                f"Progress: {value}%"
            )

        self.progress_label.setText(
            text
        )

    # =========================================================
    # Export Pipeline
    # =========================================================

    def export_selected(self):
        """Triggers the export process for the currently selected session."""
        row = (
            self.recordings_list.currentRow()
        )

        if row < 0:
            return

        pack_path, session_path = (
            self.sessions[row]
        )

        wavs = sorted(
            session_path.glob("*.wav")
        )

        if not wavs:
            QMessageBox.warning(
                self,
                "Error",
                "No WAV recordings found.",
            )

            return

        try:
            backing_track = (
                self.find_backing_track(
                    pack_path
                )
            )

            video = (
                self.find_video(
                    pack_path
                )
            )

            export_name = (
                self.get_export_name(
                    pack_path
                )
            )

            self.audio_output = (
                Path.cwd()
                / f"{export_name}.wav"
            )

            self.video_output = (
                Path.cwd()
                / f"{export_name}.mp4"
            )

            print()
            print("=" * 60)
            print("EXPORTING")
            print(
                f"Pack:     {pack_path.name}"
            )
            print(
                f"Session:  {session_path.name}"
            )
            print(
                f"Backing:  {backing_track.name}"
            )
            print(
                f"Video:    {video.name}"
            )
            print(
                f"Output:   {export_name}"
            )
            print("=" * 60)

            # =================================================
            # Stage 1: Build Audio Mix
            # =================================================

            inputs = [
                "ffmpeg",
                "-y",

                "-nostats",

                "-progress",
                "pipe:1",

                "-i",
                str(backing_track),
            ]

            filters = []

            mix_inputs = [
                "[0:a]"
            ]

            ffmpeg_input_index = 1
            valid_recordings = 0

            for wav in wavs:

                metadata = (
                    self.find_metadata(
                        pack_path,
                        wav,
                    )
                )

                if metadata is None:
                    print(
                        "[WARNING] Missing metadata for: "
                        f"{wav.name}"
                    )

                    continue

                timestamp = (
                    self.get_timestamp(
                        metadata
                    )
                )

                print(
                    f"{timestamp:8.3f}s - "
                    f"{wav.name} -> "
                    f"{metadata.name}"
                )

                inputs += [
                    "-i",
                    str(wav),
                ]

                delay_ms = round(
                    timestamp * 1000
                )

                filters.append(
                    f"[{ffmpeg_input_index}:a]"
                    f"adelay={delay_ms}|{delay_ms}"
                    f"[voice{ffmpeg_input_index}]"
                )

                mix_inputs.append(
                    f"[voice{ffmpeg_input_index}]"
                )

                ffmpeg_input_index += 1
                valid_recordings += 1

            if valid_recordings == 0:
                raise RuntimeError(
                    "No recordings contain valid metadata."
                )

            filters.append(
                "".join(mix_inputs)
                + f"amix=inputs="
                f"{len(mix_inputs)}:"
                "duration=first:"
                "normalize=0"
                "[out]"
            )

            filter_complex = (
                ";".join(filters)
            )

            audio_cmd = inputs + [
                "-filter_complex",
                filter_complex,

                "-map",
                "[out]",

                "-c:a",
                "pcm_s16le",

                str(
                    self.audio_output
                ),
            ]

            # Store backing track duration for progress tracking
            self.stage_duration = (
                self.get_media_duration(
                    backing_track
                )
            )

            self.export_stage = (
                "audio"
            )

            self.export_button.setEnabled(
                False
            )

            self.recordings_list.setEnabled(
                False
            )

            self.set_progress(
                0,
                "Audio: 0% — Total: 0%",
            )

            self.status.setText(
                "Exporting audio..."
            )

            self.start_ffmpeg(
                audio_cmd
            )

        except Exception as e:
            self.export_error(
                str(e)
            )

    # =========================================================
    # FFmpeg Process Controller
    # =========================================================

    def start_ffmpeg(
        self,
        command,
    ):
        """Spawns FFmpeg as an asynchronous QProcess."""
        self.process = QProcess(
            self
        )

        self.process.setProcessChannelMode(
            QProcess.MergedChannels
        )

        self.process.readyReadStandardOutput.connect(
            self.read_ffmpeg_output
        )

        self.process.finished.connect(
            self.ffmpeg_finished
        )

        self.process.errorOccurred.connect(
            self.ffmpeg_error
        )

        self.process.start(
            command[0],
            command[1:],
        )

    # =========================================================
    # FFmpeg Output Parsing
    # =========================================================

    def read_ffmpeg_output(self):
        """Parses stdout/stderr from FFmpeg progress pipe in real time."""
        if not self.process:
            return

        data = bytes(
            self.process.readAllStandardOutput()
        )

        text = data.decode(
            "utf-8",
            errors="ignore",
        )

        # Parse FFmpeg time tags:
        # out_time_us=1234567 or out_time_ms=1234567

        match = re.findall(
            r"out_time_us=(\d+)",
            text,
        )

        if match:
            current_time = (
                int(match[-1])
                / 1_000_000
            )

        else:
            match = re.findall(
                r"out_time_ms=(\d+)",
                text,
            )

            if not match:
                return

            current_time = (
                int(match[-1])
                / 1_000_000
            )

        if self.stage_duration <= 0:
            return

        stage_percent = (
            current_time
            / self.stage_duration
            * 100
        )

        stage_percent = max(
            0,
            min(
                100,
                stage_percent,
            ),
        )

        # Stage 1: Audio processing represents the first 50%
        if self.export_stage == "audio":

            total_percent = (
                stage_percent * 0.5
            )

            self.set_progress(
                total_percent,
                (
                    f"Audio: "
                    f"{int(stage_percent)}% "
                    f"— Total: "
                    f"{int(total_percent)}%"
                ),
            )

        # Stage 2: Video processing represents the remaining 50%
        elif self.export_stage == "video":

            total_percent = (
                50
                + stage_percent * 0.5
            )

            self.set_progress(
                total_percent,
                (
                    f"Video: "
                    f"{int(stage_percent)}% "
                    f"— Total: "
                    f"{int(total_percent)}%"
                ),
            )

    # =========================================================
    # FFmpeg Completion Handlers
    # =========================================================

    def ffmpeg_finished(
        self,
        exit_code,
        exit_status,
    ):
        """Dispatches stage completion logic upon FFmpeg exit."""
        if exit_code != 0:

            self.export_error(
                "FFmpeg process failed.\n\n"
                f"Exit code: {exit_code}"
            )

            return

        if self.export_stage == "audio":

            self.audio_finished()

            return

        if self.export_stage == "video":

            self.video_finished()

            return

        self.export_error(
            "Unknown export stage."
        )

    # =========================================================
    # FFmpeg Error Handler
    # =========================================================

    def ffmpeg_error(
        self,
        error,
    ):
        """Handles process execution errors."""
        if error == QProcess.FailedToStart:

            self.export_error(
                "Failed to start FFmpeg.\n\n"
                "Please verify that FFmpeg is installed and available in PATH."
            )

    # =========================================================
    # Stage 1 Complete (Audio) -> Stage 2 Start (Video)
    # =========================================================

    def audio_finished(self):
        """Triggers the video encoding stage after audio mix completion."""

        print(
            f"\nAudio file generated: "
            f"{self.audio_output}"
        )

        self.set_progress(
            50,
            "Audio ready — 50%",
        )

        self.status.setText(
            "Audio complete. Rendering MP4 video..."
        )

        QApplication.processEvents()

        try:
            row = (
                self.recordings_list.currentRow()
            )

            pack_path, _ = (
                self.sessions[row]
            )

            video = (
                self.find_video(
                    pack_path
                )
            )

            video_duration = (
                self.get_media_duration(
                    video
                )
            )

            video_cmd = [
                "ffmpeg",
                "-y",

                "-nostats",

                "-progress",
                "pipe:1",

                # Input 0: Source video
                "-i",
                str(video),

                # Input 1: Generated audio mix
                "-i",
                str(
                    self.audio_output
                ),

                # Stream mapping: video from 0, audio from 1
                "-map",
                "0:v:0",

                "-map",
                "1:a:0",

                # Video codec
                "-c:v",
                "libx264",

                # Audio codec
                "-c:a",
                "aac",

                # Quality / CRF
                "-crf",
                "18",

                # Encoding preset
                "-preset",
                "medium",

                # Stop encoding when shortest stream ends
                "-shortest",

                str(
                    self.video_output
                ),
            ]

            self.stage_duration = (
                video_duration
            )

            self.export_stage = (
                "video"
            )

            self.set_progress(
                50,
                "Video: 0% — Total: 50%",
            )

            self.start_ffmpeg(
                video_cmd
            )

        except Exception as e:

            self.export_error(
                str(e)
            )

    # =========================================================
    # Stage 2 Complete (Video)
    # =========================================================

    def video_finished(self):
        """Finalizes export workflow when MP4 generation finishes successfully."""

        print(
            f"Video file generated: "
            f"{self.video_output}"
        )

        self.set_progress(
            100,
            "Export complete — 100%",
        )

        self.status.setText(
            "Export complete: "
            f"{self.video_output.name}"
        )

        QMessageBox.information(
            self,
            "Export Completed",
            "Export completed successfully!\n\n"
            f"Audio:\n"
            f"{self.audio_output}\n\n"
            f"Video:\n"
            f"{self.video_output}",
        )

        self.cleanup_export()

    # =========================================================
    # Export Cleanup
    # =========================================================

    def cleanup_export(self):
        """Resets internal export states and re-enables UI controls."""

        self.process = None
        self.export_stage = None
        self.stage_duration = 0

        self.export_button.setEnabled(
            True
        )

        self.recordings_list.setEnabled(
            True
        )

    # =========================================================
    # Export Error Interruption
    # =========================================================

    def export_error(
        self,
        message,
    ):
        """Handles export errors, terminates background processes, and displays alert."""

        self.status.setText(
            "Error occurred during export."
        )

        self.progress_label.setText(
            "Export interrupted."
        )

        if self.process:

            try:
                self.process.kill()

            except Exception:
                pass

        QMessageBox.critical(
            self,
            "Export Error",
            message,
        )

        self.cleanup_export()


# =============================================================
# Application Entry Point
# =============================================================

app = QApplication(sys.argv)

window = MainWindow()

window.show()

sys.exit(
    app.exec()
)