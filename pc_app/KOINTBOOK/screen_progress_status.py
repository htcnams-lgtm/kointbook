# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""집계표관리 > 재고조사 진행 현황 화면 (대시보드).

  총섹션   : 등록(계획)된 SECTION과 실제로 스캔된 SECTION을 합친 전체 개수
  완료섹션 : 등록되어 있고, 실제로도 스캔이 끝난 SECTION
  미완료섹션 : 등록은 되어 있는데 아직 스캔이 안 된 SECTION (Section Check의 "결번"과 같은 개념)
  중복섹션 : 같은 SECTION을 작업자 2명 이상이 각각 스캔한 것 (아직 "인지" 처리 전)
  추가섹션 : 등록되어 있지 않은데 스캔 데이터가 들어온 SECTION (계획에 없던 추가 작업)
  진행률   : 완료섹션 / 총섹션 * 100(%)

[2026-09-23 실제 화면 재확인] 아래 목록을 표(리스트)로 보여주던 것을,
캡처와 같이 SECTION 하나당 한 칸씩 색칠된 타일 그리드로 바꿨다 - 칸에는
AREA(2자리)+SECTION(3자리)을 이어붙인 "A_SECTION" 코드가 그대로 보이고
(`ui_common.area_section_code`), 상태에 따라 색이 다르다(완료/미완료/
중복/추가 - 위 5개 박스와 같은 색). 한 SECTION이 여러 상태에 걸치면
중복 > 추가 > 완료 > 미완료 순으로 우선해서 색을 정한다.

