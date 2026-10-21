import os
import random
import time

W, H = 60, 20

class Bola:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = random.randint(1, W - 2)
        self.y = random.randint(1, H - 2)
        self.vx = random.choice([-1, 1]) * random.choice([0.5, 1, 1.5])
        self.vy = random.choice([-1, 1]) * random.choice([0.5, 1, 1.5])

    def mover(self):
        self.x += self.vx
        self.y += self.vy
        if self.x <= 0:
            self.x = 0
            self.vx = abs(self.vx)
        if self.x >= W - 1:
            self.x = W - 1
            self.vx = -abs(self.vx)
        if self.y <= 0:
            self.y = 0
            self.vy = abs(self.vy)
        if self.y >= H - 1:
            self.y = H - 1
            self.vy = -abs(self.vy)


def dibujar(bolas):
    grid = [[' '] * W for _ in range(H)]
    for b in bolas:
        xi, yi = int(round(b.x)), int(round(b.y))
        if 0 <= xi < W and 0 <= yi < H:
            grid[yi][xi] = 'O'
    for f in range(H):
        print('|' + ''.join(grid[f]) + '|')


bolas = [Bola() for _ in range(8)]
try:
    for t in range(150):
        os.system('cls')
        print(f'Simulacion de rebotes - paso {t + 1}')
        for b in bolas:
            b.mover()
        dibujar(bolas)
        time.sleep(0.06)
except KeyboardInterrupt:
    print('\nSimulacion detenida')
