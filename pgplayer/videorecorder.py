from fractions import Fraction
import threading
import time
import queue

import av
import pygame as pg
import numpy as np
from pygame.typing import Point
import sounddevice as sd


class VideoRecorder:
    def __init__(
        self,
        output_file: str,
        size: Point,
        frame_rate: int = 30,
        video_codec: str = "libx264",
        video_format: str = "yuv420p",
        record_audio: bool = False,
        frequency: int = 44100,
        channels: int = 2,
        channel_layout: str = "stereo",
        audio_codec: str = "aac",
    ) -> None:
        """
        The constructor for the VideoRecorder class

        Params:
            - output_file: str. The file where the output will be stored.

            - size: Point. The dimensions of the video.

            - frame_rate: int. The frame rate of the video. Defaults to 30

            - video_codec: The name of the video codec to use. Defaults to `libx264`.

            - video_format: str. The format of the video. Defaults to `rgb24`

            - record_audio: bool. Whether or not audio will be recorded. Defaults to True.

            - frequency: int. The frequency of the audio. Defaults to 44100

            - channels: int. The amount of audio channels. Defaults to 2.

            - channel_layout: str. The layout of the audio channels. Defaults to `stereo`.

            - audio_codec: str. The name of the audio codec to use. Defaults to `aac`
        """
        self._output = output_file

        self._size = size
        self._fps = Fraction(frame_rate)
        self._video_codec = video_codec
        self._pixel_format = video_format

        self._record_audio = record_audio
        self._frequency = frequency
        self._channels = channels
        self._channel_layout = channel_layout
        self._audio_codec = audio_codec

        self._container = av.open(self._output, "w")

        if self._record_audio:
            self._audio_stream = self._container.add_stream(
                self._audio_codec, self._frequency
            )
            self._audio_stream.layout = self._channel_layout
            self._audio_stream.format = "fltp"
            self._audio_stream.time_base = Fraction(1, self._frequency)

            self._input_stream = sd.InputStream(
                self._frequency, channels=self._channels, dtype=np.float32
            )

            self._audio_thread = None
        else:
            self._audio_stream = None
            self._input_stream = None
            self._audio_thread = None

        self._video_frames: queue.Queue[pg.Surface] = queue.Queue(50)

        self._video_stream = self._container.add_stream(self._video_codec, self._fps)
        self._video_stream.width = self._size[0]
        self._video_stream.height = self._size[1]
        self._video_stream.pix_fmt = self._pixel_format

        self._stopped = False

        self._frame_thread = None

    @property
    def output_file(self) -> str:
        """
        The name of the output file (read-only).
        """
        return self._output

    @property
    def width(self) -> int:
        """
        The width of the video in pixels(read-only).
        """
        return self._size[0]

    @property
    def height(self) -> int:
        """
        The height of the video in pixels (read-only).
        """
        return self._size[1]

    @property
    def size(self) -> tuple[int, int]:
        """
        The size of the video in pixels (read-only).
        """
        return self._size

    @property
    def fps(self) -> int:
        """
        The FPS of the video (read-only).
        """
        return int(self._fps)

    @property
    def video_codec(self) -> str:
        """
        The codec of the video (read-only).
        """
        return self._video_codec

    @property
    def pixel_format(self) -> str:
        """
        The pixel format of the video (read-only).
        """
        return self._pixel_format

    @property
    def frequency(self) -> int:
        """
        The frequency of the audio in hertz (read-only).
        """
        return self._frequency

    @property
    def channels(self) -> int:
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
    def record_audio(self) -> bool:
        """
        Whether or not the audio will be recorded (read-only).
        """
        return self._record_audio

    @property
    def stopped(self) -> bool:
        """
        Whether or not the video recording has been stopped(read-only).
        """
        return self._stopped

    def start(self) -> None:
        """
        Start the video recorder.
        """
        if self._record_audio:
            self._audio_thread = threading.Thread(
                target=self._audio_record, daemon=True
            )
            self._audio_thread.start()

        self._frame_thread = threading.Thread(target=self._write_frame, daemon=True)
        self._frame_thread.start()

    def _audio_record(self) -> None:
        """
        Gets audio and adds it to the file.
        """
        self._input_stream.start()

        pts = 0
        while not self._stopped:
            if not self._input_stream.stopped or self._input_stream.closed:
                data, overflowed = self._input_stream.read(1024)
                if overflowed:
                    raise OverflowError("Audio input stream overflowed.")

                data = np.ascontiguousarray(data.T)

                frame = av.AudioFrame.from_ndarray(
                    data, "fltp", self._audio_stream.layout
                )

                frame.pts = pts
                pts += frame.samples

                for i in self._audio_stream.encode(frame):
                    self._container.mux(i)

            for i in self._audio_stream.encode():
                self._container.mux(i)

    def _write_frame(self) -> None:
        """
        Writes video frames to the file.
        """
        start = time.perf_counter()
        while not self._stopped:
            if self._stopped:
                break

            try:
                surf = self._video_frames.get(timeout=0.1)
            except queue.Empty:
                continue

            if surf.get_size() != self._size:
                surf = pg.transform.scale(surf, self._size)

            buf = pg.image.tobytes(surf, "RGBA")

            frame = av.VideoFrame.from_bytes(buf, self._size[0], self._size[1], "rgba")
            frame = frame.reformat(format=self._pixel_format)

            now = int((time.perf_counter() - start) * float(self._fps))
            frame.pts = now
            frame.time_base = Fraction(1, self._fps)

            for i in self._video_stream.encode(frame):
                self._container.mux(i)

            time.sleep(float(frame.time_base))

        for i in self._video_stream.encode():
            self._container.mux(i)

    def write_frame(self, frame: pg.Surface) -> None:
        """
        Add a frame to the video.

        Params:
            - frame: pg.Surface. The surface to add to to the video.
        """
        try:
            self._video_frames.put(frame, False)
        except queue.Full:
            self._video_frames.get_nowait()
            self._video_frames.put(frame, False)

    def stop(self) -> None:
        """
        Stop the recorder.
        """
        self._stopped = True

        for i in [self._frame_thread, self._audio_thread]:
            if i:
                i.join()

        if self._record_audio:
            self._input_stream.close()

        self._container.close()
