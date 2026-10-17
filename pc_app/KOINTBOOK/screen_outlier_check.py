# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""집계표관리 > 이상치 체크 확인 화면.

AREA/SECTION 범위와 수량 범위를 지정해서, 그 범위 안에 있는 실사 데이터를
그대로 뽑아본다. 보통 "수량"란에 아주 큰 값(예: 100~)을 넣어서, 한 번에
비정상적으로 많이 찍힌(이상치로 의심되는) 스캔 건을 걸러내는 용도로 쓴다."""

import tkinter as tk
from tkinter import messagebox
from . import db as dbmod
from .virtual_table import VirtualList, ListModel
from .ui_common import setup_treeview, export_rows_to_excel, file_date, CL_BG, CL_NAVY, CL_TEXT_DIM, win_button

# [2026-09-28] "프로그램 전체 목록이 렉 없이" - 이 화면은 수량 필터를
# 비워두면(이상치 확인 전, 필터를 아직 안 걸었을 때) stock_counts 전체를
# 표에 한 번에 그려 넣는다 - 실적관리와 같은 이유로 페이지 단위로 나눈다.
PAGE_ROWS = 300


class OutlierCheckScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._rows = []
        self._view_page = 0
        self._view_total_pages = 1
        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self, bg=CL_BG)
        top.pack(fill=tk.X, padx=8, pady=(10, 6))

        tk.Label(top, text="AREA", bg=CL_BG).pack(side=tk.LEFT, padx=(0, 4))
        self.e_area_from = tk.Entry(top, width=8)
        self.e_area_from.pack(side=tk.LEFT)
        tk.Label(top, text="~", bg=CL_BG).pack(side=tk.LEFT, padx=2)
        self.e_area_to = tk.Entry(top, width=8)
        self.e_area_to.pack(side=tk.LEFT)

        tk.Label(top, text="SECTION", bg=CL_BG).pack(side=tk.LEFT, padx=(16, 4))
        self.e_sec_from = tk.Entry(top, width=8)
        self.e_sec_from.pack(side=tk.LEFT)
        tk.Label(top, text="~", bg=CL_BG).pack(side=tk.LEFT, padx=2)
        self.e_sec_to = tk.Entry(top, width=8)
        self.e_sec_to.pack(side=tk.LEFT)

        tk.Label(top, text="수량", bg=CL_BG).pack(side=tk.LEFT, padx=(16, 4))
        self.e_qty_from = tk.Entry(top, width=8)
        self.e_qty_from.pack(side=tk.LEFT)
        tk.Label(top, text="~", bg=CL_BG).pack(side=tk.LEFT, padx=2)
        self.e_qty_to = tk.Entry(top, width=8)
        self.e_qty_to.pack(side=tk.LEFT)

        win_button(top, text="조회", command=self.refresh, kind="normal").pack(side=tk.LEFT, padx=10)
        win_button(top, text="엑셀저장", command=self.export_excel, kind="accent").pack(side=tk.RIGHT, padx=4)

        columns = ("no", "area", "section", "dan", "yeol", "isbn", "book_name", "qty")
        headings = ("NO", "AREA", "SECTION", "단", "열", "바코드", "상품명", "수량")
        # [2026-09-23 정정] "SECTION" 헤더 글자가 안 잘리도록 폭을 늘렸다.
        widths = (45, 70, 95, 45, 45, 130, 260, 70)
        # 가상 스크롤 표(virtual_table.py): 화면에 보이는 줄만 두고 스크롤할 때 글자만 바꾼다.
        # 예전의 페이지 버튼(처음/이전/다음/끝)은 없고, 스크롤 하나로 끝까지 볼 수 있다.
        self.vl = VirtualList(self, columns, headings, widths, height=20)
        self.vl.container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))
        self.tree = self.vl.tree

        status = tk.Frame(self, bg=CL_BG)
        status.pack(fill=tk.X, padx=8, pady=(4, 8))
        self.lbl_total = tk.Label(status, text="(총 0건)", bg=CL_BG, fg=CL_NAVY, font=("", 10, "bold"))
        self.lbl_total.pack(side=tk.LEFT)

    @staticmethod
    def _to_int(text, default=None):
        text = (text or "").strip()
        if not text:
            return default
        try:
            return int(text)
        except ValueError:
            return default

    def refresh(self):
        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        area_from = self.e_area_from.get().strip()
        area_to = self.e_area_to.get().strip()
        sec_from = self.e_sec_from.get().strip()
        sec_to = self.e_sec_to.get().strip()
        qty_from = self._to_int(self.e_qty_from.get())
        qty_to = self._to_int(self.e_qty_to.get())

        conn = dbmod.get_conn()
        rows = conn.execute(
            "SELECT area, section, dan, yeol, isbn, book_name, qty FROM stock_counts "
            "WHERE store_code=? AND survey_date=? ORDER BY CAST(area AS INTEGER), area, CAST(section AS INTEGER), section, CAST(dan AS INTEGER), dan, CAST(yeol AS INTEGER), yeol",
            (store_code, date)
        ).fetchall()
        conn.close()

        self._rows = []
        for r in rows:
            if area_from and str(r["area"]) < area_from:
                continue
            if area_to and str(r["area"]) > area_to:
                continue
            if sec_from and str(r["section"]) < sec_from:
                continue
            if sec_to and str(r["section"]) > sec_to:
                continue
            qty = r["qty"] or 0
            if qty_from is not None and qty < qty_from:
                continue
            if qty_to is not None and qty > qty_to:
                continue
            self._rows.append((r["area"], r["section"], r["dan"], r["yeol"], r["isbn"], r["book_name"], f"{qty:,}"))

        self._view_total_pages = max(1, (len(self._rows) + PAGE_ROWS - 1) // PAGE_ROWS)
        self._load_page(0)

    def _load_page(self, page=0):
        """조회된 줄(self._rows) 전체를 가상 스크롤 표에 보여준다(이름은 예전 그대로)."""
        self.vl.set_model(ListModel(self._rows))
        self.lbl_total.config(text=f"(총 {len(self._rows):,}건)")

    def export_excel(self):
        if not getattr(self, "_rows", None):
            messagebox.showinfo("알림", "저장할 데이터가 없습니다. 먼저 [조회]를 눌러주세요.")
            return
        headers = ("AREA", "SECTION", "단", "열", "바코드", "상품명", "수량")
        path = export_rows_to_excel(self._rows, headers, default_name=f"이상치체크확인_{file_date(self.app)}.xlsx", parent=self)
        if path:
            messagebox.showinfo("완료", f"저장되었습니다:\n{path}")
