from collections import deque
import io
import os
import sys
import shutil
import time
import threading
from urllib.parse import urlparse

import pygame as pg
from pygame.typing import Point
import av
from av.audio.resampler import AudioResampler
import sounddevice as sd
import numpy as np


class VideoPlayer:
    def __init__(
        self,
        source: str | bytes,
        speed: float = 1,
        volume: float = 1,
        loop: int = 1,
        frequency: int = 44100,
    ) -> None:
        """
        The constructor for the VideoPlayer class.

        Params:
            - source: str | bytes. A file path, a URL or a bytes object. Raises FileNotFoundError if source is a non-existent file path.

            - speed: float. The playback speed for the video. Defaults to 1.

            - volume: float. A value between 0 and 1. Defaults to 1.

            - loop: int. The amount of times the video will loop. Video will repeat forever if loop = 0. Defaults to 1.

            - frequency: int. The frequency of the audio. Defaults to 44100.
        """
        if isinstance(source, bytes):
            source = io.BytesIO(source)

        self.source = source
        self.speed = max(0.1, min(16.0, speed))
        self.volume = max(0, min(1.0, volume))
        self.loop = max(0, loop)
        self.frequency = frequency

        self.audio_container = av.open(self.source)
        self.video_container = av.open(self.source)

        self.audio_stream = self.audio_container.streams.audio
        if self.audio_stream:
            self.stream = sd.OutputStream(
                self.frequency,
                channels=self.audio_stream.channels,
                dtype=np.float32,
            )
            self.resampler = AudioResampler(
                "fltp", self.audio_stream.layout.name, self.frequency
            )

            self.has_audio = True
        else:
            self.has_audio = False

        self.video_stream = self.video_container.streams.video[0]

        self.fps = self.video_stream.average_rate
        self.fps = float(self.fps.numerator / self.fps.denominator)

        self.duration = self.video_stream.duration

        self.w = self.video_stream.coded_width
        self.h = self.video_stream.coded_height
        self.size = (self.w, self.h)

        self.audio_loop_count = 0
        self.video_loop_count = 0

        self.paused = False
        self.stopped = False

        self.frame = [pg.Surface((self.w, self.h)), "used"]

        self.audio_thread = None
        self.video_thread = None

        self.pause_event = threading.Event()
        self.pause_event.set()

        self.frame_ready = threading.Event()
        self.frame_ready.set()

        self.frame_lock = threading.Lock()

        self.audio_pts_lock = threading.Lock()
        self.audio_pts = None

    def _audio_process(self) -> None:
        self.stream.start()

        while not self.stopped:
            for frame in self.audio_container.decode(audio=0):
                if self.stopped:
                    break

                self.pause_event.wait()

                with self.audio_pts_lock:
                    self.audio_pts = frame.pts * frame.time_base

                frame = self.resampler.resample(frame)[0]
                data = frame.to_ndarray().astype(np.float32)
                data = np.transpose(data)
                data *= self.volume
                data = np.ascontiguousarray(data)

                self.stream.write(data)

            self.audio_loop_count += 1
            if self.audio_loop_count < self.loop or self.loop == 0:
                self.audio_container.seek(0)
            else:
                return

    def _video_process(self) -> None:
        """
        Extract video frames and turn them into pygame Surfaces in a loop
        """
        while not self.stopped:
            for i in self.video_container.decode(video=0):
                if self.frame[1] == "unused":
                    self.frame_ready.clear()
                else:
                    self.frame_ready.set()

                self.pause_event.wait()
                self.frame_ready.wait()

                if self.stopped:
                    break

                with self.audio_pts_lock:
                    if self.audio_pts:
                        audio_pts = self.audio_pts
                    else:
                        audio_pts = 0

                pts = (i.pts * i.time_base) / self.speed
                delay = pts - audio_pts

                if delay > 0.005:
                    time.sleep(min(delay, 0.005))
                elif delay < -0.2:
                    # frame is too late so drop it
                    continue

                frame = i.to_rgb().to_ndarray()
                frame = np.transpose(frame, (1, 0, 2))
                frame = pg.surfarray.make_surface(frame)

                with self.frame_lock:
                    self.frame = [frame, "unused"]

                time.sleep((1 / self.fps) / self.speed)

            self.video_loop_count += 1
            if self.video_loop_count < self.loop or self.loop == 0:
                self.video_container.seek(0)
            else:
                print("video ended.")
                return

    def get_frame(self, size: Point = None) -> pg.Surface:
        """
        Get the latest frame from the video as a pygame Surface.

        Params:
            - size: Point. The size of the surface to return. If `None`, the size will be the default size of the video. Defaults to `None`
        """
        with self.frame_lock:
            if size and self.size != size:
                self.frame[0] = pg.transform.scale(self.frame[0], size)

            self.frame[1] = "used"
            return self.frame[0]

    def start(self) -> None:
        """
        Starts playing the video and audio.
        """
        if self.has_audio:
            self.audio_thread = threading.Thread(
                target=self._audio_process, daemon=True
            )

        self.video_thread = threading.Thread(target=self._video_process, daemon=True)

        if self.has_audio:
            self.audio_thread.start()

        self.video_thread.start()

    def set_volume(self, volume: float) -> None:
        """
        Set the volume of the audio.

        Params:
            - volume: float. A value between 0 and 1.
        """
        self.volume = max(0, min(1.0, volume))

    def increase_volume(self, value: float) -> None:
        """
        Increase the volume by the given value.

        Params:
            - value: float. The amount to increase the volume by.
        """
        self.set_volume(self.volume + value)

    def decrease_volume(self, value: float) -> None:
        """
        Decrease the volume by the given value.

        Params:
            - value: float. The amount to decrease the volume by.
        """
        self.set_volume(self.volume - value)

    def set_playback_speed(self, value: float) -> None:
        """
        Set the playback speed of the video.

        Params:
            - value: float. The value to set the speed as.
        """
        self.speed = min(16.0, max(1.0, value))

    def increase_playback_speed(self, value: float) -> None:
        """
        increase the playback speed of the video by the given value.

        Params:
            - value: float. The amount to increase the playback speed by.
        """
        self.set_playback_speed(self.speed + value)

    def decrease_playback_speed(self, value: float) -> None:
        """
        decrease the playback speed of the video by the given value.

        Params:
            - value: float. The amount to decrease the playback speed by.
        """
        self.set_playback_speed(self.speed - value)

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

            self.audio_container.close()
            self.video_container.close()

            for i in [self.pause_event, self.frame_ready]:
                if not i.is_set:
                    i.set()

            for i in [self.audio_thread, self.video_thread]:
                try:
                    i.join()
                except Exception:
                    pass

            return
