# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""마스터관리 > 상품마스터(도서마스터) 화면.

[2026-10-08] "실사자료 전체삭제" 버튼을 없앴다(요청). 실사자료 삭제는 PDA Data 수신 화면에서 한다.

실제로 받은 "도서 마스터정보 업로드" 원본 파일(*_MST.csv, 헤더: cmdtCode,
cmdtName,jo_name,pbcm_name,rcdsInvnQntt,realInvnQntt,qntt,exceptYsno)을
보면 전산재고/실재고/누락재고/예외여부는 KOINTBOOK이 매번 다시 계산하는 값이
아니라, 마스터 파일 자체에 이미 들어있는 값이었다. 그래서 이 화면은 그
4개를 books 테이블에 그대로 저장해두고(rcds_qty/real_qty/missing_qty/
except_flag) 계산 없이 그대로 보여준다.

  바코드/도서명/분야명/출판사 = cmdtCode/cmdtName/jo_name/pbcm_name
  전산재고 = rcdsInvnQntt (마스터 파일의 값 그대로. [2026-10-08] 이 값은 PDA용이고,
             PC 화면/엑셀의 전산재고 기준은 장부마스터 화면에서 불러온 값이다)
  실재고   = realInvnQntt (마스터 파일의 값 그대로 - "이번 조사에서 스캔된
             수량"이 아니다. 그 값은 [자료생성]의 "스캔재고" 열에서 따로
             보여준다)
  누락재고 = qntt (마스터 파일의 값 그대로)
  예외여부 = exceptYsno 값(Y/N)을 그대로 보여준다. 다만 화면에서 더블클릭으로
             수동 지정했으면 파일 값이 N이라도 "Y"로 보인다(둘 중 하나만
             Y여도 Y로 보인다). [2026-09-23] 예전엔 Y일 때 "예외", 나머지는
             빈칸으로 보여줬는데, 그러면 파일의 N값 자체가 안 보이는 문제가
             있어 Y/N을 그대로 보여주도록 고쳤다.

[2026-09-23] "적용" 버튼을 없애고 조사일자는 고르는 즉시 반영된다.
점포코드/점포명은 ZZOINT처럼 직접 타이핑하는 입력칸이 아니라, 굵은 글씨로
현재 값만 보여주는 표시칸이다 - 값을 바꾸려면 "점포검색"으로 점포마스터에서
다시 골라야 한다(점포마스터에 등록된 점포가 없으면 점포검색 목록도 비어
있다). 화면을 새로고침할 때마다 그 점포코드가 점포마스터(stores)에 실제로
남아있는지 다시 확인해서, 점포마스터에서 이미 삭제된 점포면 점포코드/점포명
표시를 비운다(삭제된 점포의 옛 값이 화면에 그대로 남아있는 문제를 막기
위함). [파일선택변환](상품마스터 불러오기)도 점포코드가 실제로 점포마스터에
존재하고 조사일자도 있어야만 눌릴 수 있다(점포가 하나도 없거나 이미
삭제됐으면 불러오기 자체가 막힌다). [2026-09-23 정정] "파일선택변환"은
아래 조회 줄이 아니라 상단 "조사일자" 바로 옆으로 옮겼고, "⬆ PDA전송"은
그 옆에 간격을 좀 더 두고 배치했다(전송은 계속 상단, "실사자료 전체삭제"는
계속 하단).
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
from . import db as dbmod
from .virtual_table import VirtualList, ListModel
from . import pda_transfer
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


