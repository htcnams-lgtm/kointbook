# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""재고실사수신 > 실적관리 화면.

저장된 실사자료(stock_counts)를 AREA/SECTION/서가번호/바코드/도서명 기준으로
검색해서 보여준다. "AREA 합산전/후"는 AREA 뒤에 붙는 구역 접미사(1A/1B 등)를
뗄지 말지를 정한다 (ui_common.normalize_area 참고).

[2026-09-23 정정] 조회 조건(검색모드/키워드)을 명시적으로 확정할 수 있게
"조회" 버튼을 추가했다(Entry에서 Enter 치는 것과 동일하게 동작). [2026-09-23
재정정] 한 번 없앴던 "AREA 합산전/후" 라디오를 다시 살려서 "조회" 버튼
바로 왼쪽에 배치했다.

[2026-09-23 재재정정] ZZOINT(원본) 실적관리 화면과 기능을 맞췄다:
  - 조회 항목(라디오)에 "전체"를 맨 앞에, "SECTION"과 "바코드" 사이에
    "서가번호"를 추가했다 - 최종 순서: 전체/AREA/SECTION/서가번호/바코드/도서명.
  - "전체"를 고르고 조회하면(키워드 없이도 됨) 이 화면 맨 위 목록에 바로
    뿌려주고, 그 외(AREA/SECTION/서가번호/바코드/도서명)를 고르고 조회하면
    ZZOINT처럼 별도 팝업창에 그 결과만 보여준다(맨 위 목록은 그대로 둔다).
  - [등록]/[수정]/[삭제] 버튼과 기능을 ZZOINT와 동일하게 추가했다. 목록의
    체크박스(맨 왼쪽 칸)로 여러 줄을 골라 [삭제]할 수 있고, 줄을 더블클릭
    (또는 골라두고 [수정])하면 수정 팝업이 뜬다. [등록]은 바코드/수량/AREA/
    SECTION/서가번호만 입력하면 단/열은 그 위치의 다음 순번으로, 작업자는
    그 위치에서 기존에 쓰던 작업자(처음이면 'KOINTBOOK')로 자동 채워진다.
    ZZOINT는 로케이션 한 칸이지만 KOINTBOOK은 AREA/SECTION/서가번호 세 칸을
    쓰는 것만 다르다.

