# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""집계표관리 > 샘플링 결과보고서 화면.

[2026-10-08] 상단을 [재고조사 차이명세] 발행 양식과 동일하게(제목만 "샘플링 결과보고서",
"차이수량(±)" 줄 삭제), 버튼을 조회/출력/엑셀저장으로, 조회 화면 헤더를 출력(엑셀)과 같은
3단 병합 헤더(Canvas)로, 표는 LOC/구분 구성으로 바꿨다. 아래 2026-09-24 설명 중 여러 줄
헤더/LOC·SEC 구성/[자료생성] 이야기는 이 변경으로 대체됐다.

[매대등록 > 샘플링 자료등록]에서 쌓인 미스(오차) 기록을 LOC(AREA)/SEC
(SECTION)별로 모아서(샘플링 자료등록에 등록된 SECTION만 대상 - 2026-10-02), KOINT(실사 대행사) 책임 미스유형별 / 고객사(매장)
책임 미스유형별로 나눠 보여준다.

  TOT       : 그 LOC/SEC의 전체 실사 수량/건수 (stock_counts 기준)
  KOINT미스 : 미스유형 책임소재가 KOINT인 것들의 합
  미스율    : KOINT미스 수량/건수를 각각 TOT수량/건수로 나눈 값(%) - 수량
              기준/건수 기준 두 가지를 따로 보여준다
  그 아래 각 미스유형별 수량/건수 (db.MISS_TYPES 순서, 소속그룹별로 묶임)

