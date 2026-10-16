# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""집계표관리 > AREA별 합산 화면.

[2026-10-08 개편] 다른 PC에서 자료생성 화면의 [합산자료(AREA)] 버튼으로 저장한
파일(실사내역 전체)을 모아 합치는 화면.
 1) AREA 01~99 체크 목록에서 가져올 AREA를 체크
 2) [파일 불러오기] - 합산자료(AREA) 파일을 여러 개 선택 (체크한 AREA 행만 들어옴)
 3) [합산] - AREA별 건수/수량 재계산 (불러오기 직후에도 자동 실행)
 4) 아래 자료①②/단품/서가별/미등록 생성 버튼은 합쳐진 자료 기준
같은 파일을 다시 불러오면 이전에 그 파일로 들어온 행을 지우고 새로 넣는다.
점포코드/실사일자는 PC 기준(상품마스터) 값으로 저장된다."""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from . import db as dbmod
from . import generation
from . import scope
from .scope_ui import ScopeBar
from .ui_common import setup_treeview, file_date, write_rows_to_excel_file, export_rows_to_excel, print_rows_to_excel, print_excel_file, CL_BG, win_button


SRC_LIKE = generation.AREA_SRC_PREFIX + "%"


class AreaSumScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # [2026-10-08] AREA 01~99 체크 목록. 체크한 AREA만 파일 불러오기/합산 대상이 된다.
        box = tk.LabelFrame(self, text=" AREA 선택 (01~99) ", bg=CL_BG, font=("", 10, "bold"))
        box.pack(fill=tk.X, padx=8, pady=(10, 4))
        grid = tk.Frame(box, bg=CL_BG)
        grid.pack(fill=tk.X, padx=6, pady=4)
        self.area_vars = {}
        self.area_checks = {}
        for n in range(1, 100):
            code = f"{n:02d}"
            v = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(grid, text=code, variable=v, bg=CL_BG, anchor="w", width=4)
            cb.grid(row=(n - 1) // 15, column=(n - 1) % 15, sticky="w", padx=1)
            self.area_vars[code] = v
            self.area_checks[code] = cb
        sel = tk.Frame(box, bg=CL_BG)
        sel.pack(fill=tk.X, padx=6, pady=(0, 6))
        win_button(sel, text="전체선택", command=lambda: self._set_all(True), kind="normal").pack(side=tk.LEFT)
        win_button(sel, text="전체해제", command=lambda: self._set_all(False), kind="normal").pack(side=tk.LEFT, padx=6)
        win_button(sel, text="불러온 AREA만 선택", command=self._select_with_data, kind="normal").pack(side=tk.LEFT)
        tk.Label(sel, text="(굵은 파란색 = 엑셀로 불러온 자료가 있는 AREA)", bg=CL_BG, fg="#555").pack(side=tk.LEFT, padx=10)
        self.lbl_sel = tk.Label(sel, text="선택 0개", bg=CL_BG)
        self.lbl_sel.pack(side=tk.RIGHT)

        # [2026-10-13] 서적/문구 구분(AREA·SECTION 범위). 합산 목록·출력·엑셀저장·자료생성에 적용.
        srow = tk.Frame(self, bg=CL_BG)
        srow.pack(fill=tk.X, padx=8, pady=(4, 0))
        self.bar = ScopeBar(srow, on_change=self.refresh)
        self.bar.pack(side=tk.LEFT)
        win_button(srow, text="구분 AREA 선택", command=self._select_scope_areas, kind="normal").pack(side=tk.LEFT, padx=6)
        win_button(srow, text="출력", command=self.print_sum, kind="normal").pack(side=tk.RIGHT, padx=(6, 0))
        win_button(srow, text="엑셀저장", command=self.export_sum, kind="accent").pack(side=tk.RIGHT)

        top = tk.Frame(self, bg=CL_BG)
        top.pack(fill=tk.X, padx=8, pady=(4, 6))
        win_button(top, text="파일 불러오기", command=self.import_files, kind="accent").pack(side=tk.LEFT)
        win_button(top, text="합산", command=self.do_sum, kind="accent").pack(side=tk.LEFT, padx=(8, 0))
        win_button(top, text="선택 AREA 불러온 자료 삭제", command=self.delete_selected_imports, kind="danger").pack(side=tk.LEFT, padx=(8, 0))

        tk.Label(top, text="건수합계 :", bg=CL_BG).pack(side=tk.LEFT, padx=(30, 4))
        self.lbl_count_total = tk.Label(top, text="0", bg="white", width=10, relief="sunken")
        self.lbl_count_total.pack(side=tk.LEFT)
        tk.Label(top, text="수량합계 :", bg=CL_BG).pack(side=tk.LEFT, padx=(16, 4))
        self.lbl_qty_total = tk.Label(top, text="0", bg="white", width=10, relief="sunken")
        self.lbl_qty_total.pack(side=tk.LEFT)

        win_button(top, text="합산자료 전체삭제", command=self.delete_all, kind="danger").pack(side=tk.RIGHT)

        mid = tk.Frame(self, bg=CL_BG)
        mid.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        c1, self.tree_sum = setup_treeview(mid, ("no", "area", "count", "qty"), ("NO", "AREA", "건수", "수량"),
                                           (45, 90, 90, 90), height=10)
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        c2, self.tree_files = setup_treeview(mid, ("no", "area", "file"), ("NO", "AREA", "등록된 파일명"),
                                             (45, 90, 260), height=10)
        c2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        gen_row = tk.Frame(self, bg=CL_BG)
        gen_row.pack(fill=tk.X, padx=8, pady=(4, 10))
        win_button(gen_row, text="서적 자료①,②생성", command=self.generate_1_2, kind="normal").pack(side=tk.LEFT)
        win_button(gen_row, text="서적 ③ 단품 리스트생성", command=self.generate_item_list, kind="normal").pack(side=tk.LEFT, padx=6)
        win_button(gen_row, text="서적 ④ 서가별 생성", command=self.generate_shelf, kind="normal").pack(side=tk.LEFT, padx=6)
        win_button(gen_row, text="문구 자료 생성", command=self.generate_stat, kind="normal").pack(side=tk.LEFT, padx=6)
        win_button(gen_row, text="자료생성(미등록)", command=self.generate_unregistered, kind="normal").pack(side=tk.LEFT, padx=6)

    def _select_scope_areas(self):
        """고른 구분의 AREA 범위에 드는 AREA만 체크한다(구분이 전체면 전체 체크)."""
        kind = self.bar.kind()
        for c, v in self.area_vars.items():
            v.set(scope.matches_area(kind, c))
        self._update_sel_label()

    def _filtered_sum_rows(self):
        kind = self.bar.kind()
        conn = dbmod.get_conn()
        rows = conn.execute(
            "SELECT area, count_total, qty_total FROM area_sum WHERE store_code=? AND survey_date=? ORDER BY area",
            (self.app.state.store_code, self.app.state.survey_date)).fetchall()
        conn.close()
        return [r for r in rows if scope.matches_area(kind, r["area"])]

    def _sum_table(self):
        rows = self._filtered_sum_rows()
        data = [(r["area"], r["count_total"] or 0, r["qty_total"] or 0) for r in rows]
        if data:
            data.append(("TOTAL", sum(d[1] for d in data), sum(d[2] for d in data)))
        return ("AREA", "건수", "수량"), data

    def _ktag(self):
        t = self.bar.tag()
        return f"_{t}" if t else ""

    def export_sum(self):
        headers, data = self._sum_table()
        if not data:
            messagebox.showinfo("알림", "저장할 합산 자료가 없습니다. 먼저 [합산]을 하세요.")
            return
        path = export_rows_to_excel(data, headers, default_name=f"AREA별합산{self._ktag()}_{file_date(self.app)}.xlsx", parent=self)
        if path:
            messagebox.showinfo("완료", f"저장되었습니다:\n{path}")

    def print_sum(self):
        headers, data = self._sum_table()
        if not data:
            messagebox.showinfo("알림", "출력할 합산 자료가 없습니다. 먼저 [합산]을 하세요.")
            return
        path = print_rows_to_excel(data, headers, default_name=f"AREA별합산{self._ktag()}_{file_date(self.app)}.xlsx")
        if path:
            print_excel_file(path)

    def _distinct_areas(self):
        conn = dbmod.get_conn()
        areas = [r["area"] for r in conn.execute(
            "SELECT DISTINCT area FROM stock_counts WHERE store_code=? AND survey_date=? "
            "AND source_file LIKE ? ORDER BY area",
            (self.app.state.store_code, self.app.state.survey_date, SRC_LIKE)
        ) if r["area"]]
        conn.close()
        return areas

    def _checked(self):
        return [c for c, v in self.area_vars.items() if v.get()]

    def _update_sel_label(self):
        self.lbl_sel.config(text=f"선택 {len(self._checked())}개")

    def _set_all(self, on):
        for v in self.area_vars.values():
            v.set(on)
        self._update_sel_label()

    def _select_with_data(self):
        have = set(generation._norm_area_code(a) for a in self._distinct_areas())
        for c, v in self.area_vars.items():
            v.set(c in have)
        self._update_sel_label()

    def refresh(self):
        have = set(generation._norm_area_code(a) for a in self._distinct_areas())
        for c, cb in self.area_checks.items():
            if c in have:
                cb.config(fg="#0050c8", font=("", 9, "bold"))
            else:
                cb.config(fg="black", font=("", 9))
            cb.config(command=self._update_sel_label)
        self._update_sel_label()

        conn = dbmod.get_conn()
        sum_rows = conn.execute(
            "SELECT area, count_total, qty_total FROM area_sum WHERE store_code=? AND survey_date=? ORDER BY area",
            (self.app.state.store_code, self.app.state.survey_date)
        ).fetchall()
        file_rows = conn.execute(
            "SELECT DISTINCT area, source_file FROM stock_counts "
            "WHERE store_code=? AND survey_date=? AND source_file LIKE ? ORDER BY area, source_file",
            (self.app.state.store_code, self.app.state.survey_date, SRC_LIKE)
        ).fetchall()
        conn.close()
        kind = self.bar.kind()
        sum_rows = [r for r in sum_rows if scope.matches_area(kind, r["area"])]
        file_rows = [r for r in file_rows if scope.matches_area(kind, r["area"])]

        self.tree_sum.delete(*self.tree_sum.get_children())
        count_total = qty_total = 0
        for i, r in enumerate(sum_rows, start=1):
            self.tree_sum.insert("", tk.END, values=(i, r["area"], f"{r['count_total'] or 0:,}", f"{r['qty_total'] or 0:,}"),
                                 tags=("odd",) if i % 2 == 0 else ())
            count_total += r["count_total"] or 0
            qty_total += r["qty_total"] or 0
        self.lbl_count_total.config(text=f"{count_total:,}")
        self.lbl_qty_total.config(text=f"{qty_total:,}")

        self.tree_files.delete(*self.tree_files.get_children())
        for i, r in enumerate(file_rows, start=1):
            self.tree_files.insert("", tk.END, values=(i, r["area"], r["source_file"][len(generation.AREA_SRC_PREFIX):]),
                                   tags=("odd",) if i % 2 == 0 else ())

    def import_files(self):
        """체크한 AREA의 자료를 합산자료(AREA) 파일(여러 개 가능)에서 불러온다."""
        areas = self._checked()
        if not areas:
            messagebox.showinfo("알림", "먼저 불러올 AREA를 체크하세요.")
            return
        paths = filedialog.askopenfilenames(
            title="합산자료(AREA) 파일 선택 (여러 개 선택 가능)",
            filetypes=[("Excel 파일", "*.xlsx")])
        if not paths:
            return
        msgs = []
        total_in = 0
        for path in paths:
            try:
                n, skipped, in_file = generation.import_area_file(
                    self.app.state.store_code, self.app.state.store_name,
                    self.app.state.survey_date, path, areas)
            except ImportError:
                messagebox.showerror("오류", "엑셀 읽기를 위해 openpyxl이 필요합니다.\npip install openpyxl")
                return
            except Exception as e:
                msgs.append(f"{os.path.basename(path)} : 실패 - {e}")
                continue
            total_in += n
            msgs.append(f"{os.path.basename(path)} : {n:,}건 불러옴 / 선택 AREA가 아니라 제외 {skipped:,}건"
                        f" (파일 안 AREA: {', '.join(sorted(in_file)) or '-'})")
        self.refresh()
        self.do_sum(quiet=True)
        messagebox.showinfo("불러오기 완료",
                            "\n".join(msgs) + f"\n\n합계 {total_in:,}건을 불러와 합산까지 반영했습니다.\n"
                            "(같은 파일을 다시 불러오면 이전 내용을 지우고 새로 넣습니다)")

    def do_sum(self, quiet=False):
        """[2026-10-08] 엑셀 파일로 불러온 행만 대상으로, 체크한 AREA(없으면 불러온 전체 AREA)의
        건수/수량을 다시 계산한다. PC에 수신된 PDA 자료는 이 화면에서 끌어오지 않는다.
        (자료생성 버튼들은 불러온 자료까지 포함한 stock_counts 전체를 기준으로 한다.)"""
        from datetime import datetime
        areas = self._checked()
        conn = dbmod.get_conn()
        if not areas:
            areas = [r["area"] for r in conn.execute(
                "SELECT DISTINCT area FROM stock_counts WHERE store_code=? AND survey_date=? AND source_file LIKE ?",
                (self.app.state.store_code, self.app.state.survey_date, SRC_LIKE)) if r["area"]]
        if not areas:
            conn.close()
            if not quiet:
                messagebox.showinfo("알림", "합산할 자료가 없습니다.")
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for area in areas:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt, COALESCE(SUM(qty),0) AS qty FROM stock_counts "
                "WHERE store_code=? AND survey_date=? AND area=? AND source_file LIKE ?",
                (self.app.state.store_code, self.app.state.survey_date, area, SRC_LIKE)
            ).fetchone()
            if not row["cnt"]:
                conn.execute("DELETE FROM area_sum WHERE store_code=? AND survey_date=? AND area=?",
                             (self.app.state.store_code, self.app.state.survey_date, area))
                continue
            conn.execute(
                "INSERT INTO area_sum(store_code, survey_date, area, count_total, qty_total, summed_at) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(store_code, survey_date, area) DO UPDATE SET "
                "count_total=excluded.count_total, qty_total=excluded.qty_total, summed_at=excluded.summed_at",
                (self.app.state.store_code, self.app.state.survey_date, area, row["cnt"], row["qty"], now))
        conn.commit()
        conn.close()
        self.refresh()
        if not quiet:
            messagebox.showinfo("합산 완료", f"{len(areas)}개 AREA를 합산했습니다.\n"
                                "이제 아래 자료생성 버튼은 불러온 자료까지 포함해 만들어집니다.")

    def delete_selected_imports(self):
        areas = self._checked()
        if not areas:
            messagebox.showinfo("알림", "삭제할 AREA를 체크하세요.")
            return
        if not messagebox.askyesno("확인", f"체크한 {len(areas)}개 AREA 중 '파일에서 불러온 자료'만 삭제할까요?\n"
                                   "(PC에 수신된 PDA 자료는 지워지지 않습니다)"):
            return
        conn = dbmod.get_conn()
        for a in areas:
            conn.execute("DELETE FROM stock_counts WHERE store_code=? AND survey_date=? AND area=? "
                         "AND source_file LIKE ?",
                         (self.app.state.store_code, self.app.state.survey_date, a, SRC_LIKE))
            conn.execute("DELETE FROM area_sum WHERE store_code=? AND survey_date=? AND area=?",
                         (self.app.state.store_code, self.app.state.survey_date, a))
        conn.commit()
        conn.close()
        dbmod.bump_stock_version()
        self.do_sum(quiet=True)

    def delete_all(self):
        if not messagebox.askyesno("확인", "AREA별 합산 결과를 모두 삭제할까요?\n(원본 실사자료는 지워지지 않습니다)"):
            return
        conn = dbmod.get_conn()
        conn.execute("DELETE FROM area_sum WHERE store_code=? AND survey_date=?",
                     (self.app.state.store_code, self.app.state.survey_date))
        conn.commit()
        conn.close()
        self.refresh()

    def _generate_to_folder(self, headers, rows, filename, label, kind="서적"):
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

    def generate_1_2(self):
        out_dir = generation.output_dir(self.app, "서적")
        results = generation.generate_kyobo_data_1_2(self.app, out_dir)
        summary = "\n".join(f"{name} ({count:,}건)" for name, count in results)
        messagebox.showinfo("완료", f"서적 자료①,② 파일이 생성되었습니다:\n{out_dir}\n\n{summary}")

    def generate_item_list(self):
        headers, rows = generation.item_list_rows(self.app)
        self._generate_to_folder(headers, rows, generation.item_list_filename(self.app, "서적"), "서적 단품 리스트(결과확인리스트)")

    def generate_shelf(self):
        headers, rows = generation.shelf_rows(self.app)
        self._generate_to_folder(headers, rows, generation.shelf_filename(self.app, "서적"), "서적 서가별 자료(서가별스캔데이터)")

    def generate_stat(self):
        out_dir = generation.output_dir(self.app, "문구")
        results = generation.generate_stat_files(self.app, out_dir)
        if not results:
            messagebox.showinfo("알림", "문구 실사 자료가 없습니다. (구분 범위 또는 문구 상품마스터를 확인하세요)")
            return
        summary = "\n".join(f"{name} ({count:,}건)" for name, count in results)
        messagebox.showinfo("완료", f"문구 자료가 생성되었습니다(납품 txt, 로케이션별스캔데이터, 결과확인리스트):\n{out_dir}\n\n{summary}")

    def generate_unregistered(self):
        kind = self.bar.kind()
        headers, rows = generation.unregistered_rows(self.app)
        if kind in scope.KINDS:
            rows = [r for r in rows if scope.matches(kind, r[0], r[1])]  # r[0]=AREA, r[1]=SECTION
        self._generate_to_folder(headers, rows, f"미등록상품자료{self._ktag()}_{file_date(self.app)}.xlsx", "미등록상품 자료",
                                 kind if kind in scope.KINDS else "서적")
