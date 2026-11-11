"""Жесты тачпада:
  1) три пальца вниз -> сразу свернуть активное окно (даже полноэкранное);
  2) один палец вверх/вниз у правого края тачпада -> громкость.

Ручной шаг для (1): Параметры -> Bluetooth и устройства -> Сенсорная панель ->
Расширенные жесты -> «Провести тремя пальцами вниз» -> Пользовательское сочетание
клавиш -> нажать Ctrl+Alt+Shift+M.

Запуск: двойной клик (без консоли) или `py touchpad_gestures.pyw --debug` / `--selftest`.
"""
import ctypes
import struct
import sys
from ctypes import wintypes as W

EDGE_X = 0.93   # доля ширины, правее которой начинается «зона громкости»
STEP_Y = 0.05   # доля высоты на один шаг громкости (шаг Windows = 2%)
HOTKEY = (0x0001 | 0x0002 | 0x0004 | 0x4000, ord('M'))  # Alt|Ctrl|Shift|NoRepeat + M
DEBUG = '--debug' in sys.argv


class Edge:
    """Автомат края. feed(список (x, y) пальцев в долях 0..1) -> число шагов громкости (+ громче)."""

    def __init__(self):
        self.active = False
        self.idle = True
        self.anchor = 0.0

    def feed(self, pts):
        if not pts:
            self.active, self.idle = False, True
            return 0
        if self.idle:  # касание только началось
            self.idle = False
            self.active = len(pts) == 1 and pts[0][0] >= EDGE_X
            self.anchor = pts[0][1]
            return 0
        if len(pts) != 1:
            self.active = False
        if not self.active:
            return 0
        steps = int((self.anchor - pts[0][1]) / STEP_Y)  # y растёт вниз, вверх = громче
        self.anchor -= steps * STEP_Y
        return steps


def selftest():
    e = Edge()
    assert e.feed([(0.5, 0.5)]) == 0 and not e.active          # касание не у края
    assert e.feed([(0.97, 0.2)]) == 0 and not e.active         # заехал на край позже — не считается
    assert e.feed([]) == 0 and e.idle
    assert e.feed([(0.97, 0.5)]) == 0 and e.active             # начал у края
    assert e.feed([(0.97, 0.44)]) == 1                         # вверх на шаг
    assert e.feed([(0.97, 0.43)]) == 0                         # остаток копится
    assert e.feed([(0.97, 0.61)]) == -3                        # вниз
    assert e.feed([(0.97, 0.6), (0.5, 0.5)]) == 0 and not e.active  # второй палец — выход
    assert e.feed([(0.97, 0.1)]) == 0                          # и обратно не включается
    assert e.feed([]) == 0
    assert e.feed([(0.97, 0.5), (0.9, 0.5)]) == 0 and not e.active  # начал двумя пальцами
    print('selftest OK')


# ---------------- WinAPI ----------------
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32')
hid = ctypes.WinDLL('hid')
LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, W.WPARAM, W.LPARAM)

user32.CreateWindowExW.restype = W.HWND
user32.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
user32.GetRawInputData.argtypes = [W.HANDLE, W.UINT, W.LPVOID, ctypes.POINTER(W.UINT), W.UINT]
user32.GetRawInputDeviceInfoW.argtypes = [W.HANDLE, W.UINT, W.LPVOID, ctypes.POINTER(W.UINT)]
user32.SetWindowsHookExW.restype = W.HHOOK
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, W.HINSTANCE, W.DWORD]
user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = [W.HHOOK, ctypes.c_int, W.WPARAM, W.LPARAM]
user32.GetForegroundWindow.restype = W.HWND
user32.ShowWindowAsync.argtypes = [W.HWND, ctypes.c_int]
user32.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
kernel32.GetModuleHandleW.restype = W.HMODULE
for f in (hid.HidP_GetValueCaps, hid.HidP_GetUsageValue, hid.HidP_GetUsages):
    f.restype = ctypes.c_long
