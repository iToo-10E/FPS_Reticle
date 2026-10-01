"""設定可能なセンタードットレティクルを描画するWindowsオーバーレイ"""

from __future__ import annotations

import argparse
import math
import re
import sys
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable


# ===== ユーザー調整可能なデフォルト値 ============================================
#
# スクリプトを起動するたびにコマンドラインオプションを指定せずに、
# 外観や動作を変更したい場合は、これらの定数を編集してください。
# コマンドラインのフラグは常にここに記載された値を上書きします。
DEFAULT_RADIUS_PX = 2  # ピクセル単位の半径（1 => 直径2px）。小数も使用可能。
DEFAULT_DOT_COLOR = "#00E33A"  # RGBAに解析される16進数カラーコード
DEFAULT_WINDOW_ALPHA = None  # None => カラーに含まれるアルファチャンネルを使用
DEFAULT_OUTLINE_WIDTH = 0
DEFAULT_HOTKEY_TOGGLE = "<Control-Alt-c>"
DEFAULT_HOTKEY_QUIT = "<Control-Alt-q>"
# ================================================================================


DOT_COLOR_PATTERN = re.compile(r"^#?(?P<rgb>[0-9a-fA-F]{6})(?P<alpha>[0-9a-fA-F]{2})?$")


def _parse_hex_color(value: str) -> tuple[int, int, int, int]:
    """``#RRGGBB`` または ``#RRGGBBAA`` の色文字をRGBAのタプルに変換します。"""

    match = DOT_COLOR_PATTERN.match(value.strip())
    if not match:
        raise ValueError("Invalid colour literal")

    rgb = match.group("rgb")
    alpha = match.group("alpha") or "FF"
    r = int(rgb[0:2], 16)
    g = int(rgb[2:4], 16)
    b = int(rgb[4:6], 16)
    a = int(alpha, 16)
    return r, g, b, a


DEFAULT_DOT_RGBA = _parse_hex_color(DEFAULT_DOT_COLOR)
DEFAULT_DIAMETER_PX = max(1.0, float(DEFAULT_RADIUS_PX) * 2)


@dataclass
class ReticleConfig:
    """レティクルの外観と動作を制御する設定値。"""

    diameter: float = DEFAULT_DIAMETER_PX
    dot_rgba: tuple[int, int, int, int] = DEFAULT_DOT_RGBA
    outline_rgba: tuple[int, int, int, int] | None = None
    outline_width: int = DEFAULT_OUTLINE_WIDTH
    window_alpha: int = DEFAULT_DOT_RGBA[3]
    hotkey_toggle: str = DEFAULT_HOTKEY_TOGGLE
    hotkey_quit: str = DEFAULT_HOTKEY_QUIT

    @property
    def radius(self) -> float:
        return self.diameter / 2


def parse_color(value: str) -> tuple[int, int, int, int]:
    """16進数のカラー文字列をRGBAタプルに解析します。"""

    try:
        return _parse_hex_color(value)
    except ValueError as exc:  # pragma: no cover - 防御的分岐
        raise argparse.ArgumentTypeError(
            "Colour must be a hex value like '#RRGGBB' or '#RRGGBBAA'."
        ) from exc


