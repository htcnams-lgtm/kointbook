# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""매대등록 > Section Check 화면.

이 매장에서 실제로 조사해야 할 SECTION 범위를 AREA별로 "From~To"로 미리
등록해두고(조사 Section), 실사자료가 들어올 때마다 그 범위를 기준으로

  조사완료 Section : 등록된 범위 안에서 실제로 스캔 데이터가 들어온 SECTION
  중복 Section     : 같은 SECTION을 2명 이상의 작업자가 각각 스캔한 경우
                     (매대를 나눠 맡았는데 겹쳐서 두 번 조사된 것으로 추정)
  결번 Section     : 등록된 범위 안인데 아직 스캔 데이터가 하나도 없는 SECTION

세 가지를 자동으로 구분해서 보여준다.

[2026-09-23 실제 화면 재확인] AREA/SECTION은 등록(조사 Section) 다이얼로그
에서는 계속 따로 입력받지만(현장 확인), 표에 보여줄 때는 AREA(2자리)+
SECTION(3자리)을 이어붙인 "A_SECTION" 코드 하나로 합쳐서 보여준다(예:
AREA "1" + SECTION "101" -> "01101") - `ui_common.area_section_code`.
그래서 "조사 Section" 표에는 AREA 컬럼이 따로 없고 From/To 두 컬럼만
있다(각 컬럼 값 자체가 이미 AREA를 포함한 A_SECTION 코드).

