# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""마스터관리 > 장부마스터 화면.

[2026-10-08] 상품마스터 화면과 같은 구성인데, 이 화면에서 불러온 값은 PDA가
아니라 "전산재고 수량이 필요한 모든 화면/엑셀"(재고조사 차이명세, 결과확인
리스트 등)의 기준이 된다. 상품마스터에서 불러온 값은 PDA 실사용이다.

 - 점포코드/점포명/조사일자는 상품마스터에서 지정한 값(app.state)으로 고정이고
   이 화면에서는 바꿀 수 없다(점포검색/날짜선택 비활성).
 - PDA전송 버튼은 없다(PDA로는 상품마스터만 보낸다).
 - 저장 테이블은 books와 같은 컬럼의 ledger_master다.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
from . import db as dbmod
from .virtual_table import VirtualList, ListModel
from .progress_core import Cancelled
from .progress_dialog import run_with_progress
from .masters import disp_qty, disp_exc
from .ui_common import (
    center_on_app,
    COLOR_HEADER_BG, setup_treeview, read_excel_columns, read_csv_columns, export_rows_to_excel,
    today_str, open_calendar_picker, CL_BG, CL_NAVY, CL_TEXT_DIM, win_button
)

# 점포코드/점포명을 "값을 보여주기만 하는" 굵은 글씨 칸으로 그릴 때 쓰는
# 스타일 - ZZOINT의 조사일자/점포 값칸(VALUE_BTN_OPT)과 같은 느낌으로,
# 흰 배경에 얇은 테두리를 두르고 진하게(bold) 보여준다.
# [2026-09-23 정정] 세로 길이가 옆의 "점포검색" 버튼보다 두꺼워 보여서,
# 글씨 크기를 살짝 줄이고 grid()의 ipady도 줄여 버튼과 비슷한 높이로 맞췄다.
VALUE_LBL_OPT = dict(font=("", 11, "bold"), fg=CL_NAVY, bg="white", relief="flat",
                      highlightthickness=1, highlightbackground="#C4C8D0")

PAGE_ROWS = 3000


class LedgerMasterScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._view_loaded = 0
        self._view_total = 0
        self._view_rows_cache = []
        self._build_ui()
        self.refresh()

    # ---- 상단: 점포코드/점포명/조사일자 + 실사자료 전체삭제 ----
    def _build_ui(self):
        top = tk.Frame(self, bg=COLOR_HEADER_BG, highlightbackground="#C4C8D0", highlightthickness=1)
        top.pack(fill=tk.X, padx=4, pady=(4, 2))

        tk.Label(top, text="점포코드", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=0, column=0, padx=(12, 4), pady=10)
        self.lbl_store_code = tk.Label(top, text=self.app.state.store_code, width=12, anchor="center", **VALUE_LBL_OPT)
        self.lbl_store_code.grid(row=0, column=1, padx=(0, 14), ipady=1)

        tk.Label(top, text="점포명", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=0, column=2, padx=(0, 4))
        self.lbl_store_name = tk.Label(top, text=self.app.state.store_name, width=20, anchor="w", **VALUE_LBL_OPT)
        self.lbl_store_name.grid(row=0, column=3, padx=(0, 6), ipady=1)
        # 점포검색/조사일자는 상품마스터에서 정한 값으로 고정 - 눌러도 바뀌지 않게 비활성.
        win_button(top, text="점포검색", command=lambda: None, kind="normal", state="disabled").grid(row=0, column=4, padx=(0, 20))

        tk.Label(top, text="조사일자", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=0, column=5, padx=(0, 4))
        self.pending_date = self.app.state.survey_date
        self.btn_date = win_button(top, text=self.pending_date, command=lambda: None, kind="normal", state="disabled")
        self.btn_date.grid(row=0, column=6, padx=(0, 10))

        # [2026-10-13] 서적/문구는 파일 양식이 달라서 불러오기 버튼을 둘로 나눴다(각각 같은 구분만 교체).
        imp = tk.Frame(top, bg=COLOR_HEADER_BG)
        imp.grid(row=0, column=7, padx=(0, 20))
        win_button(imp, text="서적 불러오기", command=lambda: self.import_kind("서적"), kind="normal").pack(side=tk.LEFT, padx=(0, 4))
        win_button(imp, text="문구 불러오기", command=lambda: self.import_kind("문구"), kind="normal").pack(side=tk.LEFT)

        # ---- 조회 줄 ----
        search_row = tk.Frame(self, bg=CL_BG)
        search_row.pack(fill=tk.X, padx=8, pady=(10, 4))
        self.search_mode = tk.StringVar(value="바코드")
        tk.Radiobutton(search_row, text="바코드", variable=self.search_mode, value="바코드", bg=CL_BG).pack(side=tk.LEFT, padx=4)
        tk.Radiobutton(search_row, text="도서명", variable=self.search_mode, value="도서명", bg=CL_BG).pack(side=tk.LEFT)
        self.e_search = tk.Entry(search_row, width=26)
        self.e_search.pack(side=tk.LEFT, padx=(8, 4), ipady=2)
        self.e_search.bind("<Return>", lambda ev: self.refresh())
        tk.Label(search_row, text="구분", bg=CL_BG, fg=CL_TEXT_DIM).pack(side=tk.LEFT, padx=(14, 4))
        self.cb_kind = ttk.Combobox(search_row, values=("전체", "서적", "문구"), state="readonly", width=6)
        self.cb_kind.set("전체")
        self.cb_kind.pack(side=tk.LEFT)
        self.cb_kind.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        win_button(search_row, text="조회", command=self.refresh, kind="normal").pack(side=tk.LEFT, padx=4)

        win_button(search_row, text="엑셀저장", command=self.export_excel, kind="accent").pack(side=tk.LEFT, padx=(20, 4))
        win_button(search_row, text="새로고침", command=self.refresh, kind="normal").pack(side=tk.LEFT, padx=4)

        columns = ("no", "kind", "isbn", "book_name", "category", "publisher", "ledger_qty", "real_qty", "missing_qty", "exception")
        headings = ("NO", "구분", "바코드", "도서명", "분야명", "출판사", "전산재고", "실재고", "누락재고", "예외여부")
        widths = (45, 50, 130, 300, 120, 150, 80, 70, 80, 70)
        # 가상 스크롤 표(virtual_table.py): 화면에 보이는 줄만 두고 스크롤할 때 글자만 바꾼다
        # (예전의 "스크롤이 끝에 닿으면 3000건씩 더 채우기" 방식은 더 이상 필요 없다).
        self.vl = VirtualList(self, columns, headings, widths, height=17)
        container = self.vl.container
        self.tree = self.vl.tree
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        # [2026-10-08] 더블클릭 예외 지정/해제는 막았다(요청) - 예외여부는 불러온 파일 값 그대로 보인다.

        bottom = tk.Frame(self, bg=CL_BG)
        bottom.pack(fill=tk.X, padx=8, pady=8)
        self.lbl_count = tk.Label(bottom, text="0 개의 자료 검색이 완료되었습니다.", bg=CL_BG)
        self.lbl_count.pack(side=tk.LEFT)

    # ---- 조회 ----
    def refresh(self):
        # 점포마스터에서 이미 삭제된 점포코드가 화면에 그대로 남아있는 문제를
        # 막기 위해, 새로고침할 때마다 그 점포코드가 stores 테이블에 실제로
        # 있는지 다시 확인한다 - 없으면(삭제됐으면) 화면 기준값을 비워서
        # 옛 점포명/상품마스터가 더 이상 보이지 않게 하고, [파일선택변환]도
        # 다시 막는다.
        store_code = self.app.state.store_code
        if store_code:
            conn = dbmod.get_conn()
            exists = conn.execute("SELECT 1 FROM stores WHERE store_code=?", (store_code,)).fetchone()
            conn.close()
            if not exists:
                self.app.state.store_code = ""
                self.app.state.store_name = ""
                self.app.state.save()

        self.lbl_store_code.config(text=self.app.state.store_code or "-")
        self.lbl_store_name.config(text=self.app.state.store_name or "-")
        self.pending_date = self.app.state.survey_date
        self.btn_date.config(text=self.pending_date)

        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        mode = self.search_mode.get()
        keyword = self.e_search.get().strip()

        conn = dbmod.get_conn()
        sql = ("SELECT isbn, book_name, category, publisher, rcds_qty, real_qty, missing_qty, except_flag, kind, rcds_x, real_x, missing_x "
               "FROM ledger_master WHERE store_code=?")
        params = [store_code]
        kind_sel = self.cb_kind.get()
        if kind_sel in ("서적", "문구"):
            sql += " AND kind=?"
            params.append(kind_sel)
        if keyword:
            col = "isbn" if mode == "바코드" else "book_name"
            sql += f" AND {col} LIKE ?"
            params.append(f"%{keyword}%")
        sql += " ORDER BY isbn"
        books = conn.execute(sql, params).fetchall()

        exc_set = {
            r["isbn"] for r in conn.execute(
                "SELECT isbn FROM exceptions WHERE store_code=? AND survey_date=?", (store_code, date)
            )
        }
        conn.close()

        rows = []
        for b in books:
            rcds_qty = b["rcds_qty"] or 0
            real_qty = b["real_qty"] or 0
            missing_qty = b["missing_qty"] or 0
            # [2026-09-23] 예전엔 Y일 때만 "예외"라고 보여주고 N이면 빈칸으로
            # 뒀는데, 마스터 파일에 실제로 들어있는 N값 자체가 화면에서
            # 안 보이는 문제가 있었다. generation.py(자료생성)와 똑같이
            # Y/N 원래 값을 그대로 보여주도록 통일했다(수동으로 예외 지정한
            # 경우는 파일 값이 N이라도 Y로 보이게 한다).
            is_exc = disp_exc(b["except_flag"], b["isbn"] in exc_set)
            rcds_qty = disp_qty(rcds_qty, b["rcds_x"])
            real_qty = disp_qty(real_qty, b["real_x"])
            missing_qty = disp_qty(missing_qty, b["missing_x"])
            rows.append((b["kind"] or "서적", b["isbn"], b["book_name"], b["category"], b["publisher"],
                        rcds_qty, real_qty, missing_qty, is_exc))
        self._view_rows_cache = rows
        self._view_total = len(rows)

        self.vl.set_model(ListModel(rows))
        cnt = {}
        for r in rows:
            cnt[r[0]] = cnt.get(r[0], 0) + 1
        detail = "  (" + ", ".join(f"{k} {v:,}" for k, v in sorted(cnt.items())) + ")" if cnt else ""
        self.lbl_count.config(text=f"{self._view_total:,} 개의 자료 검색이 완료되었습니다.{detail}")

    def _toggle_exception(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        isbn = values[2]
        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        conn = dbmod.get_conn()
        existing = conn.execute(
            "SELECT 1 FROM exceptions WHERE store_code=? AND survey_date=? AND isbn=?",
            (store_code, date, isbn)
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM exceptions WHERE store_code=? AND survey_date=? AND isbn=?",
                         (store_code, date, isbn))
        else:
            conn.execute(
                "INSERT INTO exceptions(store_code, survey_date, isbn, note, created_at) VALUES (?,?,?,?,?)",
                (store_code, date, isbn, "수동지정", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
        conn.commit()
        conn.close()
        self.refresh()

    # ---- 마스터 파일 불러오기/저장 ----
    # 실제 "도서 마스터정보 업로드"는 .csv(cmdtCode,cmdtName,jo_name,
    # pbcm_name,rcdsInvnQntt,realInvnQntt,qntt,exceptYsno)로 왔지만, 엑셀로
    # 정리해서 주는 경우도 있을 수 있어서 둘 다 같은 방식으로 읽는다.
    MASTER_COLUMNS = [
        ["ISBN", "바코드", "cmdtCode"],
        ["도서명", "cmdtName", "상품명", "품명"],
        ["분야명", "분야", "jo_name"],
        ["출판사", "pbcm_name"],
        ["전산재고", "rcdsInvnQntt"],
        ["실재고", "realInvnQntt"],
        ["누락재고", "누락수량", "qntt"],
        ["예외여부", "exceptYsno"],
    ]

    def import_kind(self, kind):
        """[서적 불러오기]/[문구 불러오기] - 양식이 서로 달라서 구분을 먼저 고르고 파일을 연다
        (masters.py 참고). 같은 점포의 같은 구분만 교체한다."""
        from .masters_ui import import_master_dialog
        import_master_dialog(self, "ledger_master", "장부마스터", kind)

    def export_excel(self):
        if not self._view_rows_cache:
            messagebox.showinfo("알림", "저장할 데이터가 없습니다.")
            return
        headers = ("구분", "바코드", "도서명", "분야명", "출판사", "전산재고", "실재고", "누락재고", "예외여부")
        path = export_rows_to_excel(self._view_rows_cache, headers, default_name=f"장부마스터_{today_str()}.xlsx", parent=self)
        if path:
            messagebox.showinfo("완료", f"저장되었습니다:\n{path}")
