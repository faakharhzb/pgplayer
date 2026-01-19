import os
import shutil
import subprocess
import threading
import time

import ffmpeg
import pygame as pg
from pygame.typing import Point
import pyaudio
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
        self.loop = loop
        self.volume = max(0, min(1.0, volume))
        self.frequency = frequency
        self.speed = max(0.1, min(8.0, speed))

        self.data = ffmpeg.probe(self.source)
        self.duration = float(self.data["format"]["duration"])

        self.fps = str(self.data["streams"][0]["avg_frame_rate"])
        self.fps = self.fps.split("/")
        self.fps = int(self.fps[0]) / int(self.fps[1])

        self.w = int(self.data["streams"][0]["coded_width"])
        self.h = int(self.data["streams"][0]["coded_height"])

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
                "pipe:",
                format="s16le",
                acodec="pcm_s16le",
                ac=2,
                ar=self.frequency,
                af=f"atempo={self.speed}",
            )
            .run_async(pipe_stdout=True, quiet=True)
        )

        self.pyaudio = pyaudio.PyAudio()
        self.stream = self.pyaudio.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=self.frequency,
            output=True,
        )

        self.frame = pg.Surface((self.w, self.h))

    def _play_video(self) -> None:
        """Play video frames in a loop until stopped."""
        frames = []

        while not self.stopped:
            self.video_process = (
                ffmpeg.input(self.source)
                .output("pipe:", format="rawvideo", pix_fmt="rgb24")
                .run_async(pipe_stdout=True, quiet=True)
            )

            try:
                while not self.stopped:
                    if self.paused:
                        time.sleep(0.0001)
                        continue

                    time.sleep((1 / self.fps) / self.speed)

                    buf = self.video_process.stdout.read(self.w * self.h * 3)
                    if not buf:
                        break  # EOF

                    frame = np.frombuffer(buf, np.uint8).reshape([self.h, self.w, 3])
                    self.frame = pg.image.frombuffer(
                        frame.tobytes(), (self.w, self.h), "RGB"
                    )

            finally:
                self.video_process.kill()

            self.video_loop_count += 1
            if self.loop > 0 and self.video_loop_count >= self.loop:
                self.stop()
                break

    def _play_audio(self) -> None:
        """Play video frames in a loop until stopped."""
        while not self.stopped:
            self.audio_process = (
                ffmpeg.input(self.source)
                .output(
                    "pipe:",
                    format="s16le",
                    acodec="pcm_s16le",
                    ac=2,
                    ar=self.frequency,
                    af=f"atempo={self.speed}",
                )
                .run_async(pipe_stdout=True, quiet=True)
            )

            try:
                while not self.stopped:
                    if self.paused:
                        time.sleep(0.0001)
                        continue

                    if self.stream.is_stopped():
                        raise SystemExit

                    buf = self.audio_process.stdout.read(1024 * 32)
                    if not buf:
                        break  # EOF

                    frame = np.frombuffer(buf, np.int16)
                    frame = (frame * self.volume).astype(np.int16)

                    self.stream.write(frame.tobytes())

            finally:
                self.audio_process.kill()

            self.audio_loop_count += 1
            if self.loop > 0 and self.audio_loop_count >= self.loop:
                self.stop()
                break

    def get_frame(self, size: Point = None) -> pg.Surface:
        if size:
            return pg.transform.scale(self.frame, size)
        else:
            return self.frame

    def play(self, size: Point = None) -> None:
        threading.Thread(target=self._play_video).start()
        threading.Thread(target=self._play_audio).start()

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
        self.paused = not self.paused

    def stop(self) -> None:
        """Stops the VideoPlayer class."""
        self.stopped = True
        self.stream.close()
        self.pyaudio.terminate()
