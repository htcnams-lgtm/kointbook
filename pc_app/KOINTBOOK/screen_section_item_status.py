# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""집계표관리 > 섹션별 아이템 재고현황 화면.

전체 / AREA / SECTION / 서가번호 / 바코드 중 하나를 골라 옆 입력칸에 값을
넣으면 그 범위만 걸러서, LOCATION(AREA-SECTION-서가번호-단-열)별로 어떤
바코드가 몇 권씩 있는지 낱개(품목) 단위로 보여준다.

[2026-09-23 정정] ZZOINT/실적관리 화면과 조회 항목 구성을 맞췄다: ALL을
빼고 전체를 넣었고, AREA를 추가했고, SECTION 다음에 서가번호를 추가했고,
DAN은 빼고 바코드를 추가했다(최종 순서: 전체/AREA/SECTION/서가번호/바코드).
"AREA 합산전/후"는 조회 버튼 왼쪽으로 옮겼고, "전체 조회"라는 조건 문구는
없앴다(전체를 고르면 조건 표시 자체가 비어 있음). [발행]/[엑셀저장]도
아래 별도 줄이 아니라 조회 줄과 같은 줄, 오른쪽에 간격을 두고 배치했다.
[발행]은 다른 화면들과 똑같이 실제로 기본 프린터에 인쇄한다.

