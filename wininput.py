"""Documented Windows APIs for foreground checks, scan-code input and hotkeys."""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import threading
import time
import os

U = C.WinDLL('user32', use_last_error=True)
K = C.WinDLL('kernel32', use_last_error=True)
A = C.WinDLL('advapi32', use_last_error=True)
ULONG_PTR = C.c_size_t


class MOUSEINPUT(C.Structure):
    _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('mouseData', W.DWORD),
                ('dwFlags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ULONG_PTR)]


class KEYBDINPUT(C.Structure):
    _fields_ = [('wVk', W.WORD), ('wScan', W.WORD), ('dwFlags', W.DWORD),
                ('time', W.DWORD), ('dwExtraInfo', ULONG_PTR)]


class HARDWAREINPUT(C.Structure):
    _fields_ = [('uMsg', W.DWORD), ('wParamL', W.WORD), ('wParamH', W.WORD)]


class INPUTUNION(C.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]


class INPUT(C.Structure):
    _anonymous_ = ('value',)
    _fields_ = [('type', W.DWORD), ('value', INPUTUNION)]


U.GetForegroundWindow.argtypes = []; U.GetForegroundWindow.restype = W.HWND
U.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
U.GetWindowThreadProcessId.restype = W.DWORD
K.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]; K.OpenProcess.restype = W.HANDLE
K.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
K.QueryFullProcessImageNameW.restype = W.BOOL
K.CloseHandle.argtypes = [W.HANDLE]; K.CloseHandle.restype = W.BOOL
U.MapVirtualKeyW.argtypes = [W.UINT, W.UINT]; U.MapVirtualKeyW.restype = W.UINT
U.SendInput.argtypes = [W.UINT, C.POINTER(INPUT), C.c_int]; U.SendInput.restype = W.UINT
U.GetAsyncKeyState.argtypes = [C.c_int]; U.GetAsyncKeyState.restype = W.SHORT
U.RegisterHotKey.argtypes = [W.HWND, C.c_int, W.UINT, W.UINT]; U.RegisterHotKey.restype = W.BOOL
U.UnregisterHotKey.argtypes = [W.HWND, C.c_int]; U.UnregisterHotKey.restype = W.BOOL
U.PeekMessageW.argtypes = [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT]
U.PeekMessageW.restype = W.BOOL
ENUMPROC = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
U.EnumWindows.argtypes = [ENUMPROC, W.LPARAM]; U.EnumWindows.restype = W.BOOL
U.IsWindowVisible.argtypes = [W.HWND]; U.IsWindowVisible.restype = W.BOOL
U.IsIconic.argtypes = [W.HWND]; U.IsIconic.restype = W.BOOL
U.ShowWindow.argtypes = [W.HWND, C.c_int]; U.ShowWindow.restype = W.BOOL
U.SetForegroundWindow.argtypes = [W.HWND]; U.SetForegroundWindow.restype = W.BOOL
U.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]; U.GetWindowTextW.restype = C.c_int
A.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)]
A.OpenProcessToken.restype = W.BOOL
A.GetTokenInformation.argtypes = [W.HANDLE, C.c_int, W.LPVOID, W.DWORD, C.POINTER(W.DWORD)]
A.GetTokenInformation.restype = W.BOOL


def window_process(hwnd):
    if not hwnd: return None
    pid = W.DWORD()
    U.GetWindowThreadProcessId(hwnd, C.byref(pid))
    handle = K.OpenProcess(0x1000, False, pid.value)
    if not handle: return None
    try:
        length = W.DWORD(32768)
        name = C.create_unicode_buffer(length.value)
        if not K.QueryFullProcessImageNameW(handle, 0, name, C.byref(length)): return None
        return (int(hwnd), pid.value, name.value)
    finally:
        K.CloseHandle(handle)


def foreground_game():
    """Return (HWND, PID) only for supported Genshin processes in the foreground."""
    result = window_process(U.GetForegroundWindow())
    if result and Path(result[2]).name.lower() in ('yuanshen.exe', 'genshinimpact.exe'):
        return result[:2]
    return None


