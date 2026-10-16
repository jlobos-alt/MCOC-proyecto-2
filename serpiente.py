import os
import random
import sys
import time

if os.name == 'nt':
    import ctypes
    import msvcrt
    ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)

ANCHO, ALTO = 30, 12
TECLAS = {b'H': 'arriba', b'K': 'izq', b'M': 'der', b'P': 'abajo'}
DIRECCIONES = {'arriba': (0, -1), 'abajo': (0, 1), 'izq': (-1, 0), 'der': (1, 0)}


def limpiar():
    os.system('cls')


def dibujar(snake, comida, puntos, vel, msg=''):
    filas = []
    cabeza = snake[0]
    cuerpo = set(snake[1:])
    for y in range(ALTO):
        fila = ''
        for x in range(ANCHO):
            if (x, y) == cabeza:
                fila += '@'
            elif (x, y) in cuerpo:
                fila += 'o'
            elif (x, y) == comida:
                fila += '*'
            else:
                fila += ' '
        filas.append(fila)
    borde = '=' * (ANCHO + 2)
    limpiar()
    print(borde)
    print('  PUNTOS: ' + str(puntos) + '   (flechas para mover, ESC salir)')
    for f in filas:
        print('|' + f + '|')
    print(borde)
    if msg:
        print(msg)


def juego():
    snake = [(ALTO // 2, ANCHO // 2)]
    dir_actual = 'der'
    comida = (random.randrange(ANCHO), random.randrange(ALTO))
    puntos = 0
    vel = 0.15
    while True:
        dibujar(snake, comida, puntos, vel)
        if msvcrt.kbhit():
            tecla = msvcrt.getch()
            if tecla == b'\x1b':
                break
            if tecla in (b'\xe0', b'\x00'):
                tecla = msvcrt.getch()
                nueva = TECLAS.get(tecla)
                if nueva and not (
                    (nueva == 'arriba' and dir_actual == 'abajo') or
                    (nueva == 'abajo' and dir_actual == 'arriba') or
                    (nueva == 'izq' and dir_actual == 'der') or
                    (nueva == 'der' and dir_actual == 'izq')
                ):
                    dir_actual = nueva
        dx, dy = DIRECCIONES[dir_actual]
        cabeza = (snake[0][0] + dx, snake[0][1] + dy)
        if cabeza in snake or not (0 <= cabeza[0] < ANCHO) or not (0 <= cabeza[1] < ALTO):
            dibujar(snake, comida, puntos, vel, '  FIN DEL JUEGO - PUNTOS: ' + str(puntos))
            time.sleep(2)
            break
        snake.insert(0, cabeza)
        if cabeza == comida:
            puntos += 1
            vel = max(0.05, vel * 0.97)
            while comida in snake:
                comida = (random.randrange(ANCHO), random.randrange(ALTO))
        else:
            snake.pop()
        time.sleep(vel)


if __name__ == '__main__':
    limpiar()
    print('JUEGO DE LA SERPIENTE')
    print()
    print('La serpiente es @ (cabeza) con cuerpo o.')
    print('Come el * rojo para sumar puntos.')
    print('No choques con las paredes ni contigo mismo.')
    print()
    print('Usa las FLECHAS del teclado para moverte.')
    print('ESC para salir.')
    print()
    print('Presiona ESPACIO para empezar...')
    msvcrt.getch()
    limpiar()
    try:
        juego()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write('\x1b[0m\nFin del juego. Gracias por jugar!\n')
