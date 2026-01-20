import os
import pygame as pg
from pgplayer import VideoPlayer

pg.init()

screen = pg.display.set_mode((1280, 720), pg.RESIZABLE)
w, h = screen.get_size()
clock = pg.time.Clock()

player = VideoPlayer(
    os.path.join(os.path.dirname(__file__), "video.mp4"), 1
)
player.play()

running = True
while running:
    for event in pg.event.get():
        if event.type == pg.QUIT:
            running = False

        if event.type == pg.KEYDOWN:
            if event.key == pg.K_SPACE:
                player.toggle_pause()

            if event.key == pg.K_RIGHT:
                player.increase_volume(0.05)
            if event.key == pg.K_LEFT:
                player.decrease_volume(0.05)

        if event.type == pg.VIDEORESIZE:
            w, h = event.size

    frame = player.get_frame((w, h))
    if frame:
        screen.blit(frame)

    pg.display.flip()
    clock.tick(player.fps)

player.stop()
pg.quit()