def find_games():
    games = []
    @ENUMPROC
    def callback(hwnd, extra):
        if not U.IsWindowVisible(hwnd): return True
        result = window_process(hwnd)
        if result and Path(result[2]).name.lower() in ('yuanshen.exe', 'genshinimpact.exe'):
            games.append(result[:2])
        return True
    U.EnumWindows(callback, 0)
    return games


def activate_game(target):
    """Request focus following a user click; the caller must verify actual focus."""
    if U.IsIconic(target[0]): U.ShowWindow(target[0], 9)
    return bool(U.SetForegroundWindow(target[0]))


def process_elevated(pid=None):
    process = K.OpenProcess(0x1000, False, pid or os.getpid())
    if not process: return None
    token = W.HANDLE()
    try:
        if not A.OpenProcessToken(process, 0x0008, C.byref(token)): return None
        value, needed = W.DWORD(), W.DWORD()
        if not A.GetTokenInformation(token, 20, C.byref(value), C.sizeof(value), C.byref(needed)):
            return None
        return bool(value.value)
    finally:
        if token: K.CloseHandle(token)
        K.CloseHandle(process)


def preflight(target=None):
    target = target or foreground_game()
    if not target: return '未找到原神窗口，请先启动原神。'
    if process_elevated(target[1]) is True and process_elevated() is False:
        return '检测到原神以管理员身份运行，工具箱权限不足。请点击“管理员重开”，在系统提示中自行确认后再试。'
    return None


def modifiers_held():
    return any(U.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x5B, 0x5C))


class Keyboard:
    def __init__(self):
        self.held = set()

    def send(self, keys, up=False):
        if not keys: return
        entries = (INPUT * len(keys))()
        for index, key in enumerate(keys):
            entries[index].type = 1
            entries[index].ki = KEYBDINPUT(0, U.MapVirtualKeyW(ord(key), 0),
                                          0x0008 | (0x0002 if up else 0), 0, 0)
        if not up: self.held.update(keys)
        sent = U.SendInput(len(entries), entries, C.sizeof(INPUT))
        if sent != len(entries):
            raise RuntimeError('Windows 未完整接收按键。若原神以管理员身份运行，请关闭播放器后右键“以管理员身份运行”，再试一次。')
        if up: self.held.difference_update(keys)

    def release(self):
        keys = tuple(self.held)
        if keys: self.send(keys, up=True)


HOTKEY_CHOICES = tuple(f'F{i}' for i in range(6, 12))


class Hotkeys:
    def __init__(self, emit, play='F8', stop='F9'):
        self.emit, self.play, self.stop = emit, play, stop
        self.closing = threading.Event()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def loop(self):
        registered = []
        try:
            for identity, name in ((1, self.play), (2, self.stop)):
                if name not in HOTKEY_CHOICES: raise ValueError('快捷键设置无效。')
                vk = 0x70 + int(name[1:]) - 1
                if not U.RegisterHotKey(None, identity, 0x4000, vk):
                    raise RuntimeError(f'{name} 已被其他程序占用，请在窗口中更换快捷键并点击“应用”。')
                registered.append(identity)
            self.ready.set()
            self.emit(dict(kind='hotkeys', ok=True, message=f'{self.play} 开始/暂停 · {self.stop} 停止'))
            message = W.MSG()
            while not self.closing.wait(0.01):
                while U.PeekMessageW(C.byref(message), None, 0x0312, 0x0312, 1):
                    self.emit(dict(kind='toggle' if message.wParam == 1 else 'stop'))
        except Exception as exc:
            self.emit(dict(kind='hotkeys', ok=False, message=str(exc)))
        finally:
            self.ready.clear()
            for identity in registered: U.UnregisterHotKey(None, identity)

    def close(self):
        self.closing.set()
        self.thread.join(timeout=1)
