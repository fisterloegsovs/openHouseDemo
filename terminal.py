"""Fælles terminalhåndtering; indeholder ingen scenarier eller holdvalg."""

import ctypes
import math
import os
import shutil
import sys


class Terminal:
    """Terminaltilstand gendannes ved normal afslutning og ved exceptions."""
    def __init__(self, stream=sys.stdout):
        self.stream = stream
        self.saved = None
        self.windows_mode = None

    def __enter__(self):
        try:
            if os.name == "nt":
                from ctypes import wintypes
                kernel = ctypes.windll.kernel32
                kernel.GetStdHandle.argtypes = [wintypes.DWORD]
                kernel.GetStdHandle.restype = wintypes.HANDLE
                kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
                kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                handle = kernel.GetStdHandle(-11)
                mode = wintypes.DWORD()
                if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                    raise OSError("Åbn programmet i Windows Terminal eller PowerShell.")
                if not kernel.SetConsoleMode(handle, mode.value | 0x0004):
                    raise OSError("Terminalen understøtter ikke ANSI-visning.")
                self.windows_mode = handle, mode.value
            elif sys.stdin.isatty():
                import termios
                import tty
                self.saved = termios.tcgetattr(sys.stdin.fileno())
                tty.setcbreak(sys.stdin.fileno())
            self.stream.write("\033[?1049h\033[?25l\033[2J\033[H")
            self.stream.flush()
            return self
        except BaseException:
            self.restore()
            raise

    def key(self):
        if os.name == "nt":
            import msvcrt
            if msvcrt.kbhit():
                return msvcrt.getwch().lower()
        elif sys.stdin.isatty():
            import select
            if select.select([sys.stdin], [], [], 0)[0]:
                return os.read(sys.stdin.fileno(), 1).decode("utf-8", errors="ignore").lower()
        return ""

    def draw(self, lines):
        self.stream.write("\033[H" + "\r\n".join(line + "\033[K" for line in lines))
        self.stream.flush()

    def restore(self):
        try:
            self.stream.write("\033[0m\033[?25h\033[?1049l")
            self.stream.flush()
        finally:
            if self.saved is not None:
                import termios
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.saved)
            if self.windows_mode is not None:
                ctypes.windll.kernel32.SetConsoleMode(*self.windows_mode)

    def __exit__(self, *_):
        self.restore()


def terminal_size():
    try:
        return os.get_terminal_size(sys.stdout.fileno())
    except OSError:
        return shutil.get_terminal_size((100, 32))


def duration_arg(text):
    import argparse
    value = float(text)
    if not math.isfinite(value) or not 20 <= value <= 3600:
        raise argparse.ArgumentTypeError("Forløbet skal vare mellem 20 og 3600 sekunder.")
    return value
