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
따로 뜬다.

[2026-10-16] "섹션별 아이템 재고현황 목록을 실적관리와 비슷하게 에리어 섹션
서가번호 단 열 바코드 도서명 작업자 실사시간 수량 비고 항목이 나오게" -
표 열을 AREA/SECTION/서가번호/단/열/바코드/도서명/작업자/실사시간/수량/비고로
바꿨다(비고는 인쇄물에 손으로 적는 빈 칸). "단끝에 단소계 섹션 끝에
섹션소계 최종 하단에 합계" - 서가번호 안의 단이 끝날 때마다 단소계, AREA+SECTION이
끝날 때마다 섹션소계, 맨 아래에 합계 줄을 넣는다(소계/합계 줄은 NO를 붙이지 않고
총 건수·총 수량에도 넣지 않는다). 소계가 묶이려면 같은 단의 줄이 이어져 있어야 하므로
정렬을 AREA > SECTION > 서가번호 > 단 > 열 순으로 바꿨다(화면 열 순서와 같다).
엑셀저장/발행은 재고조사 차이내역과 같은 양식(상단 기업명·점포·검수자·조사일자·
출력일자 정보 블록 + 페이지 머리글/바닥글)으로 만들고, 제목은 "섹션별 아이템
재고현황", 정보 블록 가운데 칸(차이수량 조건 자리)에는 조회한 범위(AREA/SECTION/
서가번호)를 적는다. [발행]/[엑셀저장]은 [조회] 버튼 바로 옆으로 옮겼다.

