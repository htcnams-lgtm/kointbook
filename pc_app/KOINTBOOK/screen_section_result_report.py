# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""집계표관리 > 섹션별 결과보고서 화면.

SECTION(AREA-SECTION)별 건수/재고수량을 인쇄용 3단 배치(왼쪽부터 순서대로
1/3씩)로 보여준다 - 종이를 아끼려고 한 줄에 Location/건수/재고수량을
세 번 반복해서 배치하는 인쇄 습관을 그대로 옮긴 것이다."""

import tkinter as tk
from tkinter import messagebox
from . import db as dbmod
from .ui_common import setup_treeview, export_rows_to_excel, print_rows_to_excel, print_excel_file, today_str, \
    normalize_area, CL_BG, CL_NAVY, CL_TEXT_DIM, win_button


class SectionResultReportScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = tk.Frame(self, bg=CL_BG)
        top.pack(fill=tk.X, padx=12, pady=(10, 6))
        LBL_VALUE_OPT = dict(bg=CL_BG, fg=CL_NAVY, font=("", 12, "bold"))
        tk.Label(top, text="점포코드", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=0, column=0, padx=(0, 6))
        self.lbl_store_code = tk.Label(top, text=self.app.state.store_code, **LBL_VALUE_OPT)
        self.lbl_store_code.grid(row=0, column=1, padx=(0, 24))
        tk.Label(top, text="점포명", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=0, column=2, padx=(0, 6))
        self.lbl_store_name = tk.Label(top, text=self.app.state.store_name, **LBL_VALUE_OPT)
        self.lbl_store_name.grid(row=0, column=3, padx=(0, 24))
        tk.Label(top, text="조사일자", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=0, column=4, padx=(0, 6))
        self.lbl_date = tk.Label(top, text=self.app.state.survey_date, **LBL_VALUE_OPT)
        self.lbl_date.grid(row=0, column=5, padx=(0, 20))

        self.merge_mode = tk.StringVar(value="합산전")
        tk.Radiobutton(top, text="AREA 합산전", variable=self.merge_mode, value="합산전", bg=CL_BG,
                       command=self.refresh).grid(row=0, column=6, padx=(10, 0))
        tk.Radiobutton(top, text="AREA 합산후", variable=self.merge_mode, value="합산후", bg=CL_BG,
                       command=self.refresh).grid(row=0, column=7)

        win_button(top, text="조회", command=self.refresh, kind="normal").grid(row=0, column=8, padx=6)
        win_button(top, text="엑셀저장", command=self.export_excel, kind="accent").grid(row=0, column=9, padx=4)
        win_button(top, text="발행", command=self.print_report, kind="normal").grid(row=0, column=10, padx=4)

        columns = ("loc1", "count1", "qty1", "loc2", "count2", "qty2", "loc3", "count3", "qty3")
        headings = ("Location", "건수", "재고수량", "Location", "건수", "재고수량", "Location", "건수", "재고수량")
        widths = (140, 60, 90, 140, 60, 90, 140, 60, 90)
        container, self.tree = setup_treeview(self, columns, headings, widths, height=22)
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def refresh(self):
        self.lbl_store_code.config(text=self.app.state.store_code)
        self.lbl_store_name.config(text=self.app.state.store_name)
        self.lbl_date.config(text=self.app.state.survey_date)

        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        merged = self.merge_mode.get() == "합산후"

        conn = dbmod.get_conn()
        rows = conn.execute(
            "SELECT area, section, qty FROM stock_counts WHERE store_code=? AND survey_date=?",
            (store_code, date)
        ).fetchall()
        conn.close()

        totals = {}
        for r in rows:
            area = normalize_area(r["area"], merged=merged) or "(미지정)"
            key = f"{area}-{r['section']}"
            t = totals.setdefault(key, {"count": 0, "qty": 0})
            t["count"] += 1
            t["qty"] += r["qty"] or 0

        flat = [(loc, t["count"], t["qty"]) for loc, t in sorted(totals.items())]
        self._flat = flat
        self.tree.delete(*self.tree.get_children())

        n = len(flat)
        cols = 3
        per_col = -(-n // cols) if n else 0  # 올림 나눗셈
        chunks = [flat[i * per_col:(i + 1) * per_col] for i in range(cols)]
        for i in range(per_col):
            values = []
            for c in range(cols):
                if i < len(chunks[c]):
                    values.extend(chunks[c][i])
                else:
                    values.extend(("", "", ""))
            self.tree.insert("", tk.END, values=values, tags=("odd",) if i % 2 == 1 else ())

    def export_excel(self):
        if not getattr(self, "_flat", None):
            messagebox.showinfo("알림", "저장할 데이터가 없습니다.")
            return
        headers = ("Location", "건수", "재고수량")
        path = export_rows_to_excel(self._flat, headers, default_name=f"섹션별결과보고서_{today_str()}.xlsx", parent=self)
        if path:
            messagebox.showinfo("완료", f"저장되었습니다:\n{path}")

    def print_report(self):
        """[2026-09-28] "발행버튼을 누르면 왜 엑셀저장이 뜨냐" - [발행]은
        저장 위치를 묻지 않고 바로 인쇄로 이어져야 하므로, "다른 이름으로
        저장" 대화상자가 뜨는 export_rows_to_excel() 대신 조용히 임시
        파일을 만드는 print_rows_to_excel()을 쓴다([엑셀저장] 버튼은 계속
        export_rows_to_excel()을 그대로 쓴다)."""
        if not getattr(self, "_flat", None):
            messagebox.showinfo("알림", "인쇄할 데이터가 없습니다.")
            return
        headers = ("Location", "건수", "재고수량")
        path = print_rows_to_excel(self._flat, headers, default_name=f"섹션별결과보고서_{today_str()}.xlsx")
        if not path:
            return
        print_excel_file(path)