def parse_args(argv: list[str]) -> ReticleConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--radius",
        type=float,
        default=DEFAULT_RADIUS_PX,
        help="Radius of the dot in pixels.",
    )
    parser.add_argument(
        "--diameter",
        "--size",
        type=float,
        help="Optional diameter in pixels (overrides --radius if supplied).",
    )
    parser.add_argument(
        "--color",
        type=parse_color,
        default=DEFAULT_DOT_RGBA,
        help="Dot colour in hex (e.g. #ff0000 or #ff0000aa).",
    )
    parser.add_argument(
        "--outline-color",
        type=parse_color,
        help="Outline colour in hex. Leave unset for no outline.",
    )
    parser.add_argument(
        "--outline-width",
        type=int,
        default=DEFAULT_OUTLINE_WIDTH,
        help="Outline width in pixels. Set to 0 to disable the outline.",
    )
    parser.add_argument(
        "--alpha",
        type=int,
        default=DEFAULT_WINDOW_ALPHA,
        help="Window alpha (0-255). Defaults to the colour alpha or 255.",
    )
    parser.add_argument(
        "--hotkey-toggle",
        default=DEFAULT_HOTKEY_TOGGLE,
        help="Hotkey for toggling visibility (Tk-style syntax).",
    )
    parser.add_argument(
        "--hotkey-quit",
        default=DEFAULT_HOTKEY_QUIT,
        help="Hotkey for quitting the application.",
    )

    args = parser.parse_args(argv)

    dot_rgba = args.color
    if args.radius is not None and args.radius <= 0:
        parser.error("--radius must be a positive number.")
    if args.diameter is not None:
        if args.diameter <= 0:
            parser.error("--diameter must be a positive number.")
        diameter = float(args.diameter)
    else:
        diameter = float(args.radius) * 2
    diameter = max(1.0, diameter)

    outline_rgba = None
    if args.outline_width > 0 and args.outline_color is not None:
        outline_rgba = args.outline_color

    window_alpha = args.alpha if args.alpha is not None else dot_rgba[3]
    window_alpha = max(0, min(255, window_alpha))

    return ReticleConfig(
        diameter=diameter,
        dot_rgba=dot_rgba,
        outline_rgba=outline_rgba,
        outline_width=max(0, args.outline_width),
        window_alpha=window_alpha,
        hotkey_toggle=args.hotkey_toggle,
        hotkey_quit=args.hotkey_quit,
    )


def _configure_dpi() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


HCURSOR = getattr(wintypes, "HCURSOR", wintypes.HANDLE)
HICON = getattr(wintypes, "HICON", wintypes.HANDLE)


if ctypes.sizeof(ctypes.c_void_p) == ctypes.sizeof(ctypes.c_long):
    LRESULT = ctypes.c_long
else:
    LRESULT = ctypes.c_longlong

WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 1)]


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


DIB_RGB_COLORS = 0
ULW_ALPHA = 0x00000002
AC_SRC_ALPHA = 0x01
AC_SRC_OVER = 0x00

WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

WS_POPUP = 0x80000000

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

WM_DESTROY = 0x0002
WM_ERASEBKGND = 0x0014
WM_SETCURSOR = 0x0020
WM_MOUSEACTIVATE = 0x0021
WM_NCHITTEST = 0x0084
WM_DISPLAYCHANGE = 0x007E
WM_DPICHANGED = 0x02E0
WM_HOTKEY = 0x0312

MA_NOACTIVATE = 3
HTTRANSPARENT = -1

SM_CXSCREEN = 0
SM_CYSCREEN = 1

MOD_NOREPEAT = 0x4000

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# 64ビットビルドにおける32ビット切捨てを防止するための関数プロトタイプ
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(BITMAPINFO),
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.HANDLE,
    wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC

gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ

gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL

gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL

user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND,
    wintypes.HDC,
    ctypes.POINTER(POINT),
    ctypes.POINTER(SIZE),
    wintypes.HDC,
    ctypes.POINTER(POINT),
    wintypes.COLORREF,
    ctypes.POINTER(BLENDFUNCTION),
    wintypes.DWORD,
]
user32.UpdateLayeredWindow.restype = wintypes.BOOL

user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
user32.RegisterClassW.restype = wintypes.ATOM

user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_uint,
]
user32.SetWindowPos.restype = wintypes.BOOL

user32.SetCursor.argtypes = [HCURSOR]
user32.SetCursor.restype = HCURSOR

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL

user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

user32.PostQuitMessage.argtypes = [ctypes.c_int]

user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]


class HotkeyRegistrationError(RuntimeError):
    """ホットキーのバインドを変換または登録できない場合に発生します。"""


