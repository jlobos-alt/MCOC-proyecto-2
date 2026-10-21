import os
import random
import time
import sys

W, H = 80, 24

if os.name == 'nt':
    os.system('')
    import msvcrt

COLORES = [31, 33, 34, 35, 36, 91, 93, 95, 96]

class Estrella:
    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        self.x = random.random() * W
        self.y = random.random() * H
        self.z = random.random() * 1.5
        self.color = random.choice(COLORES)

    def avanzar(self):
        self.z -= 0.05
        if self.z <= 0.1:
            self.reiniciar()

    def pos(self):
        return int(self.x / self.z), int(self.y / self.z)


def dibujar(estrellas, paso):
    grid = [[' '] * W for _ in range(H)]
    color_grid = [[None] * W for _ in range(H)]
    for e in estrellas:
        x, y = e.pos()
        if 0 <= x < W and 0 <= y < H:
            grid[y][x] = '#'
            color_grid[y][x] = e.color
    salida = ['\x1b[1;40m' + f'Viaje a velocidad warp - paso {paso:3d}']
    for y in range(H):
        linea = ''
        for x in range(W):
            c = grid[y][x]
            if c == ' ':
                linea += ' '
            else:
                linea += f'\x1b[{color_grid[y][x]}m*'
        salida.append(linea)
    sys.stdout.write('\x1b[H' + '\x1b[0m\n'.join(salida) + '\x1b[0m')
    sys.stdout.flush()


os.system('cls')
estrellas = [Estrella() for _ in range(80)]
try:
    for paso in range(300):
        for e in estrellas:
            e.avanzar()
        dibujar(estrellas, paso + 1)
        time.sleep(0.05)
except KeyboardInterrupt:
    sys.stdout.write('\x1b[0m\nSimulacion detenida\n')
