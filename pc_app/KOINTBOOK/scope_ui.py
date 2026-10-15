# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""자료생성 그룹 화면 공용: [구분: 전체/서적/문구] + [범위설정] 막대 (scope.py 참고)."""

import tkinter as tk
from tkinter import ttk, messagebox
from . import scope
from .ui_common import CL_BG, CL_TEXT_DIM, CL_NAVY, win_button, center_on_app


class ScopeBar(tk.Frame):
    def __init__(self, parent, on_change=None, bg=CL_BG):
        super().__init__(parent, bg=bg)
        self._on_change = on_change
        tk.Label(self, text="구분", bg=bg, fg=CL_TEXT_DIM).pack(side=tk.LEFT, padx=(0, 4))
        self.cb = ttk.Combobox(self, values=("전체", "서적", "문구"), state="readonly", width=6)
        self.cb.set("전체")
        self.cb.pack(side=tk.LEFT)
        self.cb.bind("<<ComboboxSelected>>", lambda e: self._changed())
        win_button(self, text="범위설정", command=self.open_dialog, kind="normal").pack(side=tk.LEFT, padx=6)
        self.lbl = tk.Label(self, text="", bg=bg, fg=CL_NAVY)
        self.lbl.pack(side=tk.LEFT, padx=4)
        self._update_label()

    # ---- 값 ----
    def kind(self):
        return self.cb.get()

    def tag(self):
        return scope.tag(self.kind())

    def sql(self):
        return scope.sql_cond(self.kind())

    def ready(self):
        """구분을 골랐는데 범위가 하나도 없으면 안내하고 범위설정 창을 연다. 진행 가능하면 True."""
        if self.kind() in scope.KINDS and not any(scope.is_defined(k) for k in scope.KINDS):
            messagebox.showinfo("범위 설정 필요", "서적/문구를 구분할 AREA 또는 SECTION 범위를 먼저 설정하세요.")
            self.open_dialog()
            return any(scope.is_defined(k) for k in scope.KINDS)
        return True

    def _update_label(self):
        k = self.kind()
        if k in scope.KINDS:
            self.lbl.config(text=f"{k}: {scope.describe(k)}")
        else:
            self.lbl.config(text="")

    def _changed(self):
        self._update_label()
        if self._on_change:
            self._on_change()  # 범위가 없으면 화면의 refresh()가 ready()로 안내한다

    # ---- 범위 설정 창 ----
    def open_dialog(self):
        win = tk.Toplevel(self)
        win.title("서적 / 문구 범위 설정")
        win.transient(self.winfo_toplevel())
        win.configure(bg=CL_BG)
        tk.Label(win, text="서적과 문구를 나누는 AREA / SECTION 범위입니다. 비운 칸은 제한 없음.\n"
                           "AREA와 SECTION을 둘 다 적으면 둘 다 맞는 자료만, 한 구분만 적으면 나머지는 그 밖 전부입니다.",
                 bg=CL_BG, fg=CL_TEXT_DIM, justify="left").pack(anchor="w", padx=14, pady=(12, 6))
        ents = {}
        for kind in scope.KINDS:
            box = tk.LabelFrame(win, text=f" {kind} ", bg=CL_BG, font=("", 10, "bold"))
            box.pack(fill=tk.X, padx=12, pady=6)
            r = scope.get_range(kind)
            row1 = tk.Frame(box, bg=CL_BG); row1.pack(fill=tk.X, padx=8, pady=(6, 2))
            row2 = tk.Frame(box, bg=CL_BG); row2.pack(fill=tk.X, padx=8, pady=(2, 8))
            for row, label, kf, kt in ((row1, "AREA", "af", "at"), (row2, "SECTION", "sf", "st")):
                tk.Label(row, text=label, width=8, anchor="w", bg=CL_BG).pack(side=tk.LEFT)
                e1 = tk.Entry(row, width=6); e1.insert(0, r[kf]); e1.pack(side=tk.LEFT)
                tk.Label(row, text=" ~ ", bg=CL_BG).pack(side=tk.LEFT)
                e2 = tk.Entry(row, width=6); e2.insert(0, r[kt]); e2.pack(side=tk.LEFT)
                ents[(kind, kf)] = e1
                ents[(kind, kt)] = e2
        btns = tk.Frame(win, bg=CL_BG)
        btns.pack(fill=tk.X, padx=12, pady=(4, 12))

        def save():
            for kind in scope.KINDS:
                scope.set_range(kind, **{f: ents[(kind, f)].get() for f in scope.FIELDS})
            win.destroy()
            self._update_label()
            if self._on_change:
                self._on_change()

        def clear():
            for e in ents.values():
                e.delete(0, tk.END)

        win_button(btns, text="저장", command=save, kind="accent").pack(side=tk.RIGHT)
        win_button(btns, text="취소", command=win.destroy, kind="normal").pack(side=tk.RIGHT, padx=6)
        win_button(btns, text="모두 비우기", command=clear, kind="normal").pack(side=tk.LEFT)
        try:
            center_on_app(win)
            win.grab_set()
        except Exception:
            pass
