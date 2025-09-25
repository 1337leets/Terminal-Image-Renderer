# console_font.py
import os
if os.name != "nt":
    def set_font_safe(face: str = "Consolas", size_y: int = 6):
        return None
    def restore_font_safe(prev):
        return None
else:
    import ctypes
    import ctypes.wintypes

    LF_FACESIZE = 32

    class COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class CONSOLE_FONT_INFOEX(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.ULONG),
            ("nFont", ctypes.wintypes.DWORD),
            ("dwFontSize", COORD),
            ("FontFamily", ctypes.c_uint),
            ("FontWeight", ctypes.c_uint),
            ("FaceName", ctypes.c_wchar * LF_FACESIZE),
        ]

    kernel32 = ctypes.windll.kernel32
    STD_OUTPUT_HANDLE = -11

    def _get_handle():
        return kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

    def _get_font_info():
        h = _get_handle()
        info = CONSOLE_FONT_INFOEX()
        info.cbSize = ctypes.sizeof(CONSOLE_FONT_INFOEX)
        ok = kernel32.GetCurrentConsoleFontEx(h, ctypes.c_bool(False), ctypes.byref(info))
        if not ok:
            return None
        return info

    def set_font_safe(face: str = "Consolas", size_y: int = 6):
        try:
            h = _get_handle()
            prev = _get_font_info()
            if prev is None:
                return None
            new = CONSOLE_FONT_INFOEX()
            new.cbSize = ctypes.sizeof(CONSOLE_FONT_INFOEX)
            new.nFont = prev.nFont
            new.dwFontSize = COORD(0, int(size_y))
            new.FontFamily = prev.FontFamily
            new.FontWeight = prev.FontWeight
            face = str(face)[:LF_FACESIZE - 1]
            new.FaceName = face
            ok = kernel32.SetCurrentConsoleFontEx(h, ctypes.c_bool(False), ctypes.byref(new))
            if not ok:
                new.FontFamily = 54
                ok = kernel32.SetCurrentConsoleFontEx(h, ctypes.c_bool(False), ctypes.byref(new))
            if not ok:
                return None
            return prev
        except Exception:
            return None

    def restore_font_safe(prev):
        if not prev:
            return
        try:
            h = _get_handle()
            prev.cbSize = ctypes.sizeof(CONSOLE_FONT_INFOEX)
            kernel32.SetCurrentConsoleFontEx(h, ctypes.c_bool(False), ctypes.byref(prev))
        except Exception:
            pass
