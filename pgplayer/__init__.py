import os
import shutil
import subprocess
import threading
import time
import json

import ffmpeg
import pygame as pg
from pygame.typing import Point
import sounddevice as sd
import numpy as np

"""
pgplayer is a python library that allows you to run videos in pygame(-ce). It uses ffmpeg to convert frames from a video into a pygame surface and plays audio using pyaudio.
"""


class VideoPlayer:
    def __init__(
        self,
        source: os.PathLike,
        loop: int = 1,
        volume: float = 1.0,
        frequency: int = 44100,
        speed: float = 1.0,
    ) -> None:
        """
        The constructor for the VideoPlayer class.

        Params:
            - source: os.PathLike | bytes. Either a file path or raw bytes. raises FileNotFoundError if source is a non-existent file path.

            - loop: int. The amount of times the video will loop. Video will repeat forever if `loop = 0`. Defaults to 0.

            - volume: float. A value between 0 and 1. Defaults to 1.

            - frequency: int. The frequency of the audio. Defaults to 44100.
        """
        if not shutil.which("ffmpeg"):
            print("Program ffmpeg is not installed.")
            raise SystemExit

        if not source:
            raise ValueError("Source not provided.")

        if isinstance(source, (str, os.PathLike)) and not os.path.exists(source):
            raise FileNotFoundError(f"File: {source} not found.")

        self.source = source
        self.loop = max(0, loop)
        self.volume = max(0, min(1.0, volume))
        self.frequency = frequency
        self.speed = max(0.1, min(8.0, speed))

        self.data = ffmpeg.probe(self.source)
        self.duration = float(self.data["format"]["duration"])

        self.fps = eval(self.data["streams"][0]["avg_frame_rate"])

        self.w = int(self.data["streams"][0]["width"])
        self.h = int(self.data["streams"][0]["height"])

        self.timestamps = self._extract_timestamps()

        self.audio_loop_count = 0
        self.video_loop_count = 0

        self.paused = False
        self.stopped = False

        self.video_process = (
            ffmpeg.input(self.source)
            .output("pipe:", format="rawvideo", pix_fmt="rgb24")
            .run_async(pipe_stdout=True, quiet=True)
        )
        self.audio_process = (
            ffmpeg.input(self.source)
            .output(
                "pipe:", format="s16le", acodec="pcm_s16le", ac=2, ar=self.frequency
            )
            .run_async(pipe_stdout=True, quiet=True)
        )
        self.audio_size = 0

        self.stream = sd.OutputStream(self.frequency, channels=2, dtype=np.int16)

        self.frame = [pg.Surface((self.w, self.h)), "used"]

        self.audio_thread = None
        self.video_thread = None

        self.pause_event = threading.Event()
        self.pause_event.set()

        self.frame_ready = threading.Event()
        self.frame_ready.set()

        self.frame_lock = threading.Lock()

    def _extract_timestamps(self) -> list:
        """Extract frame timestamps using ffprobe."""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=pts_time",
            "-of",
            "json",
            self.source,
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )  # didn't use ffmpeg.probe() because it couldn't get frames

        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")

        info = json.loads(result.stdout)
        return [float(f["pts_time"]) for f in info.get("frames", []) if "pts_time" in f]

    def _play_video(self) -> None:
        """Play video frames in a loop until stopped."""
        while not self.stopped:
            self.video_process = (
                ffmpeg.input(self.source)
                .output("pipe:", format="rawvideo", pix_fmt="rgb24")
                .run_async(pipe_stdout=True, quiet=True)
            )
            frame_idx = 0

            try:
                while not self.stopped:
                    self.pause_event.wait()

                    buf = self.video_process.stdout.read(self.w * self.h * 3)
                    if not buf:
                        break

                    pts = (
                        self.timestamps[frame_idx]
                        if frame_idx < len(self.timestamps)
                        else frame_idx / self.fps
                    ) / self.speed
                    frame_idx += 1

                    now = time.perf_counter() - self.start
                    delay = pts - now

                    if delay > 0.005:
                        time.sleep(min(delay, 0.005))
                    elif delay < -0.2:
                        # frame is too late so drop it
                        continue

                    frame = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)
                    with self.frame_lock:
                        self.frame = [
                            pg.image.frombuffer(
                                frame.tobytes(), (self.w, self.h), "RGB"
                            ).convert(),
                            "unused",
                        ]

                    time.sleep(1 / self.fps)

            finally:
                self.video_process.kill()

            self.video_loop_count += 1
            if self.loop > 0 and self.video_loop_count >= self.loop:
                self.stop()
                break

    def _play_audio(self) -> None:
        """Play video frames in a loop until stopped."""
        self.stream.start()

        while not self.stopped:
            self.audio_size = 0
            self.audio_process = (
                ffmpeg.input(self.source)
                .output(
                    "pipe:", format="s16le", acodec="pcm_s16le", ac=2, ar=self.frequency
                )
                .run_async(pipe_stdout=True, quiet=True)
            )

            if self.audio_loop_count > 0:
                self.start = time.perf_counter()

            try:
                while not self.stopped:
                    self.pause_event.wait()

                    if self.stream.closed:
                        self.stopped = True

                    buf = self.audio_process.stdout.read(1024 * 32)
                    if not buf:
                        break  # EOF

                    frame = np.frombuffer(buf, np.int16).reshape(-1, 2)
                    frame = (frame * self.volume).astype(np.int16)

                    if not self.stream.closed:
                        self.stream.write(frame)

                    self.audio_size += len(frame.tobytes())

            finally:
                self.audio_process.kill()

            self.audio_loop_count += 1
            if self.loop > 0 and self.audio_loop_count >= self.loop:
                self.stop()
                break

    def check_frame_status(self) -> None:
        if self.frame[1] == "used":
            self.frame_ready.set()
        else:
            self.frame_ready.wait()

    def get_frame(self, size: Point = None) -> pg.Surface:
        with self.frame_lock:
            if size and size != (self.w, self.h):
                self.frame[1] = "used"
                return pg.transform.scale(self.frame[0], size)
            else:
                self.frame[1] = "used"
                return self.frame[0]

    def play(self, size: Point = None) -> None:
        self.start = time.perf_counter()
        self.video_thread = threading.Thread(target=self._play_video, daemon=True)
        self.audio_thread = threading.Thread(target=self._play_audio, daemon=True)

        self.video_thread.start()
        self.audio_thread.start()

    def set_volume(self, volume: float) -> None:
        """
        Sets the volume of the audio.

        Params:
            - volume: float. A value between 0 and 1.
        """
        self.volume = max(0, min(1.0, volume))

    def increase_volume(self, value: float) -> None:
        """
        Increases the volume by the given value.

        Params:
            - value: float. The amount to increase the volume by.
        """
        self.set_volume(self.volume + value)

    def decrease_volume(self, value: float) -> None:
        """
        Decreases the volume by the given value.

        Params:
            - value: float. The amount to decrease the volume by.
        """
        self.set_volume(self.volume - value)

    def toggle_pause(self) -> None:
        """Pauses or resumes the audio and video."""
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.paused = True
        else:
            self.pause_event.set()
            self.paused = False

    def stop(self) -> None:
        """Stops the VideoPlayer class."""
        if not self.stopped:
            self.stopped = True
            self.stream.close()

            for i in [self.audio_process, self.video_process]:
                try:
                    i.kill()
                except Exception:
                    pass

            for i in [self.audio_thread, self.video_thread]:
                try:
                    i.join()
                except Exception:
                    pass

            print(self.audio_size / 1024 / 1024)

            return