[2026-09-24 2차 정정] 실제 운영 화면/보고서 캡쳐 3장(PC 화면 2장 + 엑셀
결과물 1장)을 다시 보고 화면을 전체적으로 다시 짰다:

  - 예전엔 "AREA 합산전/후" 라디오가 있었는데, 캡쳐엔 그 대신 "고객/자사"
    라디오가 있었다 - 이걸로 바꿨다. 이 라디오는 표시 문구만 바꾼다
    (db.MISS_TYPES의 owner 값 자체는 그대로): "자사"를 고르면 두 책임그룹
    헤더를 내부 코드값("KOINT"/"KYOBO")으로, "고객"을 고르면 실제 고객사에
    보여줄 이름("코인트서비스"/점포명)으로 보여준다. (참고: 캡쳐에는 매장
    쪽 그룹 헤더가 "GS슈퍼"/"홈플러스"처럼 점포명과는 다른 원청 그룹사
    이름으로 나와 있었는데, KOINTBOOK 점포마스터에는 그런 별도 필드가 없어
    지금은 점포명을 그대로 쓴다 - 원청 그룹사 이름을 따로 관리하고 싶으면
    점포마스터에 필드를 추가해야 한다.)
  - 캡쳐의 표 헤더가 LOC/SEC 두 칸으로 나뉘어 있어서(예전엔 LOC 하나뿐),
    AREA/SECTION을 따로 보여주도록 컬럼을 나눴다 - 그래서 이제 AREA별이
    아니라 AREA+SECTION별로 한 줄씩 나온다.
  - "미스율"도 캡쳐엔 수량/건수 두 칸으로 나뉘어 있어서(예전엔 %한 칸)
    똑같이 나눴다(수량 기준율, 건수 기준율 각각 계산).
  - 표 헤더가 캡쳐에서는 위/아래 2단(그룹명 + 세부유형, 그리고 그 아래
    수량/건수)으로 병합돼 있었다 - Tkinter 표(Treeview)는 엑셀처럼 셀을
    합쳐서 그리는 기능이 없어서 완전히 똑같이는 못 그리고, 대신 헤더 글자를
    "그룹명\\n유형명\\n수량"처럼 여러 줄로 겹쳐 보여줘서 같은 정보를
    전달한다(그룹으로 묶여 있다는 것 자체는 [자료생성]으로 만드는 엑셀
    파일에서는 캡쳐와 완전히 동일하게(병합 셀로) 그린다).
  - 버튼 이름을 캡쳐와 똑같이 "출력"/"자료생성"으로 바꿨다(예전 "발행"/
    "엑셀저장"). [자료생성]은 캡쳐 이미지와 같은 양식(로고 자리에 상호명/
    "Koint" 글자, 제목, 점포코드/점포명/조사일자, 그룹으로 병합된 표 헤더,
    맨 아래 "합계" 줄)으로 엑셀 파일을 만든다.
  - 다른 화면들처럼 위쪽에 점포코드/점포명/조사일자를 보여주는 줄을 추가했다."""

import tkinter as tk
from tkinter import filedialog, messagebox
from . import db as dbmod
from .ui_common import (
    setup_treeview, export_rows_to_excel, print_rows_to_excel, print_excel_file, file_date,
    normalize_area, area_section_code, CL_BG, CL_NAVY, CL_TEXT_DIM, win_button
)

# 표 안에서 각 "single"/"pair" 그룹 이름 <-> 내부 컬럼id 매핑 (헤더 만들 때
# 공용으로 쓴다 - 화면/엑셀 양쪽 다 이 이름 그대로 씀).
_PAIR_ID = {"미스율": "miss_ratio", "TOT": "tot", "KOINT미스": "koint_miss"}


class SamplingReportScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._rows = []
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # 헤더/컬럼 구성 (화면-Treeview용과 엑셀-병합헤더용이 뒷부분(미스율/TOT/
    # KOINT미스/두 책임그룹)을 공유하도록 한 곳에서 만든다)
    # ------------------------------------------------------------------
    def _owner_labels(self):
        """(KOINT 그룹 표시명, 고객사 그룹 표시명)을 "고객/자사" 라디오에
        맞춰 돌려준다."""
        if self.view_mode.get() == "자사":
            return "KOINT", "KYOBO"
        return "코인트서비스", (self.app.state.store_name or "고객사")

    def _shared_group_spec(self):
        """LOC/SEC(또는 구분) 다음에 오는, 화면/엑셀이 공유하는 그룹 구성.
        "single": 칸 하나(수량/건수 구분 없음). "pair": 수량/건수 두 칸.
        "typegroup": 미스유형 여러 개, 각각 수량/건수 두 칸씩."""
        koint_label, kyobo_label = self._owner_labels()
        koint_types = [name for name, owner in dbmod.MISS_TYPES if owner == "KOINT"]
        kyobo_types = [name for name, owner in dbmod.MISS_TYPES if owner == "KYOBO"]
        return [
            {"kind": "pair", "label": "미스율"},
            {"kind": "pair", "label": "TOT"},
            {"kind": "pair", "label": "KOINT미스"},
            {"kind": "typegroup", "label": koint_label, "types": koint_types},
            {"kind": "typegroup", "label": kyobo_label, "types": kyobo_types},
        ]

    def _screen_spec(self):
        """[2026-10-08] 화면 헤더를 출력(엑셀) 헤더와 똑같이 보이게 하려고, 화면도
        출력과 같은 구성(LOC + 구분 + 공유 그룹)을 쓴다."""
        return [{"kind": "single", "label": "LOC"}, {"kind": "single", "label": "구분"}] + self._shared_group_spec()

    def _flatten_for_tree(self, spec):
        """spec을 Treeview용 (컬럼id, 칸 제목, 폭)으로 편다. 칸 제목은 폭 계산용일
        뿐이고, 실제 헤더는 위쪽 Canvas(_draw_header)가 병합 모양으로 그린다."""
        columns, headings, widths = [], [], []
        for g in spec:
            if g["kind"] == "single":
                columns.append("loc" if g["label"] == "LOC" else "gubun")
                headings.append(g["label"])
                widths.append(72 if g["label"] == "LOC" else 56)
            elif g["kind"] == "pair":
                base = _PAIR_ID[g["label"]]
                columns += [f"{base}_qty", f"{base}_cnt"]
                headings += ["수량", "건수"]
                widths += [72, 72]
            else:  # typegroup
                for name in g["types"]:
                    columns += [f"{name}_qty", f"{name}_cnt"]
                    headings += ["수량", "건수"]
                    widths += [92, 92]
        return columns, headings, widths

    # ------------------------------------------------------------------
    # 화면 구성
    # ------------------------------------------------------------------
    HDR_ROW_H = 22      # 병합 헤더 한 줄 높이(3줄)
    HDR_FILL = "#F2F2F2"  # 출력(엑셀) 표 헤더 배경과 같은 옅은 회색
    HDR_LINE = "#B0B0B0"

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

        # [2026-09-24 2차 정정] "AREA 합산전/후" 대신 캡쳐에 있던 "고객/자사"
        # 라디오로 바꿨다 - 표시 문구(그룹 헤더 이름)만 바꾸는 토글이다.
        self.view_mode = tk.StringVar(value="고객")
        tk.Radiobutton(top, text="고객", variable=self.view_mode, value="고객", bg=CL_BG,
                       command=self.refresh).grid(row=0, column=6, padx=(16, 0))
        tk.Radiobutton(top, text="자사", variable=self.view_mode, value="자사", bg=CL_BG,
                       command=self.refresh).grid(row=0, column=7, padx=(0, 20))

        # [2026-10-08] 버튼 이름: 출력 / 자료생성 -> 엑셀저장. [조회]와 [출력] 사이는
        # 간격을 넓게(28px) 두고, [출력]/[엑셀저장]은 붙여 둔다.
        win_button(top, text="조회", command=self.refresh, kind="normal").grid(row=0, column=8, padx=(4, 28))
        win_button(top, text="출력", command=self.print_report, kind="normal").grid(row=0, column=9, padx=4)
        win_button(top, text="엑셀저장", command=self.generate_report, kind="accent").grid(row=0, column=10, padx=4)

        self._spec = self._screen_spec()
        columns, headings, widths = self._flatten_for_tree(self._spec)
        self._columns = tuple(columns)

        # [2026-10-08] 표 위에 병합 모양 헤더(Canvas)를 따로 그린다 - Treeview는 셀 병합
        # 헤더를 못 그려서 여러 줄 글자로 겹쳐 놓았더니 행이 이상하게 보였다.
        wrap = tk.Frame(self, bg=CL_BG)
        wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=1)
        self.hdr_canvas = tk.Canvas(wrap, height=self.HDR_ROW_H * 3, bg=self.HDR_FILL,
                                    highlightthickness=0, bd=0)
        self.hdr_canvas.grid(row=0, column=0, sticky="ew")
        # 오른쪽 세로 스크롤바 폭만큼 비워서 헤더와 표의 가로 위치를 맞춘다.
        tk.Frame(wrap, width=17, bg=CL_BG).grid(row=0, column=1)

        container, self.tree = setup_treeview(wrap, tuple(columns), tuple(headings), tuple(widths), height=18)
        container.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.tree.configure(show="")  # 기본 1줄 헤더는 숨기고 위 Canvas 헤더를 쓴다
        self.tree.tag_configure("total_row", background="#E8D9B0", font=("", 9, "bold"))

        # 표가 가로로 스크롤되면 헤더도 같이 움직이게 한다.
        _orig_xscroll = str(self.tree.cget("xscrollcommand"))

        def _xscroll(*args):
            try:
                self.tree.tk.call(_orig_xscroll, *args)
            except Exception:
                pass
            self._draw_header()

        self.tree.configure(xscrollcommand=_xscroll)
        self.hdr_canvas.bind("<Configure>", lambda e: self._draw_header())
        # [2026-10-13] "가로는 스크롤 없이 한 화면에" - 열 폭을 화면 폭에 맞춰 비율로 늘이고 줄인다(가로 스크롤바 숨김).
        self._base_widths = [int(self.tree.column(col, "width")) for col in columns]
        for _w in container.winfo_children():
            try:
                if str(_w.cget("orient")) == "horizontal":
                    _w.grid_remove()
            except Exception:
                pass
        self._fit_after = None
        container.bind("<Configure>", lambda e: self._schedule_fit(e.width))
        self.tree.bind("<B1-Motion>", lambda e: self._draw_header(), add="+")
        self.after(60, self._draw_header)

    def _schedule_fit(self, width):
        if self._fit_after is not None:
            try:
                self.after_cancel(self._fit_after)
            except Exception:
                pass
        self._fit_after = self.after(30, lambda: self._fit_columns(width))

    def _fit_columns(self, width):
        """열 폭을 (표 폭 - 세로스크롤바)에 딱 맞게 비율로 조정한다."""
        self._fit_after = None
        avail = int(width) - 20
        base = self._base_widths
        total = sum(base)
        if avail < 200 or total <= 0:
            return
        scale = avail / total
        widths = [max(28, int(w * scale)) for w in base]
        widths[-1] += avail - sum(widths)
        for col, w in zip(self._columns, widths):
            self.tree.column(col, width=max(28, w), stretch=False)
        try:
            self.tree.xview_moveto(0)
        except Exception:
            pass
        self._draw_header()

    def _draw_header(self):
        """출력(엑셀)과 같은 3단 병합 헤더를 Canvas에 그린다(_write_report_excel의
        헤더 구성과 동일: single=3줄 병합, pair=위 2줄 병합+수량/건수,
        typegroup=그룹명 / 유형명 / 수량·건수)."""
        c = self.hdr_canvas
        c.delete("all")
        try:
            frac_start, _ = self.tree.xview()
            widths = [self.tree.column(col, "width") for col in self._columns]
        except Exception:
            return
        total = sum(widths) or 1
        off = int(frac_start * total)
        H = self.HDR_ROW_H
        xs = [0]
        for w in widths:
            xs.append(xs[-1] + w)

        def cell(c0, c1, r0, r1, text):
            x0, x1 = xs[c0] - off, xs[c1 + 1] - off
            y0, y1 = r0 * H, (r1 + 1) * H
            c.create_rectangle(x0, y0, x1, y1, fill=self.HDR_FILL, outline=self.HDR_LINE)
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=text, font=("", 9))

        col = 0
        for g in self._spec:
            if g["kind"] == "single":
                cell(col, col, 0, 2, g["label"])
                col += 1
            elif g["kind"] == "pair":
                cell(col, col + 1, 0, 1, g["label"])
                cell(col, col, 2, 2, "수량")
                cell(col + 1, col + 1, 2, 2, "건수")
                col += 2
            else:
                n = len(g["types"])
                if n == 0:
                    continue
                cell(col, col + n * 2 - 1, 0, 0, g["label"])
                for ti, name in enumerate(g["types"]):
                    c0 = col + ti * 2
                    cell(c0, c0 + 1, 1, 1, name)
                    cell(c0, c0, 2, 2, "수량")
                    cell(c0 + 1, c0 + 1, 2, 2, "건수")
                col += n * 2
        c.configure(scrollregion=(0, 0, total, H * 3))

    def _refresh_headings(self):
        """"고객/자사" 라디오가 바뀌면 그룹 헤더 이름이 바뀌므로 구성을 다시 만들어 그린다."""
        self._spec = self._screen_spec()
        self._draw_header()

    def _display_row(self, row):
        """화면/출력 공통 표시 행: (AREA, SECTION)을 LOC 코드 + 구분(매장/합계)으로 바꾼다."""
        area, section = row[0], row[1]
        if area == "합계":
            return ["합계", "합계"] + list(row[2:])
        return [area_section_code(area, section), "매장"] + list(row[2:])

    # ------------------------------------------------------------------
    # 데이터
    # ------------------------------------------------------------------
    def refresh(self):
        self.lbl_store_code.config(text=self.app.state.store_code)
        self.lbl_store_name.config(text=self.app.state.store_name)
        self.lbl_date.config(text=self.app.state.survey_date)
        self._refresh_headings()

        store_code = self.app.state.store_code
        date = self.app.state.survey_date

        conn = dbmod.get_conn()
        tot_rows = conn.execute(
            "SELECT area, section, COUNT(*) AS cnt, COALESCE(SUM(qty),0) AS qty FROM stock_counts "
            "WHERE store_code=? AND survey_date=? GROUP BY area, section",
            (store_code, date)
        ).fetchall()
        miss_rows = conn.execute(
            "SELECT area, section, miss_type, COALESCE(SUM(miss_qty),0) AS qty, COALESCE(SUM(miss_count),0) AS cnt "
            "FROM sampling_miss WHERE store_code=? AND survey_date=? GROUP BY area, section, miss_type",
            (store_code, date)
        ).fetchall()
        conn.close()

        totals = {}

        def key_of(r):
            area = normalize_area(r["area"]) or "(미지정)"
            section = (r["section"] or "").strip()
            # SECTION은 PDA에서 항상 3자리("005")로 들어오므로, 등록 화면에서 "5"처럼
            # 입력했어도 같은 SECTION으로 맞춰 본다(숫자일 때만 앞에 0을 채움).
            if section.isdigit():
                section = section.zfill(3)
            return (area, section or "(미지정)")

        # [2026-10-02] "샘플링 결과보고서는 샘플링자료등록에서 등록한 섹션에 대해서만 결과를 낸다" -
        # 예전에는 실사 데이터(stock_counts)에 있는 모든 AREA/SECTION이 TOT과 함께 줄로 나왔다.
        # 이제 [샘플링 자료등록]에 등록된 AREA/SECTION만 줄로 만들고, TOT(실사 수량/건수)도 그
        # SECTION들 것만 더한다(맨 아래 합계와 미스율도 같은 기준).
        for r in miss_rows:
            t = totals.setdefault(key_of(r), {"tot_qty": 0, "tot_count": 0, "miss": {}})
            m = t["miss"].setdefault(r["miss_type"], {"qty": 0, "count": 0})
            m["qty"] += r["qty"] or 0
            m["count"] += r["cnt"] or 0

        for r in tot_rows:
            t = totals.get(key_of(r))
            if t is None:
                continue  # 샘플링 등록이 없는 SECTION은 보고서에서 뺀다
            t["tot_qty"] += r["qty"] or 0
            t["tot_count"] += r["cnt"] or 0

        self.tree.delete(*self.tree.get_children())
        self._rows = []
        grand = {"tot_qty": 0, "tot_count": 0, "koint_qty": 0, "koint_count": 0}
        grand_type = {name: {"qty": 0, "count": 0} for name, _ in dbmod.MISS_TYPES}

        for i, ((area, section), t) in enumerate(sorted(totals.items()), start=1):
            koint_qty = sum(t["miss"].get(name, {}).get("qty", 0) for name, owner in dbmod.MISS_TYPES if owner == "KOINT")
            koint_cnt = sum(t["miss"].get(name, {}).get("count", 0) for name, owner in dbmod.MISS_TYPES if owner == "KOINT")
            ratio_qty = (koint_qty * 100.0 / t["tot_qty"]) if t["tot_qty"] else 0.0
            ratio_cnt = (koint_cnt * 100.0 / t["tot_count"]) if t["tot_count"] else 0.0
            row = [area, section, f"{ratio_qty:.1f}", f"{ratio_cnt:.1f}",
                   t["tot_qty"], t["tot_count"], koint_qty, koint_cnt]
            for name, owner in dbmod.MISS_TYPES:
                m = t["miss"].get(name, {"qty": 0, "count": 0})
                row += [m["qty"], m["count"]]
                grand_type[name]["qty"] += m["qty"]
                grand_type[name]["count"] += m["count"]
            self._rows.append(row)
            self.tree.insert("", tk.END, values=self._display_row(row), tags=("odd",) if i % 2 == 0 else ())
            grand["tot_qty"] += t["tot_qty"]
            grand["tot_count"] += t["tot_count"]
            grand["koint_qty"] += koint_qty
            grand["koint_count"] += koint_cnt

        if totals:
            ratio_qty = (grand["koint_qty"] * 100.0 / grand["tot_qty"]) if grand["tot_qty"] else 0.0
            ratio_cnt = (grand["koint_count"] * 100.0 / grand["tot_count"]) if grand["tot_count"] else 0.0
            total_row = ["합계", "", f"{ratio_qty:.1f}", f"{ratio_cnt:.1f}",
                         grand["tot_qty"], grand["tot_count"], grand["koint_qty"], grand["koint_count"]]
            for name, _owner in dbmod.MISS_TYPES:
                total_row += [grand_type[name]["qty"], grand_type[name]["count"]]
            self._rows.append(total_row)
            self.tree.insert("", tk.END, values=self._display_row(total_row), tags=("total_row",))

    # ------------------------------------------------------------------
    # 출력/자료생성
    # ------------------------------------------------------------------
    def _flat_headings(self):
        """openpyxl이 없을 때 CSV로 저장하는 경우에만 쓰는 한 줄 헤더."""
        heads = []
        for g in self._spec:
            if g["kind"] == "single":
                heads.append(g["label"])
            elif g["kind"] == "pair":
                heads += [f"{g['label']} 수량", f"{g['label']} 건수"]
            else:
                for name in g["types"]:
                    heads += [f"{g['label']} {name} 수량", f"{g['label']} {name} 건수"]
        return heads

    def print_report(self):
        """[출력]: [엑셀저장]과 같은 서식(_write_report_excel)으로 임시 파일을 만들어
        인쇄 대화상자(print_excel_file)로 보낸다. [2026-10-08] 예전엔 평평한 1줄 헤더
        표를 찍어서 화면/엑셀 양식과 달랐다."""
        if not self._rows:
            messagebox.showinfo("알림", "인쇄할 데이터가 없습니다.")
            return
        import os
        import tempfile
        from datetime import datetime as _dt
        tmp_dir = os.path.join(tempfile.gettempdir(), "kointbook_print")
        os.makedirs(tmp_dir, exist_ok=True)
        path = os.path.join(tmp_dir, f"{_dt.now().strftime('%Y%m%d_%H%M%S_%f')}_샘플링결과보고서_{file_date(self.app)}.xlsx")
        try:
            self._write_report_excel(path)
        except ImportError:
            path = print_rows_to_excel([self._display_row(r) for r in self._rows], self._flat_headings(),
                                       default_name=f"샘플링결과보고서_{file_date(self.app)}.xlsx")
            if not path:
                return
        except OSError as e:
            messagebox.showerror("오류", f"인쇄 파일을 만드는 중 오류가 발생했습니다:\n{e}")
            return
        print_excel_file(path)

    def generate_report(self):
        """[엑셀저장](전 [자료생성]): 그룹으로 병합된 헤더(미스율/TOT/KOINT미스/
        코인트서비스-유형들/고객사-유형들)를 가진 엑셀 보고서를 만든다.
        [출력]과 같은 서식이다."""
        if not self._rows:
            messagebox.showinfo("알림", "저장할 데이터가 없습니다.")
            return
        default_name = f"샘플링결과보고서_{file_date(self.app)}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 파일", "*.xlsx")],
            initialfile=default_name,
        )
        if not path:
            return
        try:
            self._write_report_excel(path)
        except ImportError:
            import csv
            csv_path = path.rsplit(".", 1)[0] + ".csv"
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(self._flat_headings())
                for row in self._rows:
                    w.writerow(self._display_row(row))
            messagebox.showinfo(
                "알림",
                f"openpyxl이 설치되어 있지 않아 양식 없이 CSV로 저장했습니다:\n{csv_path}\n\n"
                "pip install openpyxl 설치 후 다시 시도하면 양식이 있는 .xlsx로 저장됩니다."
            )
            return
        except OSError as e:
            messagebox.showerror("오류", f"저장 중 오류가 발생했습니다:\n{e}")
            return
        messagebox.showinfo("완료", f"보고서가 저장되었습니다:\n{path}")

    def _write_report_excel(self, path):
        """[2026-10-08] 상단을 [재고조사 차이명세] 발행 양식과 똑같이 맞췄다: 정보 블록 3줄
        (기업명/검수자(인), 점포코드/조사일자, 점포명/출력일자) + 여백 1줄 + 표 헤더,
        그리고 인쇄 머리글(가운데 제목 "샘플링 결과보고서", 오른쪽 "&P of &N")과
        바닥글("(주)코인트써비스"). 제목 밑의 "차이수량(±)" 줄은 뺐다."""
        import openpyxl
        from datetime import datetime as _dt
        from openpyxl.cell.cell import MergedCell
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter

        store_code = self.app.state.store_code
        store_name = self.app.state.store_name

        excel_spec = self._screen_spec()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "샘플링결과보고서"

        info_pt = max(7, round(11 * 0.8))
        info_font = Font(size=info_pt + 4, name="맑은 고딕", bold=True)  # 1~3행 굵게 + [2026-10-08] 2사이즈 업
        hdr_font = Font(size=info_pt, name="맑은 고딕")
        thin = Side(style="thin", color="B0B0B0")
        border_all = Border(left=thin, right=thin, top=thin, bottom=thin)
        header_fill = PatternFill("solid", fgColor="F2F2F2")
        total_fill = PatternFill("solid", fgColor="D9D9D9")
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")
        align_right_indent = Alignment(horizontal="right", vertical="center", indent=3)

        total_cols = 0
        for g in excel_spec:
            total_cols += 1 if g["kind"] == "single" else (2 if g["kind"] == "pair" else len(g["types"]) * 2)

        # ---- 정보 블록(재고조사 차이명세와 같은 배치) ----
        def _info_cell(row, c0, c1, text, align=align_left):
            if c1 > c0:
                ws.merge_cells(start_row=row, start_column=c0, end_row=row, end_column=c1)
            cell = ws.cell(row=row, column=c0, value=text)
            cell.font = info_font
            cell.alignment = align

        left_end = 4
        value_start, value_end = total_cols - 2, total_cols
        label_start, label_end = total_cols - 4, total_cols - 3
        survey_date = (self.app.state.survey_date or "").strip()
        if len(survey_date) == 8 and survey_date.isdigit():
            survey_date_disp = f"{survey_date[:4]}년 {survey_date[4:6]}월 {survey_date[6:]}일"
        else:
            survey_date_disp = survey_date or "-"
        printed_at = _dt.now().strftime("%Y년 %m월 %d일 %H:%M:%S")

        _info_cell(1, 1, left_end, "기업명 : (주)교보문고")
        _info_cell(1, label_start, label_end, "검수자 :", align=align_right)
        _info_cell(1, value_start, value_end, "(인)", align=align_right_indent)
        _info_cell(2, 1, left_end, f"점포코드 : {store_code or ''}")
        _info_cell(2, label_start, label_end, "조사일자 :", align=align_right)
        _info_cell(2, value_start, value_end, survey_date_disp)
        _info_cell(3, 1, left_end, f"점포명 : {store_name or ''}")
        _info_cell(3, label_start, label_end, "출력일자 :", align=align_right)
        _info_cell(3, value_start, value_end, printed_at)
        for _r in (1, 2, 3):
            ws.row_dimensions[_r].height = 21
        ws.row_dimensions[4].height = 6  # 정보 블록과 표 헤더 사이 얇은 여백

        # ---- 표 헤더(3단, 그룹 병합) ----
        r = 5
        col = 1
        for g in excel_spec:
            if g["kind"] == "single":
                ws.merge_cells(start_row=r, start_column=col, end_row=r + 2, end_column=col)
                ws.cell(row=r, column=col, value=g["label"])
                col += 1
            elif g["kind"] == "pair":
                ws.merge_cells(start_row=r, start_column=col, end_row=r + 1, end_column=col + 1)
                ws.cell(row=r, column=col, value=g["label"])
                ws.cell(row=r + 2, column=col, value="수량")
                ws.cell(row=r + 2, column=col + 1, value="건수")
                col += 2
            else:  # typegroup
                n = len(g["types"])
                if n == 0:
                    continue
                ws.merge_cells(start_row=r, start_column=col, end_row=r, end_column=col + n * 2 - 1)
                ws.cell(row=r, column=col, value=g["label"])
                for ti, name in enumerate(g["types"]):
                    c0 = col + ti * 2
                    ws.merge_cells(start_row=r + 1, start_column=c0, end_row=r + 1, end_column=c0 + 1)
                    ws.cell(row=r + 1, column=c0, value=name)
                    ws.cell(row=r + 2, column=c0, value="수량")
                    ws.cell(row=r + 2, column=c0 + 1, value="건수")
                col += n * 2
        last_col = col - 1
        for rr in (r, r + 1, r + 2):
            for cc in range(1, last_col + 1):
                cell = ws.cell(row=rr, column=cc)
                # 병합된 칸의 "숨은" 칸(MergedCell)은 값을 새로 못 넣는다 - 스타일만 넣는다.
                if not isinstance(cell, MergedCell) and cell.value is None:
                    cell.value = ""
                cell.font = hdr_font
                cell.fill = header_fill
                cell.alignment = center
                cell.border = border_all
                ws.column_dimensions[get_column_letter(cc)].width = 10.5
        ws.column_dimensions["A"].width = 12
        header_last_row = r + 2
        ws.print_title_rows = f"1:{header_last_row}"  # 페이지마다 정보 블록+헤더 반복

        # ---- 데이터 행 ----
        r += 3
        for row_vals in self._rows:
            values = self._display_row(row_vals)
            is_total = values[0] == "합계"
            for cc, v in enumerate(values, start=1):
                cell = ws.cell(row=r, column=cc, value=v)
                cell.border = border_all
                cell.alignment = center
                cell.font = Font(bold=is_total, size=info_pt, name="맑은 고딕")
                if is_total:
                    cell.fill = total_fill
            r += 1

        # ---- 인쇄 머리글/바닥글(재고조사 차이명세와 동일, 제목만 다름) ----
        ws.oddHeader.center.text = "샘플링 결과보고서"
        ws.oddHeader.center.size = 22  # [2026-10-08] 제목 22pt
        ws.oddHeader.center.font = "맑은 고딕,Bold"  # 머리글/바닥글 제목 포함 굵게
        ws.oddHeader.right.text = "&P of &N"
        ws.oddHeader.right.size = 11
        ws.oddFooter.right.text = "(주)코인트써비스"
        ws.oddFooter.right.size = 10
        ws.oddHeader.right.font = "맑은 고딕,Bold"
        ws.oddFooter.right.font = "맑은 고딕,Bold"
        try:
            ws.evenHeader.center.text = ws.oddHeader.center.text
            ws.evenHeader.center.size = ws.oddHeader.center.size
            ws.evenHeader.center.font = ws.oddHeader.center.font
            ws.evenHeader.right.text = ws.oddHeader.right.text
            ws.evenHeader.right.size = ws.oddHeader.right.size
            ws.evenFooter.right.text = ws.oddFooter.right.text
            ws.evenFooter.right.size = ws.oddFooter.right.size
            ws.evenHeader.right.font = ws.oddHeader.right.font
            ws.evenFooter.right.font = ws.oddFooter.right.font
        except Exception:
            pass

        ws.page_setup.orientation = "landscape"
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        # [2026-10-08] 페이지설정(cm): 왼쪽 0.4 / 오른쪽 0.4 / 바닥글 0.4
        ws.page_margins.left = 0.4 / 2.54
        ws.page_margins.right = 0.4 / 2.54
        ws.page_margins.top = 1.5 / 2.54
        ws.page_margins.bottom = 0.9 / 2.54
        ws.page_margins.header = 0.8 / 2.54
        ws.page_margins.footer = 0.4 / 2.54

        wb.save(path)
