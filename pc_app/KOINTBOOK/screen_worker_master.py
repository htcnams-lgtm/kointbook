# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""작업자마스터 화면: 작업자코드/작업자명 등록·수정·삭제 + 엑셀 불러오기 + PDA 전송."""

import tkinter as tk
from tkinter import filedialog, messagebox
from . import db as dbmod
from . import pda_transfer
from .ui_common import center_on_app, COLOR_HEADER_BG, setup_treeview, read_excel_two_columns, CL_BG, CL_NAVY, win_button


class WorkerMasterScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self.selected_code = None
        self.checked = set()  # 체크박스로 고른 작업자코드들 (여러 명 한 번에 삭제용)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = tk.Frame(self, bg=COLOR_HEADER_BG, highlightbackground="#C4C8D0", highlightthickness=1)
        top.pack(fill=tk.X)
        tk.Label(top, text="조회조건: 전체", bg=COLOR_HEADER_BG).pack(side=tk.LEFT, padx=8, pady=8)
        win_button(top, text="조회", command=self.refresh, kind="normal").pack(side=tk.LEFT, padx=8)
        # [2026-10-02] 등록/수정/삭제를 아래쪽에서 위쪽 [조회] 옆으로 옮겼다(간격을 두고 배치).
        win_button(top, text="등록", width=10, command=self.open_register_dialog, kind="normal").pack(side=tk.LEFT, padx=(36, 0))
        win_button(top, text="수정", width=10, command=self.open_edit_dialog, kind="normal").pack(side=tk.LEFT, padx=(6, 0))
        win_button(top, text="삭제", width=10, command=self.delete_selected, kind="normal").pack(side=tk.LEFT, padx=(6, 0))
        win_button(top, text="⬆ PDA 전송", command=self.send_to_pda, kind="normal").pack(side=tk.RIGHT, padx=8, pady=6)
        win_button(top, text="불러오기(엑셀)", command=self.import_excel, kind="normal").pack(side=tk.RIGHT, padx=4)

        # [2026-10-02] 작업자코드 앞에 체크박스 칸 - 여러 명을 체크해서 한 번에 삭제할 수 있다.
        # 체크칸 클릭 = 체크/해제, "선택" 헤더 클릭 = 전체 체크/해제, Space = 선택한 줄 체크/해제.
        container, self.tree = setup_treeview(
            self, columns=("check", "code", "name"), headings=("선택", "작업자코드", "작업자명"),
            widths=(50, 90, 180), height=16, style_name="BigCheck.Treeview"
        )
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Button-1>", self._on_tree_click, add="+")
        self.tree.bind("<space>", self._on_space)
        self.tree.heading("check", command=self._toggle_all)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        self.selected_code = self.tree.set(sel[0], "code") if sel else None

    def _set_check(self, iid, on):
        code = self.tree.set(iid, "code")
        if on:
            self.checked.add(code)
        else:
            self.checked.discard(code)
        self.tree.set(iid, "check", "☑" if on else "☐")

    def _on_tree_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        iid = self.tree.identify_row(event.y)
        if iid:
            self._set_check(iid, self.tree.set(iid, "code") not in self.checked)

    def _on_space(self, _e=None):
        for iid in self.tree.selection():
            self._set_check(iid, self.tree.set(iid, "code") not in self.checked)
        return "break"

    def _toggle_all(self):
        items = self.tree.get_children()
        if not items:
            return
        all_on = all(self.tree.set(i, "code") in self.checked for i in items)
        for i in items:
            self._set_check(i, not all_on)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        conn = dbmod.get_conn()
        codes = set()
        for i, row in enumerate(conn.execute("SELECT worker_code, worker_name FROM workers ORDER BY worker_code")):
            code = row["worker_code"]
            codes.add(code)
            self.tree.insert("", tk.END, values=("☑" if code in self.checked else "☐", code, row["worker_name"]),
                              tags=("odd",) if i % 2 == 1 else ())
        conn.close()
        self.checked &= codes  # 지워진 작업자는 체크 목록에서도 뺀다

    def open_register_dialog(self):
        self._open_form_dialog(mode="new")

    def open_edit_dialog(self):
        # 선택한 줄이 없어도 체크한 작업자가 딱 한 명이면 그 사람을 수정한다.
        code = self.selected_code or (next(iter(self.checked)) if len(self.checked) == 1 else None)
        if not code:
            messagebox.showinfo("알림", "수정할 작업자를 목록에서 선택하세요.")
            return
        conn = dbmod.get_conn()
        row = conn.execute("SELECT * FROM workers WHERE worker_code=?", (code,)).fetchone()
        conn.close()
        if row is None:
            self.refresh()
            return
        self._open_form_dialog(mode="edit", code=row["worker_code"], name=row["worker_name"])

    def _open_form_dialog(self, mode, code="", name=""):
        win = tk.Toplevel(self)
        center_on_app(win)
        win.title("작업자마스터 등록")
        win.geometry("360x180")
        win.bind("<Escape>", lambda e: win.destroy())

        # [2026-10-02] 엔터 = 다음 칸으로(작업자코드 -> 작업자명), 마지막 칸(작업자명)에서 엔터 = [등록],
        # ESC = 취소(창 닫기).
        tk.Label(win, text="작업자코드").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        e_code = tk.Entry(win, width=24)
        e_code.grid(row=0, column=1, padx=10, pady=10)
        e_code.insert(0, code)
        if mode == "edit":
            e_code.configure(state="readonly")

        tk.Label(win, text="작업자명").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        e_name = tk.Entry(win, width=24)
        e_name.grid(row=1, column=1, padx=10, pady=10)
        e_name.insert(0, name)

        keep_open = tk.BooleanVar(value=False)
        tk.Checkbutton(win, text="연속 추가", variable=keep_open).grid(row=2, column=0, columnspan=2, sticky="w", padx=10)

        def save():
            c = e_code.get().strip()
            n = e_name.get().strip()
            if not c or not n:
                # [2026-10-02] 값 없이 엔터/[등록] -> 안내 후 팝업은 닫지 않고(안내창을 이 팝업 위에 띄움)
                # 비어 있는 칸으로 커서를 돌려준다(작업자코드가 비었으면 작업자코드 칸).
                messagebox.showwarning("알림", "작업자코드와 작업자명을 입력하세요.", parent=win)
                target = e_code if (not c and mode != "edit") else e_name
                win.lift()
                target.focus_force()
                target.select_range(0, tk.END)
                return "break"
            conn = dbmod.get_conn()
            conn.execute(
                "INSERT INTO workers(worker_code, worker_name) VALUES (?,?) "
                "ON CONFLICT(worker_code) DO UPDATE SET worker_name=excluded.worker_name",
                (c, n)
            )
            conn.commit()
            conn.close()
            self.refresh()
            if keep_open.get() and mode == "new":
                e_code.delete(0, tk.END)
                e_name.delete(0, tk.END)
                e_code.focus_set()
            else:
                win.destroy()

        btns = tk.Frame(win)
        btns.grid(row=3, column=0, columnspan=2, pady=14)
        win_button(btns, text="등록", width=10, command=save, kind="normal").pack(side=tk.LEFT, padx=6)
        win_button(btns, text="취소", width=10, command=win.destroy, kind="normal").pack(side=tk.LEFT)

        e_code.bind("<Return>", lambda e: (e_name.focus_set(), e_name.icursor(tk.END), "break")[-1])
        e_name.bind("<Return>", lambda e: (save(), "break")[-1])
        e_code.bind("<KP_Enter>", lambda e: (e_name.focus_set(), "break")[-1])
        e_name.bind("<KP_Enter>", lambda e: (save(), "break")[-1])
        # 새 등록이면 작업자코드부터, 수정이면(코드는 못 바꾸므로) 작업자명부터 입력하게 한다.
        (e_name if mode == "edit" else e_code).focus_set()
        win.after(50, lambda: (e_name if mode == "edit" else e_code).focus_force())

    def delete_selected(self):
        """체크박스로 고른 작업자들을 한 번에 지운다. 체크한 게 없으면 예전처럼 선택한 한 줄을 지운다."""
        codes = sorted(self.checked) if self.checked else ([self.selected_code] if self.selected_code else [])
        if not codes:
            messagebox.showinfo("알림", "삭제할 작업자를 체크하거나 목록에서 선택하세요.")
            return
        if len(codes) == 1:
            question = f"작업자 [{codes[0]}]를 삭제할까요?"
        else:
            shown = ", ".join(codes[:10]) + (" ..." if len(codes) > 10 else "")
            question = f"체크한 작업자 {len(codes):,}명을 삭제할까요?\n({shown})"
        if not messagebox.askyesno("확인", question):
            return
        conn = dbmod.get_conn()
        conn.executemany("DELETE FROM workers WHERE worker_code=?", [(c,) for c in codes])
        conn.commit()
        conn.close()
        self.checked.difference_update(codes)
        self.selected_code = None
        self.refresh()

    def import_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel 파일", "*.xlsx")])
        if not path:
            return
        try:
            rows = read_excel_two_columns(path, ["작업자코드", "코드"], ["작업자명", "이름", "성명"])
        except ImportError:
            messagebox.showerror("오류", "엑셀을 읽으려면 openpyxl이 필요합니다.\npip install openpyxl 을 실행하세요.")
            return
        except Exception as e:
            messagebox.showerror("오류", f"엑셀을 읽는 중 오류: {e}")
            return

        conn = dbmod.get_conn()
        for code, name in rows:
            conn.execute(
                "INSERT INTO workers(worker_code, worker_name) VALUES (?,?) "
                "ON CONFLICT(worker_code) DO UPDATE SET worker_name=excluded.worker_name",
                (code, str(name).strip() if name is not None else "")
            )
        conn.commit()
        conn.close()
        self.refresh()
        messagebox.showinfo("완료", f"{len(rows):,}건 불러왔습니다.")

    def send_to_pda(self):
        ok, msg, count = pda_transfer.push_workers()
        if ok:
            messagebox.showinfo("완료", f"작업자마스터 {count:,}건을 PDA로 전송했습니다.")
        else:
            messagebox.showerror("오류", f"전송 실패: {msg}")
