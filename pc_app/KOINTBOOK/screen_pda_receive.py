# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""재고실사수신 > PDA Data 수신 화면.

[2026-10-08] ZZOINT(원본) PDA DATA 수신 화면의 중복 기능을 가져왔다.
  - 재전송 중복: 이미 저장된 자료/수신 대기 자료와 (AREA, SECTION, 서가번호, 단, 열, 바코드,
    실사일시)가 완전히 같은 줄은 분홍색으로 표시하고 "중복데이터 N건" 안내를 띄운다.
  - 중복 섹션: 같은 AREA-SECTION을 서로 다른 작업자가 스캔했으면(Section Check의 [중복 Section]과
    같은 기준) 그 줄들을 분홍색으로 표시하고, 아래 [중복 섹션 목록]에 저장됨/대기(저장전)로 나눠
    보여준다. 체크한 쪽을 [선택 섹션 삭제]하면 저장됨은 PC에서 실제 삭제, 대기는 목록에서만 삭제.
  - 중복이 뜬 채로 삭제 없이 [저장]하면 "그대로 두기로 확인한 것"으로 보고 그 섹션은 더 이상
    중복으로 표시하지 않는다(기존 dup_ack 표 - Section Check의 [중복 인지]와 같은 기록).

동작 방식
---------
1) [⬇ PDA Data 수신] : ZZOINT의 [DATA 수신] 버튼과 완전히 동일하게, adb로
   PDA가 USB 연결되어 있는지 확인하고 STOCK.db를 pull 받아서 그대로 "수신
   대기(아직 저장 전)" 목록(위 표)에 쌓는다. 그 외의 경로는 없다 - 연결이
   안 됐거나 pull/읽기가 실패하면 그 원인을 오류창으로 보여줄 뿐이다.
   [2026-09-23 정정] 예전에는 여기서 adb가 실패하면 자동으로 엑셀 파일
   선택창이 뜨게 해뒀었는데, ZZOINT의 PDA Data 수신 화면(screen_pda_receive.py)
   전체를 다시 확인해보니 거기에는 엑셀로 "불러오는" 기능 자체가 없다(엑셀은
   "엑셀저장"으로 내보낼 때만 쓰인다) - PDA수신 화면에 엑셀 불러오기를 넣은
   건 KOINTBOOK에서 잘못 추가한 기능이었어서, 버튼과 관련 코드를 전부 뺐다.
2) 위 표에서 잘못 들어온 줄은 선택 후 [삭제]로 뺄 수 있다.
3) [저장] : 수신 대기 중인 자료를 실제 실사자료(stock_counts)에 반영한다.
   저장하고 나면 위 표는 비워지고, 이후 [자료생성]/[실적관리]/[재고조사
   차이명세] 등 다른 화면에서 이 데이터를 사용할 수 있다.

작업자별 실사 집계(아래 표)는 [2026-09-23 정정] 더 이상 별도의 [재집계]
버튼이 없다 - 수신하거나 삭제할 때마다 recalc_summary()가 자동으로 다시
계산해서 항상 최신 상태로 보여준다.

[2026-09-23 재정정] recalc_summary()가 화면 맨 위의 "수신 대기(아직 저장
전)" 목록(self.staged)만 집계하고 있어서, [저장]을 누르고 나면(=staged가
비워지면) 방금까지 보이던 집계가 같이 사라지는 문제가 있었다. ZZOINT의
PDA DATA 수신 화면은 이 집계를 [실적관리] 화면과 완전히 똑같은 기준(필터
없이 PC에 이미 저장된 stock_counts 전체)으로 계산해서 "수신 대기 목록"과는
무관하게 항상 지금까지 쌓인(저장된) 데이터를 보여준다 - KOINTBOOK도 이제
그렇게 고쳐서, [저장]을 반복해도 집계가 계속 누적되어 보이고 [실적관리]
화면의 [전체조회(전점포)]와 항상 같은 합계가 나온다.

