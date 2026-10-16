# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""자료생성 화면: 실사내역(등록상품) 조회 + 최종 자료(엑셀) 일괄 생성."""

import os
import platform
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
from . import db as dbmod
from .virtual_table import VirtualList, IdListModel
from . import generation
from . import scope
from .scope_ui import ScopeBar
from .ui_common import setup_treeview, export_rows_to_excel, write_rows_to_excel_file, file_date, \
    CL_BG, CL_NAVY, CL_TEXT_DIM, win_button, split_scan_datetime


# [2026-09-28] 실사데이터가 몇 만 건씩 쌓이면 표에 한꺼번에 다 채울 때 화면이
# 멈추는(렉 걸리는) 문제가 있어서, 상품마스터 화면과 같은 방식(스크롤이 맨
# 아래에 닿을 때마다 다음 묶음을 이어서 채우는 "무한 스크롤")으로 처음에
# 고쳤었다.
#
# [2026-09-28 재수정] 이 화면(자료생성 목록)도 실적관리와 마찬가지로 실사
# "건수" 자체를 그대로 보여주는 화면이라 10만~20만 건까지 쌓일 수 있는데,
# 무한 스크롤은 끝까지 내리면 결국 표 위젯 하나가 그 많은 항목을 전부 누적해서
# 들고 있게 되고, 그때부터는 Treeview 자체가 느려진다(=여전히 남아있던 렉).
# 그래서 실적관리와 동일하게, 표에는 항상 딱 PAGE_ROWS건만 들어있도록 하는
# 진짜 페이지(이전/다음) 방식으로 바꿨다 - _load_page 참고.
PAGE_ROWS = 1000


class DataGenerateScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._view_rows_cache = []  # 조회 결과 전체(엑셀저장/자료생성용)
        self._view_page = 0  # 지금 표에 그려진 페이지(0부터 시작)
        self._view_total = 0
        self._view_total_pages = 1
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = tk.Frame(self, bg=CL_BG)
        top.pack(fill=tk.X, padx=12, pady=(10, 6))
        LBL_VALUE_OPT = dict(bg=CL_BG, fg=CL_NAVY, font=("", 12, "bold"))
        tk.Label(top, text="점포코드", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=0, column=0, padx=(0, 6))
        self.lbl_store_code = tk.Label(top, text=self.app.state.store_code, **LBL_VALUE_OPT)
        self.lbl_store_code.grid(row=0, column=1, padx=(0, 28))
        tk.Label(top, text="점포명", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=0, column=2, padx=(0, 6))
        self.lbl_store_name = tk.Label(top, text=self.app.state.store_name, **LBL_VALUE_OPT)
        self.lbl_store_name.grid(row=0, column=3, padx=(0, 28))
        tk.Label(top, text="조사일자", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=0, column=4, padx=(0, 6))
        self.lbl_date = tk.Label(top, text=self.app.state.survey_date, **LBL_VALUE_OPT)
        self.lbl_date.grid(row=0, column=5, padx=(0, 20))

        # [2026-09-28] 불필요한 "재집계 데이터생성" 버튼을 없앴다(요청) - 이
        # 화면은 [새로고침] 버튼으로 이미 다시 집계해서 보여주고 있어서 같은
        # 동작을 하는 버튼이 하나 더 있을 필요가 없었다.

        tk.Frame(self, bg="#C4C8D0", height=1).pack(fill=tk.X, padx=12, pady=(0, 8))

        # ---- [2026-10-13] 생성 패널: 서적 / 문구 카드 ------------------------------------
        # 서적과 문구는 만드는 자료 양식이 달라서 카드 두 장으로 나눴다. 필요한 쪽만 체크해서
        # 한 번에 만든다(서적만 / 문구만 / 둘 다). 카드 위쪽 숫자는 지금 DB에 있는 스캔 건수라
        # 만들기 전에 "이 구분에 자료가 있는지" 바로 알 수 있다.
        panel = tk.Frame(self, bg=CL_BG)
        panel.pack(fill=tk.X, padx=12, pady=(0, 8))
        panel.columnconfigure(0, weight=1, uniform="c")
        panel.columnconfigure(1, weight=1, uniform="c")

        self.var_do_book = tk.BooleanVar(value=True)
        self.var_do_stat = tk.BooleanVar(value=True)
        self.var_f = {k: tk.BooleanVar(value=True) for k in ("d1", "d2", "list", "shelf", *generation.STAT_FILE_KEYS)}

        def card(col, title, var_do):
            f = tk.Frame(panel, bg="white", highlightbackground="#C4C8D0", highlightthickness=1)
            f.grid(row=0, column=col, sticky="nsew", padx=(0, 8) if col == 0 else (0, 0))
            head = tk.Frame(f, bg="white")
            head.pack(fill=tk.X, padx=10, pady=(8, 2))
            tk.Checkbutton(head, text=title, variable=var_do, bg="white", fg=CL_NAVY,
                           font=("", 12, "bold"), command=self._update_go_button).pack(side=tk.LEFT)
            lbl = tk.Label(head, text="", bg="white", fg=CL_TEXT_DIM)
            lbl.pack(side=tk.RIGHT)
            return f, lbl

        fb, self.lbl_book = card(0, "서적 자료", self.var_do_book)
        for key, text in (("d1", "kyobo_data1.txt  (서가번호 + 바코드13)"),
                          ("d2", "kyobo_data2.txt  (바코드13 + 수량5)"),
                          ("shelf", "서가별스캔데이터.xlsx"),
                          ("list", "결과확인리스트.xlsx  (전산재고 / 스캔재고 / 차이)")):
            tk.Checkbutton(fb, text=text, variable=self.var_f[key], bg="white", anchor="w").pack(fill=tk.X, padx=(28, 8))
        self.var_zero = tk.BooleanVar(value=True)
        tk.Checkbutton(fb, text="결과확인리스트에 전산재고·실재고·스캔이 모두 0인 품목도 포함", variable=self.var_zero,
                       bg="white", anchor="w", fg=CL_TEXT_DIM).pack(fill=tk.X, padx=(48, 8))
        tk.Frame(fb, bg="white", height=6).pack()

        fs, self.lbl_stat = card(1, "문구 자료", self.var_do_stat)
        for key, text in (("loc", "납품로케이션데이터.txt  (위치,바코드,수량)"),
                          ("det", "납품상세데이터.txt  (날짜,납품처,바코드,수량,구분,단가+종류+위치,페이지,줄,상품명)"),
                          ("loc_x", "납품로케이션데이터.xlsx  (txt와 같은 내용)"),
                          ("det_x", "납품상세데이터.xlsx  (txt와 같은 내용)"),
                          ("stat_list", "결과확인리스트.xlsx  (문구 장부재고 / X·X·X / 스캔재고 / 차이)"),
                          ("stat_scan", "로케이션별스캔리스트.xlsx  (바코드+로케이션별 스캔총수량)")):
            tk.Checkbutton(fs, text=text, variable=self.var_f[key], bg="white", anchor="w").pack(fill=tk.X, padx=(28, 8))
        self.var_zero_stat = tk.BooleanVar(value=True)
        tk.Checkbutton(fs, text="결과확인리스트에 장부재고·스캔이 모두 0인 품목도 포함", variable=self.var_zero_stat,
                       bg="white", anchor="w", fg=CL_TEXT_DIM).pack(fill=tk.X, padx=(48, 8))
        tk.Frame(fs, bg="white", height=6).pack()

        go = tk.Frame(self, bg=CL_BG)
        go.pack(fill=tk.X, padx=12, pady=(0, 6))
        self.btn_go = win_button(go, text="선택한 자료 생성", command=self.generate_selected, kind="accent")
        self.btn_go.pack(side=tk.LEFT)
        win_button(go, text="폴더열기", command=self.open_folder, kind="normal").pack(side=tk.LEFT, padx=6)
        win_button(go, text="미등록상품 자료", command=self.generate_unregistered, kind="normal").pack(side=tk.LEFT, padx=(28, 6))
        win_button(go, text="합산자료(AREA)", command=self.generate_area_sum, kind="normal").pack(side=tk.LEFT)
        self.lbl_go = tk.Label(go, text="", bg=CL_BG, fg=CL_TEXT_DIM)
        self.lbl_go.pack(side=tk.LEFT, padx=12)

        # ---- 실사내역 표 + 구분 필터 ------------------------------------------------------
        lh = tk.Frame(self, bg=CL_BG)
        lh.pack(fill=tk.X, padx=8)
        tk.Label(lh, text="실사내역 (등록상품)", font=("", 10, "bold"), bg=CL_BG).pack(side=tk.LEFT)
        self.bar = ScopeBar(lh, on_change=self.refresh)
        self.bar.pack(side=tk.LEFT, padx=(16, 0))
        win_button(lh, text="새로고침", command=self.refresh, kind="normal").pack(side=tk.LEFT, padx=10)
        win_button(lh, text="출력", command=self.print_view, kind="normal").pack(side=tk.LEFT)
        win_button(lh, text="엑셀저장", command=self.save_excel_dialog, kind="accent").pack(side=tk.LEFT, padx=6)

        columns = ("no", "store_code", "isbn", "book_name", "qty",
                   "area", "section", "shelf_no", "dan", "yeol", "worker", "scan_date", "time")
        headings = ("NO", "점포코드", "바코드", "도서명", "조사수량",
                    "AREA", "SECTION", "서가번호", "단", "열", "작업자", "실사일자", "실사시간")
        widths = (45, 90, 120, 220, 70, 55, 60, 150, 40, 40, 90, 90, 80)
        self.vl = VirtualList(self, columns, headings, widths, height=8, on_loaded=self._on_loaded)
        self.vl.container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))
        self.tree = self.vl.tree
        self._loaded_ctx = None

        status = tk.Frame(self, bg=CL_BG)
        status.pack(fill=tk.X, padx=8, pady=(4, 8))
        self.lbl_total = tk.Label(status, text="(총 0건)", bg=CL_BG, fg=CL_NAVY, font=("", 10, "bold"))
        self.lbl_total.pack(side=tk.LEFT)

    def _update_go_button(self):
        n = int(self.var_do_book.get()) + int(self.var_do_stat.get())
        self.lbl_go.config(text="" if n else "생성할 구분(서적/문구)을 체크하세요.")

    def _row_values(self, no, r):
        """표(Treeview)에 실제로 보여줄 값을 raw row 하나에서 만든다.
        [2026-09-28 버그수정] 예전에는 generation.raw_rows()가 만들어주는
        튜플을 그대로 표에 꽂아 넣었는데(values=(i, *r)), 그 튜플은 이 표의
        컬럼 순서(NO/실사일자/점포코드/바코드/도서명/조사수량/AREA/SECTION/
        서가번호/단/열/작업자/실사일시)가 아니라 엑셀저장용 raw_rows() 자기
        헤더 순서(실사일자/점포코드/AREA/SECTION/서가번호/단/열/바코드/
        상품명/...)로 만들어진 것이라, 실제로는 컬럼과 값이 하나씩 밀려서
        엉뚱한 칸에 엉뚱한 값이 보이고 있었다 - 여기서 표 컬럼 순서에 맞게
        직접 값을 뽑아 맞춘다."""
        scan_date, scan_time = split_scan_datetime(r["received_at"], r["survey_date"])
        return (no, r["store_code"], r["isbn"], r["book_name"], f"{r['qty'] or 0:,}",
                r["area"], r["section"], r["shelf_no"], r["dan"], r["yeol"], r["worker_name"], scan_date, scan_time)

    def refresh(self):
        self.lbl_store_code.config(text=self.app.state.store_code)
        self.lbl_store_name.config(text=self.app.state.store_name)
        self.lbl_date.config(text=self.app.state.survey_date)
        self._update_go_button()

        # 순서(id 목록)만 백그라운드로 읽고, 표에는 보이는 줄만 DB에서 읽어 그린다.
        kind_sel = self.bar.kind()
        ctx = (self.app.state.store_code, self.app.state.survey_date, kind_sel)
        keep = (ctx == self._loaded_ctx)
        self._loaded_ctx = ctx

        # 카드 위쪽 건수 미리보기(서적/문구별 스캔 줄 수·바코드 수·수량)
        try:
            sm = generation.summary(self.app)
            for key, lbl in (("서적", self.lbl_book), ("문구", self.lbl_stat)):
                n, codes, qty = sm[key]
                lbl.config(text=f"스캔 {n:,}줄 · 바코드 {codes:,}종 · 수량 {qty:,}" if n else "스캔 자료 없음")
            if not sm["문구마스터"]:
                self.lbl_stat.config(text=self.lbl_stat.cget("text") + "  (문구 상품마스터 없음)")
            for kind, lbl in (("서적", self.lbl_book), ("문구", self.lbl_stat)):
                if scope.is_defined(kind):
                    lbl.config(text=lbl.cget("text") + f"  [{scope.describe(kind)}]")
        except Exception:
            pass

        def build():
            book_rows, stat_rows, _stat = generation.split_counts(self.app)
            if kind_sel == "서적":
                ids = [r["id"] for r in book_rows]
            elif kind_sel == "문구":
                ids = [r["id"] for r in stat_rows]
            else:
                conn = dbmod.get_conn()
                try:
                    ids = [r[0] for r in conn.execute(
                        "SELECT id FROM stock_counts WHERE store_code=? AND survey_date=? "
                        "ORDER BY CAST(area AS INTEGER), area, CAST(section AS INTEGER), section, CAST(dan AS INTEGER), dan, CAST(yeol AS INTEGER), yeol, shelf_no, id", ctx[:2])]
                finally:
                    conn.close()
            return IdListModel(ids, "stock_counts", self._row_values)
        self.vl.load(build, keep_position=keep)

    def _on_loaded(self, total, loading):
        try:
            self.lbl_total.config(text="(불러오는 중...)" if loading else f"(총 {total:,}건)")
        except tk.TclError:
            pass

    def open_folder(self):
        path = str(generation.output_dir(self.app))
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            messagebox.showinfo("알림", f"폴더를 여는 데 실패했습니다. 경로: {path}\n{e}")

    def save_excel_dialog(self):
        kind = self.bar.kind()
        headers, rows = generation.raw_rows(self.app, kind)
        if not rows:
            messagebox.showinfo("알림", "저장할 데이터가 없습니다.")
            return
        tag = f"_{scope.tag(kind)}" if kind in scope.KINDS else ""
        path = export_rows_to_excel(rows, headers, default_name=f"실사자료{tag}_{file_date(self.app)}.xlsx")
        if path:
            messagebox.showinfo("완료", f"저장되었습니다:\n{path}")

    def print_view(self):
        """[출력] - 지금 구분(전체/서적/문구) 범위의 실사내역을 인쇄 대화상자로 보낸다."""
        from .ui_common import print_rows_to_excel, print_excel_file
        kind = self.bar.kind()
        headers, rows = generation.raw_rows(self.app, kind)
        if not rows:
            messagebox.showinfo("알림", "출력할 데이터가 없습니다.")
            return
        tag = f"_{scope.tag(kind)}" if kind in scope.KINDS else ""
        path = print_rows_to_excel(rows, headers, default_name=f"실사자료{tag}_{file_date(self.app)}.xlsx")
        if path:
            print_excel_file(path)

    def _generate_to_folder(self, headers, rows, filename, label, kind=None):
        if not rows:
            messagebox.showinfo("알림", f"{label}: 생성할 데이터가 없습니다.")
            return
        out_path = generation.output_dir(self.app, kind) / filename
        try:
            write_rows_to_excel_file(rows, headers, out_path)
        except ImportError:
            messagebox.showerror("오류", "엑셀 생성을 위해 openpyxl이 필요합니다.\npip install openpyxl")
            return
        messagebox.showinfo("완료", f"{label} 파일이 생성되었습니다:\n{out_path}")

    def generate_selected(self):
        """체크한 서적/문구 자료를 한 번에 만든다."""
        if not (self.var_do_book.get() or self.var_do_stat.get()):
            messagebox.showinfo("알림", "생성할 구분(서적/문구)을 체크하세요.")
            return
        out_dir = generation.output_dir(self.app)
        book_dir = generation.output_dir(self.app, "서적")
        stat_dir = generation.output_dir(self.app, "문구")
        done, skipped = [], []
        try:
            book_rows, stat_rows, stat = generation.split_counts(self.app)
            if self.var_do_book.get():
                if not book_rows:
                    skipped.append("서적: 서적 실사 자료가 없습니다")
                else:
                    from .ui_common import write_text_lines_file
                    if self.var_f["d1"].get():
                        lines = generation.kyobo_data1_lines(self.app, book_rows)
                        write_text_lines_file(lines, book_dir / "kyobo_data1.txt")
                        done.append(("서적전용/kyobo_data1.txt", len(lines)))
                    if self.var_f["d2"].get():
                        lines = generation.kyobo_data2_lines(self.app, book_rows)
                        write_text_lines_file(lines, book_dir / "kyobo_data2.txt")
                        done.append(("서적전용/kyobo_data2.txt", len(lines)))
                    if self.var_f["list"].get():
                        headers, rows = generation.item_list_rows(self.app, include_zero=self.var_zero.get())
                        write_rows_to_excel_file(rows, headers, book_dir / generation.item_list_filename(self.app, "서적"))
                        done.append(("서적전용/" + generation.item_list_filename(self.app, "서적"), len(rows)))
                    if self.var_f["shelf"].get():
                        headers, rows = generation.shelf_rows(self.app)
                        write_rows_to_excel_file(rows, headers, book_dir / generation.shelf_filename(self.app, "서적"))
                        done.append(("서적전용/" + generation.shelf_filename(self.app, "서적"), len(rows)))
            if self.var_do_stat.get():
                if not stat_rows:
                    skipped.append("문구: 문구 실사 자료가 없습니다")
                else:
                    keys = [k for k in generation.STAT_FILE_KEYS if self.var_f[k].get()]
                    for name, n in generation.generate_stat_files(self.app, stat_dir, only=keys,
                                                                  include_zero=self.var_zero_stat.get()):
                        done.append(("문구전용/" + name, n))
                    if "det" in keys or "det_x" in keys:
                        miss = generation.missing_stat_master(stat_rows, stat)
                        if miss:
                            skipped.append(f"참고: 문구 범위의 바코드 {miss:,}종이 문구 상품마스터에 없어 단가·구분코드·납품처가 비어 있습니다")
        except ImportError:
            messagebox.showerror("오류", "엑셀 생성을 위해 openpyxl이 필요합니다.\npip install openpyxl")
            return
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("오류", f"자료 생성 중 오류: {e}")
            return
        msg = []
        if done:
            msg.append(f"저장 위치: {out_dir}  (서적전용 / 문구전용 폴더)\n")
            msg += [f"  {name}  ({n:,}건)" for name, n in done]
        if skipped:
            msg.append("\n확인할 항목")
            msg += [f"  {t}" for t in skipped]
        if not done and not skipped:
            msg.append("선택된 파일이 없습니다.")
        if done:
            if messagebox.askyesno("생성 완료", "\n".join(msg) + "\n\n폴더를 열까요?"):
                self.open_folder()
        else:
            messagebox.showinfo("알림", "\n".join(msg))

    def generate_unregistered(self):
        kind = self.bar.kind()
        headers, rows = generation.unregistered_rows(self.app)
        if kind in scope.KINDS:
            rows = [r for r in rows if scope.matches(kind, r[0], r[1])]  # r[0]=AREA, r[1]=SECTION
        tag = f"_{scope.tag(kind)}" if kind in scope.KINDS else ""
        self._generate_to_folder(headers, rows, f"미등록상품자료{tag}_{file_date(self.app)}.xlsx", "미등록상품 자료",
                                 kind if kind in scope.KINDS else None)

    def generate_area_sum(self):
        # [2026-10-08] 합계표가 아니라 실사내역 전체(원자료)를 저장한다.
        # 이 파일을 다른 PC의 'AREA별 합산' 화면에서 불러와 합산한다.
        kind = self.bar.kind()
        headers, rows = generation.raw_rows(self.app, kind)
        tag = f"_{scope.tag(kind)}" if kind in scope.KINDS else ""
        self._generate_to_folder(headers, rows, f"합산자료_AREA{tag}_{file_date(self.app)}.xlsx", "AREA 합산자료(실사내역)",
                                 kind if kind in scope.KINDS else None)
