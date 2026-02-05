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

            - audio_codec: str. The name of the audio codec to use. Defaults to `aac`
        """
        self.output = output_file

        self.size = size
        self.fps = Fraction(frame_rate)
        self.video_codec = video_codec
        self.video_format = video_format

        self.record_audio = record_audio
        self.frequency = frequency
        self.channels = channels
        self.audio_codec = audio_codec

        self.container = av.open(self.output, "w")

        if self.record_audio:
            self.audio_stream = self.container.add_stream(
                self.audio_codec, self.frequency
            )
            self.audio_stream.layout = "stereo"
            self.audio_stream.format = "fltp"
            self.audio_stream.time_base = Fraction(1, self.frequency)

            self.input_stream = sd.InputStream(
                self.frequency, channels=self.channels, dtype=np.float32
            )

            self.audio_thread = threading.Thread(target=self._record_audio, daemon=True)
            self.audio_thread.start()
        else:
            self.audio_stream = None
            self.input_stream = None
            self.audio_thread = None

        self.video_frames: queue.Queue[pg.Surface] = queue.Queue(50)

        self.video_stream = self.container.add_stream(self.video_codec, self.fps)
        self.video_stream.width = self.size[0]
        self.video_stream.height = self.size[1]
        self.video_stream.pix_fmt = self.video_format

        self.stopped = False

        self.frame_thread = threading.Thread(target=self._write_frame, daemon=True)
        self.frame_thread.start()

    def _record_audio(self) -> None:
        """
        Gets audio and adds it to the file.
        """
        self.input_stream.start()

        pts = 0
        while not self.stopped:
            if not self.input_stream.stopped or self.input_stream.closed:
                data, overflowed = self.input_stream.read(1024)
                if overflowed:
                    raise OverflowError("Audio input stream overflowed.")

                data = np.ascontiguousarray(data.T)

                frame = av.AudioFrame.from_ndarray(
                    data, "fltp", self.audio_stream.layout
                )

                frame.pts = pts
                pts += frame.samples

                for i in self.audio_stream.encode(frame):
                    self.container.mux(i)

            for i in self.audio_stream.encode():
                self.container.mux(i)

    def _write_frame(self) -> None:
        """
        Writes video frames to the file.
        """
        start = time.perf_counter()
        prev_pts = None
        while not self.stopped:
            if self.stopped:
                break

            try:
                surf = self.video_frames.get(timeout=0.1)
            except queue.Empty:
                continue

            if surf.get_size() != self.size:
                surf = pg.transform.scale(surf, self.size)

            buf = pg.image.tobytes(surf, "RGBA")

            frame = av.VideoFrame.from_bytes(buf, self.size[0], self.size[1], "rgba")
            frame = frame.reformat(format=self.video_format)

            pts = int((time.perf_counter() - start) / (1 / float(self.fps)))
            if pts == prev_pts:
                pts += 1
            print(pts)
            frame.pts = pts

            for i in self.video_stream.encode(frame):
                self.container.mux(i)

        for i in self.video_stream.encode():
            self.container.mux(i)

    def write_frame(self, frame: pg.Surface) -> None:
        """
        Add a frame to the video.

        Params:
            - frame: pg.Surface. The surface to add to to the video.
        """
        try:
            self.video_frames.put(frame, False)
        except queue.Full:
            self.video_frames.get_nowait()
            self.video_frames.put(frame, False)

    def stop(self) -> None:
        """
        Stop the recorder.
        """
        self.stopped = True

        for i in [self.frame_thread, self.audio_thread]:
            if i:
                i.join()

            self.input_stream.close()

        self.container.close()