[2026-09-28] ZZOINT(원본)처럼 작업자별 실사집계 표 옆에 막대그래프를
추가했다(작업자별 실사건수 비율을 한눈에 비교). 작업자가 많아도(10명
이상) 한 화면에서 바로 보이도록, 위쪽 "수신 대기" 목록 높이를 줄이고
아래 "작업자별 실사집계" 목록 높이를 늘렸다. 하단 버튼도 ZZOINT와 같은
순서(새로고침 -> 엑셀저장 -> (오른쪽) 실사자료 전체삭제)로 맞췄다."""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk
from collections import defaultdict
from datetime import datetime
from . import db as dbmod
from . import adb_utils
from . import barcode_kind
from .progress_dialog import run_with_progress
from .ui_common import (
    COLOR_HEADER_BG, setup_treeview, export_rows_to_excel,
    today_str, split_scan_datetime, CL_BG, CL_NAVY, CL_GOLD, CL_TEXT_DIM, win_button
)

# [2026-09-28] 작업자별 실사집계 막대그래프에 쓰는 색상 순환(ZZOINT와 동일).
COLOR_DUP_ROW = "#FADADD"  # [2026-10-08] 중복 강조(ZZOINT와 같은 분홍)
COLOR_KIND_BAD_ROW = "#FF9E9E"  # [2026-10-16] 서적/문구 AREA와 안 맞는 줄(중복의 연분홍보다 진한 빨강)
BAR_COLORS = [CL_NAVY, CL_GOLD, "#5F6470", "#7C9AC7", "#8A6D2E", "#3E5C8A"]

STAGE_COLUMNS = ("no", "area", "section", "shelf_no", "dan", "yeol", "isbn", "book_name",
                 "qty", "worker_code", "worker_name", "scan_date", "scan_time", "store_code")
STAGE_HEADINGS = ("NO", "AREA", "SECTION", "서가번호", "단", "열", "바코드", "상품명",
                  "실사수량", "작업자코드", "작업자명", "실사일자", "실사시간", "점포코드")
# [2026-09-23 정정] "SECTION" 컬럼이 좁아서 마지막 글자(N)가 잘려 보였다 -
# 헤더 글자가 안 잘리도록 폭을 넉넉하게 늘렸다.
STAGE_WIDTHS = (40, 60, 95, 70, 45, 45, 120, 220, 70, 90, 90, 95, 85, 100)


class PdaReceiveScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self.staged = []  # 아직 저장하지 않은 수신 대기 목록 (dict 리스트)
        self._build_ui()
        self.refresh()

    def refresh(self):
        self._render_staged()
        self.recalc_summary()
        self._refresh_duplicate_check()

    def _build_ui(self):
        top = tk.Frame(self, bg=COLOR_HEADER_BG, highlightbackground="#C4C8D0", highlightthickness=1)
        top.pack(fill=tk.X, padx=4, pady=(4, 2))
        tk.Label(top, text="점포코드", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=0, column=0, padx=(12, 4), pady=10)
        self.lbl_store_code = tk.Label(top, text=self.app.state.store_code, bg=COLOR_HEADER_BG, font=("", 11, "bold"))
        self.lbl_store_code.grid(row=0, column=1, padx=(0, 20))
        tk.Label(top, text="점포명", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=0, column=2, padx=(0, 4))
        self.lbl_store_name = tk.Label(top, text=self.app.state.store_name, bg=COLOR_HEADER_BG, font=("", 11, "bold"))
        self.lbl_store_name.grid(row=0, column=3, padx=(0, 20))
        tk.Label(top, text="조사일자", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=0, column=4, padx=(0, 4))
        self.lbl_date = tk.Label(top, text=self.app.state.survey_date, bg=COLOR_HEADER_BG, font=("", 11, "bold"))
        self.lbl_date.grid(row=0, column=5, padx=(0, 20))

        # [2026-09-23 정정] "재집계" 버튼은 없앴다(수신/삭제할 때마다
        # recalc_summary()를 이미 자동으로 다시 부르고 있어서 따로 누를
        # 일이 없었다) - 그래서 옆에 맞추려고 키워뒀던 [⬇ PDA Data 수신]
        # 버튼의 세로 길이(ipady/ipadx)도 다른 버튼들과 같은 기본 높이로
        # 되돌렸다.
        win_button(top, text="⬇ PDA Data 수신", command=self.receive_from_pda, kind="accent").grid(row=0, column=6, padx=(20, 8))

        mid = tk.Frame(self, bg=CL_BG)
        mid.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        # [2026-09-23 정정] container를 expand=True로 두면 창 크기에 따라
        # 목록 폭이 늘었다 줄었다 해서, 마지막 컬럼(점포코드)이 잘려 보이거나
        # 옆의 저장/삭제 버튼과 사이가 붕 뜨는 문제가 있었다 - 폭을 컬럼
        # 합계(+약간의 여유)에 맞춰 고정해서, 목록 폭이 마지막 항목(점포코드)
        # 끝보다 살짝 더 넓게 나오고 저장/삭제 버튼이 항상 목록 바로 옆에
        # 붙게 했다.
        # [2026-09-28] 아래 "작업자별 실사집계" 목록이 10명 이상 한 화면에
        # 보이도록, 이 "수신 대기" 목록 높이를 13 -> 7로 줄였다.
        container, self.tree = setup_treeview(mid, STAGE_COLUMNS, STAGE_HEADINGS, STAGE_WIDTHS, height=7)
        # [2026-10-15] 창을 줄이면 저장/삭제 버튼이 목록 오른쪽 밖으로 밀려 안 보여서, 버튼을
        # 먼저(오른쪽 끝) 배치하고 목록이 남는 폭만큼만 차지하게(넘치면 가로 스크롤) 바꿨다.
        # 단, 창을 넓히면 버튼이 멀리 떨어져 보여서 넓을 때는 목록 바로 옆으로 붙인다(아래 _place_side).
        # 창이 넓으면 버튼이 목록 바로 옆에, 좁아 목록과 같이 못 들어가면 오른쪽 끝에 놓는다.
        side_btns = tk.Frame(mid, bg=CL_BG)
        self._side_mode = None

        def _place_side(_e=None):
            need = container.winfo_reqwidth() + side_btns.winfo_reqwidth() + 16
            mode = "near" if mid.winfo_width() >= need else "edge"
            if mode == self._side_mode:
                return
            self._side_mode = mode
            container.pack_forget()
            side_btns.pack_forget()
            if mode == "near":
                container.pack(side=tk.LEFT, fill=tk.Y)
                side_btns.pack(side=tk.LEFT, fill=tk.Y, padx=6)
            else:
                side_btns.pack(side=tk.RIGHT, fill=tk.Y, padx=6)
                container.pack(side=tk.LEFT, fill=tk.Y)
        mid.bind("<Configure>", _place_side)
        _place_side()

        self.tree.tag_configure("dup", background=COLOR_DUP_ROW)
        self.tree.tag_configure("kindbad", background=COLOR_KIND_BAD_ROW)
        win_button(side_btns, text="저장", width=8, command=self.save_staged, kind="accent").pack(pady=(40, 6))
        win_button(side_btns, text="삭제", width=8, command=self.delete_selected_staged, kind="danger").pack()

        # ---- 중복 로케이션 목록 (이미 저장된 자료 + 저장 전 자료) ----
        self.dup_label = tk.Label(self, text="중복 섹션 목록", fg="#666666", bg=CL_BG)
        self.dup_default_font = self.dup_label.cget("font")
        self.dup_label.pack(anchor="w", padx=8, pady=(6, 2))
        self.dup_checked = set()
        dup_wrap = tk.Frame(self, bg=CL_BG)
        dup_wrap.pack(fill=tk.X, padx=8)
        dup_container, self.dup_tree = setup_treeview(
            dup_wrap, ("check", "location", "worker_code", "worker_name", "count", "qty", "status"),
            ("선택", "AREA-SECTION", "작업자코드", "작업자명", "건수", "수량", "상태"),
            (50, 160, 100, 130, 70, 80, 110), height=3
        )
        dup_container.pack(side=tk.LEFT, fill=tk.Y)
        self.dup_tree.configure(selectmode="none")
        self.dup_tree.bind("<Button-1>", self._on_dup_tree_click)
        win_button(dup_wrap, text="선택 섹션 삭제", command=self.delete_selected_duplicates,
                   kind="danger").pack(side=tk.LEFT, padx=8, anchor="n")

        # ---- 작업자별 실사집계 + 막대그래프 ----
        # [2026-09-28] ZZOINT처럼 집계 표 옆에 막대그래프를 추가했다. 목록
        # 높이도 6 -> 12로 늘려서 작업자가 10명 이상이어도 스크롤 없이 대부분
        # 한 화면에 보인다(그래도 더 많으면 목록/그래프 모두 스크롤된다).
        tk.Label(self, text="작업자별 실사 집계", font=("", 10, "bold"), bg=CL_BG).pack(anchor="w", padx=8, pady=(6, 0))
        summary_row = tk.Frame(self, bg=CL_BG)
        summary_row.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 4))

        container2, self.tree_summary = setup_treeview(
            summary_row, ("no", "worker", "count", "qty", "ratio"),
            ("NO", "작업자", "실사건수", "실사총수량", "비율"),
            (45, 160, 90, 100, 80), height=8
        )
        container2.pack(side=tk.LEFT, fill=tk.Y)

        # 막대그래프 캔버스: 작업자가 많아 캔버스 보이는 영역보다 그래프가
        # 길어져도(예: 40명) 세로 스크롤로 전부 볼 수 있게 스크롤바를 같이
        # 붙인다(ZZOINT와 동일한 방식). 그릴 때마다 실제 그려진 높이만큼
        # 스크롤 범위를 다시 잡는다.
        chart_frame = tk.Frame(summary_row, bg=CL_BG)
        chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
        self.summary_canvas = tk.Canvas(chart_frame, bg="white",
                                        highlightthickness=1, highlightbackground="#C4C8D0")
        chart_vsb = ttk.Scrollbar(chart_frame, orient="vertical", command=self.summary_canvas.yview)
        self.summary_canvas.configure(yscrollcommand=chart_vsb.set)
        self.summary_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chart_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        # 마우스 휠로도 그래프를 스크롤할 수 있게(다른 스크롤 목록들과 동일).
        self.summary_canvas.bind("<Enter>", lambda e: self.summary_canvas.bind_all(
            "<MouseWheel>", lambda ev: self.summary_canvas.yview_scroll(int(-ev.delta / 40), "units")))
        self.summary_canvas.bind("<Leave>", lambda e: self.summary_canvas.unbind_all("<MouseWheel>"))

        bottom = tk.Frame(self, bg=CL_BG)
        bottom.pack(fill=tk.X, padx=8, pady=8)
        # [2026-09-28] 요청에 따라 "엑셀저장"과 "실사자료 전체삭제" 버튼의
        # 자리를 서로 바꿨다(ZZOINT와 동일한 배치 - 엑셀저장은 새로고침 옆에,
        # 위험한 동작인 실사자료 전체삭제는 오른쪽 끝에).
        win_button(bottom, text="새로고침", command=self.refresh, kind="normal").pack(side=tk.LEFT)
        win_button(bottom, text="엑셀저장", command=self.export_excel, kind="normal").pack(side=tk.LEFT, padx=(28, 0))
        win_button(bottom, text="실사자료 전체삭제", command=self.delete_all_committed, kind="danger").pack(side=tk.RIGHT)

    # ---- 수신 ----
    def receive_from_pda(self):
        """[⬇ PDA Data 수신] - ZZOINT의 [DATA 수신]과 동일: adb로 PDA 연결을
        확인하고 STOCK.db를 pull 받는다. 실패하면(연결 안 됨/pull 실패/읽기
        실패) 그 원인을 오류창으로 그대로 보여줄 뿐, 다른 방법으로 전환하지
        않는다(ZZOINT에도 엑셀로 불러오는 대체 경로가 없다)."""
        import tempfile
        import os
        import sqlite3

        tmp_path = os.path.join(tempfile.gettempdir(), "STOCK.db")

        def work(progress):
            progress(message="PDA 연결 확인 중...", done=0, total=0)
            ok, msg = adb_utils.check_device_connected()
            if not ok:
                return ("no_device", msg)

            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            ok2, msg2 = adb_utils.pull_file("STOCK.db", tmp_path, progress)
            if not ok2:
                return ("pull_failed", msg2)

            progress(message="받은 파일을 읽는 중...", done=0, total=0)
            try:
                conn = sqlite3.connect(tmp_path)
                conn.row_factory = sqlite3.Row
                rows = [dict(r) for r in conn.execute("SELECT * FROM stock_data").fetchall()]
                conn.close()
            except Exception as e:  # noqa: BLE001
                return ("read_failed", str(e))
            return ("ok", rows)

        def done(result, error):
            if error is not None:
                messagebox.showerror("오류", f"PDA Data 수신 중 오류: {error}")
                return
            kind, payload = result
            if kind == "no_device":
                messagebox.showerror("오류", payload)
            elif kind == "pull_failed":
                messagebox.showerror(
                    "오류",
                    "PDA Data 수신 실패\nPDA에서 [Data 전송]을 먼저 눌렀는지 확인하세요.\n\n"
                    f"({payload})"
                )
            elif kind == "read_failed":
                messagebox.showerror("오류", f"STOCK.db 파일을 읽는 중 오류: {payload}")
            elif not payload:
                messagebox.showinfo("알림", "새로 받을 데이터가 없습니다.")
            else:
                self._append_staged(payload)
                try:
                    adb_utils.remove_remote_file("STOCK.db")
                except Exception:
                    pass

        run_with_progress(self, "PDA Data 수신", work, done, cancelable=True,
                          initial_message="PDA에서 실사 데이터 받는 중...")

    @staticmethod
    def _row_key(r):
        """재전송 중복 판정 키: 같은 위치/바코드를 같은 시각에 스캔한 같은 줄인지."""
        return (str(r.get("area") or ""), str(r.get("section") or ""), str(r.get("shelf_no") or ""),
                str(r.get("dan") or ""), str(r.get("yeol") or ""), str(r.get("isbn") or ""),
                str(r.get("received_at") or ""))

    @staticmethod
    def _loc_of(r):
        """중복 판정 단위: AREA-SECTION (Section Check의 [중복 Section]과 같은 단위)."""
        return f"{r.get('area') or ''}-{r.get('section') or ''}"

    def _append_staged(self, rows):
        for r in rows:
            r.setdefault("received_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        # 재전송 중복: 이미 저장된(PC 기준 점포/조사일자) 자료 + 이미 수신 대기 중인 자료와 비교
        existing = {self._row_key(r) for r in self.staged}
        conn = dbmod.get_conn()
        for row in conn.execute(
            "SELECT area, section, shelf_no, dan, yeol, isbn, received_at FROM stock_counts "
            "WHERE store_code=? AND survey_date=?",
            (self.app.state.store_code, self.app.state.survey_date)
        ):
            existing.add(self._row_key(dict(row)))
        conn.close()
        dup_count = 0
        for r in rows:
            k = self._row_key(r)
            r["_dup"] = k in existing
            existing.add(k)
            if r["_dup"]:
                dup_count += 1
        self.staged.extend(rows)
        kind_bad = self._flag_kind_mismatch(rows)
        self._render_staged()
        loc_dup = self._refresh_duplicate_check()
        self._warn_if_mismatch(rows)
        if kind_bad:
            self._warn_kind_mismatch(kind_bad)
        if dup_count:
            messagebox.showwarning(
                "중복 데이터",
                f"중복데이터 {dup_count:,}건이 있습니다.\n"
                "목록에서 분홍색으로 표시된 줄을 확인한 뒤 [삭제]하거나, 그대로 [저장]해 확정하세요.")
        else:
            messagebox.showinfo("수신 완료", f"{len(rows):,}건을 수신했습니다. (아직 저장 전 - [저장]을 눌러야 반영됩니다)")
        if loc_dup:
            messagebox.showwarning(
                "중복 섹션",
                f"같은 섹션을 서로 다른 작업자가 중복으로 스캔했습니다 ({loc_dup:,}개 섹션).\n"
                "목록의 분홍색 줄과 아래 [중복 섹션 목록]을 확인하고, 필요없는 작업자 자료를 선택해 삭제하세요.")

    def _flag_kind_mismatch(self, rows):
        """[2026-10-16] 서적 AREA에 문구 상품, 문구 AREA에 서적 상품이 들어 있는 줄을 찾아 r["_kind_bad"]에
        정보를 달고(맞으면 None), 어긋난 줄 목록 [(줄, 정보)]를 돌려준다. PDA 앱이 이미 막지만, 옛 버전 앱이나
        다른 경로로 올라온 자료를 PC에서도 한 번 더 거른다. 판정 기준은 barcode_kind.py(상품마스터 우선, 없으면
        바코드 모양)."""
        if not rows:
            return []
        store_code = (self.app.state.store_code or "").strip()
        conn = dbmod.get_conn()
        try:
            results = barcode_kind.check_many(
                conn, store_code, [(r.get("area"), r.get("isbn")) for r in rows])
        finally:
            conn.close()
        bad = []
        for r, m in zip(rows, results):
            r["_kind_bad"] = m
            if m:
                bad.append((r, m))
        return bad

    def _warn_kind_mismatch(self, bad):
        try:
            self.bell()
        except tk.TclError:
            pass
        lines = [f"서적/문구 구분이 AREA와 맞지 않는 줄이 {len(bad):,}건 있습니다.",
                 "목록에서 진한 빨간색으로 표시됩니다.\n"]
        for r, m in bad[:8]:
            lines.append(f"· {r.get('area') or ''}-{r.get('section') or ''}  {barcode_kind.short(m)}")
        if len(bad) > 8:
            lines.append(f"  … 외 {len(bad) - 8:,}건")
        lines.append("\n이 줄들이 남아 있으면 [저장]되지 않습니다.\n"
                     "빨간 줄을 선택해 [삭제]한 뒤 저장하거나, PDA에서 올바른 AREA로 다시 입력해 받으세요.\n"
                     "(서적 AREA 10~19·90~99 / 문구 AREA 20~29·80~89)")
        messagebox.showwarning("서적/문구 구분 오류", "\n".join(lines))

    def _warn_if_mismatch(self, rows):
        """[2026-09-30] "PC쪽 조사일자가 PDA랑 안맞으면 차이내역, 자료생성등
        항상 오류가 나오니 ... PC와 PDA 정보가 다를경우 항상 경고창이나 변경
        방향을 제시" - PDA가 STOCK.db에 실어보내는 각 줄에는 실제로 그 줄을
        스캔할 당시의 점포코드/조사일자(store_code/store_name/survey_date)가
        같이 들어있다(DataManageActivity.kt의 exportAllToStockDb 참고). 그런데
        지금까지는 이 값을 화면에 표시하거나 확인하는 곳이 전혀 없었고,
        [저장]을 누르면 무조건 "현재 PC 화면에 선택된" 점포/조사일자로
        덮어써버렸다(save_staged 참고) - PC 쪽이 최근에 다른 점포/날짜를
        보고 있었다면, 방금 받은 PDA 데이터가 전혀 다른 조사일자로 조용히
        저장되어 [재고조사 차이명세]/[자료생성] 등에서 "자료가 없다"거나
        엉뚱한 결과로 보이는 원인이 됐다.

        이제 받은 줄들의 점포코드/조사일자를 뽑아서 현재 PC 화면 값과
        다르면 바로 경고창을 띄우고, PDA 쪽 값으로 PC 화면을 맞출지
        물어본다(예 -> app.state를 PDA 값으로 바꾸고 저장 -> 다음부터 이
        점포/일자 기준으로 조회됨). 저장 자체는 save_staged()가 각 줄에
        실려온 PDA의 실제 값을 그대로 쓰도록 이미 고쳤으니, 여기서 아니오를
        선택해도 데이터가 잘못된 점포/일자로 저장되는 일은 없다 - 이 경고는
        어디까지나 "PC 화면(조회 기준)을 PDA가 실제로 작업한 시점에 맞출지"
        를 안내하는 것이다."""
        # [2026-10-08] 저장 기준을 PC 상품마스터 기준(app.state)으로 통일했으므로, 여기서는
        # PC 화면을 PDA 값으로 바꾸자고 묻지 않고 "PC 기준으로 저장된다"는 안내만 한다.
        pc_store = (self.app.state.store_code or "").strip()
        pc_date = (self.app.state.survey_date or "").strip()
        store_codes = sorted({(r.get("store_code") or "").strip() for r in rows if (r.get("store_code") or "").strip()})
        dates = sorted({(r.get("survey_date") or "").strip() for r in rows if (r.get("survey_date") or "").strip()})
        diff_stores = [x for x in store_codes if x != pc_store]
        diff_dates = [x for x in dates if x != pc_date]
        if not diff_stores and not diff_dates:
            return
        lines = ["지금 받은 PDA 실사 데이터에 PC 기준과 다른 값이 있습니다.\n",
                 f"PC 기준(상품마스터) : [{pc_store}] {self.app.state.store_name} / {pc_date}"]
        if diff_stores:
            lines.append(f"PDA 점포코드 : {', '.join(store_codes)}")
        if diff_dates:
            lines.append(f"PDA 조사일자 : {', '.join(dates)}")
        lines.append("\n[저장]하면 모든 자료가 PC 기준 점포코드/조사일자 하나로 저장됩니다.\n"
                     "(실사 중 날짜가 넘어가 2개 날짜로 나뉜 자료도 하나로 합쳐집니다.)")
        messagebox.showinfo("점포/조사일자 확인", "\n".join(lines))

    # ------------------------------------------------------------------
    # 중복 로케이션 (같은 로케이션을 서로 다른 작업자가 스캔) - ZZOINT 이식
    # ------------------------------------------------------------------
    def _scope(self):
        return self.app.state.store_code, self.app.state.survey_date

    def _duplicate_map(self):
        """2명 이상의 작업자가 스캔한 섹션(AREA-SECTION) -> 작업자 조합 문자열.
        이미 저장된 자료(PC 기준 점포/조사일자)와 수신 대기 자료를 함께 본다."""
        loc_workers = defaultdict(set)
        conn = dbmod.get_conn()
        for row in conn.execute(
            "SELECT DISTINCT area, section, worker_code, worker_name FROM stock_counts "
            "WHERE store_code=? AND survey_date=?", self._scope()
        ):
            loc_workers[self._loc_of(dict(row))].add((row["worker_code"], row["worker_name"]))
        conn.close()
        for r in self.staged:
            loc_workers[self._loc_of(r)].add((r.get("worker_code"), r.get("worker_name")))
        result = {}
        for loc, workers in loc_workers.items():
            if len({str(code or "") for code, _n in workers}) > 1:
                result[loc] = ",".join(sorted({str(code or "") for code, _n in workers}))
        return result

    def _acknowledge_current_duplicates(self):
        """지금 떠 있는 중복 섹션을 "그대로 두기로 확인"(dup_ack)한다."""
        dup_map = self._duplicate_map()
        if not dup_map:
            return
        store_code, date = self._scope()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = dbmod.get_conn()
        try:
            conn.executemany(
                "INSERT OR IGNORE INTO dup_ack(store_code, survey_date, area, section, acked_at) VALUES (?,?,?,?,?)",
                [(store_code, date, *(loc.split("-", 1) + [""])[:2], now) for loc in dup_map])
            conn.commit()
        finally:
            conn.close()

    def _current_duplicate_locations(self):
        store_code, date = self._scope()
        conn = dbmod.get_conn()
        try:
            acked = {f"{r['area']}-{r['section']}" for r in conn.execute(
                "SELECT area, section FROM dup_ack WHERE store_code=? AND survey_date=?", (store_code, date))}
        finally:
            conn.close()
        return {loc for loc in self._duplicate_map() if loc not in acked}

    def _refresh_duplicate_check(self):
        """중복 로케이션 목록을 다시 채우고, 수신 대기 목록의 중복 줄을 분홍색으로 칠한다.
        중복 로케이션 개수를 돌려준다."""
        dup_locations = self._current_duplicate_locations()
        self.dup_checked.clear()
        for item in self.dup_tree.get_children():
            self.dup_tree.delete(item)

        if not dup_locations:
            self.dup_label.config(text="중복 섹션 목록", fg="#666666", font=self.dup_default_font)
        else:
            saved_agg = {}
            conn = dbmod.get_conn()
            for row in conn.execute(
                """SELECT area, section, worker_code, worker_name, COUNT(*) AS cnt,
                          IFNULL(SUM(qty),0) AS qty FROM stock_counts WHERE store_code=? AND survey_date=?
                   GROUP BY area, section, worker_code, worker_name""", self._scope()
            ):
                loc = self._loc_of(dict(row))
                if loc in dup_locations:
                    saved_agg[(loc, row["worker_code"] or "")] = (row["cnt"], row["qty"], row["worker_name"])
            conn.close()
            pending_agg = {}
            for r in self.staged:
                loc = self._loc_of(r)
                if loc not in dup_locations:
                    continue
                key = (loc, r.get("worker_code") or "")
                agg = pending_agg.setdefault(key, [0, 0, r.get("worker_name")])
                agg[0] += 1
                agg[1] += int(r.get("qty") or 0)
            idx = 0
            for (loc, wc), (cnt, qty, wn) in sorted(saved_agg.items()):
                self.dup_tree.insert("", tk.END, iid=f"saved|{loc}|{wc}",
                                     values=("☐", loc, wc, wn, f"{cnt:,}", f"{qty:,}", "저장됨"),
                                     tags=("odd",) if idx % 2 else ())
                idx += 1
            for (loc, wc), (cnt, qty, wn) in sorted(pending_agg.items()):
                self.dup_tree.insert("", tk.END, iid=f"pending|{loc}|{wc}",
                                     values=("☐", loc, wc, wn, f"{cnt:,}", f"{qty:,}", "대기(저장전)"),
                                     tags=("odd",) if idx % 2 else ())
                idx += 1
            self.dup_label.config(
                text=f"⚠ 중복 섹션 정리 필요: {len(dup_locations):,}개 섹션이 여러 작업자에게 중복 스캔되었습니다. "
                     "체크한 쪽을 삭제하세요('저장됨'은 PC에서 실제 삭제, '대기(저장전)'는 목록에서만 삭제).",
                fg="#C2185B", font=("", 10, "bold"))

        for i, iid in enumerate(self.tree.get_children()):
            if i < len(self.staged):
                r = self.staged[i]
                is_dup = r.get("_dup") or self._loc_of(r) in dup_locations
                if r.get("_kind_bad"):
                    self.tree.item(iid, tags=("kindbad",))
                else:
                    self.tree.item(iid, tags=("dup",) if is_dup else (("odd",) if i % 2 else ()))
        return len(dup_locations)

    def _on_dup_tree_click(self, event):
        if self.dup_tree.identify_region(event.x, event.y) != "cell":
            return
        row = self.dup_tree.identify_row(event.y)
        if not row or self.dup_tree.identify_column(event.x) != "#1":
            return
        if row in self.dup_checked:
            self.dup_checked.discard(row)
            self.dup_tree.set(row, "check", "☐")
        else:
            self.dup_checked.add(row)
            self.dup_tree.set(row, "check", "☑")

    def delete_selected_duplicates(self):
        if not self.dup_checked:
            messagebox.showinfo("알림", "삭제할 섹션/작업자를 체크박스로 선택하세요.")
            return
        saved_pairs, pending_pairs = [], set()
        for iid in self.dup_checked:
            source, loc, wc = iid.split("|", 2)
            (saved_pairs.append((loc, wc)) if source == "saved" else pending_pairs.add((loc, wc)))
        if not messagebox.askyesno(
                "확인",
                f"선택한 {len(self.dup_checked):,}건을 삭제할까요?\n"
                f"('저장됨' {len(saved_pairs):,}건은 PC에서 실제로 삭제되고, "
                f"'대기(저장전)' {len(pending_pairs):,}건은 저장 전 목록에서만 삭제됩니다)"):
            return
        if saved_pairs:
            store_code, date = self._scope()
            conn = dbmod.get_conn()
            for loc, wc in saved_pairs:
                area, section = (loc.split("-", 1) + [""])[:2]
                conn.execute(
                    "DELETE FROM stock_counts WHERE store_code=? AND survey_date=? AND area=? AND section=? "
                    "AND IFNULL(worker_code,'')=?",
                    (store_code, date, area, section, wc))
            conn.commit()
            conn.close()
            dbmod.bump_stock_version()
        if pending_pairs:
            self.staged = [r for r in self.staged
                           if (self._loc_of(r), r.get("worker_code") or "") not in pending_pairs]
            self._render_staged()
        n = len(self.dup_checked)
        self.recalc_summary()
        self._refresh_duplicate_check()
        messagebox.showinfo("완료", f"{n:,}건을 삭제했습니다.")

    def _render_staged(self):
        self.lbl_store_code.config(text=self.app.state.store_code)
        self.lbl_store_name.config(text=self.app.state.store_name)
        self.lbl_date.config(text=self.app.state.survey_date)
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.staged, start=1):
            self.tree.insert("", tk.END, values=(
                i, r.get("area", ""), r.get("section", ""), r.get("shelf_no", ""), r.get("dan", ""),
                r.get("yeol", ""), r.get("isbn", ""), r.get("book_name", ""), f"{int(r.get('qty') or 0):,}",
                r.get("worker_code", ""), r.get("worker_name", ""),
                *split_scan_datetime(r.get("received_at", "")),
                (r.get("store_code") or "").strip() or self.app.state.store_code
            ), tags=("kindbad",) if r.get("_kind_bad") else (("odd",) if i % 2 == 0 else ()))

    def delete_selected_staged(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("알림", "삭제할 줄을 선택하세요.")
            return
        idxs = sorted((self.tree.index(s) for s in sel), reverse=True)
        for idx in idxs:
            del self.staged[idx]
        self._render_staged()
        self._refresh_duplicate_check()

    # ---- 저장 ----
    def save_staged(self):
        """[2026-09-30] "PC와 PDA 정보가 다를경우 ... 설정한 값이나, PC마스터에
        따라 변동되도록" - 예전엔 여기서 무조건 "현재 PC 화면에 선택된"
        점포/조사일자(self.app.state)로 모든 줄을 덮어써서 저장했다. PDA가
        보내온 각 줄에는 실제로 그 줄을 스캔한 시점의 점포코드/점포명/조사일자가
        같이 들어있는데(_warn_if_mismatch 주석 참고), 이를 무시하고 PC 화면
        값으로 덮어쓰면 PC 쪽이 최근 다른 점포/날짜를 보고 있었을 때 데이터가
        조용히 엉뚱한 조사일자로 저장돼버린다. 이제는 각 줄에 실려온 PDA의
        실제 값을 우선 쓰고(없을 때만, 예: 옛 버전 PDA에서 받은 자료처럼 그
        값이 비어있을 때만) PC 화면 값을 대신 쓴다 - 그래서 PC 화면을 무엇으로
        맞춰뒀는지와 무관하게 항상 "실제 작업한 점포/일자"로 정확히 저장된다."""
        if not self.staged:
            messagebox.showinfo("알림", "저장할 수신 자료가 없습니다.")
            return
        # [2026-10-16] 서적/문구 구분이 AREA와 안 맞는 줄이 남아 있으면 저장하지 않는다(그 사이 상품마스터가
        # 바뀌었을 수 있어 저장 직전에 다시 판정한다).
        kind_bad = self._flag_kind_mismatch(self.staged)
        if kind_bad:
            self._render_staged()
            self._refresh_duplicate_check()
            try:
                self.bell()
            except tk.TclError:
                pass
            lines = [f"서적/문구 구분이 AREA와 맞지 않는 줄 {len(kind_bad):,}건이 있어 저장하지 않았습니다.\n"]
            for r, m in kind_bad[:8]:
                lines.append(f"· {r.get('area') or ''}-{r.get('section') or ''}  {barcode_kind.short(m)}")
            if len(kind_bad) > 8:
                lines.append(f"  … 외 {len(kind_bad) - 8:,}건")
            lines.append("\n진한 빨간색 줄을 선택해 [삭제]한 뒤 다시 [저장]하세요.")
            messagebox.showerror("저장 불가", "\n".join(lines))
            return
        conn = dbmod.get_conn()
        for r in self.staged:
            # [2026-10-08] 저장 기준은 PC에서 상품마스터를 불러올 때 정한 점포코드/조사일자다.
            # PDA 실사 중 날짜가 넘어가(예: 10/7 -> 10/8) 자료가 2개 날짜로 갈라져 있어도 전부
            # 이 기준 하나로 저장해야 차이명세/자료생성이 빠짐없이 한 묶음으로 나온다.
            store_code = self.app.state.store_code or (r.get("store_code") or "").strip()
            store_name = self.app.state.store_name or r.get("store_name")
            date = self.app.state.survey_date or (r.get("survey_date") or "").strip()
            conn.execute(
                """INSERT INTO stock_counts(store_code, store_name, survey_date, area, section, shelf_no,
                    dan, yeol, isbn, book_name, qty, worker_code, worker_name, received_at, source_file)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (store_code, store_name, date, r.get("area"), r.get("section"), r.get("shelf_no"),
                 r.get("dan"), r.get("yeol"), r.get("isbn"), r.get("book_name"), r.get("qty", 0),
                 r.get("worker_code"), r.get("worker_name"), r.get("received_at"), r.get("source_file"))
            )
        conn.commit()
        conn.close()
        dbmod.bump_stock_version()
        dbmod.analyze_in_background()  # 대량 저장 뒤 DB 통계 갱신(조회 속도용)
        # 중복 섹션이 떠 있는데 삭제 없이 그대로 저장했으면 "확인한 것"으로 본다.
        self._acknowledge_current_duplicates()
        count = len(self.staged)
        self.staged = []
        self._render_staged()
        self.recalc_summary()
        self._refresh_duplicate_check()
        messagebox.showinfo("완료", f"{count:,}건을 실사자료로 저장했습니다.")

    # ---- 집계 ----
    def recalc_summary(self):
        """작업자별 실사 집계: [실적관리] 화면의 [전체조회(전점포)]와 똑같은
        기준(필터 없이 stock_counts 전체)으로 집계한다. [2026-09-23 재정정]
        예전엔 아직 저장 전인 self.staged(수신 대기 목록)만 집계해서, [저장]
        을 누르면(=staged가 비워지면) 집계가 같이 사라지는 문제가 있었다 -
        ZZOINT처럼 이미 쌓인(저장된) 데이터를 기준으로 계산하도록 고쳤다."""
        conn = dbmod.get_conn()
        rows = conn.execute("SELECT worker_name, qty FROM stock_counts").fetchall()
        conn.close()

        totals = {}
        for r in rows:
            key = r["worker_name"] or "(미지정)"
            t = totals.setdefault(key, {"count": 0, "qty": 0})
            t["count"] += 1
            t["qty"] += r["qty"] or 0
        grand_count = sum(t["count"] for t in totals.values())
        grand_qty = sum(t["qty"] for t in totals.values())

        self.tree_summary.delete(*self.tree_summary.get_children())
        for i, (worker, t) in enumerate(sorted(totals.items()), start=1):
            ratio = f"{t['count'] * 100.0 / grand_count:.1f}%" if grand_count else "0%"
            self.tree_summary.insert("", tk.END, values=(i, worker, f"{t['count']:,}", f"{t['qty']:,}", ratio),
                                      tags=("odd",) if i % 2 == 0 else ())
        if totals:
            self.tree_summary.insert("", tk.END, values=("", "계", f"{grand_count:,}", f"{grand_qty:,}", "100.0%"))

        self._draw_worker_bar_chart(totals, grand_count)

    def _draw_worker_bar_chart(self, totals, grand_count):
        """작업자별 실사건수 비율을 가로 막대그래프로 그린다. [2026-09-28]
        ZZOINT(원본)의 같은 그래프를 그대로 가져왔다."""
        c = self.summary_canvas
        c.delete("all")
        if not totals or grand_count == 0:
            c.create_text(200, 70, text="표시할 데이터가 없습니다", fill="#999999")
            c.configure(scrollregion=(0, 0, 420, 120))
            return

        items = sorted(totals.items(), key=lambda kv: kv[1]["count"], reverse=True)
        row_h = 26
        bar_max_w = 260
        top_pad = 10

        # 작업자 이름이 길면("테스트작업자01" 등) 라벨 폭(고정값)보다 글자가
        # 넓어져서 캔버스 왼쪽 밖으로 밀려나 잘려 보일 수 있다 - 실제로 그릴
        # 이름들의 폭을 재서, 가장 긴 이름 기준으로 라벨 영역을 넉넉히
        # 잡는다(너무 길어지는 것만 상한선으로 막는다).
        name_font = tkfont.Font(font=("", 9))
        label_w = min(max([name_font.measure(worker) for worker, _ in items] + [40]) + 20, 200)

        for i, (worker, t) in enumerate(items):
            y = top_pad + i * row_h
            ratio = t["count"] / grand_count if grand_count else 0
            bar_w = max(2, int(bar_max_w * ratio))
            color = BAR_COLORS[i % len(BAR_COLORS)]

            c.create_text(label_w - 6, y + row_h / 2, text=worker, anchor="e", font=("", 9))
            c.create_rectangle(label_w, y + 4, label_w + bar_max_w, y + row_h - 4,
                                fill="#EEEEEE", outline="")
            c.create_rectangle(label_w, y + 4, label_w + bar_w, y + row_h - 4,
                                fill=color, outline="")
            c.create_text(label_w + bar_max_w + 10, y + row_h / 2,
                          text=f"{t['count']:,}건 ({ratio*100:.1f}%)", anchor="w", font=("", 9))

        # 방금 그린 내용 전체 높이만큼 스크롤 범위를 다시 잡는다 - 작업자가
        # 많아서(예: 40명) 캔버스 보이는 영역보다 그래프가 길어져도 스크롤로
        # 전부 볼 수 있게 한다.
        total_h = top_pad + len(items) * row_h + top_pad
        c.configure(scrollregion=(0, 0, max(420, label_w + bar_max_w + 140), max(120, total_h)))

    # ---- 삭제/내보내기 ----
    def delete_all_committed(self):
        """[2026-10-08] "실사자료 전체삭제를 해도 전체 삭제가 안 된다" 수정.
        아래 [작업자별 집계]는 점포/조사일자 구분 없이 stock_counts 전체를 세는데,
        예전 삭제는 지금 화면의 점포+조사일자 것만 지워서 다른 날짜/점포(또는 PDA가
        보낸 다른 점포코드) 자료가 남아 집계가 그대로였다. 이제 집계와 같은 범위(전체)를
        지우고, 아직 저장 전인 수신 대기 목록도 같이 비운다."""
        conn = dbmod.get_conn()
        total = conn.execute("SELECT COUNT(*) FROM stock_counts").fetchone()[0]
        conn.close()
        if total == 0 and not self.staged:
            messagebox.showinfo("알림", "삭제할 실사자료가 없습니다.")
            return
        if not messagebox.askyesno(
                "확인", f"저장된 실사자료 {total:,}건(모든 점포/조사일자)과 수신 대기 목록을 모두 삭제할까요?"):
            return
        conn = dbmod.get_conn()
        conn.execute("DELETE FROM stock_counts")
        conn.execute("DELETE FROM dup_ack")
        conn.commit()
        conn.close()
        self.staged = []
        dbmod.bump_stock_version()
        self._render_staged()
        self.recalc_summary()
        self._refresh_duplicate_check()
        messagebox.showinfo("완료", "삭제했습니다.")

    def export_excel(self):
        rows = [self.tree.item(i, "values")[1:] for i in self.tree.get_children()]
        if not rows:
            messagebox.showinfo("알림", "저장할 데이터가 없습니다. (수신 대기 목록 기준)")
            return
        path = export_rows_to_excel(rows, STAGE_HEADINGS[1:], default_name=f"PDA수신_{today_str()}.xlsx", parent=self)
        if path:
            messagebox.showinfo("완료", f"저장되었습니다:\n{path}")