HIDP_OK = 0x00110000


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [('usUsagePage', W.USHORT), ('usUsage', W.USHORT), ('dwFlags', W.DWORD), ('hwndTarget', W.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [('dwType', W.DWORD), ('dwSize', W.DWORD), ('hDevice', W.HANDLE), ('wParam', W.WPARAM)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [('UsagePage', W.USHORT), ('ReportID', W.BYTE), ('IsAlias', W.BYTE), ('BitField', W.USHORT),
                ('LinkCollection', W.USHORT), ('LinkUsage', W.USHORT), ('LinkUsagePage', W.USHORT),
                ('flags', W.BYTE * 6), ('BitSize', W.USHORT), ('ReportCount', W.USHORT),
                ('Reserved2', W.USHORT * 5), ('UnitsExp', W.ULONG), ('Units', W.ULONG),
                ('LogicalMin', W.LONG), ('LogicalMax', W.LONG), ('PhysicalMin', W.LONG),
                ('PhysicalMax', W.LONG), ('Usage', W.USHORT), ('rest', W.USHORT * 7)]


assert ctypes.sizeof(HIDP_VALUE_CAPS) == 72


# ---------------- тачпад ----------------
devices = {}     # hDevice -> (preparsed, [(link, (xmin, xmax), (ymin, ymax)), ...])
contacts = {}    # contact id -> (x, y)
remaining = 0    # сколько пальцев ещё ждём в текущем кадре (для «гибридного» режима отчётов)
edge = Edge()
last_report = 0


def device(hdev):
    if hdev not in devices:
        size = W.UINT(0)
        user32.GetRawInputDeviceInfoW(hdev, 0x20000005, None, ctypes.byref(size))  # RIDI_PREPARSEDDATA
        ppd = ctypes.create_string_buffer(size.value)
        user32.GetRawInputDeviceInfoW(hdev, 0x20000005, ppd, ctypes.byref(size))
        caps, n = (HIDP_VALUE_CAPS * 256)(), W.ULONG(256)
        hid.HidP_GetValueCaps(0, caps, ctypes.byref(n), ppd)
        ranges = {}
        for c in caps[:n.value]:
            if c.UsagePage == 1 and c.Usage in (0x30, 0x31):
                ranges.setdefault(c.LinkCollection, {})[c.Usage] = (c.LogicalMin, c.LogicalMax)
        fingers = [(l, r[0x30], r[0x31]) for l, r in sorted(ranges.items()) if len(r) == 2]
        devices[hdev] = (ppd, fingers)
        if DEBUG:
            print('touchpad', hdev, fingers)
    return devices[hdev]


def on_report(hdev, report):
    global remaining
    ppd, fingers = device(hdev)
    rl, v = len(report), W.ULONG()

    def value(page, link, usage):
        return v.value if hid.HidP_GetUsageValue(0, page, link, usage, ctypes.byref(v), ppd, report, rl) == HIDP_OK else None

    count = value(0x0D, 0, 0x54)  # Contact Count: в первом отчёте кадра, в остальных 0
    if count:
        remaining = count
    for link, (x0, x1), (y0, y1) in fingers:
        if remaining <= 0:
            break
        remaining -= 1
        cid = value(0x0D, link, 0x51)
        if cid is None:
            continue
        usages, ul = (W.USHORT * 32)(), W.ULONG(32)
        ok = hid.HidP_GetUsages(0, 0x0D, link, usages, ctypes.byref(ul), ppd, report, rl) == HIDP_OK
        if not (ok and 0x42 in usages[:ul.value]):  # нет Tip Switch -> палец поднят
            contacts.pop(cid, None)
            continue
        contacts[cid] = ((value(1, link, 0x30) - x0) / max(1, x1 - x0),
                         (value(1, link, 0x31) - y0) / max(1, y1 - y0))
    if remaining <= 0:  # кадр собран
        steps = edge.feed(list(contacts.values()))
        for _ in range(abs(steps)):
            key = 0xAF if steps > 0 else 0xAE  # VK_VOLUME_UP / VK_VOLUME_DOWN
            user32.keybd_event(key, 0, 1, 0)
            user32.keybd_event(key, 0, 1 | 2, 0)
        if DEBUG:
            pts = ' '.join(f'({x:.2f},{y:.2f})' for x, y in contacts.values())
            print(f'{pts or "-":40} edge={"on" if edge.active else "off"} steps={steps:+d}')


def on_raw_input(lparam):
    global last_report
    size = W.UINT(0)
    hdr = ctypes.sizeof(RAWINPUTHEADER)
    user32.GetRawInputData(lparam, 0x10000003, None, ctypes.byref(size), hdr)  # RID_INPUT
    buf = ctypes.create_string_buffer(size.value)
    if user32.GetRawInputData(lparam, 0x10000003, buf, ctypes.byref(size), hdr) != size.value:
        return
    h = RAWINPUTHEADER.from_buffer(buf)
    one, count = struct.unpack_from('II', buf, hdr)
    for i in range(count):
        start = hdr + 8 + i * one
        on_report(h.hDevice, buf.raw[start:start + one])
    last_report = kernel32.GetTickCount()


@HOOKPROC
def mouse_hook(code, wparam, lparam):
    # пока палец ведёт громкость — курсор стоит; таймаут не даст ему «залипнуть», если отчёт потерялся
    if code == 0 and wparam == 0x0200 and edge.active and kernel32.GetTickCount() - last_report < 300:
        return 1
    return user32.CallNextHookEx(None, code, wparam, lparam)


def minimize_foreground():
    hwnd = user32.GetForegroundWindow()
    cls = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, cls, 64)
    if hwnd and cls.value not in ('Progman', 'WorkerW', 'Shell_TrayWnd'):  # рабочий стол и панель задач не трогаем
        user32.ShowWindowAsync(hwnd, 6)  # SW_MINIMIZE — сразу, без промежуточного восстановления
    if DEBUG:
        print('minimize', hwnd, cls.value)


def main():
    if not user32.RegisterHotKey(None, 1, *HOTKEY):
        user32.MessageBoxW(None, 'Сочетание Ctrl+Alt+Shift+M уже занято — возможно, программа уже запущена.',
                           'Жесты тачпада', 0x30)
        return
    hwnd = user32.CreateWindowExW(0, 'STATIC', 'touchpad_gestures', 0, 0, 0, 0, 0, W.HWND(-3), None, None, None)
    rid = RAWINPUTDEVICE(0x0D, 0x05, 0x00000100, hwnd)  # Digitizer / Touch Pad, RIDEV_INPUTSINK
    if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
        user32.MessageBoxW(None, f'Не удалось подписаться на тачпад (ошибка {ctypes.get_last_error()}).',
                           'Жесты тачпада', 0x30)
    hook = user32.SetWindowsHookExW(14, mouse_hook, kernel32.GetModuleHandleW(None), 0)  # WH_MOUSE_LL
    if DEBUG:
        print('running, hwnd', hwnd, 'hook', hook, '— закройте окно, чтобы выйти')
    msg = W.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == 0x0312:  # WM_HOTKEY
            minimize_foreground()
        elif msg.message == 0x00FF:  # WM_INPUT
            on_raw_input(msg.lParam)
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == '__main__':
    selftest() if '--selftest' in sys.argv else main()