[2026-10-16] "AREA 10에 SECTION 001~002 범위를 지정" - AREA+SECTION 조회의 SECTION 칸을 시작~끝 두 칸으로
나눴다(`SECTION [001] ~ [002]`). 끝 칸을 비우면 예전처럼 SECTION 하나만, 시작이 끝보다 크면 자동으로 바꿔서
조회하고, 범위는 숫자 크기로 비교한다(01과 1이 같은 SECTION). 조회 조건 표시와 엑셀 정보 블록에는
`SECTION : 001~002`로 적는다. 섹션소계는 섹션마다, 합계는 범위 전체의 합이다."""

import os
import tempfile
import tkinter as tk
from datetime import datetime as _dt
from tkinter import filedialog, messagebox
from . import db as dbmod
from .progress_core import Cancelled
from .progress_dialog import run_with_progress
from .screen_diff_detail import _write_diff_detail_workbook, _delete_partial_file, PROGRESS_ROW_THRESHOLD
from .virtual_table import VirtualList, ListModel
from .ui_common import setup_treeview, print_rows_to_excel, print_excel_file, file_date, friendly_save_error, \
    split_scan_datetime, normalize_area, digit_code_variants, CL_BG, CL_NAVY, CL_TEXT_DIM, win_button

# [2026-09-28] "실적관리 목록등 프로그램 전체 목록이 렉 없이 화면전환/
# 스크롤되도록" - 이 화면은 조회 모드 기본값이 "전체"라 화면에 들어오자마자
# store_code/survey_date의 stock_counts 전체(스캔한 낱개 전부)를 표에 한
# 번에 그려 넣고 있었다(실적관리가 PAGE_ROWS로 고치기 전과 같은 문제).
# 스캔 건수가 많은 매장은 화면 진입 자체가 몇 초씩 멈춘 것처럼 보이고
# 스크롤도 버벅였다 - 실적관리/재고조사 차이명세와 같은 방식(표에는 항상
# PAGE_ROWS건만 그리고, 나머지는 메모리에 들고 있다가 페이지 버튼으로
# 넘김)으로 고친다.
PAGE_ROWS = 300

# [2026-10-16] 표 열(맨 앞 NO는 표가 자동으로 붙인다)과 엑셀 열. 엑셀은 NO를 뺀 11칸.
COLUMNS = ("no", "area", "section", "shelf_no", "dan", "yeol", "isbn", "book_name",
           "worker", "time", "qty", "note")
HEADINGS = ("NO", "AREA", "SECTION", "서가번호", "단", "열", "바코드", "도서명",
            "작업자", "실사시간", "수량", "비고")
WIDTHS = (50, 60, 85, 150, 45, 45, 130, 240, 90, 80, 70, 100)
XL_HEADERS = HEADINGS[1:]
QTY_IDX = 9                       # 줄 튜플 안에서 수량 칸 번호(NO 제외)
XL_LEFT_COLS = (5, 6)             # 바코드, 도서명: 왼쪽 정렬 + 들여쓰기
XL_CENTER_COLS = (0, 1, 2, 3, 4, 7, 8)  # AREA/SECTION/서가번호/단/열/작업자/실사시간: 가운데 정렬
XL_EQUAL_WIDTH = ("실사시간", "수량", "비고")  # 정보 블록의 라벨 칸(수량)/값 칸(비고)이 넉넉하도록 같은 너비로
XL_TITLE = "섹션별 아이템 재고현황"
LABEL_DAN = "단소계"
LABEL_SECTION = "섹션소계"
LABEL_TOTAL = "합계"
# 줄 종류 -> 표 줄 색(태그). 엑셀은 같은 종류를 "sub"/"sec"/"total"로 넘긴다.
KIND_TAGS = {"sub": "dan_sub", "sec": "sec_sub", "total": "grand_total"}


def _num_key(value):
    """같은 단/섹션인지 비교할 때 "1"과 "01"을 같은 값으로 본다."""
    text = str(value if value is not None else "").strip()
    return int(text) if text.isdigit() else text


def build_status_rows(db_rows, merged=False):
    """조회된 stock_counts 줄(area, section, shelf_no, dan, yeol, isbn, book_name, qty, worker_name,
    received_at, survey_date)을 화면/엑셀에 보여줄 줄로 바꾼다. db_rows는 AREA > SECTION > 서가번호 > 단 > 열
    순으로 정렬되어 있어야 한다. 돌려주는 값: (줄 튜플 목록, 줄 종류 목록, NO 목록, 낱개 줄 수, 총 수량).
    줄 종류는 None(낱개) / "sub"(단소계) / "sec"(섹션소계) / "total"(합계). NO는 낱개 줄만 1부터 센다."""
    rows, kinds, nos = [], [], []
    items = 0
    grand = 0
    dan_key = sec_key = None
    dan_disp = sec_disp = None
    dan_qty = sec_qty = 0

    def flush_dan():
        rows.append((dan_disp[0], dan_disp[1], dan_disp[2], dan_disp[3], "", "", LABEL_DAN, "", "", dan_qty, ""))
        kinds.append("sub")
        nos.append(0)

    def flush_section():
        rows.append((sec_disp[0], sec_disp[1], "", "", "", "", LABEL_SECTION, "", "", sec_qty, ""))
        kinds.append("sec")
        nos.append(0)

    for r in db_rows:
        area = normalize_area(r["area"], merged=merged)
        this_sec = (area, _num_key(r["section"]))
        this_dan = (this_sec, str(r["shelf_no"] or ""), _num_key(r["dan"]))
        if dan_key is not None and this_dan != dan_key:
            flush_dan()
            dan_qty = 0
        if sec_key is not None and this_sec != sec_key:
            flush_section()
            sec_qty = 0
        if this_sec != sec_key:
            sec_key, sec_disp = this_sec, (area, r["section"])
        if this_dan != dan_key:
            dan_key, dan_disp = this_dan, (area, r["section"], r["shelf_no"], r["dan"])
        qty = r["qty"] or 0
        scan_time = split_scan_datetime(r["received_at"], r["survey_date"])[1]
        items += 1
        rows.append((area, r["section"], r["shelf_no"], r["dan"], r["yeol"], r["isbn"], r["book_name"],
                     r["worker_name"] or "", scan_time, qty, ""))
        kinds.append(None)
        nos.append(items)
        dan_qty += qty
        sec_qty += qty
        grand += qty
    if dan_key is not None:
        flush_dan()
        flush_section()
        rows.append(("", "", "", "", "", "", LABEL_TOTAL, "", "", grand, ""))
        kinds.append("total")
        nos.append(0)
    return rows, kinds, nos, items, grand


class _StatusModel(ListModel):
    """낱개 줄에는 NO를 붙이고, 단소계/섹션소계/합계 줄은 NO 없이 색을 달리 보여 주는 표 모델."""

    def __init__(self, rows, kinds, nos):
        super().__init__(rows)
        self.kinds = kinds
        self.nos = nos

    def rows(self, lo, hi):
        hi = min(hi, len(self.rows_data))
        out = []
        for pos in range(lo, hi):
            row = self.rows_data[pos]
            kind = self.kinds[pos]
            no = "" if kind else self.nos[pos]
            tag = KIND_TAGS[kind] if kind else ("odd" if self.nos[pos] % 2 == 0 else None)
            cells = (no,) + tuple(row[:QTY_IDX]) + (f"{row[QTY_IDX]:,}",) + tuple(row[QTY_IDX + 1:])
            out.append((cells, tag))
        return out


def _code_text(value, width):
    """조회 범위에 적을 AREA/SECTION: 숫자면 자리수만큼 0채움, 비었으면 전체."""
    text = (value or "").strip()
    if not text:
        return "전체"
    return text.zfill(width) if text.isdigit() else text


def section_range(start, end):
    """SECTION 시작~끝 칸 -> (작은 값, 큰 값) 정수. 둘 다 숫자일 때만 범위로 보고, 아니면 None.
    시작이 끝보다 크면 자동으로 바꾼다."""
    start, end = (start or "").strip(), (end or "").strip()
    if not (start.isdigit() and end.isdigit()):
        return None
    lo, hi = int(start), int(end)
    return (lo, hi) if lo <= hi else (hi, lo)


def section_range_text(start, end):
    """조회 범위·조건 표시에 적을 SECTION 글자: 범위면 `001~002`, 하나면 `001`, 없으면 `전체`."""
    start, end = (start or "").strip(), (end or "").strip()
    if not start and end:
        start, end = end, ""
    if not end:
        return _code_text(start, 3)
    rng = section_range(start, end)
    if rng:
        return f"{rng[0]:03d}~{rng[1]:03d}"
    return f"{start}~{end}"


def build_range_text(mode, value="", area_kw="", section_kw="", section_end_kw=""):
    """엑셀 정보 블록 가운데 칸에 적을 "조회한 범위" 글자. 바코드로 찾은 경우만 바코드를 덧붙인다."""
    area = section = shelf = "전체"
    barcode = ""
    value = (value or "").strip()
    if mode == "AREA+SECTION":
        area, section = _code_text(area_kw, 2), section_range_text(section_kw, section_end_kw)
    elif mode == "AREA":
        area = _code_text(value, 2)
    elif mode == "SECTION":
        section = _code_text(value, 3)
    elif mode == "서가번호":
        shelf = value or "전체"
    elif mode == "바코드":
        barcode = value
    text = f"AREA : {area}      SECTION : {section}      서가번호 : {shelf}"
    if barcode:
        text += f"      바코드 : {barcode}"
    return text


class SectionItemStatusScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._rows = []          # 조회된 전체(페이지 제한 없이, 소계/합계 줄 포함) - 엑셀저장/발행에 사용
        self._kinds = []         # _rows와 같은 길이: None(낱개)/"sub"(단소계)/"sec"(섹션소계)/"total"(합계)
        self._nos = []           # 낱개 줄 NO(소계/합계 줄은 0)
        self._item_count = 0     # 낱개 줄 수
        self._qty_total = 0      # 총 수량
        self._range_text = build_range_text("전체")
        self._view_page = 0
        self._view_total_pages = 1
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = tk.Frame(self, bg=CL_BG)
        top.pack(fill=tk.X, padx=8, pady=(10, 2))
        # [2026-10-01] "버튼이 많아 화면을 넘어가 안 보임" - 두 줄로 나눈다: 위 줄(top) = 조회 조건과 [조회]
        # ([2026-10-16] [발행] [엑셀저장] 포함), 아래 줄(actions) = 조회 조건 표시.
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
        # [2026-10-16] SECTION 범위: 시작 ~ 끝. 끝 칸을 비우면 시작 SECTION 하나만 조회한다.
        tk.Label(self.search_area_section_frame, text="~", bg=CL_BG).pack(side=tk.LEFT, padx=2)
        self.e_section_end_kw = tk.Entry(self.search_area_section_frame, width=6)
        self.e_section_end_kw.bind("<Return>", lambda ev: self.refresh())
        self.e_section_end_kw.pack(side=tk.LEFT)

        self._on_mode_changed(do_refresh=False)

        # [2026-09-23 정정] "AREA 합산전/후"를 오른쪽 끝에서 [조회] 버튼
        # 왼쪽으로 옮겼다.
        self.merge_mode = tk.StringVar(value="합산전")
        tk.Radiobutton(top, text="AREA 합산전", variable=self.merge_mode, value="합산전", bg=CL_BG,
                       command=self.refresh).pack(side=tk.LEFT, padx=(20, 0))
        tk.Radiobutton(top, text="AREA 합산후", variable=self.merge_mode, value="합산후", bg=CL_BG,
                       command=self.refresh).pack(side=tk.LEFT)

        win_button(top, text="조회", command=self.refresh, kind="normal").pack(side=tk.LEFT, padx=(12, 0))

        # [2026-10-16] "발행 엑셀저장 버튼을 조회 버튼 옆으로 간격을 두고 배치" - [조회] 바로 오른쪽에
        # [발행] [엑셀저장] 순서로, 버튼 사이에 간격을 둔다(예전엔 아래 줄 오른쪽 끝이었다).
        win_button(top, text="발행", command=self.print_report, kind="normal").pack(side=tk.LEFT, padx=(28, 0))
        win_button(top, text="엑셀저장", command=self.export_excel, kind="accent").pack(side=tk.LEFT, padx=(10, 0))

        # [2026-09-24 정정] 조건 표시 라벨에 주황색 음영(bg="#F4A93B")이 있었는데,
        # 사용자가 이 음영을 없애 달라고 해서 다른 화면들처럼 배경 없는 일반
        # 텍스트로 바꿨다(배경은 화면 배경색 그대로, 글자색은 남색).
        self.lbl_condition = tk.Label(actions, text="", bg=CL_BG, fg=CL_NAVY, font=("", 10, "bold"), width=32)
        self.lbl_condition.pack(side=tk.LEFT, padx=(0, 20))

        # 가상 스크롤 표(virtual_table.py): 화면에 보이는 줄만 두고 스크롤할 때 글자만 바꾼다.
        # 예전의 페이지 버튼(처음/이전/다음/끝)은 없고, 스크롤 하나로 끝까지 볼 수 있다.
        # [2026-10-16] 단소계/섹션소계/합계 줄은 회색 음영 + 굵은 글씨(재고조사 차이내역 화면과 같은 느낌).
        self.vl = VirtualList(self, COLUMNS, HEADINGS, WIDTHS, height=20,
                              tags={"dan_sub": "#EAEAEA", "sec_sub": "#DCDCDC", "grand_total": "#C9C9C9"})
        for tag_name in ("dan_sub", "sec_sub", "grand_total"):
            self.vl.tree.tag_configure(tag_name, font=("", 9, "bold"))
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
        section_end_kw = self.e_section_end_kw.get().strip()
        if not section_kw and section_end_kw:   # 끝 칸에만 적었으면 그 SECTION 하나로 본다
            section_kw, section_end_kw = section_end_kw, ""
        section_rng = None
        if mode == "AREA+SECTION" and section_end_kw:
            section_rng = section_range(section_kw, section_end_kw)
            if section_rng is None:
                messagebox.showwarning("알림", "SECTION 범위는 숫자로 입력하세요. (예: 001 ~ 002)")
                return
        merged = self.merge_mode.get() == "합산후"
        # [2026-09-23 정정] "전체 조회"라는 문구를 없앴다 - 전체를 고르면
        # 조건 표시 자체를 비워둔다.
        if mode == "AREA+SECTION":
            cond_text = (f"AREA '{area_kw}' + SECTION '{section_range_text(section_kw, section_end_kw)}'"
                         if (area_kw or section_kw) else "AREA+SECTION")
        else:
            cond_text = f"{mode}{(' = ' + value) if value else ''}" if mode != "전체" else ""
        self.lbl_condition.config(text=cond_text)
        # [2026-10-16] 엑셀 정보 블록에 적을 "조회한 범위" - 조회 순간의 조건으로 기억해 둔다
        # (조회 뒤에 입력칸만 고쳐 놓고 저장해도 표에 있는 내용과 같은 범위가 적히도록).
        self._range_text = build_range_text(mode, value, area_kw, section_kw, section_end_kw)

        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        conn = dbmod.get_conn()
        sql = ("SELECT area, section, shelf_no, dan, yeol, isbn, book_name, qty, worker_name, received_at, survey_date "
               "FROM stock_counts WHERE store_code=? AND survey_date=?")
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
            if section_rng:
                # 숫자 크기로 비교한다(01과 1, 001이 모두 같은 SECTION). 숫자가 아닌 SECTION 값은 범위에서 뺀다.
                sql += (" AND section<>'' AND section NOT GLOB '*[^0-9]*'"
                        " AND CAST(section AS INTEGER) BETWEEN ? AND ?")
                params.extend(section_rng)
            elif section_kw:
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
        # [2026-10-16] 단소계/섹션소계가 묶이도록 화면 열 순서(AREA > SECTION > 서가번호 > 단 > 열)대로 정렬한다.
        sql += (" ORDER BY CAST(area AS INTEGER), area, CAST(section AS INTEGER), section, shelf_no,"
                " CAST(dan AS INTEGER), dan, CAST(yeol AS INTEGER), yeol, id")
        rows = conn.execute(sql, params).fetchall()
        conn.close()

        self._rows, self._kinds, self._nos, self._item_count, self._qty_total = build_status_rows(rows, merged=merged)
        self._view_total_pages = max(1, (len(self._rows) + PAGE_ROWS - 1) // PAGE_ROWS)
        self._load_page(0)

    def _load_page(self, page=0):
        """조회된 줄(self._rows) 전체를 가상 스크롤 표에 보여준다(이름은 예전 그대로)."""
        self.vl.set_model(_StatusModel(self._rows, self._kinds, self._nos))
        self.lbl_total.config(text=f"(총 {self._item_count:,}건 / 총 수량 {self._qty_total:,}개)")

    # -- 엑셀저장 / 발행 -------------------------------------------------
    def _report_header(self):
        """재고조사 차이내역 [엑셀발행]/[발행]과 같은 상단 정보 블록에 들어갈 값."""
        return {
            "store_code": self.app.state.store_code,
            "store_name": self.app.state.store_name,
            "survey_date": self.app.state.survey_date,
            "threshold_text": "",
        }

    def _write_workbook(self, path, progress=None):
        _write_diff_detail_workbook(
            path, self._rows, XL_HEADERS, progress=progress, report_header=self._report_header(),
            title=XL_TITLE, info_center_text=self._range_text, row_kinds=self._kinds,
            left_align_cols=XL_LEFT_COLS, center_align_cols=XL_CENTER_COLS, numeric_cols=(QTY_IDX,),
            equal_width_headers=XL_EQUAL_WIDTH)

    def export_excel(self):
        """[엑셀저장] 버튼: [2026-10-16] 재고조사 차이내역과 같은 상단 형식(기업명/점포/검수자/조사일자/
        출력일자 블록 + 페이지 머리글·바닥글)으로 저장한다. 제목은 "섹션별 아이템 재고현황", 정보 블록
        가운데 칸에는 조회한 범위(AREA/SECTION/서가번호)가 들어간다. 줄이 많으면 진행률 창을 띄운다."""
        if not getattr(self, "_rows", None):
            messagebox.showinfo("알림", "저장할 데이터가 없습니다.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 파일", "*.xlsx")],
            initialfile=f"섹션별아이템재고현황_{file_date(self.app)}.xlsx",
        )
        if not path:
            return

        if len(self._rows) < PROGRESS_ROW_THRESHOLD:
            try:
                self._write_workbook(path)
            except ImportError:
                messagebox.showwarning(
                    "알림",
                    "openpyxl이 설치되어 있지 않아 서식 없이 저장할 수 없습니다.\n"
                    "pip install openpyxl 설치 후 다시 시도하세요.")
                return
            except OSError as e:
                _delete_partial_file(path)
                messagebox.showerror("오류", f"저장 중 오류가 발생했습니다:\n{friendly_save_error(e)}")
                return
            messagebox.showinfo("완료", f"저장되었습니다:\n{path}")
            return

        def work(progress):
            self._write_workbook(path, progress=progress)
            return path

        def on_done(result, error):
            if isinstance(error, Cancelled):
                _delete_partial_file(path)
                return
            if error is not None:
                _delete_partial_file(path)
                if isinstance(error, ImportError):
                    messagebox.showwarning(
                        "알림",
                        "openpyxl이 설치되어 있지 않아 서식 없이 저장할 수 없습니다.\n"
                        "pip install openpyxl 설치 후 다시 시도하세요.")
                    return
                messagebox.showerror("오류", f"저장 중 오류가 발생했습니다:\n{friendly_save_error(error)}")
                return
            messagebox.showinfo("완료", f"저장되었습니다:\n{result}")

        run_with_progress(self, "엑셀로 저장하는 중", work, on_done, cancelable=True)

    def print_report(self):
        """[발행] 버튼: [2026-09-23] 재고조사 차이명세 등 다른 화면의
        [발행]과 똑같이 실제로 기본 프린터에 인쇄까지 한다. [2026-09-28
        재수정] "발행버튼을 누르면 왜 엑셀저장이 뜨냐" - 저장 위치를 묻는
        대화상자 대신 조용히 임시 파일을 만든다. [2026-09-28 재수정 2차]
        "인쇄전 설정창같은게 하나 뜨잖아? 그렇게 해줘" - 저장 위치 대화상자는
        계속 안 띄우되, 프린터/매수를 고를 수 있는 진짜 인쇄 대화상자는
        뜨도록 print_excel_file()로 바꿨다. [2026-10-16] 엑셀저장과 같은
        양식(재고조사 차이내역 상단 형식)으로 인쇄한다."""
        if not getattr(self, "_rows", None):
            messagebox.showinfo("알림", "인쇄할 데이터가 없습니다.")
            return
        tmp_dir = os.path.join(tempfile.gettempdir(), "kointbook_print")
        os.makedirs(tmp_dir, exist_ok=True)
        path = os.path.join(tmp_dir, f"{_dt.now().strftime('%Y%m%d_%H%M%S_%f')}_섹션별아이템재고현황_{file_date(self.app)}.xlsx")
        fallback_name = f"섹션별아이템재고현황_{file_date(self.app)}.xlsx"

        if len(self._rows) < PROGRESS_ROW_THRESHOLD:
            try:
                self._write_workbook(path)
            except ImportError:
                path = print_rows_to_excel(self._rows, XL_HEADERS, default_name=fallback_name)
                if not path:
                    return
            except OSError as e:
                _delete_partial_file(path)
                messagebox.showerror("오류", f"인쇄 파일을 만드는 중 오류가 발생했습니다:\n{friendly_save_error(e)}")
                return
            print_excel_file(path)
            return

        def work(progress):
            try:
                self._write_workbook(path, progress=progress)
                return path
            except ImportError:
                return print_rows_to_excel(self._rows, XL_HEADERS, default_name=fallback_name)

        def on_done(result, error):
            if isinstance(error, Cancelled):
                _delete_partial_file(path)
                return
            if error is not None:
                _delete_partial_file(path)
                messagebox.showerror("오류", f"인쇄 파일을 만드는 중 오류가 발생했습니다:\n{friendly_save_error(error)}")
                return
            if not result:
                return
            print_excel_file(result)

        run_with_progress(self, "인쇄 파일을 만드는 중", work, on_done, cancelable=True)