[2026-09-23 정정] 타일이 너무 낮고 답답해 보인다는 피드백으로 세로 길이를
두 배(TILE_H)로 늘리고, 안의 글자(A_SECTION 코드)도 굵게(bold) 바꿨다.
"진행률 - 0.0%"도 입력칸처럼(sunken) 보이던 것을 점포코드 표시칸과 같은
깔끔한 스타일(흰 배경 + 얇은 테두리, flat)로 통일했다."""

import tkinter as tk
from datetime import datetime
from . import db as dbmod
from .ui_common import area_section_code, CL_BG, CL_NAVY, CL_GRID, win_button

# 5개 박스 및 그리드 타일이 공유하는 상태별 색상
STATUS_COLORS = {
    "완료": "#FFF3A0",
    "미완료": "#F6B6B6",
    "중복": "#AFCBEB",
    "추가": "#B7E3B0",
}
TILE_W, TILE_H = 74, 52  # 타일 하나 크기(px) - 그리드 열 수를 계산할 때 씀



def _code(area, section):
    """화면 표시용 코드: AREA-SECTION (예: 10-100)."""
    return area_section_code(area, section, sep="-")

class ProgressStatusScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._grid_cols = 15
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = tk.Frame(self, bg=CL_BG)
        top.pack(fill=tk.X, padx=12, pady=(10, 4))
        self.lbl_title = tk.Label(top, text="", bg=CL_BG, fg=CL_NAVY, font=("", 16, "bold"))
        self.lbl_title.pack(side=tk.LEFT)
        self.lbl_now = tk.Label(top, text="", bg=CL_BG, fg=CL_NAVY, font=("", 12))
        self.lbl_now.pack(side=tk.RIGHT)

        boxes = tk.Frame(self, bg=CL_BG)
        boxes.pack(fill=tk.X, padx=12, pady=(6, 6))
        self.box_labels = {}
        specs = [("총섹션", "#E3E6EE"), ("완료섹션", STATUS_COLORS["완료"]), ("미완료섹션", STATUS_COLORS["미완료"]),
                 ("중복섹션", STATUS_COLORS["중복"]), ("추가섹션", STATUS_COLORS["추가"])]
        for name, color in specs:
            box = tk.Frame(boxes, bg=CL_BG)
            box.pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(box, text=name, bg=CL_BG, font=("", 10, "bold")).pack()
            val = tk.Label(box, text="0", bg=color, width=10, height=2, font=("", 12, "bold"))
            val.pack()
            self.box_labels[name] = val

        right = tk.Frame(boxes, bg=CL_BG)
        right.pack(side=tk.RIGHT)
        tk.Label(right, text="진행률 -", bg=CL_BG).pack(side=tk.LEFT)
        # [2026-09-23 정정] sunken(입력칸처럼 파여 보이는) 스타일 대신, 점포코드
        # 표시칸과 같은 흰 배경+얇은 테두리(flat)로 통일해서 "값만 보여주는 칸"
        # 이라는 느낌을 맞췄다.
        self.lbl_ratio = tk.Label(right, text="0", bg="white", fg=CL_NAVY, width=8,
                                   font=("", 10, "bold"), relief="flat",
                                   highlightthickness=1, highlightbackground=CL_GRID)
        self.lbl_ratio.pack(side=tk.LEFT, padx=4, ipady=2)
        tk.Label(right, text="%", bg=CL_BG).pack(side=tk.LEFT)
        tk.Label(right, text="AREA 범위", bg=CL_BG).pack(side=tk.LEFT, padx=(20, 2))
        self.e_from = tk.Entry(right, width=6)
        self.e_from.pack(side=tk.LEFT, padx=2)
        tk.Label(right, text="~", bg=CL_BG).pack(side=tk.LEFT)
        self.e_to = tk.Entry(right, width=6)
        self.e_to.pack(side=tk.LEFT, padx=2)
        win_button(right, text="새로고침", command=self.refresh, kind="normal").pack(side=tk.LEFT, padx=(12, 4))
        win_button(right, text="발행", command=self.print_report, kind="normal").pack(side=tk.LEFT)

        # ---- SECTION 타일 그리드 (스크롤 가능) ----
        grid_wrap = tk.Frame(self, bg=CL_BG, highlightbackground=CL_GRID, highlightthickness=1)
        grid_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))
        self.canvas = tk.Canvas(grid_wrap, bg="white", highlightthickness=0)
        vsb = tk.Scrollbar(grid_wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.grid_inner = tk.Frame(self.canvas, bg="white")
        self._grid_win = self.canvas.create_window((0, 0), window=self.grid_inner, anchor="nw")
        self.grid_inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self._grid_win, width=event.width)
        cols = max(1, event.width // TILE_W)
        if cols != self._grid_cols:
            self._grid_cols = cols
            self._render_grid()

    def refresh(self):
        store_code = self.app.state.store_code
        store_name = self.app.state.store_name
        date = self.app.state.survey_date
        self.lbl_title.config(text=f"{store_name} ({store_code}) 재고조사 진행현황")
        self.lbl_now.config(text=datetime.now().strftime("%Y년 %m월 %d일 %H:%M:%S"))

        area_from = self.e_from.get().strip()
        area_to = self.e_to.get().strip()

        conn = dbmod.get_conn()
        plans = conn.execute(
            "SELECT area, section_from, section_to FROM planned_sections WHERE store_code=? AND survey_date=?",
            (store_code, date)
        ).fetchall()
        counted = conn.execute(
            "SELECT area, section, COUNT(DISTINCT worker_code) AS worker_cnt "
            "FROM stock_counts WHERE store_code=? AND survey_date=? GROUP BY area, section",
            (store_code, date)
        ).fetchall()
        acked = {
            (r["area"], r["section"]) for r in conn.execute(
                "SELECT area, section FROM dup_ack WHERE store_code=? AND survey_date=?", (store_code, date)
            )
        }
        conn.close()

        def area_ok(area):
            if area_from and str(area) < area_from:
                return False
            if area_to and str(area) > area_to:
                return False
            return True

        planned_set = set()
        for p in plans:
            if not area_ok(p["area"]):
                continue
            try:
                lo, hi = int(p["section_from"]), int(p["section_to"])
            except (TypeError, ValueError):
                continue
            for sec in range(lo, hi + 1):
                planned_set.add((p["area"], str(sec)))

        counted_map = {(r["area"], r["section"]): r for r in counted if area_ok(r["area"])}
        counted_set = set(counted_map.keys())

        done_set = planned_set & counted_set
        missing_set = planned_set - counted_set
        extra_set = counted_set - planned_set
        dup_set = {k for k, r in counted_map.items() if r["worker_cnt"] and r["worker_cnt"] > 1 and k not in acked}

        total_set = planned_set | counted_set
        self.box_labels["총섹션"].config(text=f"{len(total_set):,}")
        self.box_labels["완료섹션"].config(text=f"{len(done_set):,}")
        self.box_labels["미완료섹션"].config(text=f"{len(missing_set):,}")
        self.box_labels["중복섹션"].config(text=f"{len(dup_set):,}")
        self.box_labels["추가섹션"].config(text=f"{len(extra_set):,}")
        ratio = (len(done_set) * 100.0 / len(total_set)) if total_set else 0.0
        self.lbl_ratio.config(text=f"{ratio:.1f}")

        # 표(리스트) 대신 캡처와 같은 타일 그리드로 보여준다. 한 SECTION이
        # 여러 상태에 걸치면 중복 > 추가 > 완료 > 미완료 순으로 우선한다.
        # [2026-09-28] 더블클릭으로 그 AREA-SECTION만 인쇄할 수 있게(요청)
        # 코드/상태뿐 아니라 원래 area/section 값도 같이 들고 있는다.
        rows = []
        for k in sorted(total_set):
            if k in dup_set:
                status = "중복"
            elif k in extra_set:
                status = "추가"
            elif k in done_set:
                status = "완료"
            else:
                status = "미완료"
            rows.append((_code(k[0], k[1]), status, k[0], k[1]))
        self._rows = rows
        self._render_grid()

    def _render_grid(self):
        for w in self.grid_inner.winfo_children():
            w.destroy()
        rows = getattr(self, "_rows", [])
        cols = max(1, self._grid_cols)
        for i, (code, status, area, section) in enumerate(rows):
            r, c = divmod(i, cols)
            # height=2(텍스트 두 줄 높이)로 타일 세로 길이를 예전(height=1)의
            # 두 배로 늘렸다 - 코드 자체는 한 줄이라 위아래 여백이 늘어나는
            # 형태로 보인다.
            tile = tk.Label(self.grid_inner, text=code, bg=STATUS_COLORS[status], fg="#191C23",
                             font=("", 9, "bold"), relief="ridge", bd=1, width=9, height=2, cursor="hand2")
            tile.grid(row=r, column=c, sticky="nsew")
            # [2026-09-28] "에리어섹션 써져있는 네모칸을 더블 클릭시
            # 섹션별아이템재고현황 형식으로 프린터 인쇄로 연결" - 타일을
            # 더블클릭하면 그 AREA/SECTION의 품목 재고현황만 바로 인쇄한다.
            tile.bind("<Double-Button-1>", lambda e, a=area, s=section: self.print_section_item_status(a, s))

    def print_report(self):
        """[발행] 버튼: [2026-09-23] 예전엔 엑셀로 저장만 하고 "발행"이라고
        표시했는데, 재고조사 차이명세/재고조사 보고서/섹션별 결과보고서의
        [발행]과 똑같이 실제로 기본 프린터에 인쇄까지 하도록 통일했다.
        [2026-09-28 재수정] "발행버튼을 누르면 왜 엑셀저장이 뜨냐 - ZZOINT
        발행버튼 기능 참고해봐" - export_rows_to_excel()은 인쇄 전에 "다른
        이름으로 저장" 대화상자를 띄우는 [엑셀저장] 전용 함수라, [발행]에는
        저장 위치를 묻지 않는 print_rows_to_excel()(임시 폴더에 조용히
        만든 뒤 경로만 돌려줌)을 쓰도록 바꿨다 - ZZOINT의 [발행]처럼 버튼
        한 번으로 바로 인쇄까지 끝난다(엑셀로 만든 뒤 os.startfile(path,
        "print")로 그 파일의 기본 인쇄 동작을 호출 - Windows 전용, 그 외
        OS는 파일 저장까지만)."""
        from tkinter import messagebox
        from .ui_common import print_rows_to_excel, print_excel_file, file_date
        if not getattr(self, "_rows", None):
            messagebox.showinfo("알림", "인쇄할 데이터가 없습니다.")
            return
        headers = ("A_SECTION", "상태")
        # [2026-09-28] self._rows에 더블클릭용 area/section이 추가되면서
        # (code, status, area, section) 4개짜리로 바뀌었는데, 여기 헤더는
        # 여전히 2개(A_SECTION/상태)라 앞 2개만 잘라서 내보낸다.
        export_data = [row[:2] for row in self._rows]
        path = print_rows_to_excel(export_data, headers, default_name=f"재고조사진행현황_{file_date(self.app)}.xlsx")
        if not path:
            return
        print_excel_file(path)

    def print_section_item_status(self, area, section):
        """[2026-09-28] 진행현황 타일(AREA-SECTION 칸)을 더블클릭하면, 그
        AREA/SECTION 하나만 걸러서 "섹션별 아이템 재고현황" 화면
        (screen_section_item_status.py)과 똑같은 형식(LOCATION/바코드/
        도서명/재고수량)으로 바로 인쇄한다 - 표만 다른 화면이라 별도 필터
        화면을 거치지 않고 타일 더블클릭 한 번으로 바로 인쇄까지 끝낸다."""
        from tkinter import messagebox
        from .ui_common import print_rows_to_excel, print_excel_file, file_date, normalize_area, digit_code_variants

        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        conn = dbmod.get_conn()
        # [2026-09-28 버그수정] area/section을 그대로 "=?"로 비교하면 이
        # 타일이 들고 있는 값(집계 시 normalize_area()를 거친 "01" 같은
        # 0채움 형태)과 실제 stock_counts에 저장된 값(옛 데이터는 0채움
        # 없이 "1")이 서로 달라 못 찾는 경우가 있어(실적관리 조회와 같은
        # 문제), 0채움 후보를 모두 넣어 찾는다.
        area_variants = digit_code_variants(area, 2)
        section_variants = digit_code_variants(section, 3)
        area_ph = ",".join("?" for _ in area_variants)
        section_ph = ",".join("?" for _ in section_variants)
        rows = conn.execute(
            f"SELECT area, section, shelf_no, dan, yeol, isbn, book_name, qty "
            f"FROM stock_counts WHERE store_code=? AND survey_date=? "
            f"AND area IN ({area_ph}) AND section IN ({section_ph}) "
            "ORDER BY CAST(dan AS INTEGER), dan, CAST(yeol AS INTEGER), yeol, shelf_no",
            (store_code, date, *area_variants, *section_variants)
        ).fetchall()
        conn.close()

        if not rows:
            messagebox.showinfo("알림", f"{_code(area, section)}에 실사 데이터가 없습니다.")
            return

        data = []
        for r in rows:
            a = normalize_area(r["area"])
            location = f"{a}-{r['section']}-{r['shelf_no']}-{r['dan']}-{r['yeol']}"
            data.append((location, r["isbn"], r["book_name"], r["qty"]))

        headers = ("LOCATION", "바코드", "도서명", "재고수량")
        default_name = f"섹션별아이템재고현황_{_code(area, section)}_{file_date(self.app)}.xlsx"
        path = print_rows_to_excel(data, headers, default_name=default_name)
        if not path:
            return
        print_excel_file(path)