"조사완료 Section"의 "발" 컬럼은 그 A_SECTION을 "집계표관리 > 섹션별
아이템 재고현황"과 같은 형식(No/LOCATION/바코드/도서명/재고수량)으로 한 번
발행(인쇄/저장)했는지 표시하는 체크 표시다(`section_printed` 테이블) -
발행 여부와 무관하게 데이터 자체는 그대로 남아 있고, 다시 발행하면
체크만 갱신된다."""

import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from . import db as dbmod
from .ui_common import center_on_app, setup_treeview, export_rows_to_excel, print_rows_to_excel, print_excel_file, file_date, \
    normalize_area, digit_code_variants, area_section_code, CL_BG, CL_NAVY, win_button



def _code(area, section):
    """화면 표시용 코드: AREA-SECTION (예: 10-100)."""
    return area_section_code(area, section, sep="-")

class SectionCheckScreen(tk.Frame):
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

        panels = tk.Frame(self, bg=CL_BG)
        panels.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        for i in range(4):
            panels.grid_columnconfigure(i, weight=1, uniform="col")
        panels.grid_rowconfigure(0, weight=1)

        # ---- 1. 조사 Section (등록/수정/삭제) ----
        p1 = tk.Frame(panels, bg=CL_BG, highlightbackground="#C4C8D0", highlightthickness=1)
        p1.grid(row=0, column=0, sticky="nsew", padx=4)
        tk.Label(p1, text="조사 Section", bg=CL_BG, fg=CL_NAVY, font=("", 11, "bold")).pack(pady=(8, 2))
        btns1 = tk.Frame(p1, bg=CL_BG)
        btns1.pack(pady=(0, 6))
        win_button(btns1, text="등록", width=6, command=self.register_range, kind="normal").pack(side=tk.LEFT, padx=2)
        win_button(btns1, text="수정", width=6, command=self.edit_range, kind="normal").pack(side=tk.LEFT, padx=2)
        win_button(btns1, text="삭제", width=6, command=self.delete_range, kind="danger").pack(side=tk.LEFT, padx=2)
        c1, self.tree_plan = setup_treeview(p1, ("from", "to"), ("From", "To"), (85, 85), height=18)
        c1.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))

        # ---- 2. 조사완료 Section ----
        p2 = tk.Frame(panels, bg=CL_BG, highlightbackground="#C4C8D0", highlightthickness=1)
        p2.grid(row=0, column=1, sticky="nsew", padx=4)
        tk.Label(p2, text="조사완료 Section", bg=CL_BG, fg=CL_NAVY, font=("", 11, "bold")).pack(pady=(8, 2))
        btn_done = win_button(p2, text="발행", width=8, command=self.print_done_sections, kind="normal")
        btn_done.pack(pady=(0, 6))
        c2, self.tree_done = setup_treeview(p2, ("done", "section", "worker"), ("발", "A_SECTION", "작업자"),
                                            (30, 90, 110), height=18)
        c2.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))

        # ---- 3. 중복 Section ----
        p3 = tk.Frame(panels, bg=CL_BG, highlightbackground="#C4C8D0", highlightthickness=1)
        p3.grid(row=0, column=2, sticky="nsew", padx=4)
        tk.Label(p3, text="중복 Section", bg=CL_BG, fg="#8A2E3B", font=("", 11, "bold")).pack(pady=(8, 2))
        win_button(p3, text="중복 인지(해제)", command=self.ack_selected_dup, kind="normal").pack(pady=(0, 6))
        c3, self.tree_dup = setup_treeview(p3, ("section", "worker"), ("A_SECTION", "작업자"), (100, 160), height=18)
        c3.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))

        # ---- 4. 결번 Section ----
        p4 = tk.Frame(panels, bg=CL_BG, highlightbackground="#C4C8D0", highlightthickness=1)
        p4.grid(row=0, column=3, sticky="nsew", padx=4)
        tk.Label(p4, text="결번 Section", bg=CL_BG, fg=CL_NAVY, font=("", 11, "bold")).pack(pady=(8, 2))
        # [2026-09-28] 이 패널만 제목 아래에 버튼이 없어서, 옆 패널들과 표
        # 시작 위치를 맞추려고 예전에는 높이를 30px로 대충 고정해 흉내만
        # 냈다. 그런데 실제 버튼 높이(글꼴/여백에 따라 달라짐)와 정확히
        # 안 맞아서 이 칸만 표가 살짝 위로 붙어 보이는 문제가 있었다 - 옆
        # "조사완료 Section" 패널의 실제 [발행] 버튼 높이를 그대로 재서,
        # 똑같은 여백(pady)까지 맞춘 빈 칸으로 바꿨다.
        self.update_idletasks()
        spacer_height = max(btn_done.winfo_reqheight(), 1)
        tk.Frame(p4, bg=CL_BG, height=spacer_height).pack(pady=(0, 6))
        c4, self.tree_missing = setup_treeview(p4, ("section",), ("A_SECTION",), (140,), height=18)
        c4.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))

    # ---- 조사 Section 등록/수정/삭제 ----
    def _selected_plan_id(self):
        sel = self.tree_plan.selection()
        if not sel:
            return None
        return self.tree_plan.item(sel[0], "tags")

    def register_range(self):
        self._open_range_dialog(mode="new")

    def edit_range(self):
        sel = self.tree_plan.selection()
        if not sel:
            messagebox.showinfo("알림", "수정할 범위를 선택하세요.")
            return
        idx = self.tree_plan.index(sel[0])
        row = self._plan_rows[idx]
        self._open_range_dialog(mode="edit", row=row)

    def _open_range_dialog(self, mode, row=None):
        win = tk.Toplevel(self)
        center_on_app(win)
        win.title("조사 Section 등록")
        win.geometry("300x220")
        win.bind("<Escape>", lambda e: win.destroy())
        tk.Label(win, text="AREA").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        e_area = tk.Entry(win, width=16)
        e_area.grid(row=0, column=1, padx=10, pady=10)
        tk.Label(win, text="From (SECTION)").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        e_from = tk.Entry(win, width=16)
        e_from.grid(row=1, column=1, padx=10, pady=10)
        tk.Label(win, text="To (SECTION)").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        e_to = tk.Entry(win, width=16)
        e_to.grid(row=2, column=1, padx=10, pady=10)

        if row is not None:
            e_area.insert(0, row["area"])
            e_from.insert(0, row["section_from"])
            e_to.insert(0, row["section_to"])

        def save():
            area = e_area.get().strip()
            f = e_from.get().strip()
            t = e_to.get().strip()
            if not area or not f or not t:
                messagebox.showwarning("알림", "AREA/From/To를 모두 입력하세요.")
                return
            conn = dbmod.get_conn()
            if mode == "edit" and row is not None:
                conn.execute(
                    "UPDATE planned_sections SET area=?, section_from=?, section_to=? WHERE id=?",
                    (area, f, t, row["id"])
                )
            else:
                conn.execute(
                    "INSERT INTO planned_sections(store_code, survey_date, area, section_from, section_to, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (self.app.state.store_code, self.app.state.survey_date, area, f, t,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
            conn.commit()
            conn.close()
            win.destroy()
            self.refresh()

        btns = tk.Frame(win)
        btns.grid(row=3, column=0, columnspan=2, pady=14)
        win_button(btns, text="등록" if mode == "new" else "수정", width=10, command=save, kind="normal").pack(side=tk.LEFT, padx=6)
        win_button(btns, text="취소", width=10, command=win.destroy, kind="normal").pack(side=tk.LEFT)

    def delete_range(self):
        sel = self.tree_plan.selection()
        if not sel:
            messagebox.showinfo("알림", "삭제할 범위를 선택하세요.")
            return
        idx = self.tree_plan.index(sel[0])
        row = self._plan_rows[idx]
        from_code = _code(row["area"], row["section_from"])
        to_code = _code(row["area"], row["section_to"])
        if not messagebox.askyesno("확인", f"{from_code}~{to_code} 범위를 삭제할까요?"):
            return
        conn = dbmod.get_conn()
        conn.execute("DELETE FROM planned_sections WHERE id=?", (row["id"],))
        conn.commit()
        conn.close()
        self.refresh()

    # ---- 중복 인지 ----
    def ack_selected_dup(self):
        sel = self.tree_dup.selection()
        if not sel:
            messagebox.showinfo("알림", "인지 처리할 SECTION을 선택하세요.")
            return
        idx = self.tree_dup.index(sel[0])
        area, section = self._dup_rows[idx]
        conn = dbmod.get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO dup_ack(store_code, survey_date, area, section, acked_at) VALUES (?,?,?,?,?)",
            (self.app.state.store_code, self.app.state.survey_date, area, section,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        self.refresh()

    def print_done_sections(self):
        """조사완료 Section에서 선택한(없으면 전체) A_SECTION을 "섹션별 아이템
        재고현황"과 같은 형식(No/LOCATION/바코드/도서명/재고수량)으로 발행하고,
        발행한 A_SECTION은 "발" 컬럼에 체크가 남도록 section_printed에 기록한다."""
        sel = self.tree_done.selection()
        if sel:
            keys = [self._done_rows[self.tree_done.index(s)] for s in sel]
        else:
            keys = list(self._done_rows)
        if not keys:
            messagebox.showinfo("알림", "발행할 조사완료 Section이 없습니다.")
            return

        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        conn = dbmod.get_conn()
        raw_rows = []
        for area, section in keys:
            # [2026-09-28 버그수정] area/section을 "=?"로만 비교하면
            # 0채움 형태("01")와 옛 데이터의 미채움 형태("1")가 서로 달라
            # 못 찾는 경우가 있어(실적관리 조회와 같은 문제), 0채움 후보를
            # 모두 넣어 찾는다.
            area_variants = digit_code_variants(area, 2)
            section_variants = digit_code_variants(section, 3)
            area_ph = ",".join("?" for _ in area_variants)
            section_ph = ",".join("?" for _ in section_variants)
            raw_rows.extend(conn.execute(
                f"SELECT area, section, shelf_no, dan, yeol, isbn, book_name, qty FROM stock_counts "
                f"WHERE store_code=? AND survey_date=? AND area IN ({area_ph}) AND section IN ({section_ph}) "
                "ORDER BY CAST(dan AS INTEGER), dan, CAST(yeol AS INTEGER), yeol, shelf_no",
                (store_code, date, *area_variants, *section_variants)
            ).fetchall())
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for area, section in keys:
            conn.execute(
                "INSERT INTO section_printed(store_code, survey_date, area, section, printed_at) "
                "VALUES (?,?,?,?,?) ON CONFLICT(store_code, survey_date, area, section) "
                "DO UPDATE SET printed_at=excluded.printed_at",
                (store_code, date, area, section, now)
            )
        conn.commit()
        conn.close()

        if not raw_rows:
            messagebox.showinfo("알림", "선택한 Section에 실사 데이터가 없어 발행 표시만 남겼습니다.")
            self.refresh()
            return

        data = []
        for i, r in enumerate(raw_rows, start=1):
            location = f"{normalize_area(r['area'])}-{r['section']}-{r['shelf_no']}-{r['dan']}-{r['yeol']}"
            data.append((i, location, r["isbn"], r["book_name"], r["qty"]))
        headers = ("No", "LOCATION", "바코드", "도서명", "재고수량")
        # [2026-09-28] "발행버튼을 누르면 왜 엑셀저장이 뜨냐" - 저장 위치를
        # 묻지 않는 print_rows_to_excel()로 바꿨다. [2026-09-28 재수정]
        # "인쇄전 설정창같은게 하나 뜨잖아? 그렇게 해줘" - 저장 위치
        # 대화상자는 계속 안 띄우되, 프린터/매수를 고를 수 있는 진짜 인쇄
        # 대화상자는 뜨도록 print_excel_file()로 바꿨다.
        path = print_rows_to_excel(data, headers, default_name=f"섹션별아이템재고현황_{file_date(self.app)}.xlsx")
        if path:
            print_excel_file(path)
        self.refresh()

    # ---- 새로고침(전체 재계산) ----
    def refresh(self):
        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        self.lbl_store.config(text=store_code)
        self.lbl_date.config(text=date)

        conn = dbmod.get_conn()
        self._plan_rows = conn.execute(
            "SELECT * FROM planned_sections WHERE store_code=? AND survey_date=? ORDER BY area, section_from",
            (store_code, date)
        ).fetchall()

        self.tree_plan.delete(*self.tree_plan.get_children())
        for i, r in enumerate(self._plan_rows):
            from_code = _code(r["area"], r["section_from"])
            to_code = _code(r["area"], r["section_to"])
            self.tree_plan.insert("", tk.END, values=(from_code, to_code),
                                  tags=("odd",) if i % 2 == 1 else ())

        counted = conn.execute(
            "SELECT area, section, GROUP_CONCAT(DISTINCT worker_name) AS workers, "
            "COUNT(DISTINCT worker_code) AS worker_cnt "
            "FROM stock_counts WHERE store_code=? AND survey_date=? GROUP BY area, section",
            (store_code, date)
        ).fetchall()
        acked = {
            (r["area"], r["section"]) for r in conn.execute(
                "SELECT area, section FROM dup_ack WHERE store_code=? AND survey_date=?", (store_code, date)
            )
        }
        printed = {
            (r["area"], r["section"]) for r in conn.execute(
                "SELECT area, section FROM section_printed WHERE store_code=? AND survey_date=?", (store_code, date)
            )
        }
        conn.close()

        counted_map = {(r["area"], r["section"]): r for r in counted}

        # 조사완료 Section: 스캔 데이터가 있는 모든 (area, section)
        self.tree_done.delete(*self.tree_done.get_children())
        self._done_rows = sorted(counted_map.keys())
        for i, r in enumerate(self._done_rows):
            info = counted_map[r]
            mark = "✔" if r in printed else ""
            self.tree_done.insert("", tk.END, values=(mark, _code(r[0], r[1]), info["workers"] or ""),
                                  tags=("odd",) if i % 2 == 1 else ())

        # 중복 Section: 작업자가 2명 이상이면서 아직 "인지" 처리 안 한 것
        self.tree_dup.delete(*self.tree_dup.get_children())
        self._dup_rows = []
        i = 0
        for r, info in sorted(counted_map.items()):
            if info["worker_cnt"] and info["worker_cnt"] > 1 and r not in acked:
                self.tree_dup.insert("", tk.END, values=(_code(r[0], r[1]), info["workers"] or ""),
                                     tags=("odd",) if i % 2 == 1 else ())
                self._dup_rows.append(r)
                i += 1

        # 결번 Section: 등록된 범위 안인데 스캔 데이터가 없는 SECTION
        self.tree_missing.delete(*self.tree_missing.get_children())
        i = 0
        for plan in self._plan_rows:
            try:
                lo, hi = int(plan["section_from"]), int(plan["section_to"])
            except (TypeError, ValueError):
                continue
            for sec in range(lo, hi + 1):
                key = (plan["area"], str(sec))
                if key not in counted_map:
                    self.tree_missing.insert("", tk.END, values=(_code(plan["area"], sec),),
                                             tags=("odd",) if i % 2 == 1 else ())
                    i += 1