[2026-09-28] "AREA, SECTION 조회하는 화면에는 다 AREA+SECTION 합쳐서
조회하는 기능을 추가해줘" - 실적관리와 똑같이 AREA/SECTION 두 조건을
동시에 걸 수 있는 "AREA+SECTION" 항목을 SECTION 바로 옆에 추가했다.
이 항목을 고르면 입력칸 하나(e_value) 대신 AREA/SECTION 칸이 각각
따로 뜬다."""

import tkinter as tk
from tkinter import messagebox
from . import db as dbmod
from .virtual_table import VirtualList, ListModel
from .ui_common import setup_treeview, export_rows_to_excel, print_rows_to_excel, print_excel_file, today_str, \
    normalize_area, digit_code_variants, CL_BG, CL_NAVY, CL_TEXT_DIM, win_button

# [2026-09-28] "실적관리 목록등 프로그램 전체 목록이 렉 없이 화면전환/
# 스크롤되도록" - 이 화면은 조회 모드 기본값이 "전체"라 화면에 들어오자마자
# store_code/survey_date의 stock_counts 전체(스캔한 낱개 전부)를 표에 한
# 번에 그려 넣고 있었다(실적관리가 PAGE_ROWS로 고치기 전과 같은 문제).
# 스캔 건수가 많은 매장은 화면 진입 자체가 몇 초씩 멈춘 것처럼 보이고
# 스크롤도 버벅였다 - 실적관리/재고조사 차이명세와 같은 방식(표에는 항상
# PAGE_ROWS건만 그리고, 나머지는 메모리에 들고 있다가 페이지 버튼으로
# 넘김)으로 고친다.
PAGE_ROWS = 300


class SectionItemStatusScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._rows = []          # 조회된 전체(페이지 제한 없이) - 엑셀저장/발행/페이지 넘김에 사용
        self._view_page = 0
        self._view_total_pages = 1
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = tk.Frame(self, bg=CL_BG)
        top.pack(fill=tk.X, padx=8, pady=(10, 2))
        # [2026-10-01] "버튼이 많아 화면을 넘어가 안 보임" - 두 줄로 나눈다: 위 줄(top) = 조회 조건과 [조회],
        # 아래 줄(actions) = 조회 조건 표시 ... [발행] [엑셀저장].
        actions = tk.Frame(self, bg=CL_BG)
        actions.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Label(top, text="조회", bg=CL_BG, font=("", 10, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        self.mode = tk.StringVar(value="전체")
        for label in ("전체", "AREA", "SECTION", "AREA+SECTION", "서가번호", "바코드"):
            tk.Radiobutton(top, text=label, variable=self.mode, value=label, bg=CL_BG,
                           command=self._on_mode_changed).pack(side=tk.LEFT)

        # [2026-09-28] 조회 모드에 따라 이 자리에 "입력칸 하나"(e_value) 또는
        # "AREA/SECTION 칸 두 개"(e_area_kw/e_section_kw)가 번갈아 보이도록,
        # 둘 다 고정된 자리(search_value_frame) 안에 만들어두고 모드가 바뀔
        # 때만 그 안에서 pack/pack_forget으로 바꿔 끼운다(실적관리와 동일).
        self.search_value_frame = tk.Frame(top, bg=CL_BG)
        self.search_value_frame.pack(side=tk.LEFT, padx=8)

        self.e_value = tk.Entry(self.search_value_frame, width=14)
        self.e_value.bind("<Return>", lambda ev: self.refresh())

        self.search_area_section_frame = tk.Frame(self.search_value_frame, bg=CL_BG)
        tk.Label(self.search_area_section_frame, text="AREA", bg=CL_BG).pack(side=tk.LEFT)
        self.e_area_kw = tk.Entry(self.search_area_section_frame, width=6)
        self.e_area_kw.bind("<Return>", lambda ev: self.refresh())
        self.e_area_kw.pack(side=tk.LEFT, padx=(2, 10))
        tk.Label(self.search_area_section_frame, text="SECTION", bg=CL_BG).pack(side=tk.LEFT)
        self.e_section_kw = tk.Entry(self.search_area_section_frame, width=6)
        self.e_section_kw.bind("<Return>", lambda ev: self.refresh())
        self.e_section_kw.pack(side=tk.LEFT, padx=(2, 0))

        self._on_mode_changed(do_refresh=False)

        # [2026-09-23 정정] "AREA 합산전/후"를 오른쪽 끝에서 [조회] 버튼
        # 왼쪽으로 옮겼다.
        self.merge_mode = tk.StringVar(value="합산전")
        tk.Radiobutton(top, text="AREA 합산전", variable=self.merge_mode, value="합산전", bg=CL_BG,
                       command=self.refresh).pack(side=tk.LEFT, padx=(20, 0))
        tk.Radiobutton(top, text="AREA 합산후", variable=self.merge_mode, value="합산후", bg=CL_BG,
                       command=self.refresh).pack(side=tk.LEFT)

        win_button(top, text="조회", command=self.refresh, kind="normal").pack(side=tk.LEFT, padx=(12, 0))

        # [2026-09-23 정정] 예전엔 아래 별도 줄에 있던 [발행]/[엑셀저장]을
        # 조회 줄과 같은 줄, 오른쪽에 간격을 두고 배치했다(조회 버튼과도,
        # 발행/엑셀저장 사이도 간격을 뒀다).
        win_button(actions, text="엑셀저장", command=self.export_excel, kind="accent").pack(side=tk.RIGHT, padx=4)
        win_button(actions, text="발행", command=self.print_report, kind="normal").pack(side=tk.RIGHT, padx=(24, 4))

        # [2026-09-24 정정] 조건 표시 라벨에 주황색 음영(bg="#F4A93B")이 있었는데,
        # 사용자가 이 음영을 없애 달라고 해서 다른 화면들처럼 배경 없는 일반
        # 텍스트로 바꿨다(배경은 화면 배경색 그대로, 글자색은 남색).
        self.lbl_condition = tk.Label(actions, text="", bg=CL_BG, fg=CL_NAVY, font=("", 10, "bold"), width=24)
        self.lbl_condition.pack(side=tk.LEFT, padx=(0, 20))

        columns = ("no", "location", "isbn", "book_name", "qty")
        headings = ("No", "LOCATION", "바코드", "도서명", "재고수량")
        widths = (45, 200, 130, 280, 90)
        # 가상 스크롤 표(virtual_table.py): 화면에 보이는 줄만 두고 스크롤할 때 글자만 바꾼다.
        # 예전의 페이지 버튼(처음/이전/다음/끝)은 없고, 스크롤 하나로 끝까지 볼 수 있다.
        self.vl = VirtualList(self, columns, headings, widths, height=20)
        self.vl.container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))
        self.tree = self.vl.tree

        status = tk.Frame(self, bg=CL_BG)
        status.pack(fill=tk.X, padx=8, pady=(4, 8))
        self.lbl_total = tk.Label(status, text="(총 0건)", bg=CL_BG, fg=CL_NAVY, font=("", 10, "bold"))
        self.lbl_total.pack(side=tk.LEFT)

    def _on_mode_changed(self, do_refresh=True):
        """[2026-09-28] 조회 항목(라디오)이 바뀔 때, search_value_frame 안에서
        "일반 입력칸 하나(e_value)" 또는 "AREA+SECTION 두 칸
        (search_area_section_frame)" 중 지금 모드에 맞는 쪽만 보이게
        바꿔 끼운다(실적관리와 동일)."""
        mode = self.mode.get()
        if mode == "AREA+SECTION":
            self.e_value.pack_forget()
            self.search_area_section_frame.pack(side=tk.LEFT)
        else:
            self.search_area_section_frame.pack_forget()
            self.e_value.pack(side=tk.LEFT)
        if do_refresh:
            self.refresh()

    def refresh(self):
        mode = self.mode.get()
        value = self.e_value.get().strip()
        area_kw = self.e_area_kw.get().strip()
        section_kw = self.e_section_kw.get().strip()
        merged = self.merge_mode.get() == "합산후"
        # [2026-09-23 정정] "전체 조회"라는 문구를 없앴다 - 전체를 고르면
        # 조건 표시 자체를 비워둔다.
        if mode == "AREA+SECTION":
            cond_text = f"AREA '{area_kw}' + SECTION '{section_kw}'" if (area_kw or section_kw) else "AREA+SECTION"
        else:
            cond_text = f"{mode}{(' = ' + value) if value else ''}" if mode != "전체" else ""
        self.lbl_condition.config(text=cond_text)

        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        conn = dbmod.get_conn()
        sql = "SELECT area, section, shelf_no, dan, yeol, isbn, book_name, qty FROM stock_counts WHERE store_code=? AND survey_date=?"
        params = [store_code, date]
        # [2026-09-28 버그수정] "AREA를 01로하면 조회가 안되고 1로 하면
        # 조회가되네" - AREA/SECTION을 "=?"로만 비교하면 0채움 형태("01")와
        # 옛 데이터의 미채움 형태("1")가 서로 달라 못 찾는 경우가 있어,
        # 0채움 후보를 모두 IN절에 넣어 찾는다.
        if mode == "AREA+SECTION":
            # [2026-09-28] "AREA, SECTION 조회하는 화면에는 다 AREA+SECTION
            # 합쳐서 조회하는 기능을 추가해줘" - 실적관리와 같은 방식으로
            # 두 조건을 AND로 같이 건다. 둘 다 비어 있으면 그냥 전체를
            # 보여준다(하나만 입력해도 그 조건만 걸린다).
            if area_kw:
                variants = digit_code_variants(area_kw, 2)
                sql += f" AND area IN ({','.join('?' for _ in variants)})"
                params.extend(variants)
            if section_kw:
                variants = digit_code_variants(section_kw, 3)
                sql += f" AND section IN ({','.join('?' for _ in variants)})"
                params.extend(variants)
        elif mode == "AREA" and value:
            variants = digit_code_variants(value, 2)
            sql += f" AND area IN ({','.join('?' for _ in variants)})"
            params.extend(variants)
        elif mode == "SECTION" and value:
            variants = digit_code_variants(value, 3)
            sql += f" AND section IN ({','.join('?' for _ in variants)})"
            params.extend(variants)
        elif mode == "서가번호" and value:
            sql += " AND shelf_no=?"
            params.append(value)
        elif mode == "바코드" and value:
            sql += " AND isbn LIKE ?"
            params.append(f"%{value}%")
        sql += " ORDER BY CAST(area AS INTEGER), area, CAST(section AS INTEGER), section, CAST(dan AS INTEGER), dan, CAST(yeol AS INTEGER), yeol, shelf_no"
        rows = conn.execute(sql, params).fetchall()
        conn.close()

        self._rows = []
        for r in rows:
            area = normalize_area(r["area"], merged=merged)
            location = f"{area}-{r['section']}-{r['shelf_no']}-{r['dan']}-{r['yeol']}"
            self._rows.append((location, r["isbn"], r["book_name"], f"{r['qty'] or 0:,}"))

        self._view_total_pages = max(1, (len(self._rows) + PAGE_ROWS - 1) // PAGE_ROWS)
        self._load_page(0)

    def _load_page(self, page=0):
        """조회된 줄(self._rows) 전체를 가상 스크롤 표에 보여준다(이름은 예전 그대로)."""
        self.vl.set_model(ListModel(self._rows))
        self.lbl_total.config(text=f"(총 {len(self._rows):,}건)")

    def export_excel(self):
        if not getattr(self, "_rows", None):
            messagebox.showinfo("알림", "저장할 데이터가 없습니다.")
            return
        headers = ("LOCATION", "바코드", "도서명", "재고수량")
        path = export_rows_to_excel(self._rows, headers, default_name=f"섹션별아이템재고현황_{today_str()}.xlsx", parent=self)
        if path:
            messagebox.showinfo("완료", f"저장되었습니다:\n{path}")

    def print_report(self):
        """[발행] 버튼: [2026-09-23] 재고조사 차이명세 등 다른 화면의
        [발행]과 똑같이 실제로 기본 프린터에 인쇄까지 한다. [2026-09-28
        재수정] "발행버튼을 누르면 왜 엑셀저장이 뜨냐" - 저장 위치를 묻는
        export_rows_to_excel() 대신 조용히 임시 파일을 만드는
        print_rows_to_excel()을 쓴다. [2026-09-28 재수정 2차] "인쇄전
        설정창같은게 하나 뜨잖아? 그렇게 해줘" - 저장 위치 대화상자는 계속
        안 띄우되, 프린터/매수를 고를 수 있는 진짜 인쇄 대화상자는 뜨도록
        print_excel_file()로 바꿨다."""
        if not getattr(self, "_rows", None):
            messagebox.showinfo("알림", "인쇄할 데이터가 없습니다.")
            return
        headers = ("LOCATION", "바코드", "도서명", "재고수량")
        path = print_rows_to_excel(self._rows, headers, default_name=f"섹션별아이템재고현황_{today_str()}.xlsx")
        if not path:
            return
        print_excel_file(path)
