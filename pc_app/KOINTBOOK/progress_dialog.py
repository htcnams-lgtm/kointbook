# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
진행률 팝업 + 백그라운드 작업 실행기.

오래 걸리는 작업을 화면(메인 스레드)에서 그대로 돌리면 프로그램이 멈춘
것처럼 보이고("응답 없음"), 윈도우가 창을 하얗게 만들어버린다. 그래서
작업은 별도 스레드에서 돌리고, 메인 화면에서는 이 팝업으로 진행률을
0.1초마다 갱신해서 보여준다.

사용 예
-------
    def work(progress):                 # 백그라운드 스레드에서 실행됨
        progress(message="파일 읽는 중...", done=0, total=1000)
        ...
        return 결과값

    def done(result, error):            # 작업이 끝나면 메인 스레드에서 호출됨
        if error is not None:
            messagebox.showerror("오류", str(error))
            return
        ...

    run_with_progress(self, "제목", work, done, cancelable=True)

주의: work() 안에서는 tkinter 위젯을 절대 건드리지 말 것 (messagebox 포함).
결과는 return으로 돌려주고 done()에서 화면을 갱신한다.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk

from .progress_core import Progress, format_detail
from .ui_common import CL_BG, CL_NAVY, CL_TEXT_DIM, ensure_classic_treeview_style, win_button

_bar_style_ready = False


def _ensure_bar_style():
    global _bar_style_ready
    if _bar_style_ready:
        return
    ensure_classic_treeview_style()  # 여기서 clam 테마를 켠다 (색이 그대로 반영되는 테마)
    try:
        style = ttk.Style()
        style.configure(
            "Zz.Horizontal.TProgressbar",
            troughcolor="#E3E6EE", background=CL_NAVY,
            bordercolor="#C4C8D0", lightcolor=CL_NAVY, darkcolor=CL_NAVY,
        )
    except Exception:
        pass
    _bar_style_ready = True


def run_with_progress(parent, title, work, on_done, cancelable=False,
                      initial_message="준비 중..."):
    """work(progress)를 백그라운드에서 실행하면서 진행률 팝업을 보여준다.
    끝나면 on_done(result, error)를 메인 스레드에서 호출한다.
    - work가 정상 종료: on_done(반환값, None)
    - work에서 예외 발생: on_done(None, 예외)
    - 사용자가 [취소]: work가 progress.check_cancel()로 Cancelled 예외를 던지면 on_done(None, Cancelled)
    """
    _ensure_bar_style()
    progress = Progress()
    progress.message = initial_message
    box = {}

    def runner():
        try:
            box["result"] = work(progress)
        except Exception as e:  # noqa: BLE001 - 어떤 오류든 화면에 알려주려고 전부 잡는다
            box["error"] = e

    top = tk.Toplevel(parent)
    top.title(title)
    top.configure(bg=CL_BG)
    top.resizable(False, False)
    try:
        top.transient(parent.winfo_toplevel())
    except Exception:
        pass
    # 진행 중에는 X 버튼으로 닫을 수 없게 한다 (작업이 중간에 끊기는 것 방지).
    top.protocol("WM_DELETE_WINDOW", lambda: None)

    tk.Label(top, text=title, bg=CL_BG, fg=CL_NAVY,
             font=("", 12, "bold")).pack(anchor="w", padx=22, pady=(18, 6))
    lbl_msg = tk.Label(top, text=initial_message, bg=CL_BG, fg="#191C23",
                       font=("", 10), justify="left", anchor="w", wraplength=440)
    lbl_msg.pack(fill=tk.X, padx=22)

    bar = ttk.Progressbar(top, style="Zz.Horizontal.TProgressbar", orient="horizontal",
                          length=440, mode="indeterminate", maximum=1000)
    bar.pack(padx=22, pady=(10, 6))
    lbl_line1 = tk.Label(top, text="", bg=CL_BG, fg=CL_NAVY, font=("", 10, "bold"))
    lbl_line1.pack(anchor="w", padx=22)
    lbl_line2 = tk.Label(top, text="", bg=CL_BG, fg=CL_TEXT_DIM, font=("", 9))
    lbl_line2.pack(anchor="w", padx=22, pady=(0, 6))

    if cancelable:
        def on_cancel():
            progress.cancel()
            btn_cancel.config(state="disabled", text="취소하는 중...")
        btn_cancel = win_button(top, text="취소", command=on_cancel, kind="normal")
        btn_cancel.pack(pady=(2, 14))
        # [2026-09-28] "모든 새로운 팝업창은 ESC로 닫을수 있게" - 이 창은
        # 작업 도중 X 버튼으로 못 닫게 일부러 막아뒀지만(위 WM_DELETE_WINDOW
        # 참고), 취소 가능한 작업이면 ESC를 [취소] 버튼과 같은 동작으로
        # 연결해서 "닫는 방법이 아예 없는" 상태는 피한다.
        top.bind("<Escape>", lambda e: on_cancel())
    else:
        tk.Frame(top, bg=CL_BG, height=12).pack()

    # 부모 창 가운데에 띄운다.
    top.update_idletasks()
    try:
        root = parent.winfo_toplevel()
        x = root.winfo_rootx() + (root.winfo_width() - top.winfo_reqwidth()) // 2
        y = root.winfo_rooty() + (root.winfo_height() - top.winfo_reqheight()) // 2
        top.geometry(f"+{max(0, x)}+{max(0, y)}")
    except Exception:
        pass
    try:
        top.grab_set()  # 진행 중에는 뒤 화면을 눌러도 반응하지 않게 (중복 실행 방지)
    except Exception:
        pass

    state = {"mode": "indeterminate"}
    started = time.time()
    bar.start(12)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()

    def tick():
        message, done, total, unit, phase_elapsed = progress.snapshot()
        try:
            if message and lbl_msg.cget("text") != message:
                lbl_msg.config(text=message)
            if total and total > 0:
                if state["mode"] != "determinate":
                    bar.stop()
                    bar.config(mode="determinate")
                    state["mode"] = "determinate"
                bar["value"] = min(1000, int(done * 1000 / total))
            else:
                if state["mode"] != "indeterminate":
                    bar.config(mode="indeterminate")
                    bar.start(12)
                    state["mode"] = "indeterminate"
            line1, line2 = format_detail(done, total, unit, phase_elapsed, time.time() - started)
            lbl_line1.config(text=line1)
            lbl_line2.config(text=line2)
        except tk.TclError:
            return  # 창이 이미 닫힌 경우

        if thread.is_alive():
            top.after(100, tick)
            return

        try:
            bar.stop()
        except Exception:
            pass
        try:
            top.grab_release()
        except Exception:
            pass
        top.destroy()
        on_done(box.get("result"), box.get("error"))

    top.after(100, tick)
    return progress
