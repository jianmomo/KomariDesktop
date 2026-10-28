"""Windows 桌面子窗口：显示 Qt 面板的内存图像，不改变系统壁纸。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import hashlib
import logging

from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QPainter


_LOGGER = logging.getLogger("komaridesktop")


def capture_widget_image(widget):
    """用独立 QImage 绘制控件，避免隐藏 Win32 窗口的 backing store 过期。"""
    if widget is None:
        raise ValueError("桌面面板控件不可用")
    size = widget.size()
    if size.width() <= 0 or size.height() <= 0:
        raise RuntimeError("桌面面板控件尺寸无效")
    try:
        dpr = max(1.0, float(widget.devicePixelRatioF()))
    except (AttributeError, TypeError, ValueError):
        dpr = 1.0
    width = max(1, int(round(size.width() * dpr)))
    height = max(1, int(round(size.height() * dpr)))
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(0)
    painter = QPainter(image)
    if not painter.isActive():
        raise RuntimeError("无法创建桌面面板绘制器")
    try:
        widget.render(painter, QPoint(0, 0))
    finally:
        painter.end()
    return image


class _BitmapHeader(ctypes.Structure):
    _fields_ = [("size", w.DWORD), ("width", w.LONG), ("height", w.LONG),
                ("planes", w.WORD), ("bit_count", w.WORD), ("compression", w.DWORD),
                ("size_image", w.DWORD), ("xppm", w.LONG), ("yppm", w.LONG),
                ("colors_used", w.DWORD), ("colors_important", w.DWORD)]


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("header", _BitmapHeader), ("colors", w.DWORD * 3)]


class _Blend(ctypes.Structure):
    _fields_ = [("operation", ctypes.c_ubyte), ("flags", ctypes.c_ubyte),
                ("alpha", ctypes.c_ubyte), ("format", ctypes.c_ubyte)]


def _declare(lib, name, args, result):
    function = getattr(lib, name)
    function.argtypes, function.restype = args, result
    return function


class DesktopSurface:
    """保留 Qt 顶级窗口的多屏缩放，桌面仅持有透明子窗口。"""

    def __init__(self):
        self.u = ctypes.WinDLL("user32", use_last_error=True)
        self.g = ctypes.WinDLL("gdi32", use_last_error=True)
        self.hwnd = 0
        self.host = 0
        _declare(self.u, "CreateWindowExW", [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                 ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                 w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID], w.HWND)
        _declare(self.u, "DestroyWindow", [w.HWND], w.BOOL)
        _declare(self.u, "IsWindow", [w.HWND], w.BOOL)
        _declare(self.u, "GetParent", [w.HWND], w.HWND)
        _declare(self.u, "GetWindowRect", [w.HWND, ctypes.POINTER(w.RECT)], w.BOOL)
        _declare(self.u, "ScreenToClient", [w.HWND, ctypes.POINTER(w.POINT)], w.BOOL)
        _declare(self.u, "GetDC", [w.HWND], w.HDC)
        _declare(self.u, "ReleaseDC", [w.HWND, w.HDC], ctypes.c_int)
        _declare(self.u, "SetWindowPos", [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int,
                 ctypes.c_int, ctypes.c_int, w.UINT], w.BOOL)
        _declare(self.u, "SetWindowLongPtrW", [w.HWND, ctypes.c_int, ctypes.c_ssize_t], ctypes.c_ssize_t)
        _declare(self.u, "GetWindowLongPtrW", [w.HWND, ctypes.c_int], ctypes.c_ssize_t)
        _declare(self.u, "UpdateLayeredWindow", [w.HWND, w.HDC, ctypes.POINTER(w.POINT),
                 ctypes.POINTER(w.SIZE), w.HDC, ctypes.POINTER(w.POINT), w.DWORD,
                 ctypes.POINTER(_Blend), w.DWORD], w.BOOL)
        _declare(self.g, "CreateCompatibleDC", [w.HDC], w.HDC)
        _declare(self.g, "DeleteDC", [w.HDC], w.BOOL)
        _declare(self.g, "CreateDIBSection", [w.HDC, ctypes.POINTER(_BitmapInfo), w.UINT,
                 ctypes.POINTER(ctypes.c_void_p), w.HANDLE, w.DWORD], w.HBITMAP)
        _declare(self.g, "SelectObject", [w.HDC, w.HGDIOBJ], w.HGDIOBJ)
        _declare(self.g, "DeleteObject", [w.HGDIOBJ], w.BOOL)

    def alive(self):
        return bool(self.hwnd and self.u.IsWindow(self.hwnd)
                    and self.u.GetParent(self.hwnd) == self.host)

    def destroy(self):
        if self.hwnd and self.u.IsWindow(self.hwnd):
            if not self.u.DestroyWindow(self.hwnd):
                raise ctypes.WinError(ctypes.get_last_error())
        self.hwnd = self.host = 0

    def update(self, widget, host, icons, click_through, opacity):
        """仅在内容变化时调用；DIB 与 DC 每次均在 finally 中释放。"""
        host, icons = int(host or 0), int(icons or 0)
        if not host or not icons or not self.u.IsWindow(host) or not self.u.IsWindow(icons):
            raise RuntimeError("Windows 桌面宿主或图标窗口不可用")
        if int(self.u.GetParent(icons) or 0) != host:
            raise RuntimeError("桌面图标窗口不属于选定宿主")
        rect = w.RECT()
        if not self.u.GetWindowRect(int(widget.winId()), ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        point = w.POINT(rect.left, rect.top)
        if not self.u.ScreenToClient(host, ctypes.byref(point)):
            raise ctypes.WinError(ctypes.get_last_error())
        image = capture_widget_image(widget)
        width, height = image.width(), image.height()
        if image.isNull() or not width or not height or width * height > 64_000_000:
            raise RuntimeError("桌面面板图像尺寸无效")
        if self.host != host or not self.alive():
            self.destroy()
            exstyle = 0x08080000 | (0x20 if click_through else 0)
            self.hwnd = int(self.u.CreateWindowExW(exstyle, "STATIC", "KomariDesktop Qt Probe",
                0x50000000, point.x, point.y, width, height, host, None, None, None) or 0)
            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self.host = host
        else:
            style = int(self.u.GetWindowLongPtrW(self.hwnd, -20))
            desired = (style | 0x20) if click_through else (style & ~0x20)
            if desired != style:
                ctypes.set_last_error(0)
                self.u.SetWindowLongPtrW(self.hwnd, -20, desired)
                if ctypes.get_last_error():
                    raise ctypes.WinError(ctypes.get_last_error())
        if not self.u.SetWindowPos(self.hwnd, icons, point.x, point.y, width, height, 0x0210):
            raise ctypes.WinError(ctypes.get_last_error())
        dc = memory_dc = bitmap = old = None
        try:
            dc = self.u.GetDC(None)
            if not dc:
                raise ctypes.WinError(ctypes.get_last_error())
            memory_dc = self.g.CreateCompatibleDC(dc)
            if not memory_dc:
                raise ctypes.WinError(ctypes.get_last_error())
            info = _BitmapInfo()
            info.header.size = ctypes.sizeof(_BitmapHeader)
            info.header.width, info.header.height = width, -height
            info.header.planes, info.header.bit_count = 1, 32
            bits = ctypes.c_void_p()
            bitmap = self.g.CreateDIBSection(dc, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
            if not bitmap or not bits:
                raise ctypes.WinError(ctypes.get_last_error())
            old = self.g.SelectObject(memory_dc, bitmap)
            if not old or old == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            data = bytes(image.constBits())
            payload_size = width * height * 4
            if len(data) < payload_size:
                raise RuntimeError("桌面面板图像数据不完整")
            payload = data[:payload_size]
            digest = hashlib.blake2s(payload, digest_size=8).hexdigest()
            _LOGGER.info(
                "桌面图像提交 size=%sx%s dpr=%.2f digest=%s",
                width, height, image.devicePixelRatio(), digest,
            )
            ctypes.memmove(bits, payload, payload_size)
            size, origin = w.SIZE(width, height), w.POINT(0, 0)
            blend = _Blend(0, 0, max(0, min(255, int(opacity))), 1)
            if not self.u.UpdateLayeredWindow(self.hwnd, dc, None, ctypes.byref(size), memory_dc,
                                              ctypes.byref(origin), 0, ctypes.byref(blend), 2):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            if old:
                self.g.SelectObject(memory_dc, old)
            if bitmap:
                self.g.DeleteObject(bitmap)
            if memory_dc:
                self.g.DeleteDC(memory_dc)
            if dc:
                self.u.ReleaseDC(None, dc)