[2026-09-28] ZZOINT(원본) 실적관리의 "디테일한" 기능들을 추가로 가져왔다
(불필요한 부분은 걸러냄):
  - 조회 항목(라디오)에 "작업자"를 추가했다(작업자명으로 검색).
  - [수정] 팝업을 ZZOINT처럼 "바코드"와 "수량"만 실제로 고칠 수 있게 바꿨다.
    AREA/SECTION/서가번호/단/열/작업자코드/작업자명은 그 실사 데이터가 실제로
    스캔된 위치·작업자를 그대로 보여주는 자동배정 값이라, 회색 배경의
    읽기전용 칸으로만 보여준다(임의로 바꿔서 위치가 뒤섞이는 사고를 막기
    위함 - 위치를 바꿔야 한다면 삭제 후 다시 등록한다). 바코드를 바꾸면
    도서명 칸이 입력하는 즉시(키를 뗄 때마다) 상품마스터에서 다시 찾아
    보여주고, 마스터에 없는 바코드로 저장하려 하면 확인창으로 한 번 더
    물어본다.
  - [등록] 팝업에도 바코드를 입력하는 즉시 도서명을 미리 보여주는 칸을
    추가했고, 마스터에 없는 바코드를 그대로 등록하려 하면 확인창으로 물어
    본다. 이 팝업도 모달(다른 창 조작 막힘)로 열리게 했다(수정 팝업과 동일).
  - ZZOINT의 "전체" 조회가 점포/조사일자 구분 없이 전체 DB를 그대로
    보여주는 부분은 가져오지 않았다(2026-09-24에 KOINTBOOK에서 이미
    "전체조회(전점포)" 기능 자체를 없앤 것과 같은 이유) - 여기 "전체"는
    계속 현재 점포/조사일자 기준으로만 보여준다."""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from . import db as dbmod
from . import scope
from . import barcode_kind
from .virtual_table import VirtualTable
from .ui_common import (
    center_on_app,
    setup_treeview, export_rows_to_excel, file_date, normalize_area,
    digit_code_variants as _digit_code_variants,
    CL_BG, CL_NAVY, CL_TEXT, CL_TEXT_DIM, win_button, split_scan_datetime
)

CL_READONLY_BG = "#E4E4E4"  # 읽기전용 칸(수정 못 하고 보여주기만 하는 칸)의 회색 배경

# [2026-09-28] "AREA 2자리필수, SECTION 3자리필수, 서가번호 11자리이하로
# PDA랑 동일하게 제한해줘" - android_app의 LocationInputActivity와 같은
# 자릿수 제한을 PC 등록 팝업에도 그대로 맞춘다. PDA 쪽 상수와 동일:
#   MAX_LENGTHS = (2, 3, 20), EXACT_LENGTHS = (2, 3, -1)
AREA_MAX_LEN = 2
SECTION_MAX_LEN = 3
SHELF_NO_MAX_LEN = 20   # [2026-10-16] 서가번호 20자리 이하 (예전 11자리)


def _limit_entry_length(entry, max_len):
    """Entry 위젯에 최대 입력 글자수 제한을 건다(PDA의 android:maxLength와
    동일한 효과) - 그 이상은 타이핑/붙여넣기 자체가 안 먹힌다."""
    vcmd = (entry.register(lambda p: len(p) <= max_len), "%P")
    entry.config(validate="key", validatecommand=vcmd)

# [2026-09-30] 실사데이터가 몇 만~몇 십만 건씩 쌓여도 화면이 가볍도록 "가상 스크롤" 표를
# 쓴다(virtual_table.py 참고): 표에는 화면에 보이는 만큼(약 30줄)만 두고, 스크롤할 때
# 줄을 지우고 다시 만들지 않고 그 줄의 글자만 바꾼다. 스크롤바는 전체 건수 길이이며,
# 예전의 페이지 버튼(처음/이전/다음/끝)은 없다. 체크/선택/수정/삭제는 모두 레코드 id 기준이다.
# 조회 조건과 정렬(AREA, SECTION, 서가번호, 단, 열)은 예전과 같다.




def _confirm_unregistered(popup, verb):
    """[2026-10-08] 상품마스터에 없는 바코드 처리: 상품마스터 화면의 [미등록상품] 설정을 따른다.
    허용 = 바로 진행, 경고 후 허용 = 경고음 + 확인창, 차단 = 안내 후 진행 안 함. 진행하면 True."""
    policy = dbmod.get_unreg_policy()
    if policy == "허용":
        return True
    popup.bell()
    if policy == "차단":
        messagebox.showwarning("미등록 상품", "상품마스터에 없는 바코드는 입력할 수 없습니다.\n"
                               "(상품마스터 화면의 [미등록상품] 설정: 차단)", parent=popup)
        return False
    return messagebox.askyesno("확인", f"상품마스터에 없는 바코드입니다.\n그래도 {verb}하시겠습니까?", parent=popup)


def _kind_blocked(popup, store_code, area, code):
    """[2026-10-16] 서적 AREA에 문구 상품(문구 AREA에 서적 상품)을 넣으려 하면 경고음 + 안내 후 True.
    PDA의 입력 금지(BarcodeKind.kt)와 같은 기준이다(상품마스터 구분 우선, 마스터에 없으면 바코드 모양)."""
    conn = dbmod.get_conn()
    try:
        m = barcode_kind.check(conn, store_code, area, code)
        name = barcode_kind.master_name(conn, store_code, code) if m else ""
    finally:
        conn.close()
    if m is None:
        return False
    popup.bell()
    messagebox.showerror(f"입력 금지 - {m['item_kind']} 상품", barcode_kind.message(m, name), parent=popup)
    return True


class PerformanceScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._view_merged = False  # 지금 목록을 AREA 합산후 기준으로 보여주고 있는지
        self._loaded_ctx = None  # 마지막으로 읽었을 때의 (점포코드, 조사일자)
        self._last_loc_edit = None  # 마지막 위치 수정 1회분 (수정 취소용)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = tk.Frame(self, bg=CL_BG)
        top.pack(fill=tk.X, padx=8, pady=(10, 2))
        # [2026-10-01] "버튼이 많아 화면을 넘어가 안 보임" - 한 줄에 다 넣으면 1366px 화면에서 오른쪽
        # 버튼(수정/삭제/엑셀저장)이 잘렸다. 두 줄로 나눈다: 위 줄(top) = 조회 조건(조회방식, 입력칸,
        # AREA 합산전/후, [조회]), 아래 줄(actions) = 작업 버튼(등록/수정/삭제 ... 엑셀저장).
        actions = tk.Frame(self, bg=CL_BG)
        actions.pack(fill=tk.X, padx=8, pady=(0, 6))

        tk.Label(top, text="조회", bg=CL_BG, font=("", 10, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        self.search_mode = tk.StringVar(value="전체")
        # [2026-09-28] "AREA와 SECTION을 같이 조회하고 싶을 때" - 기존
        # 조회 항목들은 한 번에 한 가지 조건(AREA만, SECTION만, ...)만
        # 검색할 수 있었다. 그 두 조건을 동시에 걸 수 있는 "AREA+SECTION"
        # 항목을 AREA/SECTION 바로 옆에 추가했다 - 이 항목을 고르면 입력칸
        # 하나(e_search) 대신 AREA/SECTION 칸이 각각 따로 뜬다.
        for label in ("전체", "AREA", "SECTION", "AREA+SECTION", "서가번호", "바코드", "도서명", "작업자"):
            tk.Radiobutton(top, text=label, variable=self.search_mode, value=label, bg=CL_BG,
                           command=self._on_search_mode_changed).pack(side=tk.LEFT)

        # [2026-09-28] 조회 모드에 따라 이 자리에 "입력칸 하나"(e_search) 또는
        # "AREA/SECTION 칸 두 개"(e_area_kw/e_section_kw)가 번갈아 보이도록,
        # 둘 다 이 고정된 자리(search_value_frame) 안에 만들어두고 모드가
        # 바뀔 때만 그 안에서 pack/pack_forget으로 바꿔 끼운다 - 이렇게 해야
        # 조회/등록/수정/삭제 등 오른쪽 버튼들 위치가 모드 전환 때마다
        # 흔들리지 않는다.
        self.search_value_frame = tk.Frame(top, bg=CL_BG)
        self.search_value_frame.pack(side=tk.LEFT, padx=(8, 4))

        # 일반 조회용 입력칸 하나(AREA/SECTION/서가번호/바코드/도서명/작업자 공용).
        self.e_search = tk.Entry(self.search_value_frame, width=22)
        self.e_search.bind("<Return>", lambda ev: self._do_search())

        # "AREA+SECTION" 전용 - AREA칸/SECTION칸을 한 프레임에 같이 묶어둬서
        # 모드가 바뀔 때 이 프레임 하나만 통째로 pack/pack_forget하면 된다.
        self.search_area_section_frame = tk.Frame(self.search_value_frame, bg=CL_BG)
        tk.Label(self.search_area_section_frame, text="AREA", bg=CL_BG, fg=CL_TEXT_DIM).pack(side=tk.LEFT)
        self.e_area_kw = tk.Entry(self.search_area_section_frame, width=6)
        self.e_area_kw.bind("<Return>", lambda ev: self._do_search())
        self.e_area_kw.pack(side=tk.LEFT, padx=(2, 10))
        tk.Label(self.search_area_section_frame, text="SECTION", bg=CL_BG, fg=CL_TEXT_DIM).pack(side=tk.LEFT)
        self.e_section_kw = tk.Entry(self.search_area_section_frame, width=6)
        self.e_section_kw.bind("<Return>", lambda ev: self._do_search())
        self.e_section_kw.pack(side=tk.LEFT, padx=(2, 0))

        # 기본 모드("전체")에 맞는 쪽(e_search)만 보이게 시작한다.
        self._on_search_mode_changed()

        # [2026-09-23 재정정] 한 번 없앴던 "AREA 합산전/후" 라디오를 다시
        # 살렸다(요청) - "조회" 버튼 바로 왼쪽에 배치한다.
        self.merge_mode = tk.StringVar(value="합산전")
        tk.Radiobutton(top, text="AREA 합산전", variable=self.merge_mode, value="합산전", bg=CL_BG,
                       command=self._do_search).pack(side=tk.LEFT, padx=(24, 0))
        tk.Radiobutton(top, text="AREA 합산후", variable=self.merge_mode, value="합산후", bg=CL_BG,
                       command=self._do_search).pack(side=tk.LEFT)

        win_button(top, text="조회", command=self._do_search, kind="normal").pack(side=tk.LEFT, padx=(12, 4))

        # [2026-09-23 재재정정] "조회" 버튼과 간격을 띄우고 ZZOINT와 똑같이
        # [등록]/[수정]/[삭제]를 나란히 둔다.
        win_button(actions, text="등록", command=self.open_register_popup, kind="accent").pack(side=tk.LEFT, padx=(0, 0))
        win_button(actions, text="수정", command=self.edit_selected, kind="accent").pack(side=tk.LEFT, padx=(6, 0))
        win_button(actions, text="위치 수정", command=self.open_location_edit_checked_main, kind="accent").pack(side=tk.LEFT, padx=(6, 0))
        win_button(actions, text="수정 취소", command=self.undo_location_edit, kind="normal").pack(side=tk.LEFT, padx=(6, 0))
        win_button(actions, text="삭제", command=self.delete_selected_main, kind="danger").pack(side=tk.LEFT, padx=(18, 0))

        # [2026-09-24 정정] "전체조회(전점포)" 버튼을 없앴다(요청) - 다른
        # 점포/다른 날짜 자료까지 보여주는 기능 자체를 더 이상 쓰지 않는다.
        win_button(actions, text="엑셀저장", command=self.export_excel, kind="accent").pack(side=tk.RIGHT, padx=4)

        columns = ("check", "no", "store_code", "isbn", "book_name", "qty", "area", "section",
                   "shelf_no", "dan", "yeol", "worker", "date", "time")
        headings = ("선택", "NO", "점포코드", "바코드", "도서명", "조사수량", "AREA", "SECTION",
                    "서가번호", "단", "열", "작업자", "실사일자", "실사시간")
        # [2026-09-23 정정] "SECTION" 헤더 글자가 안 잘리도록 폭을 늘렸다.
        widths = (45, 45, 80, 120, 260, 70, 60, 95, 150, 45, 45, 90, 90, 80)
        self.vt = VirtualTable(
            self, columns, headings, widths,
            lambda r: self._row_values(0, r, self._view_merged)[2:], height=20,
            style_name="BigCheck.Treeview", on_loaded=self._on_main_loaded,
            on_double=lambda rid: self.open_edit_popup(rid, self._after_edit_main))
        self.vt.container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))
        self.tree = self.vt.tree
        self._popup_trees = []  # 조회 결과 팝업들: (팝업, VirtualTable, 수정후콜백)

        status = tk.Frame(self, bg=CL_BG)
        status.pack(fill=tk.X, padx=8, pady=(4, 8))
        self.lbl_total = tk.Label(status, text="불러오는 중...", bg=CL_BG, fg=CL_NAVY, font=("", 10, "bold"))
        self.lbl_total.pack(side=tk.LEFT)
        tk.Label(status, text="(스크롤바/마우스 휠/방향키·PageUp·PageDown, Space = 포커스 줄 선택, \"선택\" 헤더 = 전체선택/해제)",
                 bg=CL_BG, fg=CL_TEXT_DIM, font=("", 9)).pack(side=tk.LEFT, padx=(14, 0))

    def _on_main_loaded(self, total, qty):
        try:
            if self.vt.loading:
                self.lbl_total.config(text="불러오는 중...")
            else:
                self.lbl_total.config(text=f"(총 {total:,}건 / 총 수량 {(qty or 0):,}개)")
        except tk.TclError:
            pass

    _ORDER = "CAST(area AS INTEGER), area, CAST(section AS INTEGER), section, CAST(dan AS INTEGER), dan, CAST(yeol AS INTEGER), yeol, shelf_no"

    def refresh(self, force=False):
        """이 화면(맨 위 목록)에 현재 점포/조사일자 기준 전체 데이터를 조건 없이 보여준다
        ("전체" 조회 및 [새로고침] 공용). 화면에 들어올 때마다 불리지만, 점포/조사일자/합산 기준이
        그대로이고 실사 데이터도 바뀌지 않았으면 다시 읽지 않는다(PDA 수신 저장/삭제/복원 등으로
        바뀐 경우에만 백그라운드로 다시 읽는다). force=True([조회] 버튼)는 처음부터 다시 읽는다."""
        merged = self.merge_mode.get() == "합산후"
        ctx = (self.app.state.store_code, self.app.state.survey_date)
        where = "store_code=? AND survey_date=?"
        if force or self._loaded_ctx != ctx:
            self._loaded_ctx = ctx
            self._view_merged = merged
            self.vt.load(where, ctx, order_by=self._ORDER)
        elif merged != self._view_merged:
            self._view_merged = merged
            self.vt.load(where, ctx, keep_position=True, order_by=self._ORDER)
        elif self.vt.is_stale():
            self.vt.load(where, ctx, keep_position=True, order_by=self._ORDER)

    def _live_popups(self):
        alive = []
        for entry in self._popup_trees:
            try:
                if entry[0].winfo_exists():
                    alive.append(entry)
            except tk.TclError:
                continue
        self._popup_trees = alive
        return alive

    def _apply_changes(self, changed_ids=(), deleted_ids=(), added_ids=()):
        """전체 재조회 없이, 바뀐 줄(수정/삭제/추가)만 맨 위 목록과 열려 있는 조회 팝업들에 반영한다.
        보던 위치, 선택, 체크 상태는 그대로 유지된다."""
        self.vt.apply_changes(changed_ids=changed_ids, deleted_ids=deleted_ids, added_ids=added_ids)
        for _popup, pvt, _cb in self._live_popups():
            pvt.apply_changes(changed_ids=changed_ids, deleted_ids=deleted_ids, added_ids=added_ids,
                              append_added=False)


    def _row_values(self, no, r, merged):
        area = normalize_area(r["area"], merged=merged)
        # [2026-10-15] 날짜/시간 칸은 조사일자가 아니라 실제로 스캔한 날짜(YYYYMMDD)와 시간(HH:MM:SS)을 보여준다.
        scan_date, scan_time = split_scan_datetime(r["received_at"], r["survey_date"])
        return ("☐", no, r["store_code"], r["isbn"], r["book_name"], f"{r['qty'] or 0:,}", area, r["section"],
                r["shelf_no"], r["dan"], r["yeol"], r["worker_name"], scan_date, scan_time)

    def _delete_records(self, record_ids):
        """실사 데이터를 실제로 DB에서 지우고, 열려 있는 모든 표(맨 위 목록 + 조회 팝업들)에서도 반영한다."""
        if not record_ids:
            return
        conn = dbmod.get_conn()
        conn.executemany("DELETE FROM stock_counts WHERE id=?", [(rid,) for rid in record_ids])
        conn.commit()
        conn.close()
        self._apply_changes(deleted_ids=record_ids)

    def delete_selected_main(self):
        """상단 [삭제] 버튼: 맨 위 목록에서 체크박스로 고른 줄들을 지운다
        (스크롤해서 화면 밖에 있는 체크된 줄도 포함)."""
        ids = self.vt.checked_ids()
        if not ids:
            messagebox.showinfo("알림", "삭제할 행을 체크박스로 선택하세요.")
            return
        if not messagebox.askyesno("확인", f"선택한 {len(ids):,}건을 삭제할까요?\n(되돌릴 수 없습니다)"):
            return
        self._delete_records(ids)
        messagebox.showinfo("완료", f"{len(ids):,}건을 삭제했습니다.")


    def _on_search_mode_changed(self):
        """[2026-09-28] 조회 항목(라디오)이 바뀔 때, search_value_frame
        안에서 "일반 입력칸 하나(e_search)" 또는 "AREA+SECTION 두 칸
        (search_area_section_frame)" 중 지금 모드에 맞는 쪽만 보이게
        바꿔 끼운다."""
        mode = self.search_mode.get()
        if mode == "AREA+SECTION":
            self.e_search.pack_forget()
            self.search_area_section_frame.pack(side=tk.LEFT)
        else:
            self.search_area_section_frame.pack_forget()
            self.e_search.pack(side=tk.LEFT)

    def _do_search(self):
        mode = self.search_mode.get()
        if mode == "전체":
            # 전체 조회는 팝업을 따로 띄우지 않고, 이 화면의 목록에 그대로 보여준다.
            self.refresh(force=True)
            return

        merged = self.merge_mode.get() == "합산후"
        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        base_where = "store_code=? AND survey_date=?"

        if mode == "AREA+SECTION":
            # [2026-09-28] "AREA와 SECTION을 같이 조회하고 싶을 때" - 두
            # 조건을 AND로 같이 건다. [2026-09-28 버그수정] AREA/SECTION은
            # LIKE 부분검색이 아니라 정확히 일치하는 코드로 찾아야 맞고(예:
            # "1"로 검색했는데 "21"까지 걸리면 안 됨), 0채움 여부가 저장
            # 데이터마다 다를 수 있어(_digit_code_variants) 후보를 모두
            # IN절에 넣는다.
            area_kw = self.e_area_kw.get().strip()
            section_kw = self.e_section_kw.get().strip()
            if not area_kw or not section_kw:
                messagebox.showinfo("알림", "AREA와 SECTION을 모두 입력하세요.")
                return
            area_variants = _digit_code_variants(area_kw, 2)
            section_variants = _digit_code_variants(section_kw, 3)
            area_ph = ",".join("?" for _ in area_variants)
            section_ph = ",".join("?" for _ in section_variants)
            where = f"{base_where} AND area IN ({area_ph}) AND section IN ({section_ph})"
            params = (store_code, date, *area_variants, *section_variants)
            label_text = f"AREA '{area_kw}' + SECTION '{section_kw}'"
        elif mode in ("AREA", "SECTION"):
            # [2026-09-28 버그수정] "AREA를 01로하면 조회가 안되고 1로 하면
            # 조회가되네" - 위 AREA+SECTION과 같은 이유로, AREA/SECTION
            # 단독 조회도 LIKE 부분검색 대신 0채움 후보를 모두 넣은 정확히
            # 일치하는 검색으로 바꿨다.
            column = "area" if mode == "AREA" else "section"
            width = 2 if mode == "AREA" else 3
            keyword = self.e_search.get().strip()
            if not keyword:
                messagebox.showinfo("알림", f"{mode}을(를) 입력하세요.")
                return
            variants = _digit_code_variants(keyword, width)
            placeholders = ",".join("?" for _ in variants)
            where = f"{base_where} AND {column} IN ({placeholders})"
            params = (store_code, date, *variants)
            label_text = f"{mode} '{keyword}'"
        else:
            col_map = {"서가번호": "shelf_no", "바코드": "isbn", "도서명": "book_name", "작업자": "worker_name"}
            column = col_map[mode]
            keyword = self.e_search.get().strip()
            if not keyword:
                messagebox.showinfo("알림", f"{mode}을(를) 입력하세요.")
                return
            where = f"{base_where} AND {column} LIKE ?"
            params = (store_code, date, f"%{keyword}%")
            label_text = f"{mode} '{keyword}'"

        self._open_query_popup(label_text, where, params, merged)

    def _open_query_popup(self, label_text, where, params, merged):
        """조회 조건(where/params)에 맞는 결과를 별도 팝업창에 보여준다 (맨 위의 전체 목록은
        그대로 둔다). 같은 가상 스크롤 표라서 결과가 수만 건이어도 바로 뜬다. AREA/SECTION/서가번호/
        바코드/도서명/작업자 단일 조건 조회와 AREA+SECTION 복합 조건 조회가 이 팝업을 공용으로 쓴다."""
        popup = tk.Toplevel(self)
        center_on_app(popup)
        base_title = f"{label_text} 조회 결과"
        popup.title(base_title)
        popup.geometry("1200x520")
        popup.configure(bg=CL_BG)
        popup.bind("<Escape>", lambda ev: popup.destroy())

        title_lbl = tk.Label(popup, text=base_title, bg=CL_BG, fg=CL_NAVY, font=("", 11, "bold"))
        title_lbl.pack(anchor="w", padx=10, pady=(10, 4))

        state = {"empty_shown": False}

        def on_loaded(total, qty):
            try:
                if not popup.winfo_exists():
                    return
                suffix = "불러오는 중..." if vt.loading else f"(총 {total:,}건 / 총 수량 {(qty or 0):,}개)"
                popup.title(f"{base_title} {suffix}")
                title_lbl.config(text=f"{base_title}  {suffix}")
                if not vt.loading and total == 0 and not state["empty_shown"]:
                    state["empty_shown"] = True
                    messagebox.showinfo("알림", "해당하는 데이터가 없습니다.", parent=popup)
            except tk.TclError:
                pass

        def after_edit(record_id):
            self._apply_changes(changed_ids=[record_id])

        columns = ("check", "no", "store_code", "isbn", "book_name", "qty", "area", "section",
                   "shelf_no", "dan", "yeol", "worker", "date", "time")
        headings = ("선택", "NO", "점포코드", "바코드", "도서명", "조사수량", "AREA", "SECTION",
                    "서가번호", "단", "열", "작업자", "실사일자", "실사시간")
        widths = (45, 45, 80, 120, 260, 70, 60, 95, 150, 45, 45, 90, 90, 80)
        vt = VirtualTable(popup, columns, headings, widths,
                          lambda r: self._row_values(0, r, merged)[2:], height=18,
                          style_name="BigCheck.Treeview", on_loaded=on_loaded,
                          on_double=lambda rid: self.open_edit_popup(rid, after_edit, parent=popup))
        vt.container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._popup_trees.append((popup, vt, after_edit))

        def edit_in_popup():
            if vt.sel_id is None:
                messagebox.showinfo("알림", "수정할 줄을 목록에서 먼저 선택하세요.", parent=popup)
                return
            self.open_edit_popup(vt.sel_id, after_edit, parent=popup)

        def delete_in_popup():
            ids = vt.checked_ids()
            if not ids:
                messagebox.showinfo("알림", "삭제할 행을 체크박스로 선택하세요.", parent=popup)
                return
            if not messagebox.askyesno("확인", f"선택한 {len(ids):,}건을 삭제할까요?\n(되돌릴 수 없습니다)", parent=popup):
                return
            self._delete_records(ids)
            if popup.winfo_exists():
                messagebox.showinfo("완료", f"{len(ids):,}건을 삭제했습니다.", parent=popup)

        btn_row = tk.Frame(popup, bg=CL_BG)
        btn_row.pack(pady=(0, 10))
        win_button(btn_row, text="등록", command=lambda: self.open_register_popup(parent=popup),
                   kind="accent").pack(side=tk.LEFT, padx=6)
        win_button(btn_row, text="수정", command=edit_in_popup, kind="accent").pack(side=tk.LEFT, padx=6)
        win_button(btn_row, text="위치 수정", command=lambda: self.open_location_edit_popup(vt.checked_ids(), parent=popup),
                   kind="accent").pack(side=tk.LEFT, padx=6)
        win_button(btn_row, text="수정 취소", command=lambda: self.undo_location_edit(parent=popup),
                   kind="normal").pack(side=tk.LEFT, padx=6)
        win_button(btn_row, text="삭제", command=delete_in_popup, kind="danger").pack(side=tk.LEFT, padx=(24, 6))
        tk.Label(btn_row, text="(\"선택\" 헤더 클릭 = 전체선택/해제, Space = 포커스 줄 선택)",
                 bg=CL_BG, fg=CL_TEXT_DIM, font=("", 9)).pack(side=tk.LEFT, padx=(12, 0))

        # [2026-09-28 버그수정] 이 팝업은 비모달 창이라 키보드 포커스가 저절로 오지 않는다 -
        # 팝업 자신에게 포커스를 주고, 표에도 같은 ESC 동작을 걸어 어디서든 닫히게 한다.
        vt.tree.bind("<Escape>", lambda e: popup.destroy())
        popup.focus_set()

        vt.load(where, params, order_by=self._ORDER)

    # ------------------------------------------------------------------
    # 수정
    # ------------------------------------------------------------------
    def _after_edit_main(self, record_id):
        """맨 위 목록에서 수정한 뒤: 바뀐 줄만 반영하고 방금 수정한 줄을 다시 선택해둔다."""
        self._apply_changes(changed_ids=[record_id])
        self.vt.select_id(record_id)

    def edit_selected(self):
        """상단 [수정] 버튼: 조회 결과 팝업이 열려 있고 거기서 고른 줄이 있으면 그 줄을,
        아니면 맨 위 목록에서 고른 줄을 수정한다."""
        for popup, pvt, after_edit in reversed(self._live_popups()):
            if pvt.sel_id is not None:
                self.open_edit_popup(pvt.sel_id, after_edit, parent=popup)
                return
        if self.vt.sel_id is None:
            messagebox.showinfo("알림", "수정할 줄을 목록에서 먼저 선택하세요.\n(조회 후 나온 팝업 목록에서 골라도 됩니다)")
            return
        self.open_edit_popup(self.vt.sel_id, self._after_edit_main)


    def open_edit_popup(self, record_id, on_saved=None, parent=None):
        """실사 데이터 한 줄을 수정하는 팝업. [2026-09-28] ZZOINT(원본) 실적관리의
        수정 팝업과 동일하게, 실제로 고칠 수 있는 값은 "바코드"와 "수량"뿐이다.
        AREA/SECTION/서가번호/단/열/작업자코드/작업자명은 그 실사 데이터가 실제로
        스캔된 위치·작업자를 그대로 보여주는 값이라(자동배정 값) 수정 팝업에서
        임의로 바꿀 수 없게 회색 배경의 읽기전용 칸으로만 보여준다(위치를 잘못
        옮겨버리는 사고를 막기 위함) - 위치를 바꿔야 하는 경우라면 이 줄을
        [삭제]하고 올바른 위치로 다시 [등록]한다.
        바코드를 바꾸면 도서명 칸이 입력하는 즉시(키를 뗄 때마다) 상품마스터에서
        다시 찾아 보여주고, 마스터에 없는 바코드로 저장하려 하면 그대로 저장할지
        확인창으로 한 번 더 물어본다."""
        conn = dbmod.get_conn()
        r = conn.execute("SELECT * FROM stock_counts WHERE id=?", (record_id,)).fetchone()
        conn.close()
        if r is None:
            messagebox.showinfo("알림", "해당 데이터를 찾을 수 없습니다. (이미 삭제되었을 수 있습니다)")
            return

        owner = parent if parent is not None else self
        popup = tk.Toplevel(owner)
        center_on_app(popup)
        popup.title("실적 수정")
        popup.configure(bg=CL_BG)
        popup.resizable(False, False)
        try:
            popup.transient(owner.winfo_toplevel())
            popup.grab_set()
        except tk.TclError:
            pass
        popup.bind("<Escape>", lambda e: popup.destroy())

        frm = tk.Frame(popup, bg=CL_BG)
        frm.pack(fill=tk.BOTH, expand=True, padx=20, pady=18)

        ENTRY_OPT = dict(relief="flat", highlightthickness=1, highlightbackground="#C4C8D0",
                          highlightcolor=CL_NAVY, font=("", 11))
        READONLY_OPT = dict(relief="flat", highlightthickness=1, highlightbackground="#C4C8D0",
                             font=("", 11), state="readonly", readonlybackground=CL_READONLY_BG,
                             disabledforeground=CL_TEXT)

        entries = {}
        row_i = 0

        # 위치(AREA/SECTION/서가번호/단/열): 자동배정된 값을 보여주기만 하는
        # 읽기전용 칸 (실사 당시 실제로 스캔된 위치이므로 여기서는 못 바꾼다).
        # [2026-09-28 버그수정] AREA는 DB에 "1"처럼 앞자리 0 없이 저장된
        # 데이터도 있어서(등록창에서 입력한 값을 그대로 저장했던 이전
        # 데이터 등), 맨 위 목록/조회 결과에는 normalize_area로 "01"처럼
        # 2자리로 맞춰서 보여주면서 정작 이 수정 팝업에서는 DB 원본값을 그대로
        # 보여줘서 "01"인데 "1"로 보인다는 지적이 있었다 - 여기도 똑같이
        # normalize_area를 거쳐서 항상 2자리로 보여주도록 맞췄다.
        for label, key in (("AREA", "area"), ("SECTION", "section"), ("서가번호", "shelf_no"),
                            ("단", "dan"), ("열", "yeol")):
            tk.Label(frm, text=label, bg=CL_BG, fg=CL_TEXT_DIM).grid(row=row_i, column=0, sticky="w", pady=6, padx=(0, 14))
            e = tk.Entry(frm, width=22, **READONLY_OPT)
            e.config(state="normal")
            if key == "area":
                display_value = normalize_area(r["area"]) or ""
            else:
                display_value = "" if r[key] is None else str(r[key])
            e.insert(0, display_value)
            e.config(state="readonly")
            e.grid(row=row_i, column=1, pady=6, ipady=4)
            entries[key] = e
            row_i += 1

        # 바코드: 실제로 고칠 수 있는 칸.
        tk.Label(frm, text="바코드", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=row_i, column=0, sticky="w", pady=6, padx=(0, 14))
        e_isbn = tk.Entry(frm, width=22, **ENTRY_OPT)
        e_isbn.insert(0, "" if r["isbn"] is None else str(r["isbn"]))
        e_isbn.grid(row=row_i, column=1, pady=6, ipady=4)
        entries["isbn"] = e_isbn
        row_i += 1

        # 도서명: 입력칸이 아니라 바코드에 맞물리는 값을 보여주기만 하는 칸.
        tk.Label(frm, text="도서명", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=row_i, column=0, sticky="w", pady=6, padx=(0, 14))
        book_name_entry = tk.Entry(frm, width=22, **READONLY_OPT)
        book_name_entry.grid(row=row_i, column=1, pady=6, ipady=4)
        row_i += 1

        def set_book_name_display(value):
            book_name_entry.config(state="normal")
            book_name_entry.delete(0, tk.END)
            book_name_entry.insert(0, value or "(상품마스터에 없음)")
            book_name_entry.config(state="readonly")

        set_book_name_display(r["book_name"])

        # 수량: 실제로 고칠 수 있는 칸.
        tk.Label(frm, text="수량", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=row_i, column=0, sticky="w", pady=6, padx=(0, 14))
        qty_entry = tk.Entry(frm, width=22, **ENTRY_OPT)
        qty_entry.insert(0, "" if r["qty"] is None else str(r["qty"]))
        qty_entry.grid(row=row_i, column=1, pady=6, ipady=4)
        entries["qty"] = qty_entry
        row_i += 1

        # 작업자코드/작업자명: 자동배정된 값을 보여주기만 하는 읽기전용 칸.
        for label, key in (("작업자코드", "worker_code"), ("작업자명", "worker_name")):
            tk.Label(frm, text=label, bg=CL_BG, fg=CL_TEXT_DIM).grid(row=row_i, column=0, sticky="w", pady=6, padx=(0, 14))
            e = tk.Entry(frm, width=22, **READONLY_OPT)
            e.config(state="normal")
            e.insert(0, "" if r[key] is None else str(r[key]))
            e.config(state="readonly")
            e.grid(row=row_i, column=1, pady=6, ipady=4)
            entries[key] = e
            row_i += 1

        # [2026-09-29] "영문 소문자,대문자 구분하지 않고 상품마스터에 맞는쪽으로
        # 자동변경하여 매칭되도록" - SQLite의 기본 "=" 비교는 대소문자를 구분해서,
        # 사용자가 상품마스터와 대소문자만 다르게 입력하면 매칭이 안 됐다.
        # COLLATE NOCASE로 대소문자 구분 없이 찾되, 실제 저장은 항상 상품마스터에
        # 있는 그대로의 표기(isbn 컬럼도 같이 조회)로 맞춘다.
        def find_book(isbn):
            c = dbmod.get_conn()
            b = c.execute(
                "SELECT isbn, book_name FROM books WHERE store_code=? AND isbn=? COLLATE NOCASE LIMIT 1",
                (r["store_code"], isbn)
            ).fetchone()
            c.close()
            return b

        def on_isbn_changed(_e=None):
            bc = e_isbn.get().strip()
            if bc and bc != (r["isbn"] or ""):
                b = find_book(bc)
                set_book_name_display(b["book_name"] if b else None)
            else:
                set_book_name_display(r["book_name"])

        # 바코드는 포커스가 빠질 때가 아니라 입력하는 즉시(키를 뗄 때마다) 도서명이
        # 바로 반영되도록 한다.
        e_isbn.bind("<KeyRelease>", on_isbn_changed)

        def save():
            isbn = e_isbn.get().strip()
            qty_str = qty_entry.get().strip()
            if not isbn or not qty_str:
                messagebox.showinfo("알림", "바코드/수량은 비워둘 수 없습니다.", parent=popup)
                return
            try:
                qty = int(qty_str)
            except ValueError:
                messagebox.showinfo("알림", "수량은 숫자로 입력하세요.", parent=popup)
                return

            book_name = r["book_name"]
            isbn_changed = isbn != (r["isbn"] or "")
            if isbn_changed:
                # [2026-10-16] 바코드를 바꿀 때는 이 줄의 AREA(서적/문구)에 맞는 상품이어야 한다.
                if _kind_blocked(popup, r["store_code"], r["area"], isbn):
                    e_isbn.focus_set()
                    return
                b = find_book(isbn)
                if b is None:
                    # [2026-09-30] "마스터에없는 미등록바코드 입력되어 팝업창이
                    # 나올시 경고소리를 나게 해주고" - 팝업을 띄우기 직전에
                    # 시스템 경고음을 울린다(bell()은 OS 기본 알림음이라 별도
                    # 사운드 파일 없이도 모든 환경에서 동작한다).
                    if not _confirm_unregistered(popup, "저장"):
                        return
                    book_name = ""
                else:
                    book_name = b["book_name"]
                    isbn = b["isbn"]  # 상품마스터에 실제 저장된 대소문자로 맞춰 저장

            conn2 = dbmod.get_conn()
            conn2.execute(
                "UPDATE stock_counts SET isbn=?, book_name=?, qty=? WHERE id=?",
                (isbn, book_name, qty, record_id)
            )
            conn2.commit()
            conn2.close()
            popup.destroy()
            if on_saved is not None:
                on_saved(record_id)

        btn_row = tk.Frame(popup, bg=CL_BG)
        btn_row.pack(fill=tk.X, padx=20, pady=(0, 16))
        win_button(btn_row, text="수정완료", command=save, kind="accent").pack(side=tk.LEFT)
        win_button(btn_row, text="닫기", command=popup.destroy, kind="normal").pack(side=tk.LEFT, padx=8)
        e_isbn.bind("<Return>", lambda e: qty_entry.focus_set())
        qty_entry.bind("<Return>", lambda e: save())

        def _focus_qty():
            qty_entry.focus_set()
            qty_entry.selection_range(0, tk.END)

        popup.after(50, _focus_qty)

    def export_excel(self):
        """지금 목록(조회된 전체)을 DB에서 바로 읽어 엑셀로 저장한다(표가 아니라 DB 기준이라
        화면에 보이는 부분만이 아니라 전체가 저장된다). 행 수가 많으면 진행률 창이 뜬다."""
        if not self.vt.ids:
            messagebox.showinfo("알림", "저장할 데이터가 없습니다.")
            return
        conn = dbmod.get_conn()
        try:
            db_rows = conn.execute(
                f"SELECT * FROM stock_counts WHERE {self.vt.where} ORDER BY {self._ORDER}, id",
                self.vt.params).fetchall()
        finally:
            conn.close()
        rows = [self._row_values(i, r, self._view_merged)[2:] for i, r in enumerate(db_rows, start=1)]
        if not rows:
            messagebox.showinfo("알림", "저장할 데이터가 없습니다.")
            return
        headers = ("점포코드", "바코드", "도서명", "조사수량", "AREA", "SECTION", "서가번호", "단", "열", "작업자", "실사일자", "실사시간")
        path = export_rows_to_excel(rows, headers, default_name=f"실적관리_{file_date(self.app)}.xlsx", parent=self)
        if path:
            messagebox.showinfo("완료", f"저장되었습니다:\n{path}")


    # ------------------------------------------------------------------
    # 위치(AREA/SECTION/서가번호) 수정 (여러 줄 한꺼번에 / 한 줄) + 수정 취소
    # [2026-10-14] ZZOINT 실적관리의 [로케이션 수정]을 KOINTBOOK 위치 세 칸(AREA/SECTION/서가번호)에 맞게 가져왔다.
    # ------------------------------------------------------------------
    @staticmethod
    def _loc_txt(area, section, shelf):
        return f"{area or '(없음)'}-{section or '(없음)'}-{shelf or '(없음)'}"

    @staticmethod
    def _norm_section(v):
        """SECTION을 숫자면 3자리 0채움으로 맞춘다(DB에 "1"과 "001"이 섞여 있어도 같은 위치로 본다)."""
        v = str(v or "").strip()
        return v.zfill(SECTION_MAX_LEN) if v.isdigit() else v

    @staticmethod
    def _fmt_sources(sources, limit=6):
        """위치별 건수 목록을 짧게: 처음 몇 곳만 보여주고 나머지는 '외 N곳'으로 줄인다."""
        n = len(sources)
        total = sum(c for _loc, c in sources)
        head = ", ".join(f"{loc}({c:,}건)" for loc, c in sources[:limit])
        if n <= limit:
            return head
        return f"{n:,}곳 {total:,}건 — 예: {head} … 외 {n - limit:,}곳"

    def _plan_location_move(self, ids, target):
        """ids 줄들을 target(area, section, shelf_no) 위치로 수정할 때의 결과를 미리 계산한다(DB는 안 바꿈).
        - 이미 target 위치에 있는 줄은 건너뛴다(skipped).
        - 서로 다른 위치에서 모인 줄도 모두 target 한 곳으로 가며, 원래 순서(위치, 단, 열, 등록순)대로
          target의 마지막 빈 열부터 차례로 열을 배정한다(단은 target에 이미 있던 최근 단, 없으면 1단).
        - 작업자는 target에 이미 있던 작업자를 따르고, target이 새 위치면 각 줄의 기존 작업자를 그대로 둔다.
        반환: dict(items, sources=[(위치글자, 건수)], skipped, dan, has_existing, worker)"""
        t_area, t_section, t_shelf = target
        ids = [int(i) for i in ids]
        conn = dbmod.get_conn()
        rows = []
        for k in range(0, len(ids), 500):
            chunk = ids[k:k + 500]
            q = ",".join("?" * len(chunk))
            rows += conn.execute(f"SELECT * FROM stock_counts WHERE id IN ({q})", chunk).fetchall()
        if not rows:
            conn.close()
            return dict(items=[], sources=[], skipped=0, dan="", has_existing=False, worker=None)

        def num(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return 0

        def loc_of(x):
            # AREA는 2자리, SECTION은 3자리로 맞춰 비교 (DB에 0채움 없는 값이 섞여 있어도 같은 위치로 취급)
            return (normalize_area(x["area"]), self._norm_section(x["section"]), x["shelf_no"] or "")

        movable = [x for x in rows if loc_of(x) != (t_area, t_section, t_shelf)]
        skipped = len(rows) - len(movable)
        movable.sort(key=lambda x: (loc_of(x)[0], loc_of(x)[1], x["shelf_no"] or "",
                                    num(x["dan"]), num(x["yeol"]), x["id"]))
        move_ids = {x["id"] for x in movable}

        first = rows[0]
        a_vars = _digit_code_variants(t_area, AREA_MAX_LEN)
        s_vars = _digit_code_variants(t_section, SECTION_MAX_LEN)
        existing = [e for e in conn.execute(
            "SELECT id, dan, yeol, worker_code, worker_name FROM stock_counts "
            "WHERE store_code=? AND survey_date=? "
            f"AND area IN ({','.join('?' * len(a_vars))}) AND section IN ({','.join('?' * len(s_vars))}) "
            "AND shelf_no=? ORDER BY id DESC",
            (first["store_code"], first["survey_date"], *a_vars, *s_vars, t_shelf)).fetchall()
            if e["id"] not in move_ids]
        conn.close()

        if existing:
            dan = existing[0]["dan"]
            worker = (existing[0]["worker_code"], existing[0]["worker_name"])
            taken = {num(e["yeol"]) for e in existing if e["dan"] == dan}
        else:
            dan, worker, taken = "1", None, set()

        items, sources, yeol = [], {}, 0
        for x in movable:
            yeol += 1
            while yeol in taken:
                yeol += 1
            key = self._loc_txt(*loc_of(x))
            sources[key] = sources.get(key, 0) + 1
            items.append(dict(
                id=x["id"], isbn=x["isbn"], dan=str(dan), yeol=str(yeol),
                worker_code=worker[0] if worker else x["worker_code"],
                worker_name=worker[1] if worker else x["worker_name"],
                old=(x["area"], x["section"], x["shelf_no"], x["dan"], x["yeol"], x["worker_code"], x["worker_name"]),
            ))
        return dict(items=items, sources=list(sources.items()), skipped=skipped,
                    dan=str(dan), has_existing=bool(existing), worker=worker)

    def _kind_conflicts(self, plan, target):
        """[2026-10-16] 위치를 target AREA로 옮길 때 서적/문구 구분이 안 맞게 되는 줄 [(item, 정보)]."""
        items = plan["items"]
        if not items:
            return []
        conn = dbmod.get_conn()
        try:
            res = barcode_kind.check_many(conn, self.app.state.store_code,
                                          [(target[0], it["isbn"]) for it in items])
        finally:
            conn.close()
        return [(it, m) for it, m in zip(items, res) if m]

    def _apply_location_plan(self, plan, target):
        """_plan_location_move 결과를 DB에 반영하고, 마지막 수정 1회를 [수정 취소]용으로 기억한다."""
        conn = dbmod.get_conn()
        conn.executemany(
            "UPDATE stock_counts SET area=?, section=?, shelf_no=?, dan=?, yeol=?, worker_code=?, worker_name=? WHERE id=?",
            [(target[0], target[1], target[2], it["dan"], it["yeol"], it["worker_code"], it["worker_name"], it["id"])
             for it in plan["items"]])
        conn.commit()
        conn.close()
        self._last_loc_edit = [(it["id"],) + tuple(it["old"]) for it in plan["items"]]
        self._apply_changes(changed_ids=[it["id"] for it in plan["items"]])

    def undo_location_edit(self, parent=None):
        """[수정 취소]: 가장 최근에 한 위치 수정 1회를 원래대로 되돌린다."""
        last = getattr(self, "_last_loc_edit", None)
        owner = parent if parent is not None else self
        if not last:
            messagebox.showinfo("알림", "취소할 위치 수정이 없습니다.", parent=owner)
            return
        if not messagebox.askyesno("수정 취소", f"마지막 위치 수정({len(last):,}건)을 취소하고\n원래 위치로 되돌릴까요?",
                                   parent=owner):
            return
        conn = dbmod.get_conn()
        conn.executemany(
            "UPDATE stock_counts SET area=?, section=?, shelf_no=?, dan=?, yeol=?, worker_code=?, worker_name=? WHERE id=?",
            [(a, sec, sh, dan, yeol, wc, wn, rid) for (rid, a, sec, sh, dan, yeol, wc, wn) in last])
        conn.commit()
        conn.close()
        ids = [x[0] for x in last]
        self._last_loc_edit = None
        self._apply_changes(changed_ids=ids)
        messagebox.showinfo("완료", f"{len(ids):,}건의 위치를 원래대로 되돌렸습니다.", parent=owner)

    def open_location_edit_checked_main(self):
        """맨 위 목록에서 체크한 줄들의 위치 수정."""
        self.open_location_edit_popup(self.vt.checked_ids())

    def open_location_edit_popup(self, ids, parent=None):
        """체크한 여러 줄의 위치(AREA/SECTION/서가번호)를 한 곳으로 수정하는 확인 팝업(미리보기 포함)."""
        ids = [int(i) for i in ids]
        owner = parent if parent is not None else self
        if not ids:
            messagebox.showinfo("알림", "위치를 수정할 줄을 체크박스로 먼저 선택하세요.", parent=owner)
            return
        popup = tk.Toplevel(owner)
        center_on_app(popup)
        popup.title("위치 수정")
        popup.configure(bg=CL_BG)
        popup.resizable(False, False)
        try:
            popup.transient(owner.winfo_toplevel())
            popup.grab_set()
        except tk.TclError:
            pass
        popup.bind("<Escape>", lambda e: popup.destroy())

        frm = tk.Frame(popup, bg=CL_BG)
        frm.pack(fill=tk.BOTH, expand=True, padx=22, pady=18)
        tk.Label(frm, text=f"선택한 {len(ids):,}건의 위치를 수정합니다", bg=CL_BG, fg=CL_NAVY,
                 font=("", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        lbl_from = tk.Label(frm, text="", bg=CL_BG, fg=CL_TEXT, justify="left", font=("", 10), wraplength=440)
        lbl_from.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 10))

        EOPT = dict(relief="flat", highlightthickness=2, highlightbackground="#2E9E4F",
                    highlightcolor="#2E9E4F", font=("", 12, "bold"))
        fields = []
        for r, (label, width, maxlen) in enumerate((("수정할 AREA (2자리)", 8, AREA_MAX_LEN),
                                                    ("수정할 SECTION (3자리)", 8, SECTION_MAX_LEN),
                                                    ("수정할 서가번호 (20자리 이하)", 24, SHELF_NO_MAX_LEN))):
            tk.Label(frm, text=label, bg=CL_BG, fg=CL_TEXT_DIM).grid(row=2 + r, column=0, sticky="w", padx=(0, 14), pady=3)
            e = tk.Entry(frm, width=width, **EOPT)
            _limit_entry_length(e, maxlen)
            e.grid(row=2 + r, column=1, ipady=4, sticky="w", pady=3)
            fields.append(e)
        e_area, e_section, e_shelf = fields

        # 기존 값(선택한 줄 중 첫 줄의 현재 위치)을 미리 채워 두고, 칸에 커서가 올 때마다 전체 선택해서
        # 바로 새 값을 치면 덮어쓰게 한다(Tab/Enter로 다음 칸으로 가도 마찬가지).
        try:
            conn = dbmod.get_conn()
            cur_row = conn.execute("SELECT area, section, shelf_no FROM stock_counts WHERE id=?", (ids[0],)).fetchone()
            conn.close()
        except Exception:
            cur_row = None
        if cur_row:
            for e, v in zip(fields, (normalize_area(cur_row["area"]), self._norm_section(cur_row["section"]),
                                     cur_row["shelf_no"])):
                e.insert(0, str(v or ""))

        def _select_all(ev):
            w = ev.widget
            w.after_idle(lambda: (w.select_range(0, tk.END), w.icursor(tk.END)))

        for e in fields:
            e.bind("<FocusIn>", _select_all)
            e.bind("<ButtonRelease-1>", lambda ev: ev.widget.after_idle(lambda w=ev.widget: w.select_range(0, tk.END)))

        lbl_prev = tk.Label(frm, text="", bg="#F1F6FB", fg=CL_TEXT, justify="left", anchor="w",
                            font=("", 10), padx=10, pady=8, width=56, wraplength=430)
        lbl_prev.grid(row=5, column=0, columnspan=2, sticky="we", pady=(12, 0))
        tk.Label(frm, text="서로 다른 위치의 줄도 모두 위 위치 한 곳으로 수정됩니다.\n"
                           "수정 후에도 [수정 취소]로 마지막 수정을 되돌릴 수 있습니다.",
                 bg=CL_BG, fg=CL_TEXT_DIM, font=("", 9), justify="left").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

        first_plan = self._plan_location_move(ids, ("\x00", "\x00", "\x00"))   # 원래 위치별 건수 집계용
        lbl_from.config(text="현재 위치(AREA-SECTION-서가번호) : " + self._fmt_sources(first_plan["sources"]))

        state = {"plan": None, "target": None}

        def read_target(show_msg=False):
            """입력칸을 검사해 (area, section, shelf)를 돌려준다. 아직 덜 입력했거나 자릿수가 틀리면 None."""
            ra, rs, rh = e_area.get().strip(), e_section.get().strip(), e_shelf.get().strip()
            msg, widget = None, None
            if not ra and not rs and not rh:
                msg = "수정할 위치(AREA, SECTION, 서가번호)를 입력하세요."
            elif len(ra) != AREA_MAX_LEN:
                msg, widget = f"AREA는 {AREA_MAX_LEN}자리로 입력하세요.", e_area
            elif not scope.is_valid_area(ra):
                msg, widget = scope.invalid_area_message(), e_area
            elif len(rs) != SECTION_MAX_LEN:
                msg, widget = f"SECTION은 {SECTION_MAX_LEN}자리로 입력하세요.", e_section
            elif not rh and scope.kind_of_area(ra) == "문구":
                rh = scope.STATIONERY_SHELF_NO   # 문구는 서가번호가 없어 X로 저장(PDA와 동일)
            elif not rh:
                msg, widget = "서가번호를 입력하세요.", e_shelf
            elif len(rh) > SHELF_NO_MAX_LEN:
                msg, widget = f"서가번호는 {SHELF_NO_MAX_LEN}자리 이하로 입력하세요.", e_shelf
            if msg:
                if show_msg:
                    messagebox.showinfo("알림", msg, parent=popup)
                    if widget is not None:
                        widget.focus_set()
                return None, msg
            return (normalize_area(ra), rs, rh), None

        def update_preview(_e=None):
            tgt, msg = read_target()
            if tgt is None:
                lbl_prev.config(text=msg)
                state["plan"] = state["target"] = None
                return
            plan = self._plan_location_move(ids, tgt)
            state["plan"], state["target"] = plan, tgt
            tgt_txt = self._loc_txt(*tgt)
            if not plan["items"]:
                lbl_prev.config(text="선택한 줄이 모두 이미 이 위치에 있습니다. (수정할 것이 없음)")
                return
            src = self._fmt_sources(plan["sources"])
            yeols = [int(it["yeol"]) for it in plan["items"]]
            lines = [f"{src}  →  {tgt_txt}",
                     f"새 단/열 : {plan['dan']}단 {min(yeols)}열 ~ {max(yeols)}열 (원래 순서대로 배정)"]
            if plan["has_existing"]:
                w = plan["worker"][1] if plan["worker"] and plan["worker"][1] else ""
                lines.append(f"※ {tgt_txt}에 이미 데이터가 있어 그 뒤에 합쳐집니다" + (f" (작업자: {w})" if w else ""))
            else:
                lines.append(f"※ {tgt_txt}은(는) 새 위치입니다 (작업자는 각 줄의 기존 값 유지)")
            if len(plan["sources"]) > 1:
                lines.append("⚠ 서로 다른 위치가 섞여 있습니다 - 모두 한 곳으로 합쳐집니다")
            if plan["skipped"]:
                lines.append(f"※ 이미 {tgt_txt}에 있는 {plan['skipped']:,}건은 제외됩니다")
            kind_bad = self._kind_conflicts(plan, tgt)
            if kind_bad:
                lines.append(f"⛔ {tgt[0]} AREA({scope.kind_of_area(tgt[0])})와 서적/문구 구분이 맞지 않는 줄 "
                             f"{len(kind_bad):,}건 - 이대로는 수정할 수 없습니다")
            lbl_prev.config(text="\n".join(lines))

        def do_apply():
            tgt, _msg = read_target(show_msg=True)
            if tgt is None:
                return
            update_preview()
            plan = state["plan"]
            if plan is None:
                return
            if not plan["items"]:
                messagebox.showinfo("알림", "선택한 줄이 모두 이미 이 위치에 있습니다.", parent=popup)
                return
            tgt_txt = self._loc_txt(*tgt)
            # [2026-10-16] 옮겨 갈 AREA가 서적이면 서적 상품만, 문구면 문구 상품만 들어갈 수 있다.
            kind_bad = self._kind_conflicts(plan, tgt)
            if kind_bad:
                popup.bell()
                ex = "\n".join(f"· {barcode_kind.short(m)}" for _it, m in kind_bad[:6])
                more = f"\n  … 외 {len(kind_bad) - 6:,}건" if len(kind_bad) > 6 else ""
                messagebox.showerror(
                    "위치 수정 불가 - 서적/문구 구분",
                    f"선택한 줄 중 {len(kind_bad):,}건이 {tgt[0]} AREA({scope.kind_of_area(tgt[0])})에 "
                    f"들어갈 수 없는 상품입니다.\n수정하지 않았습니다.\n\n{ex}{more}\n\n"
                    "해당 줄을 빼고 선택하거나, 맞는 구분의 AREA로 수정하세요.", parent=popup)
                return
            if len(plan["sources"]) > 1:
                src = self._fmt_sources(plan["sources"])
                if not messagebox.askyesno(
                        "경고 - 서로 다른 위치",
                        f"선택한 줄이 서로 다른 위치에 있습니다.\n\n{src}\n\n"
                        f"모두 {tgt_txt} 한 곳으로 합쳐서 수정합니다.\n계속할까요?",
                        icon="warning", parent=popup):
                    return
            self._apply_location_plan(plan, tgt)
            n = len(plan["items"])
            popup.destroy()
            messagebox.showinfo("완료", f"{n:,}건을 {tgt_txt}(으)로 수정했습니다.\n(잘못했다면 [수정 취소])", parent=owner)

        _job = {"id": None}

        def update_preview_later(_e=None):
            # 키를 칠 때마다 계산하면 많은 줄 선택 시 버벅이므로, 입력이 잠깐 멈추면 한 번만 계산
            if _job["id"] is not None:
                popup.after_cancel(_job["id"])
            _job["id"] = popup.after(250, update_preview)

        for e in fields:
            e.bind("<KeyRelease>", update_preview_later)
        e_area.bind("<Return>", lambda ev: e_section.focus_set())
        e_section.bind("<Return>", lambda ev: e_shelf.focus_set())
        e_shelf.bind("<Return>", lambda ev: do_apply())
        btn_row = tk.Frame(popup, bg=CL_BG)
        btn_row.pack(fill=tk.X, padx=22, pady=(0, 16))
        win_button(btn_row, text="수정완료", command=do_apply, kind="accent").pack(side=tk.LEFT)
        win_button(btn_row, text="취소", command=popup.destroy, kind="normal").pack(side=tk.LEFT, padx=8)
        update_preview()
        popup.after(50, e_area.focus_set)

    def _compute_next_dan_yeol(self, area, section, shelf_no):
        """이 위치(AREA/SECTION/서가번호)에 이미 데이터가 있으면, 최근에
        쓰던 단을 기준으로 비어있는 다음 열 번호와, 그 위치에서 쓰던
        작업자를 찾아 돌려준다. 처음 쓰는 위치면 1단 1열 + 작업자 없음(새
        위치 표시)을 돌려준다.
        반환: (단, 열, (작업자코드, 작업자명) 또는 None)"""
        conn = dbmod.get_conn()
        rows = conn.execute(
            "SELECT dan, yeol, worker_code, worker_name FROM stock_counts "
            "WHERE store_code=? AND survey_date=? AND area=? AND section=? AND shelf_no=? ORDER BY id DESC",
            (self.app.state.store_code, self.app.state.survey_date, area, section, shelf_no)
        ).fetchall()
        conn.close()

        if not rows:
            return "1", "1", None

        last_dan = rows[0]["dan"]
        worker_code = rows[0]["worker_code"]
        worker_name = rows[0]["worker_name"]

        existing_yeols = set()
        for r in rows:
            if r["dan"] == last_dan:
                try:
                    existing_yeols.add(int(r["yeol"]))
                except (TypeError, ValueError):
                    pass
        next_yeol = 1
        while next_yeol in existing_yeols:
            next_yeol += 1

        return last_dan, str(next_yeol), (worker_code, worker_name)

    def _find_worker_for_area_section(self, area, section):
        """[2026-09-28] 이 AREA/SECTION(서가번호는 상관없이)에서 최근에 쓰던
        작업자를 찾아 (작업자코드, 작업자명)으로 돌려준다 - 없으면 None.
        _compute_next_dan_yeol의 작업자 추정은 AREA/SECTION/서가번호가 전부
        같아야 했는데(단/열 계산용), 작업자 자동배정은 "이미 쓰던 에리어,
        섹션"이면 충분하다는 요청이라 서가번호는 빼고 더 넓게 찾는다."""
        area = normalize_area(area)
        conn = dbmod.get_conn()
        row = conn.execute(
            "SELECT worker_code, worker_name FROM stock_counts "
            "WHERE store_code=? AND survey_date=? AND area=? AND section=? "
            "ORDER BY id DESC LIMIT 1",
            (self.app.state.store_code, self.app.state.survey_date, area, section)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return row["worker_code"], row["worker_name"]

    def _load_worker_choices(self):
        """작업자마스터(workers)에 등록된 작업자 목록을 [(코드, 이름), ...]로
        돌려준다 - "이미 쓰던 에리어/섹션이 아니라서" 자동배정할 작업자가
        없을 때, 이 중에서 고르게 한다."""
        conn = dbmod.get_conn()
        rows = conn.execute("SELECT worker_code, worker_name FROM workers ORDER BY worker_code").fetchall()
        conn.close()
        return [(r["worker_code"], r["worker_name"]) for r in rows]

    def open_register_popup(self, parent=None):
        """실적 데이터를 직접 등록(추가)하는 팝업. 바코드/수량/AREA/SECTION/
        서가번호만 입력하면, 단/열은 그 위치의 다음 순번으로 자동 계산된다.
        [2026-09-28 재수정] 작업자는: 이미 쓴 적 있는 AREA/SECTION이면 그때
        쓰던 작업자를 그대로 자동배정하고(읽기전용으로 보여줌), 처음 쓰는
        AREA/SECTION이면 더 이상 'KOINTBOOK'으로 무조건 고정하지 않고
        작업자마스터에 등록된 작업자 중에서 직접 고르게 한다.

        [2026-09-28 버그수정] "조회팝업창에서 등록버튼을 누르면 조회팝업창은
        닫혀" - 조회 결과 팝업의 [등록] 버튼도 이 메서드를 그대로 썼는데,
        parent 없이 항상 tk.Toplevel(self)로(메인 화면 기준) 만들다 보니
        이 등록 팝업이 메인 화면에 transient로 붙고 grab까지 가져가면서,
        그 위에 떠 있던 조회 팝업이 뒤로 밀려 안 보이게(닫힌 것처럼)
        됐었다. 이제 조회 팝업에서 열 때는 parent=그 팝업을 넘겨받아
        등록 팝업이 조회 팝업 위에 transient로 붙게 한다(edit_in_popup이
        open_edit_popup에 parent=popup을 넘기는 것과 동일한 방식)."""
        owner = parent if parent is not None else self
        popup = tk.Toplevel(owner)
        center_on_app(popup)
        popup.title("실적 등록")
        popup.geometry("380x460")
        popup.configure(bg=CL_BG)
        popup.resizable(False, False)
        try:
            popup.transient(owner.winfo_toplevel())
            popup.grab_set()
        except tk.TclError:
            pass
        popup.bind("<Escape>", lambda e: popup.destroy())

        frm = tk.Frame(popup, bg=CL_BG)
        frm.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        ENTRY_OPT = dict(relief="flat", highlightthickness=1, highlightbackground="#C4C8D0",
                          highlightcolor=CL_NAVY, font=("", 11))

        tk.Label(frm, text="바코드", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=0, column=0, sticky="w", pady=8)
        e_isbn = tk.Entry(frm, width=20, **ENTRY_OPT)
        e_isbn.grid(row=0, column=1, pady=8, ipady=4)

        # [2026-09-28] ZZOINT처럼 바코드를 입력하는 즉시(키를 뗄 때마다) 도서명을
        # 상품마스터에서 찾아 미리 보여준다(등록 전에 바코드를 잘못 입력했는지
        # 바로 확인할 수 있음).
        tk.Label(frm, text="도서명", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=1, column=0, sticky="w", pady=8)
        lbl_bookname = tk.Label(frm, text="", bg=CL_BG, fg=CL_TEXT_DIM, font=("", 10), anchor="w",
                                wraplength=200, justify="left")
        lbl_bookname.grid(row=1, column=1, sticky="w", pady=8)

        tk.Label(frm, text="수량", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=2, column=0, sticky="w", pady=8)
        e_qty = tk.Entry(frm, width=20, **ENTRY_OPT)
        e_qty.grid(row=2, column=1, pady=8, ipady=4)

        # [2026-09-28] AREA 2자리/SECTION 3자리/서가번호 20자리 이하로(2026-10-16 11->20) PDA와
        # 동일하게 입력 글자수 자체를 제한한다(_limit_entry_length).
        tk.Label(frm, text="AREA", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=3, column=0, sticky="w", pady=8)
        e_area = tk.Entry(frm, width=20, **ENTRY_OPT)
        e_area.grid(row=3, column=1, pady=8, ipady=4)
        _limit_entry_length(e_area, AREA_MAX_LEN)

        tk.Label(frm, text="SECTION", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=4, column=0, sticky="w", pady=8)
        e_section = tk.Entry(frm, width=20, **ENTRY_OPT)
        e_section.grid(row=4, column=1, pady=8, ipady=4)
        _limit_entry_length(e_section, SECTION_MAX_LEN)

        tk.Label(frm, text="서가번호", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=5, column=0, sticky="w", pady=8)
        e_shelf = tk.Entry(frm, width=24, **ENTRY_OPT)
        e_shelf.grid(row=5, column=1, pady=8, ipady=4)
        _limit_entry_length(e_shelf, SHELF_NO_MAX_LEN)

        tk.Label(frm, text="단 / 열", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=6, column=0, sticky="w", pady=8)
        lbl_danyeol = tk.Label(frm, text="(위치 입력 시 자동)", bg=CL_BG, fg=CL_NAVY, font=("", 11, "bold"))
        lbl_danyeol.grid(row=6, column=1, sticky="w", pady=8)

        # [2026-09-28 재수정] 작업자 칸은 두 가지 모습을 오간다 - 이미 쓰던
        # AREA/SECTION이면 자동배정된 이름만 보여주는 읽기전용 라벨(lbl_worker),
        # 처음 쓰는 AREA/SECTION이면 작업자마스터 중에서 고르는 드롭다운
        # (cb_worker)을 같은 자리에 겹쳐두고 필요한 쪽만 보이게 한다.
        tk.Label(frm, text="작업자", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=7, column=0, sticky="w", pady=8)
        lbl_worker = tk.Label(frm, text="(위치 입력 시 자동)", bg=CL_BG, fg=CL_NAVY, font=("", 11, "bold"))
        lbl_worker.grid(row=7, column=1, sticky="w", pady=8)

        worker_var = tk.StringVar()
        cb_worker = ttk.Combobox(frm, textvariable=worker_var, state="readonly", width=22)
        # (처음엔 안 보이게 - 필요할 때(새 AREA/SECTION일 때)만 grid로 띄운다)

        state = {"dan": None, "yeol": None, "worker_code": None, "worker_name": None,
                 "worker_choices": [], "worker_needs_pick": False}

        def on_worker_picked(_e=None):
            idx = cb_worker.current()
            if idx is not None and 0 <= idx < len(state["worker_choices"]):
                state["worker_code"], state["worker_name"] = state["worker_choices"][idx]

        cb_worker.bind("<<ComboboxSelected>>", on_worker_picked)

        def compute_from_location():
            area = normalize_area(e_area.get().strip())
            section = e_section.get().strip()
            shelf_no = e_shelf.get().strip()
            if not area or not section or not shelf_no:
                return False
            dan, yeol, _shelf_worker = self._compute_next_dan_yeol(area, section, shelf_no)
            state["dan"] = dan
            state["yeol"] = yeol
            lbl_danyeol.config(text=f"{dan}단 {yeol}열")

            # [2026-09-28 재수정] 작업자는 (서가번호는 상관없이) AREA/SECTION
            # 기준으로 이미 쓰던 사람이 있으면 그대로 자동배정, 없으면
            # 작업자마스터에서 고르게 한다.
            worker = self._find_worker_for_area_section(area, section)
            if worker:
                state["worker_code"], state["worker_name"] = worker
                state["worker_needs_pick"] = False
                cb_worker.grid_forget()
                lbl_worker.config(text=state["worker_name"])
                lbl_worker.grid(row=7, column=1, sticky="w", pady=8)
            else:
                # [2026-09-28 재수정] "작업자 선택칸 기본값은 작업자마스터에
                # 없는 KOINTBOOK 으로 해주고 그밑부터 작업자마스터에 있는
                # 리스트로해줘" - 처음 쓰는 AREA/SECTION이라 자동배정할 작업자가
                # 없을 때, 실제 작업자마스터의 첫 번째 사람이 아무 확인 없이
                # 기본값으로 잡혀버리면(예전 방식) 그 사람이 실제로 작업하지
                # 않았는데도 등록될 위험이 있었다. 작업자마스터에는 없는
                # "KOINTBOOK"을 맨 앞에 얹어 기본값으로 두고, 실제 작업자는
                # 그 아래 목록에서 직접 고르게 한다.
                choices = [("KOINTBOOK", "KOINTBOOK")] + self._load_worker_choices()
                state["worker_choices"] = choices
                state["worker_needs_pick"] = True
                lbl_worker.grid_forget()
                if choices:
                    cb_worker["values"] = [f"{code} - {name}" for code, name in choices]
                    # 직전에 고른 사람이 있으면 그대로 유지, 없으면 첫 번째를 기본값으로.
                    try:
                        keep_idx = next(i for i, (c, n) in enumerate(choices) if c == state["worker_code"])
                    except StopIteration:
                        keep_idx = 0
                    cb_worker.current(keep_idx)
                    state["worker_code"], state["worker_name"] = choices[keep_idx]
                else:
                    cb_worker["values"] = []
                    worker_var.set("")
                    state["worker_code"], state["worker_name"] = None, None
                cb_worker.grid(row=7, column=1, sticky="w", pady=8)
            return True

        # [2026-09-29] "영문 대소문자 구분없이 상품마스터에 맞는쪽으로 자동변경" -
        # COLLATE NOCASE로 대소문자를 구분하지 않고 찾고, isbn 컬럼도 같이
        # 조회해서 실제 저장은 상품마스터 표기 그대로 맞춘다 (submit() 참고).
        def find_book(isbn):
            conn = dbmod.get_conn()
            b = conn.execute(
                "SELECT isbn, book_name FROM books WHERE store_code=? AND isbn=? COLLATE NOCASE LIMIT 1",
                (self.app.state.store_code, isbn)
            ).fetchone()
            conn.close()
            return b

        def on_isbn_changed(_e=None):
            bc = e_isbn.get().strip()
            if not bc:
                lbl_bookname.config(text="")
                return
            b = find_book(bc)
            lbl_bookname.config(text=b["book_name"] if b else "(상품마스터에 없음)")

        e_isbn.bind("<KeyRelease>", on_isbn_changed)

        def submit():
            isbn = e_isbn.get().strip()
            qty_s = e_qty.get().strip()
            # [2026-09-28] PDA(LocationInputActivity)의 검사값을 PC 등록
            # 팝업에도 동일하게 적용한다 - normalize_area()는 "1"도 "01"로
            # 채워버려서(뒤에서 저장/자동배정용으로는 필요) 자릿수 검사를
            # normalize 이후 값으로 하면 "1"자리만 입력해도 통과해버린다.
            # 그래서 자릿수 검사는 반드시 사용자가 실제로 입력한 원본
            # 문자열(raw_area/raw_section) 기준으로 한다.
            raw_area = e_area.get().strip()
            raw_section = e_section.get().strip()
            raw_shelf = e_shelf.get().strip()
            # [2026-09-28 버그수정] "01"처럼 앞자리 0이 있는 AREA도 그대로
            # 저장해야, 맨 위 목록에 보이는 값("01")과 실제 DB에 저장된
            # 값이 일치한다(다르면 이 수정 팝업에서 "1"로 보이는 문제가
            # 생겼었다) - 또한 이래야 작업자 자동배정(AREA/SECTION 일치
            # 검사)도 항상 정확히 맞는다.
            # [2026-10-15] 문구 AREA(20~29, 80~89)는 서가번호를 비워 두면 X로 저장한다(PDA와 동일).
            if not raw_shelf and scope.kind_of_area(raw_area) == "문구":
                raw_shelf = scope.STATIONERY_SHELF_NO
                e_shelf.insert(0, raw_shelf)
            area = normalize_area(raw_area)
            section = raw_section
            shelf_no = raw_shelf
            if not isbn or not qty_s or not area or not section or not shelf_no:
                messagebox.showinfo("알림", "바코드/수량/AREA/SECTION/서가번호를 모두 입력하세요.", parent=popup)
                return
            # [2026-09-28] AREA 2자리필수 / SECTION 3자리필수 / 서가번호
            # 20자리이하 - android_app의 LocationInputActivity.enterLocation()과
            # 동일한 검사, 같은 안내문구를 쓴다(PDA/PC가 서로 다른 자릿수를
            # 허용하면 같은 위치라도 PDA에서 찍은 값과 PC에서 등록한 값이
            # 서로 어긋날 수 있어서 반드시 맞춰야 한다).
            if len(raw_area) != AREA_MAX_LEN:
                messagebox.showinfo("알림", f"AREA는 {AREA_MAX_LEN}자리로 입력하세요.", parent=popup)
                e_area.focus_set()
                return
            if not scope.is_valid_area(raw_area):
                messagebox.showinfo("알림", scope.invalid_area_message(), parent=popup)
                e_area.focus_set()
                e_area.selection_range(0, tk.END)
                return
            if len(raw_section) != SECTION_MAX_LEN:
                messagebox.showinfo("알림", f"SECTION은 {SECTION_MAX_LEN}자리로 입력하세요.", parent=popup)
                e_section.focus_set()
                return
            if len(raw_shelf) > SHELF_NO_MAX_LEN:
                messagebox.showinfo("알림", f"서가번호는 {SHELF_NO_MAX_LEN}자리 이하로 입력하세요.", parent=popup)
                e_shelf.focus_set()
                return
            try:
                qty = int(qty_s)
            except ValueError:
                messagebox.showinfo("알림", "수량은 숫자로 입력하세요.", parent=popup)
                return

            # [2026-10-16] 서적 AREA에 문구 상품, 문구 AREA에 서적 상품은 등록할 수 없다.
            if _kind_blocked(popup, self.app.state.store_code, area, isbn):
                e_isbn.focus_set()
                e_isbn.selection_range(0, tk.END)
                return

            compute_from_location()

            if state["worker_needs_pick"] and not state["worker_code"]:
                messagebox.showinfo(
                    "알림",
                    "처음 쓰는 AREA/SECTION입니다. 작업자마스터에 등록된 작업자가 없어\n"
                    "자동배정할 수 없습니다 - 먼저 [작업자마스터]에 작업자를 등록하세요.",
                    parent=popup,
                )
                return

            book = find_book(isbn)
            if book is None:
                # [2026-09-30] 위 저장(수정) 팝업과 동일하게, 미등록 바코드
                # 확인창을 띄우기 직전에 경고음을 울린다.
                if not _confirm_unregistered(popup, "등록"):
                    return
            book_name = book["book_name"] if book else ""
            if book is not None:
                isbn = book["isbn"]  # 상품마스터에 실제 저장된 대소문자로 맞춰 저장

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = dbmod.get_conn()
            cur = conn.execute(
                """INSERT INTO stock_counts
                   (store_code, store_name, survey_date, area, section, shelf_no, dan, yeol, isbn,
                    book_name, qty, worker_code, worker_name, received_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (self.app.state.store_code, self.app.state.store_name, self.app.state.survey_date,
                 area, section, shelf_no, state["dan"], state["yeol"], isbn, book_name,
                 qty, state["worker_code"], state["worker_name"], now)
            )
            new_id = cur.lastrowid
            conn.commit()
            conn.close()

            # [2026-09-29] "등록팝업창에서 엔터를 눌러서 등록완료 버튼이나
            # 엔터를 눌러 등록완료될시 등록완료 팝업창을 띄워줘" - 지금까지는
            # 저장만 조용히 되고 아무 확인창도 없었다. [등록완료] 버튼 클릭과
            # 엔터(서가번호에서 바로, 또는 작업자 선택칸에서)로 등록이
            # 완료되는 경로가 모두 이 submit() 하나로 모이므로, 여기 한
            # 곳에서만 띄워도 두 경로 전부 커버된다.
            messagebox.showinfo("등록완료", "등록되었습니다.", parent=popup)

            self._apply_changes(added_ids=[new_id])
            # 연속으로 계속 등록할 수 있도록, 바코드/수량만 비우고 위치는
            # 그대로 둔 채 다음 열 번호로 다시 계산해서 이어간다.
            e_isbn.delete(0, tk.END)
            e_qty.delete(0, tk.END)
            lbl_bookname.config(text="")
            compute_from_location()
            e_isbn.focus_set()

        # [2026-09-28] "AREA 입력 후 다음칸으로 넘어갈 때 2자리가 아니면 바로
        # 제어" - 예전엔 submit() 시점에서만 자릿수를 검사해서, 다음 칸으로
        # 넘어간 뒤 한참 더 입력하고 나서야 "AREA는 2자리로 입력하세요"를
        # 보게 됐다. PDA(LocationInputActivity.confirmField())처럼 칸을
        # 떠나려는 그 순간(Tab/Enter로 다음 칸으로 넘어가려 할 때)에 바로
        # 자릿수를 확인해서, 안 맞으면 그 칸에 그대로 붙잡아두고 전체 선택
        # 상태로 만들어(바로 다시 입력 가능) 다음 칸으로 못 넘어가게 막는다.
        def _confirm_field(entry, field_label, exact_len, advance):
            text = entry.get().strip()
            if not text:
                messagebox.showinfo("알림", f"{field_label}를 입력하세요.", parent=popup)
                entry.focus_set()
                return "break"
            if exact_len is not None and len(text) != exact_len:
                messagebox.showinfo("알림", f"{field_label}는 {exact_len}자리로 입력하세요.", parent=popup)
                entry.selection_range(0, tk.END)
                entry.focus_set()
                return "break"
            if field_label == "AREA" and not scope.is_valid_area(text):
                messagebox.showinfo("알림", scope.invalid_area_message(), parent=popup)
                entry.selection_range(0, tk.END)
                entry.focus_set()
                return "break"
            advance()
            return "break"

        e_isbn.bind("<Return>", lambda e: (e_qty.focus_set(), "break"))
        e_qty.bind("<Return>", lambda e: (e_area.focus_set(), "break"))
        # 탭 키도 Enter와 똑같이 "다음 칸으로 넘어가는" 동작이라, 기본 탭
        # 이동에 맡기지 않고 Enter와 같은 검사 함수로 가로챈다(자릿수가
        # 안 맞으면 탭을 눌러도 다음 칸으로 못 넘어간다).
        e_area.bind("<Return>", lambda e: _confirm_field(e_area, "AREA", AREA_MAX_LEN, e_section.focus_set))
        e_area.bind("<Tab>", lambda e: _confirm_field(e_area, "AREA", AREA_MAX_LEN, e_section.focus_set))
        def _to_shelf():
            # 문구 AREA면 서가번호 칸이 비어 있을 때 X를 채워 준다(문구는 서가번호 없음).
            if not e_shelf.get().strip() and scope.kind_of_area(e_area.get().strip()) == "문구":
                e_shelf.insert(0, scope.STATIONERY_SHELF_NO)
            e_shelf.focus_set()

        e_section.bind("<Return>", lambda e: _confirm_field(e_section, "SECTION", SECTION_MAX_LEN, _to_shelf))
        e_section.bind("<Tab>", lambda e: _confirm_field(e_section, "SECTION", SECTION_MAX_LEN, _to_shelf))
        def _advance_from_shelf():
            # [2026-09-28] "상품마스터에없는 상품 입력 팝업창은 작업자까지
            # 선택후... 그 다음에 뜨게 해줘" - 예전엔 서가번호 칸에서
            # 엔터를 치면 바로 submit()이 불려서, 작업자 선택칸(cb_worker)에
            # 는 한 번도 포커스가 가지 않은 채(화면에 기본값만 떠 있는
            # 상태로) 곧바로 "상품마스터에 없는 바코드..." 확인창까지
            # 나와버렸다. 이제는 서가번호 다음엔 무조건 submit()으로 바로
            # 가지 않고, 새로 쓰는 AREA/SECTION이라 작업자를 "선택해야 하는"
            # 상황(worker_needs_pick)이면 먼저 작업자 선택칸으로 포커스를
            # 옮겨서 사용자가 실제로 그 칸을 거쳐가게 하고, 거기서 엔터를
            # 쳐야 최종 등록(및 상품마스터 확인창)으로 이어진다. 이미 쓰던
            # AREA/SECTION이라 작업자가 자동배정(읽기전용 라벨)되는
            # 경우에는 고를 칸 자체가 없으니 예전처럼 바로 등록한다.
            compute_from_location()
            if state["worker_needs_pick"]:
                cb_worker.focus_set()
            else:
                submit()

        e_shelf.bind("<Return>", lambda e: _confirm_field(e_shelf, "서가번호", None, _advance_from_shelf))
        # 작업자 선택칸에서 엔터를 치면(=작업자까지 선택을 마치면) 그제서야
        # 최종 등록을 진행한다 - 상품마스터에 없는 바코드 확인창도 이 시점
        # 이후에야 뜨게 된다.
        cb_worker.bind("<Return>", lambda e: (submit(), "break"))

        def _confirm_shelf_tab(_e=None):
            # 서가번호는 AREA/SECTION과 달리 정해진 자릿수가 없어(최대
            # 20자리는 입력 글자수 제한으로 이미 막혀 있음) 탭으로 다음
            # 칸(작업자 선택 등)으로 넘어갈 때는 "비어있지 않은지"만 확인
            # 하고, 문제 없으면 탭의 기본 동작(다음 위젯으로 포커스 이동)을
            # 그대로 둔다(area/section처럼 "break"로 가로채지 않음).
            if not e_shelf.get().strip():
                messagebox.showinfo("알림", "서가번호를 입력하세요.", parent=popup)
                e_shelf.focus_set()
                return "break"
            return None

        e_shelf.bind("<Tab>", _confirm_shelf_tab)
        e_shelf.bind("<FocusOut>", lambda e: compute_from_location())
        e_area.bind("<FocusOut>", lambda e: compute_from_location())
        e_section.bind("<FocusOut>", lambda e: compute_from_location())

        btn_row = tk.Frame(popup, bg=CL_BG)
        btn_row.pack(fill=tk.X, padx=18, pady=(0, 16))
        win_button(btn_row, text="등록완료", command=submit, kind="accent").pack(side=tk.LEFT)
        win_button(btn_row, text="닫기", command=popup.destroy, kind="normal").pack(side=tk.LEFT, padx=8)

        e_isbn.focus_set()