def _parse_hotkey(binding: str) -> tuple[int, int]:
    """Tkスタイルのバインド文字列を ``RegisterHotKey`` 用のタプルに変換します。"""

    if not binding.startswith("<") or not binding.endswith(">"):
        raise ValueError("Hotkey must be wrapped in angle brackets, e.g. '<Control-Alt-c>'.")

    tokens = [token for token in binding[1:-1].split("-") if token]
    if not tokens:
        raise ValueError("Hotkey definition is empty.")

    key_token = tokens[-1].lower()
    modifier_tokens = [token.lower() for token in tokens[:-1]]

    modifier_map = {
        "alt": 0x0001,
        "control": 0x0002,
        "ctrl": 0x0002,
        "shift": 0x0004,
        "win": 0x0008,
        "windows": 0x0008,
    }

    modifiers = 0
    for modifier in modifier_tokens:
        if modifier not in modifier_map:
            raise ValueError(f"Unsupported modifier '{modifier}' in hotkey definition.")
        modifiers |= modifier_map[modifier]

    virtual_key_map = {
        "space": 0x20,
        "tab": 0x09,
        "escape": 0x1B,
        "esc": 0x1B,
        "enter": 0x0D,
        "return": 0x0D,
        "up": 0x26,
        "down": 0x28,
        "left": 0x25,
        "right": 0x27,
        "home": 0x24,
        "end": 0x23,
        "pageup": 0x21,
        "pagedown": 0x22,
        "insert": 0x2D,
        "delete": 0x2E,
        "backspace": 0x08,
        "minus": 0xBD,
        "plus": 0xBB,
        "comma": 0xBC,
        "period": 0xBE,
    }

    if key_token in virtual_key_map:
        virtual_key = virtual_key_map[key_token]
    elif len(key_token) == 1:
        virtual_key = ord(key_token.upper())
    elif key_token.startswith("f") and key_token[1:].isdigit():
        number = int(key_token[1:])
        if number < 1 or number > 24:
            raise ValueError("Function key hotkeys must be between F1 and F24.")
        virtual_key = 0x70 + (number - 1)
    else:
        raise ValueError(f"Unsupported key '{key_token}' in hotkey definition.")

    return modifiers, virtual_key


def _premultiply_rgba(rgba: tuple[int, int, int, int]) -> int:
    r, g, b, a = rgba
    if a <= 0:
        return 0
    pre_r = (r * a + 127) // 255
    pre_g = (g * a + 127) // 255
    pre_b = (b * a + 127) // 255
    return (a << 24) | (pre_r << 16) | (pre_g << 8) | pre_b


def _bitmap_side(config: ReticleConfig) -> int:
    outer_radius = config.radius + max(0.0, float(config.outline_width))
    diameter = max(1.0, outer_radius * 2.0)
    # 直径の端数処理時のクリッピングを防ぐため、1pxの透明枠を追加します。
    return max(1, int(math.ceil(diameter)) + 2)


def create_dot_bitmap(
    width: int,
    height: int,
    radius: float,
    dot_rgba: tuple[int, int, int, int],
    outline_width: int,
    outline_rgba: tuple[int, int, int, int] | None,
) -> wintypes.HBITMAP:
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height  # トップダウンDIB
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    bmi.bmiHeader.biSizeImage = width * height * 4

    bits = ctypes.c_void_p()
    hbitmap = gdi32.CreateDIBSection(
        None,
        ctypes.byref(bmi),
        DIB_RGB_COLORS,
        ctypes.byref(bits),
        None,
        0,
    )
    if not hbitmap:
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        buffer = (ctypes.c_uint32 * (width * height)).from_address(bits.value)
        for index in range(width * height):
            buffer[index] = 0

        dot_pixel = _premultiply_rgba(dot_rgba)
        outline_pixel = _premultiply_rgba(outline_rgba) if outline_rgba else None

        center = (width - 1) / 2.0
        outer_radius = radius + max(0.0, float(outline_width))

        for y in range(height):
            dy = y - center
            for x in range(width):
                dx = x - center
                distance = math.hypot(dx, dy)
                idx = y * width + x
                if distance <= radius:
                    buffer[idx] = dot_pixel
                elif outline_pixel is not None and distance <= outer_radius:
                    buffer[idx] = outline_pixel
    except Exception:
        gdi32.DeleteObject(hbitmap)
        raise

    return hbitmap


