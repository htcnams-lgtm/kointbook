# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""마스터관리 > 점포마스터 화면: 점포코드/점포명 등록·수정·삭제 + PDA 전송."""

import tkinter as tk
from tkinter import messagebox
from . import db as dbmod
from . import pda_transfer
from .ui_common import center_on_app, COLOR_HEADER_BG, setup_treeview, CL_BG, win_button


class StoreMasterScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self.selected_code = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = tk.Frame(self, bg=COLOR_HEADER_BG, highlightbackground="#C4C8D0", highlightthickness=1)
        top.pack(fill=tk.X)
        tk.Label(top, text="조회조건: 전체", bg=COLOR_HEADER_BG).pack(side=tk.LEFT, padx=8, pady=8)
        win_button(top, text="조회", command=self.refresh, kind="normal").pack(side=tk.LEFT, padx=8)
        # [2026-10-15] 등록/수정/삭제를 아래쪽에서 위쪽 [조회] 옆으로 옮겼다(작업자마스터와 같은 위치).
        win_button(top, text="등록", width=10, command=self.open_register_dialog, kind="normal").pack(side=tk.LEFT, padx=(36, 0))
        win_button(top, text="수정", width=10, command=self.open_edit_dialog, kind="normal").pack(side=tk.LEFT, padx=(6, 0))
        win_button(top, text="삭제", width=10, command=self.delete_selected, kind="normal").pack(side=tk.LEFT, padx=(6, 0))
        win_button(top, text="⬆ PDA 전송", command=self.send_to_pda, kind="normal").pack(side=tk.RIGHT, padx=8, pady=6)

        container, self.tree = setup_treeview(
            self, columns=("code", "name"), headings=("점포코드", "점포명"),
            widths=(90, 220), height=16
        )
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        self.selected_code = self.tree.item(sel[0], "values")[0] if sel else None

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = dbmod.get_conn()
        for i, row in enumerate(conn.execute("SELECT store_code, store_name FROM stores ORDER BY store_code")):
            self.tree.insert("", tk.END, values=(row["store_code"], row["store_name"]),
                              tags=("odd",) if i % 2 == 1 else ())
        conn.close()

    def open_register_dialog(self):
        self._open_form_dialog(mode="new")

    def open_edit_dialog(self):
        if not self.selected_code:
            messagebox.showinfo("알림", "수정할 점포를 목록에서 선택하세요.")
            return
        conn = dbmod.get_conn()
        row = conn.execute("SELECT * FROM stores WHERE store_code=?", (self.selected_code,)).fetchone()
        conn.close()
        self._open_form_dialog(mode="edit", code=row["store_code"], name=row["store_name"])

    def _open_form_dialog(self, mode, code="", name=""):
        win = tk.Toplevel(self)
        center_on_app(win)
        win.title("점포마스터 등록")
        win.geometry("360x180")
        win.bind("<Escape>", lambda e: win.destroy())

        tk.Label(win, text="점포코드").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        e_code = tk.Entry(win, width=24)
        e_code.grid(row=0, column=1, padx=10, pady=10)
        e_code.insert(0, code)
        if mode == "edit":
            e_code.configure(state="readonly")

        tk.Label(win, text="점포명").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        e_name = tk.Entry(win, width=24)
        e_name.grid(row=1, column=1, padx=10, pady=10)
        e_name.insert(0, name)

        keep_open = tk.BooleanVar(value=False)
        tk.Checkbutton(win, text="연속 추가", variable=keep_open).grid(row=2, column=0, columnspan=2, sticky="w", padx=10)

        def save():
            c = e_code.get().strip()
            n = e_name.get().strip()
            if not c or not n:
                messagebox.showwarning("알림", "점포코드와 점포명을 입력하세요.")
                return
            conn = dbmod.get_conn()
            conn.execute(
                "INSERT INTO stores(store_code, store_name) VALUES (?,?) "
                "ON CONFLICT(store_code) DO UPDATE SET store_name=excluded.store_name",
                (c, n)
            )
            conn.commit()
            conn.close()
            self.refresh()
            if keep_open.get() and mode == "new":
                e_code.delete(0, tk.END)
                e_name.delete(0, tk.END)
            else:
                win.destroy()

        btns = tk.Frame(win)
        btns.grid(row=3, column=0, columnspan=2, pady=14)
        win_button(btns, text="등록", width=10, command=save, kind="normal").pack(side=tk.LEFT, padx=6)
        win_button(btns, text="취소", width=10, command=win.destroy, kind="normal").pack(side=tk.LEFT)

    def delete_selected(self):
        if not self.selected_code:
            messagebox.showinfo("알림", "삭제할 점포를 선택하세요.")
            return
        if not messagebox.askyesno("확인", f"점포 [{self.selected_code}]를 삭제할까요?"):
            return
        conn = dbmod.get_conn()
        conn.execute("DELETE FROM stores WHERE store_code=?", (self.selected_code,))
        conn.commit()
        conn.close()
        self.refresh()

    def send_to_pda(self):
        ok, msg, count = pda_transfer.push_stores()
        if ok:
            messagebox.showinfo("완료", f"점포마스터 {count:,}건을 PDA로 전송했습니다.")
        else:
            messagebox.showerror("오류", f"전송 실패: {msg}")
