import os
import shutil
import time
import threading
import subprocess

import pygame as pg
from pygame.typing import Point
import av
from av.audio.resampler import AudioResampler
import sounddevice as sd
import numpy as np


class VideoPlayer:
    def __init__(
        self,
        source: str,
        speed: float = 1,
        frame_rate: int = 30,
        video_size: tuple[int, int] = (640, 480),
        pixel_format: str = "rgb24",
        video_codec: str = "hx264",
        volume: float = 1,
        loop: int = 1,
        frequency: int = 44100,
        channels: int = 2,
        channel_layout: str = "stereo",
        audio_codec: str = "aac",
        play_audio: bool = True,
    ) -> None:
        """
        The constructor for the VideoPlayer class.

        Params:
            - source: str | bytes. A file path or a URL. Raises FileNotFoundError if source is a non-existent file path. If `source` is a URL, then it can either be a direct video URL, or a URL for a media site like `youtube.com`. If so, the program `ffmpeg` would need to be installed and available on PATH.

            - speed: float. The playback speed for the video. Defaults to 1.

            - frame_rate: int | None. The default frame rate of the video. Defaults to 30 FPS.

            - video_size: tuple[int, int]. The default size of the video in pixels. Defaults to `640x480`.

            - pixel_format: str. The pixel format of the video frames. Defaults to `rgb24`.

            - video_codec: str. The video codec to use. Defaults to `hx264`.

            - volume: float. A value between 0 and 1. Defaults to 1.

            - loop: int. The amount of times the video will loop. Video will repeat forever if loop = 0. Defaults to 1.

            - frequency: int. The frequency of the audio. Defaults to 44100.

            - channels: int. The number of audio channels. Defaults to 2.

            - channel_layout: str. The layout of the audio channels. Defaults to `stereo`.

            - audio_codec: str. The audio codec to use. Defaults to `aac`.

            - play_audio: bool. Whether or not the audio will play. Defaults to `True`.
        """
        self._source = self._parse_source(source)
        self._speed = max(0.1, min(8.0, speed))

        self._fps = frame_rate
        self._size = video_size
        self._pixel_format = pixel_format
        self._video_codec = video_codec

        self._volume = max(0, min(1.0, volume))
        self._loop = max(0, loop)
        self._frequency = frequency
        self._channels = channels
        self._channel_layout = channel_layout
        self._audio_codec = audio_codec
        self._play_audio = play_audio

        self._audio_opts = {
            "sample_rate": str(self._frequency),
            "channels": str(self._channels),
            "channel_layout": self._channel_layout,
            "codec": self._audio_codec,
        }
        self._video_opts = {
            "video_size": f"{self._size[0]}x{self._size[1]}",
            "framerate": str(self._fps),
            "pixel_format": self._pixel_format,
            "codec": self._video_codec,
        }

        if self._play_audio:
            self._audio_container = av.open(self._source, options=self._audio_opts)
            self._audio_stream = self._audio_container.streams.audio
        else:
            self._audio_container = None
            self._audio_stream = None

        if self._audio_stream and self._play_audio:
            self._audio_stream = self._audio_stream[0]
            self._stream = sd.OutputStream(
                samplerate=self._frequency,
                channels=self._audio_stream.channels,
                dtype=np.float32,
            )
            self._resampler = AudioResampler(
                "fltp", self._audio_stream.layout.name, self._frequency
            )

            self._has_audio = True
        else:
            self._has_audio = False

        self._video_container = av.open(self._source, options=self._video_opts)
        self._video_stream = self._video_container.streams.video[0]

        self._fps = float(self._video_stream.average_rate)
        self._duration = float(
            self._video_stream.duration * self._video_stream.time_base
        )

        self._w = self._video_stream.width
        self._h = self._video_stream.height
        self._size = (self._w, self._h)

        self._audio_loop_count = 0
        self._video_loop_count = 0

        self._paused = False
        self._stopped = False

        self._frame = pg.Surface((self._w, self._h))

        self._audio_thread = None
        self._video_thread = None

        self._pause_event = threading.Event()
        self._pause_event.set()

        self._frame_lock = threading.Lock()

        self._time_lock = threading.Lock()
        self._time = 0.0
        self._idx = 0

    @property
    def source(self) -> str:
        """
        The source of the video (read-only).
        """
        return self._source

    @property
    def speed(self) -> float:
        """
        The speed at which the video plays (read-only).
        """
        return self._speed

    @property
    def fps(self) -> int:
        """
        The FPS of the video (read-only).
        """
        return self._fps

    @property
    def width(self) -> int:
        """
        The width of the video in pixels (read-only).
        """
        return self._w

    @property
    def height(self) -> int:
        """
        The height of the video in pixels (read-only).
        """
        return self._h

    @property
    def size(self) -> tuple[int, int]:
        """
        The size of the video in pixels (read-only).
        """
        return self._size

    @property
    def pixel_format(self) -> str:
        """
        The pixel format of the video (read-only).
        """
        return self._pixel_format

    @property
    def video_codec(self) -> str:
        """
        The codec of the video (read-only).
        """
        return self._video_codec

    @property
    def volume(self) -> float:
        """
        The volume at which the audio plays (read-only).
        """

    @property
    def loop(self) -> int:
        """
        The number of times the video will loop (read-only).
        """
        return self._loop

    @property
    def frequency(self) -> int:
        """
        The frequency of the audio in hertz (read-only).
        """
        return self._frequency

    @property
    def channels(self) -> str:
        """
        The number of audio channels (read-only).
        """
        return self._channels

    @property
    def channel_layout(self) -> str:
        """
        The layout of the audio channels (read-only).
        """
        return self._channel_layout

    @property
    def audio_codec(self) -> str:
        """
        The codec of the audio (read-only).
        """
        return self._audio_codec

    @property
    def play_audio(self) -> bool:
        """
        Whether or not the audio will play (read-only).
        """
        return self._play_audio

    @property
    def has_audio(self) -> bool:
        """
        Whether or not the video file contains audio (read-only).
        """
        return self._has_audio

    @property
    def duration(self) -> float:
        """
        The duration of the video in seconds (read-only).
        """
        return self._duration

    @property
    def paused(self) -> bool:
        """
        Whether or not the video playback is paused (read-only).
        """
        return self._paused

    @property
    def stopped(self) -> bool:
        """
        Whether or not the video player has been stopped (read-only).
        """
        return self._stopped

    def _parse_source(self, source: str):
        if os.path.exists(source):
            return source

        try:
            subprocess.run(
                ["yt-dlp", "--skip-download", "--quiet", source],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            is_special = True
        except subprocess.CalledProcessError:
            is_special = False

        if is_special:
            if not shutil.which("ffmpeg"):
                print("FFmpeg must be installed. https://ffmpeg.com")
                raise SystemExit

            process = subprocess.run(
                ["yt-dlp", "--quiet", "-g", source],
                capture_output=True,
                text=True,
                check=True,
            )
            return process.stdout
        else:
            return source

    def _audio_process(self) -> None:
        self._stream.start()

        while not self._stopped:
            for frame in self._audio_container.decode(audio=0):
                if self._stopped:
                    break

                self._pause_event.wait()

                with self._time_lock:
                    self._idx = frame.pts
                    self._time = frame.pts * float(frame.time_base)

                frame = self._resampler.resample(frame)[0]
                data = frame.to_ndarray().astype(np.float32)
                data = np.transpose(data)
                data *= self._volume
                data = np.ascontiguousarray(data)

                if self._speed != 1:
                    indices = np.arange(0, len(data), self._speed).astype(int)
                    indices = indices[indices < len(data)]

                    data = data[indices]

                if self._stream.closed or self._stopped or not self._stream.active:
                    break

                self._stream.write(data)

            self._audio_loop_count += 1
            if self._audio_loop_count < self._loop or self._loop == 0:
                self._audio_container.seek(0)
            else:
                self.stop()

    def _video_process(self) -> None:
        """
        Extract video frames and turn them into pygame Surfaces in a loop
        """
        while not self._stopped:
            last_time = 0
            for i in self._video_container.decode(video=0):
                self._pause_event.wait()

                if self._stopped:
                    break

                with self._time_lock:
                    audio_pts = self._time

                pts = float(i.pts * i.time_base) / self._speed
                delay = pts - audio_pts

                if delay > 0.005:
                    time.sleep(min(delay, 0.005))
                elif delay < -0.005:
                    # frame is too late so drop it
                    continue

                if pts - last_time < 1 / (self._fps * self._speed):
                    continue

                if not self.has_audio or not self.play_audio:
                    with self._time_lock:
                        self._time = pts
                        self._idx = i.pts

                frame = i.to_ndarray(format="rgb24")
                frame = np.transpose(frame, (1, 0, 2))
                frame = pg.surfarray.make_surface(frame)

                with self._frame_lock:
                    self._frame = frame

                time.sleep(1 / self._fps)

            self._video_loop_count += 1
            if self._video_loop_count < self._loop or self._loop == 0:
                self._video_container.seek(0)
            else:
                self.stop()

    def get_frame(self, size: Point = None) -> pg.Surface:
        """
        Get the latest frame from the video as a pygame Surface.

        Params:
            - size: Point. The size of the surface to return. If `None`, the size will be the default size of the video frame. Defaults to `None`.
        """
        with self._frame_lock:
            if size and self._size != size:
                self._frame = pg.transform.scale(self._frame, size)

            return self._frame

    def start(self) -> None:
        """
        Starts playing the video and audio.
        """
        if self._has_audio and self._play_audio:
            self._audio_thread = threading.Thread(
                target=self._audio_process, daemon=True
            )

        self._video_thread = threading.Thread(target=self._video_process, daemon=True)

        if self._has_audio and self._play_audio:
            self._audio_thread.start()

        self._video_thread.start()

    def move(self, timestamp: float) -> None:
        """
        Move the audio and video to the given timestamp.

        Params:
            - timestamp: float. The time to move the playback to in seconds.
        """
        _time = min(self._duration, max(0, timestamp))
        idx = int(_time // self._video_stream.time_base)

        was_playing = self._paused
        if was_playing:
            self.toggle_pause()

        if self._play_audio and self._has_audio:
            self._audio_container.seek(idx, stream=self._audio_stream)

        self._video_container.seek(idx, stream=self._video_stream)

        with self._time_lock:
            self._time = _time
            self._idx = idx

        if was_playing:
            self.toggle_pause()

    def forward(self, seconds: float) -> None:
        """
        Forward the audio and video playback by the given value.

        Params:
            - seconds: float. The number of seconds to forward by.
        """
        with self._time_lock:
            current_time = self._time

        self.move(current_time + seconds)

    def rewind(self, seconds: float) -> None:
        """
        Rewind the audio and video playback by the given value.

        Params:
            - seconds: float. The number of seconds to rewind by.
        """
        with self._time_lock:
            current_time = self._time
        self.move(current_time - seconds)

    def move_frame(self, frame_number: int) -> None:
        """
        Move the audio and video to the given frame number.

        Params:
            - frame_number: into. The frame to move the playback to.
        """
        idx = min(self._duration * self._video_stream.time_base, max(0, frame_number))
        _time = idx / self._video_stream.time_base

        if not self.paused:
            self.toggle_pause()

        if self._play_audio and self._has_audio:
            self._audio_container.seek(idx, stream=self._audio_stream)

        self._video_container.seek(idx, stream=self._video_stream)

        with self._time_lock:
            self._time = _time
            self._idx = idx

        if self.paused:
            self.toggle_pause()

    def forward_frame(self, frames: int) -> None:
        """
        Forward the audio and video playback by the given frames.

        Params:
            - frames: int. The number of frames to forward by.
        """
        with self._time_lock:
            current_frame = self._idx

        self.move_frame(current_frame + frames)

    def rewind_frame(self, frames: int) -> None:
        """
        Rewind the audio and video playback by the given frames.

        Params:
            - frames: int. The number of frames to rewind by.
        """
        with self._time_lock:
            current_frame = self._idx

        self.move_frame(current_frane - frames)

    def set_volume(self, volume: float) -> None:
        """
        Set the volume of the audio.

        Params:
            - volume: float. A value between 0 and 1.
        """
        self._volume = max(0, min(1.0, volume))

    def increase_volume(self, value: float) -> None:
        """
        Increase the volume by the given value.

        Params:
            - value: float. The amount to increase the volume by.
        """
        self.set_volume(self._volume + value)

    def decrease_volume(self, value: float) -> None:
        """
        Decrease the volume by the given value.

        Params:
            - value: float. The amount to decrease the volume by.
        """
        self.set_volume(self._volume - value)

    def set_playback_speed(self, value: float) -> None:
        """
        Set the playback speed of the video.

        Params:
            - value: float. The value to set the speed as.
        """
        self._speed = min(8.0, max(0.1, value))

    def increase_playback_speed(self, value: float) -> None:
        """
        increase the playback speed of the video by the given value.

        Params:
            - value: float. The amount to increase the playback speed by.
        """
        self.set_playback_speed(self._speed + value)

    def decrease_playback_speed(self, value: float) -> None:
        """
        decrease the playback speed of the video by the given value.

        Params:
            - value: float. The amount to decrease the playback speed by.
        """
        self.set_playback_speed(self._speed - value)

    def toggle_pause(self) -> None:
        """Pauses or resumes the audio and video."""
        if self._pause_event.is_set():
            self._pause_event.clear()
            self._paused = True
        else:
            self._pause_event.set()
            self._paused = False

    def stop(self) -> None:
        """Stops the VideoPlayer class."""
        if not self._stopped:
            # # for debugging purposes
            # print(f"Duration: {self._duration / self._speed}")
            # with self._time_lock:
            #     print(f"pts duration: {self._time}")

            self._stopped = True

            if not self._pause_event.is_set():
                self._pause_event.set()

            for i in [self._audio_thread, self._video_thread]:
                try:
                    i.join()
                except Exception:
                    pass

            if self._has_audio and self._play_audio:
                self._audio_container.close()
                self._stream.abort()
                self._stream.stop()
                self._stream.close()

            self._video_container.close()

            return