class ReticleOverlay:
    """レイヤード化されたレティクルウィンドウとそのホットキーをカプセル化します。"""

    def __init__(self, config: ReticleConfig) -> None:
        self.config = config
        self._width = _bitmap_side(config)
        self._height = self._width
        self._visible = True
        self._hotkeys: dict[int, Callable[[], None]] = {}

        self._hinstance = kernel32.GetModuleHandleW(None)
        self._class_name = "ReticleOverlayWindow"
        self._wnd_proc = WNDPROC(self._handle_message)
        self._register_class()

        self.hwnd: wintypes.HWND | None = self._create_window()
        self._position = self._calculate_center_position()
        self._apply_bitmap()
        self._ensure_topmost()
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)

    # ---- ウィンドウ生成 --------------------------------------------------

    def _register_class(self) -> None:
        wndclass = WNDCLASS()
        wndclass.style = 0
        wndclass.lpfnWndProc = self._wnd_proc
        wndclass.cbClsExtra = 0
        wndclass.cbWndExtra = 0
        wndclass.hInstance = self._hinstance
        wndclass.hIcon = None
        wndclass.hCursor = None
        wndclass.hbrBackground = None
        wndclass.lpszMenuName = None
        wndclass.lpszClassName = self._class_name

        atom = user32.RegisterClassW(ctypes.byref(wndclass))
        if not atom:
            error = ctypes.get_last_error()
            if error != 1410:  # クラス登録済みエラー
                raise ctypes.WinError(error)

    def _create_window(self) -> wintypes.HWND:
        ex_style = (
            WS_EX_LAYERED
            | WS_EX_TRANSPARENT
            | WS_EX_TOPMOST
            | WS_EX_NOACTIVATE
            | WS_EX_TOOLWINDOW
        )
        hwnd = user32.CreateWindowExW(
            ex_style,
            self._class_name,
            "Reticle_FPS",
            WS_POPUP,
            0,
            0,
            self._width,
            self._height,
            None,
            None,
            self._hinstance,
            None,
        )
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        return wintypes.HWND(hwnd)

    # ---- レイアウトと描画 ------------------------------------------------

    def _calculate_center_position(self) -> tuple[int, int]:
        screen_w = user32.GetSystemMetrics(SM_CXSCREEN)
        screen_h = user32.GetSystemMetrics(SM_CYSCREEN)
        x = (screen_w - self._width) // 2
        y = (screen_h - self._height) // 2
        return x, y

    def _apply_bitmap(self) -> None:
        hwnd = self.hwnd
        if not hwnd:
            return

        outline_rgba = (
            self.config.outline_rgba
            if self.config.outline_width > 0 and self.config.outline_rgba is not None
            else None
        )

        hbitmap = create_dot_bitmap(
            self._width,
            self._height,
            self.config.radius,
            self.config.dot_rgba,
            self.config.outline_width,
            outline_rgba,
        )

        mem_dc = gdi32.CreateCompatibleDC(None)
        if not mem_dc:
            gdi32.DeleteObject(hbitmap)
            raise ctypes.WinError(ctypes.get_last_error())

        old_bitmap = gdi32.SelectObject(mem_dc, hbitmap)
        if not old_bitmap:
            error = ctypes.get_last_error()
            gdi32.DeleteDC(mem_dc)
            gdi32.DeleteObject(hbitmap)
            raise ctypes.WinError(error)

        blend = BLENDFUNCTION(AC_SRC_OVER, 0, self.config.window_alpha, AC_SRC_ALPHA)
        size = SIZE(self._width, self._height)
        dest = POINT(self._position[0], self._position[1])
        src = POINT(0, 0)

        success = user32.UpdateLayeredWindow(
            hwnd,
            None,
            ctypes.byref(dest),
            ctypes.byref(size),
            mem_dc,
            ctypes.byref(src),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )

        gdi32.SelectObject(mem_dc, old_bitmap)
        gdi32.DeleteDC(mem_dc)
        gdi32.DeleteObject(hbitmap)

        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

    def _ensure_topmost(self) -> None:
        hwnd = self.hwnd
        if not hwnd:
            return
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        if self._visible:
            flags |= SWP_SHOWWINDOW
        user32.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0, flags)

    def _center_on_screen(self) -> None:
        if not self.hwnd:
            return
        self._position = self._calculate_center_position()
        self._apply_bitmap()
        self._ensure_topmost()

    # ---- ホットキーと制御 ------------------------------------------------

    def toggle_visibility(self) -> None:
        hwnd = self.hwnd
        if not hwnd:
            return
        if self._visible:
            user32.ShowWindow(hwnd, SW_HIDE)
            self._visible = False
        else:
            self._visible = True
            self._center_on_screen()
            user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
            self._ensure_topmost()

    def register_hotkey(self, hotkey_id: int, binding: str, callback: Callable[[], None]) -> None:
        modifiers, virtual_key = _parse_hotkey(binding)
        if not user32.RegisterHotKey(self.hwnd, hotkey_id, modifiers | MOD_NOREPEAT, virtual_key):
            raise HotkeyRegistrationError(
                f"RegisterHotKey failed for binding '{binding}'. Try a different combination."
            )
        self._hotkeys[hotkey_id] = callback

    def close(self) -> None:
        hwnd = self.hwnd
        if hwnd is not None:
            for hotkey_id in list(self._hotkeys):
                user32.UnregisterHotKey(hwnd, hotkey_id)
        self._hotkeys.clear()

    def destroy(self) -> None:
        if self.hwnd is not None:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None

    def run(self) -> None:
        msg = wintypes.MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0:
                break
            if result == -1:
                raise ctypes.WinError(ctypes.get_last_error())
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    # ---- ウィンドウプロシージャ ------------------------------------------

    def _handle_message(
        self,
        hwnd: wintypes.HWND,
        msg: int,
        w_param: wintypes.WPARAM,
        l_param: wintypes.LPARAM,
    ) -> int:
        if msg == WM_DESTROY:
            self.close()
            user32.PostQuitMessage(0)
            return 0
        if msg == WM_SETCURSOR and self._visible:
            user32.SetCursor(HCURSOR())
            return 1
        if msg == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        if msg == WM_NCHITTEST:
            return HTTRANSPARENT
        if msg in (WM_DISPLAYCHANGE, WM_DPICHANGED):
            self._center_on_screen()
            return 0
        if msg == WM_HOTKEY:
            callback = self._hotkeys.get(int(w_param))
            if callback is not None:
                callback()
            return 0
        if msg == WM_ERASEBKGND:
            return 1
        return user32.DefWindowProcW(hwnd, msg, w_param, l_param)


def main(argv: list[str] | None = None) -> None:
    config = parse_args(argv or sys.argv[1:])
    _configure_dpi()

    overlay: ReticleOverlay | None = None
    try:
        overlay = ReticleOverlay(config)

        def quit_app() -> None:
            overlay.close()
            overlay.destroy()

        try:
            overlay.register_hotkey(1, config.hotkey_toggle, overlay.toggle_visibility)
            overlay.register_hotkey(2, config.hotkey_quit, quit_app)
        except HotkeyRegistrationError as exc:
            overlay.close()
            overlay.destroy()
            print(
                f"Error: {exc}\nChoose different hotkeys and relaunch.",
                file=sys.stderr,
            )
            return

        overlay.run()
    finally:
        if overlay is not None:
            overlay.close()
            overlay.destroy()


if __name__ == "__main__":
    main()