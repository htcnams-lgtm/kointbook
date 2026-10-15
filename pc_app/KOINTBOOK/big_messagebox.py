# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
"""알림창(messagebox) 글씨를 크게 보이게 하는 대체 구현.

윈도우 기본 알림창은 글씨 크기를 바꿀 수 없어서, tkinter.messagebox의
showinfo/showwarning/showerror/askyesno/askokcancel/askyesnocancel/askretrycancel을
같은 이름·같은 반환값의 직접 만든 창으로 바꿔 끼운다(install() 한 번 호출).
각 화면은 기존처럼 messagebox.showinfo(...)를 그대로 쓰면 된다.
글씨 크기를 더 키우려면 FONT_SIZE만 고친다.
"""
import tkinter as tk
from tkinter import messagebox as _mb

FONT_SIZE = 12     # 기본 알림창(약 9pt)보다 2~3 크게
BUTTON_SIZE = 11

_ICONS = {
    "info": ("i", "#1f6fd1"),
    "warning": ("!", "#d98a00"),
    "error": ("X", "#cc2b2b"),
    "question": ("?", "#1f6fd1"),
}


def _owner(parent):
    if parent is not None:
        try:
            return parent.winfo_toplevel()
        except Exception:
            pass
    root = tk._default_root
    return root


def _show(title, message, icon, buttons, default, cancel, parent=None, **_):
    """buttons: [(표시글자, 반환값)]. default/cancel: 반환값."""
    owner = _owner(parent)
    if owner is None:
        return cancel
    win = tk.Toplevel(owner)
    win.withdraw()
    win.title(title or "")
    win.resizable(False, False)
    try:
        win.transient(owner)
    except Exception:
        pass
    result = {"v": cancel}

    def done(v):
        result["v"] = v
        win.destroy()

    body = tk.Frame(win, padx=22, pady=18)
    body.pack(fill="both", expand=True)
    glyph, color = _ICONS.get(icon, _ICONS["info"])
    tk.Label(body, text=glyph, fg="white", bg=color, width=2,
             font=("", FONT_SIZE + 6, "bold")).pack(side="left", anchor="n", padx=(0, 16))
    tk.Label(body, text=str(message), justify="left", anchor="w",
             font=("", FONT_SIZE), wraplength=560).pack(side="left", fill="both", expand=True)

    bar = tk.Frame(win, pady=12)
    bar.pack(fill="x")
    inner = tk.Frame(bar)
    inner.pack()
    default_btn = None
    for text, val in buttons:
        b = tk.Button(inner, text=text, width=9, font=("", BUTTON_SIZE),
                      command=lambda v=val: done(v))
        b.pack(side="left", padx=6)
        if val == default:
            default_btn = b
    if default_btn is None:
        default_btn = inner.winfo_children()[0]

    win.bind("<Return>", lambda e: done(default))
    win.bind("<KP_Enter>", lambda e: done(default))
    win.bind("<Escape>", lambda e: done(cancel))
    win.protocol("WM_DELETE_WINDOW", lambda: done(cancel))

    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    try:
        ox, oy = owner.winfo_rootx(), owner.winfo_rooty()
        ow, oh = owner.winfo_width(), owner.winfo_height()
        x, y = ox + (ow - w) // 2, oy + (oh - h) // 2
    except Exception:
        x, y = 200, 200
    x = max(0, min(x, win.winfo_screenwidth() - w))
    y = max(0, min(y, win.winfo_screenheight() - h))
    win.geometry(f"+{x}+{y}")
    win.deiconify()
    try:
        win.bell()
    except Exception:
        pass
    win.lift()
    default_btn.focus_set()
    prev_grab = None
    try:
        prev_grab = win.grab_current()   # 이 알림창을 띄운 팝업이 잡고 있던 입력 잠금
    except Exception:
        pass
    try:
        win.grab_set()
    except Exception:
        pass
    win.wait_window()
    try:
        if prev_grab is not None and prev_grab.winfo_exists():
            prev_grab.grab_set()
    except Exception:
        pass
    return result["v"]


def showinfo(title=None, message=None, **kw):
    _show(title, message, "info", [("확인", "ok")], "ok", "ok", **kw)
    return "ok"


def showwarning(title=None, message=None, **kw):
    kw.pop("icon", None)
    _show(title, message, "warning", [("확인", "ok")], "ok", "ok", **kw)
    return "ok"


def showerror(title=None, message=None, **kw):
    _show(title, message, "error", [("확인", "ok")], "ok", "ok", **kw)
    return "ok"


def askyesno(title=None, message=None, **kw):
    d = kw.pop("default", "yes")
    kw.pop("icon", None)
    return _show(title, message, "question", [("예", True), ("아니오", False)],
                 d == "yes", False, **kw) is True


def askokcancel(title=None, message=None, **kw):
    d = kw.pop("default", "ok")
    kw.pop("icon", None)
    return _show(title, message, "question", [("확인", True), ("취소", False)],
                 d == "ok", False, **kw) is True


def askretrycancel(title=None, message=None, **kw):
    kw.pop("default", None)
    kw.pop("icon", None)
    return _show(title, message, "warning", [("다시 시도", True), ("취소", False)],
                 True, False, **kw) is True


def askyesnocancel(title=None, message=None, **kw):
    d = kw.pop("default", "yes")
    kw.pop("icon", None)
    return _show(title, message, "question",
                 [("예", True), ("아니오", False), ("취소", None)],
                 {"yes": True, "no": False, "cancel": None}.get(d, True), None, **kw)


def install():
    """tkinter.messagebox의 알림창 함수를 큰 글씨 버전으로 바꾼다."""
    for name in ("showinfo", "showwarning", "showerror", "askyesno",
                 "askokcancel", "askretrycancel", "askyesnocancel"):
        setattr(_mb, name, globals()[name])
