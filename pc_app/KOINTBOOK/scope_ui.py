# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""자료생성 그룹 화면 공용: [구분: 전체/서적/문구] 막대 (구분 기준은 AREA 번호 고정) (scope.py 참고)."""

import tkinter as tk
from tkinter import ttk
from . import scope
from .ui_common import CL_BG, CL_TEXT_DIM, CL_NAVY


class ScopeBar(tk.Frame):
    def __init__(self, parent, on_change=None, bg=CL_BG):
        super().__init__(parent, bg=bg)
        self._on_change = on_change
        tk.Label(self, text="구분", bg=bg, fg=CL_TEXT_DIM).pack(side=tk.LEFT, padx=(0, 4))
        self.cb = ttk.Combobox(self, values=("전체", "서적", "문구"), state="readonly", width=6)
        self.cb.set("전체")
        self.cb.pack(side=tk.LEFT)
        self.cb.bind("<<ComboboxSelected>>", lambda e: self._changed())
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
        """구분은 AREA 번호로 고정이라(scope.py) 따로 설정할 것이 없다. 항상 진행 가능."""
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
            self._on_change()
