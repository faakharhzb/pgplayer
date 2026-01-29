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
        frame_rate: int = 60,
        video_codec: str = "libx264",
        video_format: str = "yuv420p",
        frequency: int = 44100,
        record_audio: bool = True,
    ) -> None:
        """
        The constructor for the VideoRecorder class

        Params:
            - output_file: str. The file where the output will be stored.

            - size: Point. The dimensions of the video.

            - frame_rate: int. The frame rate of the video. Defaults to 60

            - video_codec: The name of the video codec to use. Defaults to `libx264`.

            - video_format: str. The format of the video. Defaults to `rgb24`

            - record_audio: bool. Whether or not audio will be recorded. Defaults to True.

            - frequency: int. The frequency of the audio. Defaults to 44100
        """
        self.output = output_file
        self.size = size
        self.fps = Fraction(frame_rate)
        self.video_codec = video_codec
        self.video_format = video_format
        self.frame_count = 0

        self.record_audio = record_audio
        self.frequency = frequency

        self.video_frames: queue.Queue[pg.Surface] = queue.Queue(50)

        self.video_container = av.open(self.output, "w")
        self.video_stream = self.video_container.add_stream(self.video_codec, self.fps)
        self.video_stream.width = self.size[0]
        self.video_stream.height = self.size[1]
        self.video_stream.pix_fmt = self.video_format

        self.stopped = False

        self.frame_thread = threading.Thread(target=self._write_frame, daemon=True)
        self.frame_thread.start()

        self.start_time = time.perf_counter()

    def _write_frame(self) -> None:
        while not self.stopped:
            if self.stopped:
                self.stop()

            try:
                frame = self.video_frames.get(timeout=0.1)
            except queue.Empty:
                continue

            if frame.get_size() != self.size:
                frame = pg.transform.scale(frame, self.size)

            arr = pg.surfarray.array3d(frame)
            arr = np.transpose(arr, (1, 0, 2))
            frame = av.VideoFrame.from_ndarray(arr, format="rgb24")

            now = time.perf_counter() - self.start_time
            frame.pts = now / (Fraction(1, int(self.fps)))

            for j in self.video_stream.encode(frame):
                self.video_container.mux(j)

    def write_frame(self, frame: pg.Surface) -> None:
        """
        Add a frame to the video.
        """
        try:
            self.video_frames.put(frame, False)
        except queue.Full:
            self.video_frames.get_nowait()
            self.video_frames.put(frame, False)

    def stop(self) -> None:
        self.stopped = True

        for i in [self.frame_thread]:
            if i:
                i.join()

        for i in self.video_stream.encode():
            self.video_container.mux(i)

        self.video_container.close()

        return