class ProductMasterScreen(tk.Frame):
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
        win_button(top, text="점포검색", command=self.pick_store, kind="normal").grid(row=0, column=4, padx=(0, 20))

        tk.Label(top, text="조사일자", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=0, column=5, padx=(0, 4))
        self.pending_date = self.app.state.survey_date
        self.btn_date = win_button(top, text=self.pending_date, command=self._open_calendar, kind="normal")
        self.btn_date.grid(row=0, column=6, padx=(0, 10))

        # [2026-09-23 정정] "파일선택변환"을 조사일자 바로 옆으로 옮기고(전에는
        # 아래 조회 줄에 있었다), PDA전송과는 간격을 좀 더 두어 "불러오기"
        # 계열과 "전송" 버튼이 헷갈리지 않게 구분했다.
        # [2026-10-13] 서적/문구는 파일 양식이 달라서 불러오기 버튼을 둘로 나눴다(각각 같은 구분만 교체).
        imp = tk.Frame(top, bg=COLOR_HEADER_BG)
        imp.grid(row=1, column=0, columnspan=4, sticky="w", padx=(12, 0), pady=(0, 8))
        win_button(imp, text="서적 불러오기", command=lambda: self.import_kind("서적"), kind="normal").pack(side=tk.LEFT, padx=(0, 4))
        win_button(imp, text="문구 불러오기", command=lambda: self.import_kind("문구"), kind="normal").pack(side=tk.LEFT)
        win_button(top, text="⬆ PDA전송", command=self.send_to_pda, kind="normal").grid(row=1, column=4, padx=(0, 14), pady=(0, 8))

        # [2026-10-08] 미등록 상품(상품마스터에 없는 바코드) 입력 정책 - PDA 재고입력(전송 시 함께 전달)과
        # PC 실적관리 입력·수정이 같은 값을 쓴다.
        tk.Label(top, text="미등록상품", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=1, column=5, padx=(10, 4), pady=(0, 8))
        self.cb_unreg = ttk.Combobox(top, values=dbmod.UNREG_POLICIES, state="readonly", width=11)
        self.cb_unreg.set(dbmod.get_unreg_policy())
        self.cb_unreg.grid(row=1, column=6, padx=(0, 12), pady=(0, 8))
        self.cb_unreg.bind("<<ComboboxSelected>>", lambda e: dbmod.set_setting("unreg_policy", self.cb_unreg.get()))

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
        # [2026-10-13] 오른쪽 아래 [상품마스터 초기화] - 선택한 점포의 상품마스터(서적+문구)를 모두 비운다.
        win_button(bottom, text="상품마스터 초기화", command=self.reset_master, kind="normal").pack(side=tk.RIGHT)

    # ---- 점포/조사일자 선택 ----
    def pick_store(self):
        conn = dbmod.get_conn()
        stores = conn.execute("SELECT store_code, store_name FROM stores ORDER BY store_code").fetchall()
        conn.close()
        win = tk.Toplevel(self)
        center_on_app(win)
        win.title("점포 선택")
        # [2026-09-29] "헤더 항목마다 제목이 잘리지않도록... 팝업창 너비등
        # 확인해줘" - 이 목록에는 스크롤바가 전혀 없어서, 점포명이 길면
        # (예: "교보문고 광화문점"처럼 긴 이름) 창 폭(기존 300)을 넘는
        # 부분이 가로 스크롤 없이 그냥 잘려 보이고, 점포 수가 많으면
        # 세로로도 나머지가 안 보였다. 창을 조금 더 넓히고, 세로/가로
        # 스크롤바를 둘 다 달아서 어떤 경우에도 전체 내용을 볼 수 있게 했다.
        win.geometry("340x360")
        win.bind("<Escape>", lambda e: win.destroy())
        list_frame = tk.Frame(win)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        lb_vsb = tk.Scrollbar(list_frame, orient="vertical")
        lb_hsb = tk.Scrollbar(list_frame, orient="horizontal")
        lb = tk.Listbox(list_frame, yscrollcommand=lb_vsb.set, xscrollcommand=lb_hsb.set)
        lb_vsb.config(command=lb.yview)
        lb_hsb.config(command=lb.xview)
        lb_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        lb_hsb.pack(side=tk.BOTTOM, fill=tk.X)
        lb.pack(fill=tk.BOTH, expand=True)
        for s in stores:
            lb.insert(tk.END, f"{s['store_code']} / {s['store_name']}")

        def choose(event=None):
            sel = lb.curselection()
            if not sel:
                return
            store = stores[sel[0]]
            self.app.state.store_code = store["store_code"]
            self.app.state.store_name = store["store_name"]
            # [2026-09-29] "프로그램을 껐다 키면 목록이 조회가 안되네" -
            # 점포/조사일자가 바뀌는 자리에서 바로 저장해둬야 다음에 켤 때도
            # 이어서 같은 점포/일자로 시작한다(AppState 설명 참고).
            self.app.state.save()
            win.destroy()
            self.refresh()

        lb.bind("<Double-Button-1>", choose)

    def _open_calendar(self):
        """ZZOINT와 같은 날짜선택 달력 - 직접 타이핑하지 않고 달력에서 고른다.
        "적용" 버튼이 없어졌으므로, 고르는 즉시 app.state에 반영한다."""
        def on_pick(date_str):
            self.pending_date = date_str
            self.btn_date.config(text=date_str)
            self.apply_context()
        open_calendar_picker(self, self.pending_date, on_pick)

    def apply_context(self):
        # 점포코드/점포명은 더 이상 여기서 바꾸지 않는다(점포검색에서 골라야
        # 바뀐다) - 이 함수는 달력에서 고른 조사일자만 반영한다.
        self.app.state.survey_date = self.pending_date or self.app.state.survey_date
        self.app.state.save()
        self.refresh()

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
               "FROM books WHERE store_code=?")
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
        import_master_dialog(self, "books", "상품마스터", kind)

    def reset_master(self):
        """선택한 점포의 상품마스터(서적+문구)를 전부 삭제한다. 장부마스터·실사자료는 건드리지 않는다."""
        store_code = self.app.state.store_code
        if not store_code:
            messagebox.showinfo("알림", "점포를 먼저 선택하세요.")
            return
        conn = dbmod.get_conn()
        try:
            cnt = {r[0] or "서적": r[1] for r in conn.execute(
                "SELECT kind, COUNT(*) FROM books WHERE store_code=? GROUP BY kind", (store_code,))}
        finally:
            conn.close()
        total = sum(cnt.values())
        if total == 0:
            messagebox.showinfo("알림", "초기화할 상품마스터가 없습니다.")
            return
        detail = ", ".join(f"{k} {v:,}건" for k, v in sorted(cnt.items()))
        if not messagebox.askyesno(
                "상품마스터 초기화",
                f"점포 {store_code} {self.app.state.store_name}의 상품마스터를 모두 삭제합니다.\n"
                f"({detail}, 합계 {total:,}건)\n\n"
                "장부마스터와 실사 스캔자료는 삭제되지 않습니다.\n"
                "삭제하면 되돌릴 수 없습니다. 계속할까요?", icon="warning", default="no", parent=self):
            return
        conn = dbmod.get_conn()
        try:
            conn.execute("DELETE FROM books WHERE store_code=?", (store_code,))
            conn.commit()
        finally:
            conn.close()
        self.refresh()
        messagebox.showinfo("완료", f"상품마스터 {total:,}건을 삭제했습니다.")

    def export_excel(self):
        if not self._view_rows_cache:
            messagebox.showinfo("알림", "저장할 데이터가 없습니다.")
            return
        headers = ("구분", "바코드", "도서명", "분야명", "출판사", "전산재고", "실재고", "누락재고", "예외여부")
        path = export_rows_to_excel(self._view_rows_cache, headers, default_name=f"상품마스터_{today_str()}.xlsx", parent=self)
        if path:
            messagebox.showinfo("완료", f"저장되었습니다:\n{path}")

    def send_to_pda(self):
        """[2026-10-02] 상품마스터 화면의 [PDA전송]: 상품마스터만이 아니라 점포마스터 + 작업자마스터 +
        상품마스터(지금 점포)를 한 번에 보낸다. PDA [마스터 수신]에서 세 가지를 한꺼번에 받는다."""
        store_code = self.app.state.store_code

        def work(progress):
            return pda_transfer.push_all(store_code, progress)

        def done(result, error):
            if isinstance(error, Cancelled):
                messagebox.showinfo("알림", "PDA 전송을 취소했습니다.")
                return
            if error is not None:
                messagebox.showerror("오류", f"전송 실패: {error}")
                return
            ok, summary = result
            if ok:
                messagebox.showinfo("완료", "점포/작업자/상품 마스터를 PDA로 전송했습니다.\n\n" + summary +
                                    "\n\nPDA의 [작업준비] 화면에서 [마스터 수신]을 눌러 주세요.")
            else:
                messagebox.showerror("오류", "일부 또는 전체 전송에 실패했습니다.\n\n" + summary)

        run_with_progress(self, "PDA 전송 (점포/작업자/상품 마스터)", work, done, cancelable=True)
