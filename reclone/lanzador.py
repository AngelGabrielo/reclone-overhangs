"""Arranca PostgreSQL local y la aplicación web, y apaga ambos al terminar.

"Terminar" es cualquiera de estas cosas: cerrar la ventana de la consola con la
X, pulsar Ctrl+C, el botón "Apagar todo" de la aplicación o un cierre de
sesión / apagado de Windows. Un .bat no puede reaccionar al cierre de su
ventana, por eso esto se hace desde Python.
"""

from __future__ import annotations

import ctypes
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

from . import config, servidor_local

# Eventos de consola de Windows
_CTRL_C, _CTRL_BREAK, _CTRL_CLOSE, _CTRL_LOGOFF, _CTRL_SHUTDOWN = 0, 1, 2, 5, 6


def _puerto_abierto(puerto: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", puerto), timeout=0.5):
            return True
    except OSError:
        return False


def _esperar_puerto(puerto: int, segundos: float = 60) -> bool:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if _puerto_abierto(puerto):
            return True
        time.sleep(0.3)
    return False


def ejecutar(abrir_navegador: bool = True) -> int:
    if _puerto_abierto(config.APP_PUERTO):
        print(f"El puerto {config.APP_PUERTO} ya está en uso: ¿hay otra copia de la aplicación abierta?\n"
              "Ciérrala primero, o define APP_PUERTO en el archivo .env para usar otro puerto.")
        return 1

    servidor_local.iniciar()
    url = f"http://127.0.0.1:{config.APP_PUERTO}"
    print(f"Base de datos lista en 127.0.0.1:{config.PG_PUERTO}")

    entorno = dict(os.environ, RECLONE_LANZADOR="1")  # la app muestra el botón "Apagar todo"
    app = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(config.RAIZ / "app.py"),
         "--server.port", str(config.APP_PUERTO), "--server.address", "127.0.0.1",
         "--server.headless", "true"],
        cwd=config.RAIZ, env=entorno)

    apagado = threading.Lock()
    hecho = {"ya": False}

    def apagar() -> None:
        """Detiene la app y la base de datos. Seguro de llamar varias veces."""
        with apagado:
            if hecho["ya"]:
                return
            hecho["ya"] = True
            if app.poll() is None:
                app.terminate()
                try:
                    app.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    app.kill()
            servidor_local.detener()

    if sys.platform == "win32":
        # Windows da solo ~5 s para terminar tras cerrar la ventana: pg_ctl en modo
        # "fast" tarda uno o dos. Ctrl+C se deja pasar para que Python lo maneje.
        firma = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

        def manejador(evento: int) -> bool:
            if evento in (_CTRL_CLOSE, _CTRL_LOGOFF, _CTRL_SHUTDOWN):
                apagar()
                return True
            return False

        referencia = firma(manejador)  # conservar la referencia: si no, se recoge y falla
        ctypes.windll.kernel32.SetConsoleCtrlHandler(referencia, True)

    try:
        if _esperar_puerto(config.APP_PUERTO):
            print(f"Aplicación lista en {url}")
            print("\nPara terminar: cierra esta ventana, pulsa Ctrl+C o usa «Apagar todo» en la aplicación.")
            print("Al terminar se apaga también la base de datos.\n")
            if abrir_navegador:
                webbrowser.open(url)
        else:
            print("La aplicación no respondió a tiempo; revisa los mensajes de arriba.")
        app.wait()
    except KeyboardInterrupt:
        print("\nApagando…")
    finally:
        apagar()
    print("Todo apagado.")
    return 0
