# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""매대등록 > 샘플링 자료등록 화면.

실사 품질을 확인하기 위해 일부 SECTION을 다시 세어보는 "샘플링 검수"에서
찾아낸 미스(오차) 건을 등록한다. 미스유형에 따라 책임 소재가 KOINT
(실사 대행사)인지 KYOBO(매장)인지가 정해지고(db.MISS_TYPE_OWNER), 이 자료는
[집계표관리 > 샘플링 결과보고서]에서 LOC별/책임소재별로 집계된다.

[2026-09-24 정정] 목록의 "책임" 항목 표시를 "RBSKOREA" -> "KOINT"로
바꿨다(db.py의 MISS_TYPES 값 변경에 맞춤 - 실사 대행사 자체 명칭 변경)."""

import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
from . import db as dbmod
from .ui_common import (
    center_on_app,
    setup_treeview, CL_BG, CL_NAVY, CL_GOLD, CL_PANEL, CL_GRID, CL_TEXT, CL_TEXT_DIM, win_button
)


class SamplingRegisterScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = tk.Frame(self, bg=CL_BG)
        top.pack(fill=tk.X, padx=8, pady=(10, 4))
        tk.Label(top, text="점포코드", bg=CL_BG).pack(side=tk.LEFT, padx=(0, 4))
        self.lbl_store = tk.Label(top, text=self.app.state.store_code, bg=CL_BG, font=("", 10, "bold"))
        self.lbl_store.pack(side=tk.LEFT, padx=(0, 20))
        tk.Label(top, text="조사일자", bg=CL_BG).pack(side=tk.LEFT, padx=(0, 4))
        self.lbl_date = tk.Label(top, text=self.app.state.survey_date, bg=CL_BG, font=("", 10, "bold"))
        self.lbl_date.pack(side=tk.LEFT, padx=(0, 20))
        win_button(top, text="새로고침", command=self.refresh, kind="normal").pack(side=tk.RIGHT)

        columns = ("no", "area", "section", "miss_qty", "miss_count", "miss_type", "owner")
        headings = ("NO", "AREA", "SECTION", "미스수량", "미스건수", "미스유형", "책임")
        # [2026-09-23 정정] "SECTION" 헤더 글자가 안 잘리도록 폭을 늘렸다.
        widths = (45, 70, 95, 80, 80, 120, 90)
        container, self.tree = setup_treeview(self, columns, headings, widths, height=18)
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        bottom = tk.Frame(self, bg=CL_BG)
        bottom.pack(fill=tk.X, padx=8, pady=8)
        win_button(bottom, text="등록", width=10, command=self.open_register_dialog, kind="normal").pack(side=tk.LEFT)
        win_button(bottom, text="수정", width=10, command=self.open_edit_dialog, kind="normal").pack(side=tk.LEFT, padx=6)
        win_button(bottom, text="삭제", width=10, command=self.delete_selected, kind="danger").pack(side=tk.LEFT)

    def refresh(self):
        self.lbl_store.config(text=self.app.state.store_code)
        self.lbl_date.config(text=self.app.state.survey_date)
        conn = dbmod.get_conn()
        self._rows = conn.execute(
            "SELECT * FROM sampling_miss WHERE store_code=? AND survey_date=? ORDER BY id",
            (self.app.state.store_code, self.app.state.survey_date)
        ).fetchall()
        conn.close()

        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self._rows, start=1):
            owner = dbmod.MISS_TYPE_OWNER.get(r["miss_type"], "")
            self.tree.insert("", tk.END, values=(
                i, r["area"], r["section"], f"{r['miss_qty'] or 0:,}", f"{r['miss_count'] or 0:,}", r["miss_type"], owner
            ), tags=("odd",) if i % 2 == 0 else ())

    def open_register_dialog(self):
        self._open_form_dialog(mode="new")

    def open_edit_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("알림", "수정할 줄을 선택하세요.")
            return
        idx = self.tree.index(sel[0])
        self._open_form_dialog(mode="edit", row=self._rows[idx])

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("알림", "삭제할 줄을 선택하세요.")
            return
        idx = self.tree.index(sel[0])
        row = self._rows[idx]
        if not messagebox.askyesno("확인", "선택한 샘플링 미스 기록을 삭제할까요?"):
            return
        conn = dbmod.get_conn()
        conn.execute("DELETE FROM sampling_miss WHERE id=?", (row["id"],))
        conn.commit()
        conn.close()
        self.refresh()

    def _open_form_dialog(self, mode, row=None):
        """등록/수정 팝업.

        [2026-09-23 3차 정정] 실제 운영화면 캡쳐에 맞춰 디자인을 다시
        입혔다(5가지 시안 중 "④ 화이트카드+네이비 이중테두리형" 채택) -
        프로그램 전체에서 쓰는 네이비/골드/아이보리 색을 그대로 쓴 흰
        카드를 네이비 굵은 테두리 + 골드 얇은 테두리로 감쌌다. 미스유형은
        tk.OptionMenu(기본 스타일) 대신 읽기전용 ttk.Combobox로 바꿔서
        화면캡쳐처럼 깔끔한 드롭다운으로 보이게 했다(값 자체는 그대로,
        화면에는 "1.카운터누락"처럼 번호만 붙여 보여준다).

        예전에 AREA/미스수량 라벨 자리에 SECTION/미스건수 라벨이 겹쳐
        보이던 버그(add_field가 항상 같은 칸에 그려서 생긴 문제)는 이미
        고쳐진 상태를 그대로 유지한다 - add_field가 라벨/입력칸을 원하는
        칸(column)에 바로 그린다.

        버튼은 화면캡쳐와 똑같이 [등록]/[수정]/[삭제] 세 개를 항상 보여
        준다. [등록]은 지금 입력칸 값으로 항상 "새 줄"을 추가하고(연속
        추가에 체크돼 있으면 칸을 비우고 계속 등록할 수 있게 팝업을 열어
        둔다), [수정]/[삭제]는 이 팝업이 기존 줄을 불러온 상태(=수정으로
        열렸을 때, row가 있을 때)에만 눌리고 새로 등록하는 중에는 고치거나
        지울 대상이 없으므로 비활성화해 둔다."""
        win = tk.Toplevel(self)
        center_on_app(win)
        win.title("샘플링 자료 등록 - 고객사")
        win.resizable(False, False)
        win.configure(bg=CL_BG)
        try:
            win.transient(self.winfo_toplevel())
            win.grab_set()
        except tk.TclError:
            pass
        win.bind("<Escape>", lambda e: win.destroy())

        # 바깥 네이비 굵은 테두리 + 안쪽 골드 얇은 테두리로 감싼 흰 카드.
        outer = tk.Frame(win, bg=CL_NAVY, padx=3, pady=3)
        outer.pack(padx=14, pady=14)
        inner = tk.Frame(outer, bg=CL_GOLD, padx=1, pady=1)
        inner.pack()
        card = tk.Frame(inner, bg=CL_PANEL, padx=26, pady=22)
        card.pack()

        tk.Label(card, text="샘플링 자료 등록 - 고객사", bg=CL_PANEL, fg=CL_NAVY,
                 font=("", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Frame(card, bg=CL_GRID, height=1).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 16))

        ENTRY_OPT = dict(relief="flat", highlightthickness=1, highlightbackground=CL_GRID,
                          highlightcolor=CL_NAVY, font=("", 11), bg=CL_PANEL)

        def add_field(r, c, label, width=14):
            tk.Label(card, text=label, bg=CL_PANEL, fg=CL_TEXT_DIM, font=("", 10)).grid(
                row=r, column=c, padx=(0 if c == 0 else 18, 0), pady=(0, 4), sticky="sw")
            e = tk.Entry(card, width=width, **ENTRY_OPT)
            e.grid(row=r + 1, column=c, padx=(0 if c == 0 else 18, 0), pady=(0, 16), ipady=5, sticky="w")
            return e

        e_area = add_field(2, 0, "AREA")
        e_section = add_field(2, 1, "SECTION")
        e_qty = add_field(4, 0, "미스수량")
        e_cnt = add_field(4, 1, "미스건수")

        tk.Label(card, text="미스유형", bg=CL_PANEL, fg=CL_TEXT_DIM, font=("", 10)).grid(
            row=6, column=0, columnspan=2, sticky="sw", pady=(0, 4))

        # 화면에는 "1.카운터누락"처럼 번호를 붙여 깔끔한 드롭다운으로
        # 보여주지만, DB에는 예전과 똑같이 원래 이름(예: "카운터누락")만
        # 저장한다 - db.MISS_TYPES 자체(다른 화면도 같이 쓰는 목록)는
        # 손대지 않았다.
        miss_labels = [f"{i}.{name}" for i, (name, _owner) in enumerate(dbmod.MISS_TYPES, start=1)]
        label_to_name = dict(zip(miss_labels, [name for name, _ in dbmod.MISS_TYPES]))
        name_to_label = {name: lbl for lbl, name in label_to_name.items()}

        try:
            ttk.Style().configure("Sampling.TCombobox", padding=6)
        except Exception:
            pass
        type_var = tk.StringVar(value=miss_labels[0])
        cb_type = ttk.Combobox(card, textvariable=type_var, values=miss_labels, state="readonly",
                                width=22, style="Sampling.TCombobox", font=("", 11))
        cb_type.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 16))

        keep_open = tk.BooleanVar(value=False)
        tk.Checkbutton(card, text="연속 추가", variable=keep_open, bg=CL_PANEL, fg=CL_TEXT,
                       activebackground=CL_PANEL, selectcolor=CL_PANEL, font=("", 10)).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(0, 16))

        if row is not None:
            e_area.insert(0, row["area"] or "")
            e_section.insert(0, row["section"] or "")
            e_qty.insert(0, row["miss_qty"] or 0)
            e_cnt.insert(0, row["miss_count"] or 0)
            type_var.set(name_to_label.get(row["miss_type"], miss_labels[0]))

        tk.Frame(card, bg=CL_GRID, height=1).grid(
            row=9, column=0, columnspan=2, sticky="ew", pady=(0, 16))

        def clear_fields():
            e_area.delete(0, tk.END)
            e_section.delete(0, tk.END)
            e_qty.delete(0, tk.END)
            e_cnt.delete(0, tk.END)
            type_var.set(miss_labels[0])

        def read_fields():
            area = e_area.get().strip()
            section = e_section.get().strip()
            try:
                qty = int(e_qty.get().strip() or 0)
                cnt = int(e_cnt.get().strip() or 0)
            except ValueError:
                messagebox.showwarning("알림", "미스수량/미스건수는 숫자로 입력하세요.", parent=win)
                return None
            if not area or not section:
                messagebox.showwarning("알림", "AREA와 SECTION을 입력하세요.", parent=win)
                return None
            miss_type = label_to_name.get(type_var.get(), type_var.get())
            return area, section, qty, cnt, miss_type

        def do_register():
            vals = read_fields()
            if vals is None:
                return
            area, section, qty, cnt, miss_type = vals
            conn = dbmod.get_conn()
            conn.execute(
                "INSERT INTO sampling_miss(store_code, survey_date, area, section, miss_qty, miss_count, "
                "miss_type, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (self.app.state.store_code, self.app.state.survey_date, area, section, qty, cnt,
                 miss_type, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            conn.close()
            self.refresh()
            if keep_open.get():
                clear_fields()
                e_area.focus_set()
            else:
                win.destroy()

        def do_edit():
            if row is None:
                return
            vals = read_fields()
            if vals is None:
                return
            area, section, qty, cnt, miss_type = vals
            conn = dbmod.get_conn()
            conn.execute(
                "UPDATE sampling_miss SET area=?, section=?, miss_qty=?, miss_count=?, miss_type=? WHERE id=?",
                (area, section, qty, cnt, miss_type, row["id"])
            )
            conn.commit()
            conn.close()
            self.refresh()
            win.destroy()

        def do_delete():
            if row is None:
                return
            if not messagebox.askyesno("확인", "선택한 샘플링 미스 기록을 삭제할까요?", parent=win):
                return
            conn = dbmod.get_conn()
            conn.execute("DELETE FROM sampling_miss WHERE id=?", (row["id"],))
            conn.commit()
            conn.close()
            self.refresh()
            win.destroy()

        btns = tk.Frame(card, bg=CL_PANEL)
        btns.grid(row=10, column=0, columnspan=2, sticky="e")
        btn_register = win_button(btns, text="등록", width=8, command=do_register, kind="accent")
        btn_edit = win_button(btns, text="수정", width=8, command=do_edit, kind="normal")
        btn_delete = win_button(btns, text="삭제", width=8, command=do_delete, kind="danger")
        btn_register.pack(side=tk.LEFT, padx=(0, 6))
        btn_edit.pack(side=tk.LEFT, padx=(0, 6))
        btn_delete.pack(side=tk.LEFT)
        if row is None:
            # 새로 등록하는 중에는(=기존 줄을 불러온 상태가 아니면) 고치거나
            # 지울 대상 자체가 없다.
            for b in (btn_edit, btn_delete):
                try:
                    b.state(["disabled"])
                except Exception:
                    b.config(state="disabled")

        e_area.bind("<Return>", lambda e: e_section.focus_set())
        e_section.bind("<Return>", lambda e: e_qty.focus_set())
        e_qty.bind("<Return>", lambda e: e_cnt.focus_set())
        e_area.focus_set()
