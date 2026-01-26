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
        video_format: str = "rgb24",
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
        self.fps = frame_rate
        self.video_codec = video_codec
        self.video_format = video_format

        self.record_audio = record_audio
        self.frequency = frequency

        self.video_frames: list[pg.Surface] = []

        self.video_container = av.open(self.output, "w")
        self.video_stream = self.video_container.add_stream(self.video_codec, self.fps)
        self.video_stream.width = self.size[0]
        self.video_stream.height = self.size[1]
        self.video_stream.pix_fmt = self.video_format

    def write_frame(self, frame: pg.Surface) -> None:
        """
        Add a frame to the video
        """
        self.video_frames.append(frame)

    def compile_video(self) -> None:
        """
        Compile the frames into a video.
        """
        for i in self.video_frames:
            if i.get_size() != self.size:
                i = pg.transform.scale(i, self.size)

            arr = pg.surfarray.array3d(i)
            frame = av.VideoFrame().from_ndarray(arr, format=self.video_format)

            for j in self.video_stream.encode(frame):
                self.video_container.mux(j)

    def stop(self) -> None:
        for i in self.video_stream.encode():
            container.mux(i)

        self.video_container.close()
