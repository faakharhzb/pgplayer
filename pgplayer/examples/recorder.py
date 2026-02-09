import os
import time
import pygame as pg
from pgplayer import VideoRecorder

pg.init()

screen = pg.display.set_mode((1280, 720), pg.RESIZABLE)
w, h = screen.get_size()
clock = pg.time.Clock()

recorder = VideoRecorder(
    (os.path.join(os.path.dirname(__file__), "counter.mp4")), (w, h), 60
)
recorder.start()

font = pg.Font(size=200)

start = time.time()

running = True
while running:
    screen.fill("black")
    for event in pg.event.get():
        if event.type == pg.QUIT:
            running = False

        if event.type == pg.VIDEORESIZE:
            w, h = event.size

    text = font.render(f"{time.time() - start:.3f}", True, "white")
    screen.blit(text, (w // 2, h // 2))

    recorder.write_frame(screen)

    pg.display.flip()
    clock.tick()

    if time.time() - start >= 60:
        running = False

recorder.stop()
pg.quit()
