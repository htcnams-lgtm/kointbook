# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""화면들이 공통으로 쓰는 색상/헬퍼 함수 모음."""

import functools
import os
import re
import re as _re_area
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont
from datetime import datetime
import calendar as _calendar

# ---- 클래식 디자인 팔레트 (남색+골드+아이보리) ----
CL_NAVY = "#172C5E"
CL_NAVY_DARK = "#10204A"
CL_GOLD = "#B08D3E"
CL_BG = "#F4F2EC"       # 아이보리 배경
CL_PANEL = "#FFFFFF"
CL_GRID = "#C4C8D0"
CL_TEXT = "#191C23"
CL_TEXT_DIM = "#5F6470"
CL_DUP_RED = "#8A2E3B"

# 참고 스크린샷과 비슷한 톤의 색상 (기존 화면들이 이 이름으로 참조하므로,
# 값만 클래식 팔레트로 바꿔서 화면을 일일이 안 고쳐도 전체가 같이 바뀌게 한다)
COLOR_HEADER_BG = CL_PANEL
COLOR_TITLE_BG = CL_NAVY
COLOR_HILITE = "#FFF6CE"
COLOR_TOTAL = "#FFFF66"
COLOR_SUBTOTAL_CYAN = "#F3EAD3"   # 단 소계 - 옅은 골드톤 (클래식 테마와 어울리게)
COLOR_SUBTOTAL_GREEN = "#E8D9B0"  # 로케이션 소계 - 좀 더 진한 골드톤

# 조회/등록/수정/백업 같은 "화면 위쪽 주요 버튼줄"이 모두 같은 크기·글씨체를
# 쓰도록 모아둔 규격 (실적관리 상단 버튼줄, 데이터백업 화면 버튼 등이 공유).
# 색(bg/fg)은 화면마다 따로 지정하고, 크기/글씨만 여기서 통일한다.
TOOLBAR_BTN = dict(font=("", 10), padx=14, pady=6)

_classic_style_ready = False


def ensure_classic_treeview_style():
    """이 앱 전체에서 쓰는 표(Treeview) 스타일을 한 번만 등록한다.
    일부 환경에서 특정 옵션이 안 먹힐 수 있어 try/except로 감싸서,
    실패해도 화면이 멈추지 않고 기본 스타일로 계속 동작하게 한다."""
    global _classic_style_ready
    if _classic_style_ready:
        return
    try:
        style = ttk.Style()
        # PDA DATA 수신 화면의 버튼을 윈도우 네이티브(Windows 11 기본 버튼)
        # 모양으로 만들기 위해 "vista" 테마로 바꿨다 - ttk 테마는 프로그램
        # 전체에 걸리는 설정이라, 아래 표(Treeview) 헤더 커스텀 색상도 같이
        # 영향을 받는다(다른 화면들 표 헤더가 남색 대신 밝은 기본색으로 보일
        # 수 있다 - 사용자가 이 트레이드오프를 승인함). vista는 Windows에서만
        # 있는 테마라, 그 외 환경(예: 이 코드를 macOS/Linux에서 그냥 실행해
        # 볼 때)에서는 실패하고 "clam"으로 자동 대체된다.
        try:
            style.theme_use("vista")
        except Exception:
            try:
                style.theme_use("clam")
            except Exception:
                pass
        style.configure(
            "Classic.Treeview",
            background=CL_PANEL, fieldbackground=CL_PANEL,
            foreground=CL_TEXT, font=("", 9), rowheight=20
        )
        # 헤더 배경을 좀 더 진한 남색톤으로 채워서, 밑줄 없이도 헤더와 본문이
        # 자연스럽게 구분되게 한다 (밑줄은 줄을 선택할 때마다 위치를 다시
        # 계산해야 해서 체감 렉의 원인이 될 수 있어 완전히 뺐다).
        # (참고: vista 테마에서는 Windows가 헤더를 직접 그려서 이 커스텀
        # 색이 안 먹힐 수 있다 - 그 경우 밝은 기본색 헤더로 보인다.)
        style.configure(
            "Classic.Treeview.Heading",
            background="#DFE3EE", foreground=CL_NAVY, font=("", 9),
            padding=(6, 5, 6, 5)
        )
        style.map(
            "Classic.Treeview.Heading",
            background=[("active", "#DFE3EE"), ("pressed", "#DFE3EE")]
        )
        style.map("Classic.Treeview", background=[("selected", "#7B87A6")])

        # 체크박스(☐/☑)가 들어가는 표용 - 글씨체/크기는 다른 표(실적관리 등)와
        # 완전히 동일하게 맞춘다 (앱 전체 목록 글씨체 통일).
        style.configure(
            "BigCheck.Treeview",
            background=CL_PANEL, fieldbackground=CL_PANEL,
            foreground=CL_TEXT, font=("", 9), rowheight=20
        )
        style.configure(
            "BigCheck.Treeview.Heading",
            background="#DFE3EE", foreground=CL_NAVY, font=("", 9),
            padding=(6, 5, 6, 5)
        )
        style.map(
            "BigCheck.Treeview.Heading",
            background=[("active", "#DFE3EE"), ("pressed", "#DFE3EE")]
        )
        style.map("BigCheck.Treeview", background=[("selected", "#7B87A6")])
        # relief/테두리는 일부 환경에서 지원 안 될 수 있어 별도로 감싼다 -
        # 여기서 실패해도 위에서 이미 적용된 배경/글씨색은 그대로 유지된다.
        # (예전에 여기서 bordercolor/relief="solid" 조합을 시도했었는데,
        #  그게 오히려 헤더 칸마다 사각 테두리를 그려버리는 부작용이 있어서
        #  완전히 뺐다. 이제는 relief=flat, borderwidth=0만 써서 테두리가
        #  절대 안 생기게 확실히 고정한다.)
        try:
            style.configure("Classic.Treeview.Heading", relief="flat", borderwidth=0)
            style.map("Classic.Treeview.Heading", relief=[("active", "flat"), ("pressed", "flat")])
            style.configure("BigCheck.Treeview.Heading", relief="flat", borderwidth=0)
            style.map("BigCheck.Treeview.Heading", relief=[("active", "flat"), ("pressed", "flat")])
        except Exception:
            pass

        # PDA DATA 수신 화면 버튼용 ttk 스타일 (Windows 11 네이티브 버튼 시범 적용).
        # vista 테마에서는 배경색을 직접 칠해도 Windows가 그 위에 자기 방식대로
        # 그려버려서 커스텀 색이 안 먹힐 수 있다 - 이 경우 전부 기본 회색
        # 버튼처럼 보인다("Accent.TButton"만은 vista가 기본 제공하는 강조
        # 스타일이라 파란 계열로 확실히 구분된다). 실패해도(다른 테마 등)
        # 무시하고 기본 스타일로 동작한다.
        try:
            style.configure("Win11.TButton", padding=(14, 6), font=("", 9))
            # "Accent.TButton"은 ttk가 vista 테마에서 기본 제공하는 이름이라
            # (Windows의 "강조색" 버튼) - 직접 만든 이름이 아니라 이 이름 그대로
            # 써야 실제로 파란 강조 버튼처럼 그려진다.
            style.configure("Accent.TButton", padding=(14, 6), font=("", 9))
            style.configure("Win11Danger.TButton", padding=(14, 6), font=("", 9),
                            foreground="#C42B1C")
            style.configure("Win11Disabled.TButton", padding=(14, 6), font=("", 9),
                            foreground="#A0A0A0")
            # [PDA DATA 수신] 버튼 전용 - 받을 데이터가 있으면(활성) 초록,
            # 없으면(비활성) 연회색 글자로 구분한다(vista 테마라 배경색은
            # 더 이상 못 바꾼다).
            style.configure("Win11Receive.TButton", padding=(14, 6), font=("", 9))
            style.map("Win11Receive.TButton",
                     foreground=[("disabled", "#A0A0A0"), ("!disabled", "#0B7A34")])
        except Exception:
            pass
    except Exception:
        pass
    _classic_style_ready = True


def win_button(parent, text, command=None, kind="normal", **kw):
    """앱 전체에서 쓰는 Windows 11 스타일 버튼 생성 헬퍼.

    PDA DATA 수신 화면에서만 쓰던 ttk 기반 Win11 버튼 스타일(각진 모서리,
    옅은 테두리, native vista 테마)을 프로그램 전체 화면에 통일 적용하기
    위한 함수. kind로 색 구분만 하고, 크기/모서리/테두리는 스타일이 전부
    처리한다 (화면마다 bg/fg를 따로 안 정해도 됨).

    kind: "normal"(기본 회색), "accent"(강조 - 저장/등록/백업 등 주요 동작),
          "danger"(삭제 등 위험한 동작)
    """
    ensure_classic_treeview_style()
    style_name = {
        "accent": "Accent.TButton",
        "danger": "Win11Danger.TButton",
    }.get(kind, "Win11.TButton")
    return ttk.Button(parent, text=text, command=command, style=style_name, **kw)


def today_str():
    return datetime.now().strftime("%Y%m%d")


def file_date(app):
    """[2026-10-16] 엑셀 파일 이름에 붙이는 날짜 - 컴퓨터의 오늘 날짜가 아니라 상품마스터에서
    세팅한 조사일자(YYYYMMDD). 조사일자가 비어 있을 때만 오늘 날짜를 쓴다."""
    try:
        d = str(app.state.survey_date or "").strip()
    except AttributeError:
        d = ""
    return d or today_str()


def make_labeled_entry(parent, label_text, width=15, readonly=False):
    frame = tk.Frame(parent, bg=COLOR_HEADER_BG)
    tk.Label(frame, text=label_text, bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).pack(side=tk.LEFT, padx=(4, 4))
    entry = tk.Entry(frame, width=width)
    if readonly:
        entry.configure(state="readonly")
    entry.pack(side=tk.LEFT, padx=(0, 8))
    return frame, entry


def _heading_min_width(text, heading_font):
    """헤더 글자(제목)가 잘리지 않을 최소 컬럼 폭을 실제 폰트로 측정해서
    계산한다.

    [2026-09-29] "헤더 항목마다 제목이 잘리지않도록 헤더 항목마다 너비...
    확인해줘" - 그동안은 각 화면이 widths를 숫자로 직접 정해뒀는데, 그
    숫자가 실제 글자 폭보다 좁으면(예: "SECTION"처럼 긴 영문 헤더, "전산재고"
    처럼 4글자 한글 헤더) 헤더 글자 끝이 잘려 보였다(이미 한 번 "SECTION"
    에서 실제로 발견되어 고쳐진 적 있음). 매번 화면마다 눈으로 확인하며
    숫자를 조절하는 대신, 여기서 tkinter의 실제 폰트 측정 기능
    (Font.measure)으로 헤더 글자의 실제 픽셀 폭을 재서, 화면이 지정한
    widths가 그보다 좁으면 자동으로 넓혀준다 - 이러면 이후 화면을 새로
    추가하거나 헤더 문구를 바꿔도 폭 계산을 따로 신경 안 써도 된다.

    text: 헤더 문구(줄바꿈 \\n으로 여러 줄인 헤더도 지원 - 그중 가장 넓은
    줄 기준으로 계산). heading_font: 실제 헤더에 쓰이는 tkinter Font 객체."""
    s = "" if text is None else str(text)
    lines = s.split("\n") if s else [""]
    try:
        max_px = max(heading_font.measure(line) for line in lines)
    except Exception:
        # 폰트 측정이 실패하면(이론상 거의 없음) 안전하게 글자수 기반으로 대충 추정.
        max_px = max(len(line) for line in lines) * 12
    # Classic.Treeview.Heading의 좌우 padding(6+6=12) + 헤더 테두리/정렬
    # 화살표 등 위젯이 추가로 차지하는 여유 공간을 넉넉히 더한다.
    return max_px + 26


def setup_treeview(parent, columns, headings, widths, height=14,
                   style_name="Classic.Treeview", on_yscroll=None):
    """columns: 내부 id 목록, headings: 화면 표시 텍스트, widths: 각 컬럼 너비.
    style_name: 표 스타일 (체크박스 표는 "BigCheck.Treeview").
    on_yscroll: 세로로 스크롤될 때마다 on_yscroll(맨위위치, 맨아래위치)를 불러준다
                (0~1 사이 값. 스크롤이 끝에 닿으면 다음 줄을 더 불러오는 화면에서 사용).

    widths로 넘겨준 값이 헤더 글자 폭보다 좁으면 자동으로 넓혀서, 헤더
    제목이 잘려 보이는 일이 없게 한다(_heading_min_width 참고)."""
    ensure_classic_treeview_style()
    container = tk.Frame(parent, bg=CL_BG)
    tree = ttk.Treeview(container, columns=columns, show="headings", height=height)
    try:
        tree.configure(style=style_name)
    except Exception:
        pass
    try:
        font_spec = ttk.Style().lookup(f"{style_name}.Heading", "font") or ("", 9)
        heading_font = tkfont.Font(font=font_spec)
    except Exception:
        heading_font = None
    for col, head, w in zip(columns, headings, widths):
        tree.heading(col, text=head, anchor="center")
        if heading_font is not None:
            w = max(w, _heading_min_width(head, heading_font))
        tree.column(col, width=w, anchor="center", stretch=False)

    # 줄무늬 음영: 아주 옅게 (모든 화면 공통, 행을 넣을 때 홀수 번째에
    # tags=("odd",)만 붙이면 된다).
    tree.tag_configure("odd", background="#F6F7F9")

    vsb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)

    # 세로 구분선(컬럼 사이): 가로 스크롤을 해도 실제 컬럼 경계와 같이
    # 움직이도록, xscrollcommand를 가로채서 스크롤될 때마다 선 위치를 같이
    # 다시 계산한다. 세로선은 개수가 컬럼 수만큼으로 고정이고 움직일 때만
    # 재계산하면 되니 가로줄 전체 격자보다 부담이 훨씬 적다.
    #
    # [2026-09-23 정정] 폭을 처음 만들 때 넘긴 widths 목록을 그대로 쓰면,
    # 사용자가 헤더 경계를 드래그해서 컬럼 폭을 바꿔도 구분선이 그 자리에
    # 그대로 남아 "헤더와 목록 항목이 따로 노는" 것처럼 보였다 - 그래서
    # 매번 tree.column(col, "width")로 지금 실제 폭을 다시 읽어와 계산하고,
    # 헤더 경계를 드래그하는 동안(<B1-Motion>)에도 계속 다시 그리게 했다.
    sep_frames = []
    try:
        for _ in widths:
            sep_frames.append(tk.Frame(tree, bg="#D7DAE0", width=1))
    except Exception:
        sep_frames = []

    def _reposition_separators():
        if not sep_frames:
            return
        try:
            frac_start, _ = tree.xview()
            cur_widths = [tree.column(col, "width") for col in columns]
            total_width = sum(cur_widths) or 1
            offset = int(frac_start * total_width)
            x_cum = 0
            for sep, w in zip(sep_frames, cur_widths):
                x_cum += w
                sep.place(x=x_cum - offset, y=0, relheight=1.0)
        except Exception:
            pass

    def _on_xscroll(*args):
        hsb.set(*args)
        _reposition_separators()

    def _on_yscroll(first, last):
        vsb.set(first, last)
        if on_yscroll is not None:
            try:
                on_yscroll(float(first), float(last))
            except Exception:
                pass

    tree.configure(yscrollcommand=_on_yscroll, xscrollcommand=_on_xscroll)

    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=1)

    tree.after(30, _reposition_separators)
    tree.bind("<Configure>", lambda e: _reposition_separators())
    # 헤더 경계를 마우스로 드래그해서 컬럼 폭을 바꾸는 동안/바꾼 직후에도
    # 구분선이 같이 따라오게 한다(드래그 중엔 위젯 자체 크기는 안 바뀌어서
    # <Configure>만으로는 안 잡힌다).
    tree.bind("<B1-Motion>", lambda e: _reposition_separators())
    tree.bind("<ButtonRelease-1>", lambda e: _reposition_separators())

    # [2026-09-28] "모든 목록 화면 한칸을 마우스로 클릭하고 복사하면 그
    # 내용만 복사되게" - ttk.Treeview는 원래 줄 단위 선택만 있고 "셀 하나
    # 복사"라는 개념이 없다. 처음엔 "클릭한 칸을 기억"해두는 대신 Ctrl+C를
    # 누른 "그 순간"의 마우스 포인터 위치로 매번 다시 찾는 방식으로 만들었다
    # (다른 화면의 <Button-1> 바인딩과 안 부딪히려고).
    #
    # [2026-09-29 수정] "옆셀이 복사될때도 있고 복사가 안될때도있어" - 바로
    # 그 방식이 원인이었다. 클릭 이후 Ctrl+C를 누르기까지 손을 마우스에서
    # 키보드로 옮기는 사이에 커서가 아주 조금만 움직여도(특히 노트북
    # 트랙패드) 그 사이 다른 칸/다른 줄 위로 넘어가 버리고, 팝업창처럼 표가
    # 여러 개 열려 있는 화면(실적관리 조회 팝업 등)에서는 지금 키보드
    # 포커스가 있는 표와 마우스가 실제로 올라가 있는 표가 서로 다르면 엉뚱한
    # 표의 좌표로 셀을 잘못 찾기도 했다.
    #
    # 그래서 "클릭한 순간"에 그 칸을 이 표 자신에게 기억해두고, Ctrl+C를
    # 누르면 그 기억해둔 칸을 그대로 쓰도록 고쳤다.
    #
    # 처음엔 tree.bind("<Button-1>", ..., add="+")로 "덧붙이기"만 하면 될
    # 줄 알았는데, 실적관리처럼 setup_treeview()가 반환한 "뒤에" 화면이
    # 자기 용도(체크박스 토글)로 self.tree.bind("<Button-1>", ...)을
    # add 없이 다시 거는 화면에서는 그 호출이 이 위젯의 <Button-1> 바인딩
    # 전체를 통째로 새로 덮어써 버려서(add="+"로 걸어둔 것까지 같이
    # 날아간다) 방금 붙인 기억 기능이 조용히 없어져 버렸다(실적관리에서
    # 유독 복사가 잘 안 됐던 이유). 그래서 화면이 나중에 무슨 bind를
    # 걸든 절대 안 지워지도록, 이 표 전용의 새 바인드태그를 만들어 그
    # 태그에만 걸어둔다(다른 화면이 self.tree.bind(...)를 부르면 그
    # 위젯 자체의 기본 바인드태그만 바뀔 뿐, 여기서 새로 만든 태그는
    # 건드릴 수 없다).
    _last_clicked_cell = {"row": None, "col": None}

    def _remember_clicked_cell(event):
        region = tree.identify_region(event.x, event.y)
        if region == "cell":
            _last_clicked_cell["row"] = tree.identify_row(event.y)
            _last_clicked_cell["col"] = tree.identify_column(event.x)
        else:
            # 헤더/구분선 등 칸이 아닌 곳을 클릭했으면, 예전에 클릭해뒀던
            # 칸이 엉뚱하게 복사되지 않도록 기억을 지운다.
            _last_clicked_cell["row"] = None
            _last_clicked_cell["col"] = None

    _copy_track_tag = f"CellCopyTrack{id(tree)}"
    tree.bindtags((_copy_track_tag,) + tree.bindtags())
    tree.bind_class(_copy_track_tag, "<Button-1>", _remember_clicked_cell)

    def _copy_cell_under_pointer(event=None):
        try:
            row = _last_clicked_cell["row"]
            col = _last_clicked_cell["col"]
            if not row or not col:
                # 클릭해둔 칸이 없으면(방향키로만 이동한 경우 등) 예전
                # 방식(지금 마우스 포인터 위치)을 마지막 수단으로 시도한다.
                px, py = tree.winfo_pointerxy()
                lx = px - tree.winfo_rootx()
                ly = py - tree.winfo_rooty()
                if tree.identify_region(lx, ly) == "cell":
                    row = tree.identify_row(ly)
                    col = tree.identify_column(lx)
            if not row or not col or not tree.exists(row):
                # 클릭해둔 그 줄이 그 사이 새로고침 등으로 없어졌을 수 있다.
                return "break"
            value = tree.set(row, col)
            tree.clipboard_clear()
            tree.clipboard_append("" if value is None else str(value))
        except Exception:
            pass
        return "break"

    # Ctrl+C도 같은 이유로 전용 바인드태그에 건다(어떤 화면도 Ctrl+C를
    # 따로 쓰고 있진 않지만, 나중에 어떤 화면이 걸더라도 이 기능이 조용히
    # 사라지지 않도록 미리 안전하게 해둔다).
    tree.bind_class(_copy_track_tag, "<Control-c>", _copy_cell_under_pointer)
    tree.bind_class(_copy_track_tag, "<Control-C>", _copy_cell_under_pointer)

    # [2026-09-29] "소계 아랫선만 표시" - ttk.Treeview는 tag_configure로
    # foreground/background/font/image만 바꿀 수 있고 테두리(border)는 아예
    # 지원하지 않는다(위에 세로 구분선을 tk.Frame으로 직접 그려 넣은 것과
    # 같은 이유). 그래서 세로 구분선(sep_frames)과 똑같은 방식으로, 특정
    # 줄(item id) "아래쪽"에만 가로선을 그려 넣는 tk.Frame들을 별도로 만들고,
    # 화면이 스크롤되거나 크기가 바뀔 때마다 tree.bbox(item)으로 그 줄이
    # 지금 화면 어디에 보이는지 다시 계산해서 옮겨준다(안 보이는 줄이면
    # place_forget으로 감춘다).
    #
    # 화면 쪽에서는 set_bottom_border_items(["아이템id", ...])만 불러주면
    # 되고, 필요 없는 화면은 그냥 안 부르면 된다(부르지 않으면 선도 전혀
    # 생기지 않는다).
    _border_state = {"items": [], "frames": []}

    def _update_row_borders():
        items = _border_state["items"]
        frames = _border_state["frames"]
        if not items:
            for f in frames:
                try:
                    f.place_forget()
                except Exception:
                    pass
            return
        while len(frames) < len(items):
            frames.append(tk.Frame(tree, bg="#8C8C8C", height=1))
        try:
            frac_start, _ = tree.xview()
            cur_widths = [tree.column(col, "width") for col in columns]
            total_width = sum(cur_widths) or 1
            offset = int(frac_start * total_width)
        except Exception:
            total_width = 1
            offset = 0
        for idx, frame in enumerate(frames):
            if idx >= len(items):
                try:
                    frame.place_forget()
                except Exception:
                    pass
                continue
            item = items[idx]
            try:
                if not tree.exists(item):
                    frame.place_forget()
                    continue
                bbox = tree.bbox(item)
                if not bbox:
                    frame.place_forget()
                    continue
                x, y, w, h = bbox
                frame.place(x=-offset, y=y + h - 1, width=total_width, height=1)
            except Exception:
                try:
                    frame.place_forget()
                except Exception:
                    pass

    def set_bottom_border_items(item_ids):
        """전달한 item id들 "바로 아래"에만 가로 구분선을 그린다(예: 소계
        줄 아랫선만 표시하고 윗선은 안 주는 경우). 빈 리스트를 넘기면 모두
        지운다."""
        _border_state["items"] = list(item_ids) if item_ids else []
        _update_row_borders()

    tree.set_bottom_border_items = set_bottom_border_items

    _orig_on_yscroll = _on_yscroll

    def _on_yscroll_with_border(first, last):
        _orig_on_yscroll(first, last)
        _update_row_borders()

    tree.configure(yscrollcommand=_on_yscroll_with_border)

    _orig_reposition_separators = _reposition_separators

    def _reposition_all(*_a):
        _orig_reposition_separators()
        _update_row_borders()

    tree.after(30, _update_row_borders)
    tree.bind("<Configure>", lambda e: _reposition_all())
    tree.bind("<B1-Motion>", lambda e: _reposition_all())
    tree.bind("<ButtonRelease-1>", lambda e: _reposition_all())

    return container, tree


def friendly_save_error(error):
    """[2026-09-28] "엑셀저장했더니 [Errno 13] Permission denied 오류가
    뜨네" - 실제 원인은 프로그램 버그가 아니라 "같은 이름의 파일이 이미
    엑셀 등 다른 프로그램에서 열려 있어서 윈도우가 덮어쓰기를 막는 것"인
    경우가 거의 대부분이다. 파이썬 예외 메시지를 그대로 보여주면 사용자가
    원인을 알기 어려우니, 흔한 경우들은 알아보기 쉬운 한국어 안내로
    바꿔준다(모르는 종류의 오류면 원래 메시지를 그대로 보여준다)."""
    if isinstance(error, PermissionError):
        return ("이 이름의 파일이 이미 열려 있어 저장할 수 없습니다.\n"
                "엑셀 등에서 그 파일을 닫은 뒤 다시 시도하거나, 다른 이름으로 저장해보세요.\n\n"
                f"({error})")
    if isinstance(error, FileNotFoundError):
        return f"저장 위치를 찾을 수 없습니다(폴더가 옮겨졌거나 USB 등이 빠졌을 수 있습니다).\n\n({error})"
    if isinstance(error, OSError) and getattr(error, "errno", None) == 28:  # 디스크 공간 부족
        return f"디스크 저장 공간이 부족합니다.\n\n({error})"
    return str(error)


AMOUNT_HEADER_WORDS = ("수량", "금액", "판매가", "단가", "가격", "합계", "건수", "정가", "원가")


def is_amount_header(h):
    """엑셀 제목이 수량/금액을 나타내는 칸인지 (이런 칸은 숫자 + 3자리 콤마 서식으로 저장)."""
    return isinstance(h, str) and any(w in h for w in AMOUNT_HEADER_WORDS)


def _amount_value(v):
    """수량/금액 칸의 값을 엑셀 숫자로: 정수/실수는 그대로, "1,234" 같은 글자는 숫자로. 아니면 None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        t = v.strip().replace(",", "")
        body = t[1:] if t.startswith("-") else t
        if body.isdigit():
            return int(t)
    return None


def apply_amount_format(ws, headers, first_row=2, last_row=None):
    """제목에 수량/금액이 들어간 칸을 숫자로 바꾸고 #,##0 (3자리 콤마) 서식을 넣는다.
    ISBN/바코드처럼 숫자처럼 보여도 수량/금액이 아닌 칸은 건드리지 않는다(앞자리 0 보존)."""
    cols = [i for i, h in enumerate(headers, start=1) if is_amount_header(h)]
    if not cols:
        return
    last = last_row or ws.max_row
    for r in range(first_row, last + 1):
        for c in cols:
            cell = ws.cell(row=r, column=c)
            num = _amount_value(cell.value)
            if num is not None:
                cell.value = num
                cell.number_format = "#,##0"


def write_rows_to_excel_file(rows, headers, path):
    """rows를 이미 정해진 경로(path)에 엑셀 파일로 그대로 저장한다 (다이얼로그
    없이 - 저장 위치를 미리 골라둔 여러 파일을 한 번에 저장할 때 사용).
    빠른 저장기(fast_xlsx)로 쓴다 - 굵은 제목줄, 수량/금액 콤마 서식은 예전 openpyxl 저장과 같고
    속도는 약 7배 빠르다. 열 너비는 내용에 맞춰 자동(2026-10-16)."""
    from . import fast_xlsx
    headers = list(headers)
    if not isinstance(rows, (list, tuple)):
        rows = list(rows)
    fast_xlsx.write_xlsx(path, headers, rows, amount_cols=fast_xlsx.amount_cols_for(headers, is_amount_header))


# [2026-09-28] "엑셀저장할때 오래걸려도 진행률 다이얼로그가 안뜨는데?" -
# 이 값보다 행이 많으면(=시간이 걸릴 만하면) export_rows_to_excel()이
# progress_dialog.run_with_progress()로 감싸서 ZZOINT와 같은 진행률
# 팝업을 띄운다. 적은 행일 때까지 매번 팝업을 띄우면 깜빡임만 나고
# 의미가 없어서 문턱값을 둔다.
PROGRESS_ROW_THRESHOLD = 300


def _write_plain_workbook_with_progress(path, rows, headers, progress=None):
    """write_rows_to_excel_file()과 같은 내용을 만들되, 행을 추가할 때마다
    progress(done=i, total=n)을 불러서 진행률 팝업이 갱신되게 한다.
    progress가 None이면 그냥 조용히 저장한다(기존 동작과 동일)."""
    # [2026-10-01] 빠른 저장기(fast_xlsx)로 바꿨다 - 모양은 같고(굵은 제목줄, 열 너비 16,
    # 수량/금액 콤마 서식) openpyxl보다 약 7배 빠르다. 줄을 쓰면서 진행률을 갱신하고 [취소]도 받는다.
    from . import fast_xlsx
    from .progress_core import report as _report

    total = len(rows)
    headers = list(headers)
    _report(progress, message="엑셀 파일을 만드는 중...", done=0, total=total, unit="count")
    step = max(1, total // 300)

    def _rows():
        for idx, row in enumerate(rows, start=1):
            yield row
            if progress is not None and (idx % step == 0 or idx == total):
                _report(progress, done=idx)
                progress.check_cancel()  # [취소] 눌렀으면 여기서 Cancelled 예외로 중단

    amount_cols = fast_xlsx.amount_cols_for(headers, is_amount_header)
    widths = fast_xlsx.auto_widths(headers, rows, amount_cols)   # [2026-10-16] 열 너비 자동 맞춤
    fast_xlsx.write_xlsx(path, headers, _rows(), amount_cols=amount_cols, widths=widths)
    _report(progress, message="파일에 쓰는 중...", done=total)


def export_rows_to_excel(rows, headers, default_name="export.xlsx", parent=None):
    """rows: 리스트의 리스트(각 행), headers: 컬럼명.

    [2026-09-28] "엑셀저장할때 오래걸려도 진행률 다이얼로그가 안뜨는데?" -
    parent를 넘기고 행 수가 PROGRESS_ROW_THRESHOLD를 넘으면, 실제 저장은
    백그라운드 스레드에서 ZZOINT와 같은 진행률 팝업(run_with_progress)으로
    돌리고 완료/오류 메시지도 이 함수가 직접 띄운다 - 이 경우 호출하는
    화면 쪽에서 "완료" 메시지를 따로 띄우면 두 번 뜨니 띄우지 않아야 한다
    (반환값이 None이면 비동기로 넘어간 것 - 반환값으로 완료 여부를 판단
    하지 말 것).
    행이 적거나 parent가 없으면(진행률을 붙일 화면이 없는 경우) 예전처럼
    그 자리에서 바로 저장하고 경로를 돌려준다."""
    path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel 파일", "*.xlsx")],
        initialfile=default_name,
    )
    if not path:
        return None

    use_progress = parent is not None and len(rows) >= PROGRESS_ROW_THRESHOLD

    def _save_sync():
        try:
            _write_plain_workbook_with_progress(path, rows, headers, progress=None)
            return path
        except ImportError:
            # openpyxl 미설치 시 CSV로 대체
            import csv
            csv_path = path.rsplit(".", 1)[0] + ".csv"
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(headers)
                for row in rows:
                    w.writerow(row)
            messagebox.showinfo(
                "알림",
                f"openpyxl이 설치되어 있지 않아 CSV로 저장했습니다:\n{csv_path}\n\n"
                "pip install openpyxl 설치 후 다시 시도하면 .xlsx로 저장됩니다."
            )
            return csv_path
        except OSError as e:
            # [2026-09-28] "엑셀저장했더니 Permission denied 오류가 뜨네" -
            # 이 동기 저장 경로(행이 적을 때)는 예전에 OSError를 아예 잡지
            # 않아서, 파일이 이미 열려있는 흔한 경우에도 다듬어지지 않은
            # 파이썬 예외가 그대로 튀어나올 뻔했다.
            messagebox.showerror("오류", f"저장 중 오류가 발생했습니다:\n{friendly_save_error(e)}")
            return None

    if not use_progress:
        return _save_sync()

    from .progress_core import Cancelled
    from .progress_dialog import run_with_progress

    def work(progress):
        _write_plain_workbook_with_progress(path, rows, headers, progress=progress)
        return path

    def _cleanup_partial():
        import os
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    def on_done(result, error):
        if isinstance(error, Cancelled):
            _cleanup_partial()
            return
        if error is not None:
            _cleanup_partial()
            if isinstance(error, ImportError):
                # 백그라운드 스레드 안에서는 messagebox/파일 대화상자를 새로
                # 띄우면 안 되므로, 여기(메인 스레드로 돌아온 뒤)에서 CSV로
                # 대체 저장한다.
                try:
                    import csv
                    csv_path = path.rsplit(".", 1)[0] + ".csv"
                    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                        w = csv.writer(f)
                        w.writerow(headers)
                        for row in rows:
                            w.writerow(row)
                    messagebox.showinfo(
                        "알림",
                        f"openpyxl이 설치되어 있지 않아 CSV로 저장했습니다:\n{csv_path}\n\n"
                        "pip install openpyxl 설치 후 다시 시도하면 .xlsx로 저장됩니다."
                    )
                except Exception as e2:
                    messagebox.showerror("오류", f"저장 중 오류가 발생했습니다:\n{friendly_save_error(e2)}")
                return
            messagebox.showerror("오류", f"저장 중 오류가 발생했습니다:\n{friendly_save_error(error)}")
            return
        messagebox.showinfo("완료", f"저장되었습니다:\n{result}")

    # [2026-09-28] "진행률 다이얼로그에 X표시를 눌러도 취소도 불가" -
    # cancelable=True로 바꿔 [취소] 버튼(과 ESC)으로 빠져나올 수 있게 한다.
    run_with_progress(parent, "엑셀로 저장하는 중", work, on_done, cancelable=True)
    return None


def print_rows_to_excel(rows, headers, default_name="print.xlsx"):
    """[2026-09-28] "발행 버튼을 누르면 왜 엑셀저장이 뜨냐, ZZOINT 발행버튼
    기능 참고해봐" - 그동안 [발행] 버튼이 export_rows_to_excel()을 그대로
    가져다 써서, 인쇄하기 전에 매번 "다른 이름으로 저장" 대화상자가 먼저
    뜨고 사용자가 저장 위치/파일명을 직접 골라야 했다. ZZOINT의 [발행]은
    그런 대화상자 없이 바로 인쇄로 이어지는 동작이라, 여기서도 저장 위치를
    묻지 않고 임시 폴더에 조용히 엑셀 파일을 만든 뒤 그 경로만 돌려준다 -
    호출하는 쪽(print_report 류)이 이 경로를 os.startfile(path, "print")로
    바로 인쇄하면 된다. (매번 같은 파일 이름을 쓰면 여러 화면에서 동시에
    발행할 때 서로 덮어쓸 수 있어, 파일명 앞에 타임스탬프를 붙여 겹치지
    않게 한다.)"""
    import os
    import tempfile
    from datetime import datetime

    tmp_dir = os.path.join(tempfile.gettempdir(), "kointbook_print")
    os.makedirs(tmp_dir, exist_ok=True)
    stamped_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{default_name}"
    path = os.path.join(tmp_dir, stamped_name)
    rows = list(rows)   # 열 너비 자동 맞춤이 값을 한 번 더 훑는다
    try:
        import openpyxl
        from openpyxl.styles import Font
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for row in rows:
            ws.append(list(row))
        from . import fast_xlsx
        for i, w in enumerate(fast_xlsx.auto_widths(headers, rows, fast_xlsx.amount_cols_for(headers, is_amount_header)), start=1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w   # [2026-10-16] 내용에 맞춰 자동
        apply_amount_format(ws, headers)
        wb.save(path)
        return path
    except ImportError:
        # openpyxl 미설치 시 CSV로 대체(인쇄는 못 하고 파일만 남긴다 -
        # 호출하는 쪽에서 platform 분기 시 이 경우도 안내한다).
        import csv
        csv_path = path.rsplit(".", 1)[0] + ".csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for row in rows:
                w.writerow(row)
        return csv_path


def print_excel_file(path):
    """[2026-09-28] "발행버튼을 누르면 바로 인쇄되는게 아니라 인쇄전
    설정창같은게 하나 뜨잖아? 그렇게 해줘" - 그동안은 os.startfile(path,
    "print")로 저장 위치도 안 묻고 프린터 설정창도 없이 바로 기본
    프린터에 조용히 인쇄했다(ZZOINT처럼 저장 대화상자는 안 뜨게 한다는
    요청은 계속 그대로 유지한다).

    [2026-09-28 재수정] "인쇄전 설정창" -> "인쇄 미리보기" -> "엑셀말고
    이런 윈도우 기본 인쇄 대화상자를 사용할순 없어?" -> "ZZOINT 발행누르면
    나오는 인쇄 대화상자를 참고해서 똑같이 만들어줘" - ZZOINT(원본
    프로그램)의 print_report()를 그대로 옮겨왔다. 처음엔 여기서도
    win32com으로 엑셀을 직접 띄워 엑셀 내장 [인쇄] 대화상자
    (Dialogs(xlDialogPrint))를 불러오는 방식을 썼는데, ZZOINT 쪽 설명에
    따르면 이 방식은 엑셀이 이미 열려 있을 때 새 창 없이 그 엑셀에
    붙어버려 대화상자를 기다리는 동안 프로그램이 멈춘 것처럼 보이는
    문제가 있었다(게다가 끝나고 excel.Quit()을 부르면 사용자가 엑셀에
    열어둔 다른 작업까지 같이 닫힐 위험도 있다). 그래서 엑셀은 아예
    건드리지 않고, 윈도우 자체의 [인쇄] 공용 대화상자(어느 프로그램에서
    인쇄하든 뜨는 바로 그 프린터/매수 선택 창)를 comdlg32.dll의
    PrintDlgW를 ctypes로 직접 호출해서 띄운다. (pywin32의
    win32ui.CreatePrintDialog()는 한글 윈도우에서 "'utf-8' codec can't
    decode byte..." 오류가 나서 안 쓴다 - PrintDlgW를 유니코드(W) 버전
    그대로 직접 부르면 그 문제가 없다.)

    사용자가 [확인]을 누르면 거기서 고른 프린터/매수를 읽어서, 실제
    인쇄는 win32api.ShellExecute(..., "printto", ...)로 엑셀이 등록해둔
    인쇄 처리기에 그 프린터를 콕 집어 넘긴다(매수만큼 반복 - 엑셀 쪽에는
    매수를 따로 넘길 방법이 없어서). [취소]를 누르면 조용히 끝난다.

    pywin32가 없거나 대화상자 호출이 실패하면(Excel 미설치 등),
    os.startfile(path)로 엑셀에서 파일만 열어주고 안내 팝업을 띄운다."""
    if not path:
        return
    if platform.system() != "Windows":
        messagebox.showinfo("완료", f"파일로 저장했습니다:\n{path}")
        return

    try:
        import ctypes
        from ctypes import wintypes
        import win32api
    except ImportError:
        messagebox.showwarning(
            "알림",
            "인쇄 대화상자를 쓰려면 pywin32가 필요합니다(pip install pywin32).\n"
            "대신 엑셀에서 파일을 열어드릴게요 - Ctrl+P로 직접 인쇄하세요.")
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showwarning("알림", f"엑셀에서 파일을 여는 데도 실패했습니다. 파일은 저장됐습니다:\n{path}\n\n{e}")
        return

    try:
        class _PRINTDLGW(ctypes.Structure):
            _fields_ = [
                ("lStructSize", wintypes.DWORD),
                ("hwndOwner", wintypes.HWND),
                ("hDevMode", wintypes.HANDLE),
                ("hDevNames", wintypes.HANDLE),
                ("hDC", wintypes.HANDLE),
                ("Flags", wintypes.DWORD),
                ("nFromPage", wintypes.WORD),
                ("nToPage", wintypes.WORD),
                ("nMinPage", wintypes.WORD),
                ("nMaxPage", wintypes.WORD),
                ("nCopies", wintypes.WORD),
                ("hInstance", wintypes.HANDLE),
                ("lCustData", ctypes.c_void_p),
                ("lpfnPrintHook", ctypes.c_void_p),
                ("lpfnSetupHook", ctypes.c_void_p),
                ("lpPrintTemplateName", wintypes.LPCWSTR),
                ("lpSetupTemplateName", wintypes.LPCWSTR),
                ("hPrintTemplate", wintypes.HANDLE),
                ("hSetupTemplate", wintypes.HANDLE),
            ]

        class _DEVNAMES(ctypes.Structure):
            _fields_ = [
                ("wDriverOffset", wintypes.WORD),
                ("wDeviceOffset", wintypes.WORD),
                ("wOutputOffset", wintypes.WORD),
                ("wDefault", wintypes.WORD),
            ]

        comdlg32 = ctypes.windll.comdlg32
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
        kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
        kernel32.GlobalFree.argtypes = [wintypes.HANDLE]
        comdlg32.PrintDlgW.argtypes = [ctypes.POINTER(_PRINTDLGW)]
        comdlg32.PrintDlgW.restype = wintypes.BOOL

        # PD_NOPAGENUMS/PD_NOSELECTION: 파일 전체를 통째로 인쇄만 지원하니,
        # 어차피 안 먹히는 페이지 범위/선택영역 옵션은 대화상자에서 숨긴다.
        PD_NOSELECTION = 0x00000004
        PD_NOPAGENUMS = 0x00000008

        pdlg = _PRINTDLGW()
        pdlg.lStructSize = ctypes.sizeof(_PRINTDLGW)
        pdlg.Flags = PD_NOPAGENUMS | PD_NOSELECTION
        pdlg.nCopies = 1

        ok = comdlg32.PrintDlgW(ctypes.byref(pdlg))
        if not ok:
            return  # 사용자가 [취소]를 눌렀다(또는 실패) - 조용히 넘어간다.

        printer_name = None
        try:
            if pdlg.hDevNames:
                addr = kernel32.GlobalLock(pdlg.hDevNames)
                if addr:
                    try:
                        dn = _DEVNAMES.from_address(addr)
                        name_addr = addr + dn.wDeviceOffset * ctypes.sizeof(wintypes.WCHAR)
                        printer_name = ctypes.wstring_at(name_addr)
                    finally:
                        kernel32.GlobalUnlock(pdlg.hDevNames)
        finally:
            if pdlg.hDevNames:
                kernel32.GlobalFree(pdlg.hDevNames)
            if pdlg.hDevMode:
                kernel32.GlobalFree(pdlg.hDevMode)

        if not printer_name:
            messagebox.showwarning(
                "알림",
                f"선택한 프린터 정보를 읽지 못했습니다. 파일은 저장됐습니다:\n{path}\n\n"
                "대신 엑셀에서 파일을 열어드릴게요 - Ctrl+P로 직접 인쇄하세요.")
            try:
                os.startfile(path)
            except Exception:
                pass
            return

        copies = max(1, int(pdlg.nCopies))

        # 실제 인쇄는 엑셀이 등록해둔 "인쇄" 처리기에 맡긴다 - 방금
        # 대화상자에서 고른 그 프린터로 콕 집어 보낸다. 매수만큼 반복.
        for _ in range(copies):
            win32api.ShellExecute(0, "printto", str(path), f'"{printer_name}"', ".", 0)
    except Exception as e:
        messagebox.showwarning(
            "알림",
            f"인쇄 대화상자를 여는 데 실패했습니다. 파일은 저장됐습니다:\n{path}\n\n{e}\n\n"
            "대신 엑셀에서 파일을 열어드릴게요 - Ctrl+P로 직접 인쇄하세요.")
        try:
            os.startfile(path)
        except Exception:
            pass


def _print_excel_file_silently(path):
    """print_excel_file()의 대체(fallback) 경로 - pywin32가 없거나 COM
    호출이 실패했을 때, 미리보기 없이 바로 기본 프린터로 인쇄한다
    (예전에 각 화면 print_report()마다 반복되던 코드를 여기로 모았다).
    [2026-09-28] "이런 팝업창은 불필요" - 성공했을 때는 조용히 끝내고,
    실패했을 때만 안내한다."""
    try:
        os.startfile(path, "print")
    except Exception as e:
        messagebox.showwarning("알림", f"자동 인쇄에 실패해 파일만 저장했습니다:\n{path}\n\n{e}")


def export_summary_excel_with_chart(rows, headers, default_name="summary.xlsx",
                                     chart_title=None, chart_data_col=2, chart_last_data_row=None):
    """작업자 실적 요약처럼 "적은 줄 수 + 막대그래프"가 어울리는 표를 저장한다.
    export_rows_to_excel과 거의 같지만, 가능하면 막대그래프도 같은 시트에
    넣는다 - 그래프는 어디까지나 부가 기능이라, 삽입에 실패해도(openpyxl
    버전 차이 등) 데이터 저장 자체는 그대로 성공시킨다(프로그램이 무거워지는
    것도 피하려고 그래프 없이도 완전히 정상 동작하게 만들어 뒀다).

    chart_data_col: 그래프로 그릴 값이 있는 열 번호(1부터, 보통 "건수" 열).
    chart_last_data_row: 그래프에 포함할 마지막 데이터 행(1부터, 헤더 제외한
    실데이터 기준 - 보통 맨 아래 "계" 합계 줄은 그래프에서 빼기 위해 지정한다).
    지정하지 않으면 rows 전체를 그래프에 포함한다."""
    path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel 파일", "*.xlsx")],
        initialfile=default_name,
    )
    if not path:
        return None
    try:
        import openpyxl
        from openpyxl.styles import Font
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for row in rows:
            ws.append(list(row))
        from . import fast_xlsx
        for i, w in enumerate(fast_xlsx.auto_widths(headers, rows, fast_xlsx.amount_cols_for(headers, is_amount_header)), start=1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w   # [2026-10-16] 내용에 맞춰 자동
        apply_amount_format(ws, headers)

        try:
            from openpyxl.chart import BarChart, Reference
            last_row = chart_last_data_row if chart_last_data_row is not None else len(rows)
            last_row += 1  # 헤더 한 줄만큼 밀기(엑셀은 1행이 헤더)
            if last_row >= 2:
                chart = BarChart()
                chart.type = "bar"
                chart.title = chart_title or headers[chart_data_col - 1]
                data = Reference(ws, min_col=chart_data_col, min_row=1, max_row=last_row)
                cats = Reference(ws, min_col=1, min_row=2, max_row=last_row)
                chart.add_data(data, titles_from_data=True)
                chart.set_categories(cats)
                ws.add_chart(chart, f"{openpyxl.utils.get_column_letter(len(headers) + 2)}2")
        except Exception:
            pass  # 그래프 삽입 실패는 무시 - 데이터 저장은 이미 끝난 상태

        wb.save(path)
        return path
    except ImportError:
        import csv
        csv_path = path.rsplit(".", 1)[0] + ".csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for row in rows:
                w.writerow(row)
        messagebox.showinfo(
            "알림",
            f"openpyxl이 설치되어 있지 않아 CSV로 저장했습니다:\n{csv_path}\n\n"
            "pip install openpyxl 설치 후 다시 시도하면 .xlsx로(그래프 포함) 저장됩니다."
        )
        return csv_path


def read_excel_columns(path, columns_candidates, progress=None):
    """
    엑셀 파일에서 여러 컬럼을 한 번에 읽는다 (상품마스터의 바코드/자사코드/
    상품명/판매가처럼 컬럼이 3개 이상일 때 사용). columns_candidates는
    [["바코드","PLU"], ["자사코드"], ["상품명","품명"], ["판매가"]] 처럼
    각 컬럼별 후보 헤더 이름 목록의 리스트. 헤더 이름이 후보와 일치하면
    그 위치를 쓰고, 못 찾으면 순서대로(0,1,2,3번째 열) 사용한다.
    각 행을 튜플로 담은 리스트를 돌려준다 (해당 컬럼이 없으면 None).

    수십만 줄짜리 파일도 메모리를 덜 쓰고 빠르게 읽도록 read_only(스트리밍)
    방식으로 읽는다. progress를 넘기면 읽는 도중 진행 상황을 알려준다
    (progress는 progress_core.Progress 객체이며, 백그라운드 스레드에서 호출).
    """
    import itertools
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        # 전체 줄 수(진행률 계산용). 파일에 따라 이 값이 없거나 엉터리(엑셀 전체
        # 행 수인 1048576 등)일 수 있어서, 그런 경우에는 "전체를 모르는" 상태로 둔다.
        try:
            total_hint = ws.max_row or 0
        except Exception:
            total_hint = 0
        if total_hint >= 1000000:
            total_hint = 0
        # 일부 프로그램이 만든 엑셀은 범위 정보가 틀려서, 그대로 읽으면 뒤쪽
        # 줄이 잘릴 수 있다 - 범위 정보를 무시하고 실제 있는 줄을 전부 읽는다.
        try:
            ws.reset_dimensions()
        except Exception:
            pass

        if progress is not None:
            progress(message="엑셀 파일 읽는 중...", done=0, total=total_hint, unit="count")

        it = ws.iter_rows(values_only=True)
        first = next(it, None)
        if first is None:
            return []

        header = [str(h).strip() if h is not None else "" for h in first]
        indices = []
        any_matched = False
        for candidates in columns_candidates:
            found = None
            for i, h in enumerate(header):
                if h in candidates:
                    found = i
                    break
            if found is not None:
                any_matched = True
            indices.append(found)

        # 후보 이름과 하나도 안 맞으면(헤더가 없는 파일 등) 순서대로 매핑한다.
        for i, idx in enumerate(indices):
            if idx is None:
                indices[i] = i

        data_iter = it if any_matched else itertools.chain([first], it)

        result = []
        count = 0
        for r in data_iter:
            count += 1
            if progress is not None and count % 2000 == 0:
                progress.check_cancel()
                if total_hint and count > total_hint:
                    total_hint = 0  # 예상보다 많으면 전체를 모르는 상태로 전환
                progress(done=count, total=total_hint)
            if r is None:
                continue
            row_vals = []
            for idx in indices:
                row_vals.append(r[idx] if idx < len(r) else None)
            if row_vals[0] is None:
                continue
            result.append(tuple(row_vals))
        if progress is not None:
            progress(done=count, total=count)
        return result
    finally:
        try:
            wb.close()
        except Exception:
            pass


def read_excel_two_columns(path, col_a_name_candidates, col_b_name_candidates):
    """
    엑셀 파일에서 두 개 컬럼(예: PLU/상품명, 바코드/장부수량)을 읽어
    [(a, b), ...] 리스트로 반환한다. 헤더 이름은 후보 목록 중 하나와
    대소문자 무시하고 일치하면 사용하고, 못 찾으면 A/B열을 그대로 사용한다.
    """
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    idx_a = None
    idx_b = None
    for i, h in enumerate(header):
        if h in col_a_name_candidates:
            idx_a = i
        if h in col_b_name_candidates:
            idx_b = i

    data_rows = rows[1:] if (idx_a is not None or idx_b is not None) else rows
    if idx_a is None:
        idx_a = 0
    if idx_b is None:
        idx_b = 1

    result = []
    for r in data_rows:
        if r is None or len(r) <= max(idx_a, idx_b):
            continue
        a = r[idx_a]
        b = r[idx_b]
        if a is None:
            continue
        result.append((str(a).strip(), b))
    return result


def read_csv_columns(path, columns_candidates, progress=None, encoding="utf-8-sig"):
    """read_excel_columns의 CSV 버전.

    실제 RBSKOREA/KYOBO 쪽에서 받은 "도서 마스터정보 업로드"용 원본 파일이
    .xlsx가 아니라 .csv(헤더: cmdtCode,cmdtName,jo_name,pbcm_name,
    rcdsInvnQntt,realInvnQntt,qntt,exceptYsno)였다 - 그래서 엑셀뿐 아니라
    CSV도 같은 방식(후보 헤더 이름으로 컬럼 위치 찾기, 못 찾으면 순서대로)
    으로 읽을 수 있게 만들었다. encoding은 기본이 "utf-8-sig"라 BOM이 있는
    파일도 문제없이 읽힌다(실제 파일도 BOM 있는 UTF-8이었다)."""
    import csv
    import itertools

    with open(path, "r", encoding=encoding, newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return []
        header = [str(h).strip() if h is not None else "" for h in header]

        indices = []
        any_matched = False
        for candidates in columns_candidates:
            found = None
            for i, h in enumerate(header):
                if h in candidates:
                    found = i
                    break
            if found is not None:
                any_matched = True
            indices.append(found)
        for i, idx in enumerate(indices):
            if idx is None:
                indices[i] = i

        rows_iter = reader if any_matched else itertools.chain([header], reader)

        result = []
        count = 0
        for r in rows_iter:
            count += 1
            if progress is not None and count % 5000 == 0:
                progress.check_cancel()
                progress(done=count, total=0)
            if not r:
                continue
            row_vals = []
            for idx in indices:
                row_vals.append(r[idx] if idx < len(r) else None)
            if row_vals[0] is None or row_vals[0] == "":
                continue
            result.append(tuple(row_vals))
        if progress is not None:
            progress(done=count, total=count)
        return result


def eof_crlf_enabled():
    """[2026-10-14] 교보 IT 요청: 자료생성 txt 마지막 줄 뒤에도 CRLF(EOF) 적용 — 항상 켬(화면 선택 없음)."""
    return True


def write_text_lines_file(lines, path, trailing_newline=None):
    """엑셀이 아니라 고정폭 텍스트(예: kyobo_data1.txt/kyobo_data2.txt처럼
    헤더도 구분자도 없는 EDI용 플랫 파일) 그대로 저장할 때 쓴다.
    [2026-10-13] 받은 샘플은 줄 사이만 CRLF이고 마지막 줄 뒤에는 줄바꿈이 없다 -> 기본값을 그렇게 맞췄다."""
    from pathlib import Path
    if trailing_newline is None:
        trailing_newline = eof_crlf_enabled()
    path = path if isinstance(path, Path) else Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\r\n".join(lines) + ("\r\n" if (trailing_newline and lines) else "")
    with open(path, "wb") as f:
        f.write(text.encode("ascii"))


def short_store_label(store_name):
    """생성 파일명 접두사용 - 실제 샘플 파일들은 점포명 끝의 "점"을 뗀
    형태("인천점" -> "인천")를 파일명에 썼다."""
    import re as _re_label
    name = (store_name or "매장").strip()
    if name.endswith("점") and len(name) > 1:
        name = name[:-1]
    return _re_label.sub(r'[\\/:*?"<>|]', "", name).strip() or "매장"


def open_calendar_picker(parent, initial_date_str, on_select):
    """"YYYYMMDD" 형식의 날짜를 달력에서 골라 선택하는 작은 팝업을 연다.
    날짜를 고르면 on_select(picked_date_str)가 호출되고 팝업은 닫힌다."""
    try:
        y = int(initial_date_str[:4])
        m = int(initial_date_str[4:6])
    except Exception:
        now = datetime.now()
        y, m = now.year, now.month

    win = tk.Toplevel(parent)
    center_on_app(win)
    win.title("조사일자 선택")
    win.configure(bg="white")
    win.resizable(False, False)
    win.bind("<Escape>", lambda e: win.destroy())

    state = {"year": y, "month": m}

    header = tk.Frame(win, bg=CL_NAVY)
    header.pack(fill=tk.X)
    tk.Button(header, text="◀", command=lambda: change_month(-1), relief="flat",
              bg=CL_NAVY, fg="white", activebackground=CL_NAVY_DARK).pack(side=tk.LEFT, padx=6, pady=6)
    lbl_title = tk.Label(header, text="", bg=CL_NAVY, fg="white", font=("", 12, "bold"))
    lbl_title.pack(side=tk.LEFT, expand=True)
    tk.Button(header, text="▶", command=lambda: change_month(1), relief="flat",
              bg=CL_NAVY, fg="white", activebackground=CL_NAVY_DARK).pack(side=tk.RIGHT, padx=6, pady=6)

    grid_frame = tk.Frame(win, bg="white")
    grid_frame.pack(padx=10, pady=10)

    def pick(dd):
        picked = f"{state['year']:04d}{state['month']:02d}{dd:02d}"
        win.destroy()
        on_select(picked)

    def render():
        for w in grid_frame.winfo_children():
            w.destroy()
        lbl_title.config(text=f"{state['year']}년 {state['month']}월")
        day_names = ["일", "월", "화", "수", "목", "금", "토"]
        for i, dname in enumerate(day_names):
            fg = "#B04040" if i == 0 else (CL_NAVY if i != 6 else "#2A5DB0")
            tk.Label(grid_frame, text=dname, width=4, bg="white", fg=fg,
                     font=("", 10, "bold")).grid(row=0, column=i, pady=(0, 4))
        cal = _calendar.Calendar(firstweekday=6)  # 일요일부터 시작
        weeks = cal.monthdayscalendar(state["year"], state["month"])
        today_s = today_str()
        for r, week in enumerate(weeks, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    tk.Label(grid_frame, text="", width=4, bg="white").grid(row=r, column=c)
                    continue
                is_today = f"{state['year']:04d}{state['month']:02d}{day:02d}" == today_s
                btn = tk.Button(
                    grid_frame, text=str(day), width=4, relief="flat",
                    bg=CL_GOLD if is_today else "white",
                    fg="white" if is_today else "#191C23",
                    activebackground="#DFE3EE",
                    command=lambda dd=day: pick(dd)
                )
                btn.grid(row=r, column=c, padx=1, pady=1)

    def change_month(delta):
        m2 = state["month"] + delta
        y2 = state["year"]
        if m2 < 1:
            m2 = 12
            y2 -= 1
        elif m2 > 12:
            m2 = 1
            y2 += 1
        state["month"] = m2
        state["year"] = y2
        render()

    render()


def center_on_app(win):
    """팝업(win)을 프로그램(메인 창) 정중앙에 띄운다. 팝업 안 내용이 다 그려진 뒤
    (한가해졌을 때) 실제 크기를 재서 위치를 잡으므로, 크기를 따로 안 정한 팝업도 정중앙에 온다."""
    def _do():
        try:
            win.update_idletasks()
            root = win.nametowidget(".")
            m = re.match(r"(\d+)x(\d+)", win.geometry())
            w, h = (int(m.group(1)), int(m.group(2))) if m else (1, 1)
            if w <= 1 or h <= 1:
                w, h = win.winfo_reqwidth(), win.winfo_reqheight()
            px, py = root.winfo_rootx(), root.winfo_rooty()
            pw, ph = root.winfo_width(), root.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            x = max(0, min(x, win.winfo_screenwidth() - w))
            y = max(0, min(y, win.winfo_screenheight() - h - 40))
            win.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass
    try:
        win.after_idle(_do)
    except tk.TclError:
        pass


# ---- KOINTBOOK 전용 - AREA/SECTION 관련 공용 헬퍼 ----
# 여러 화면(재고조사 보고서/차이명세/섹션별 재고현황/섹션별 결과보고서/
# 실적관리/샘플링 결과보고서)이 똑같이 "AREA 합산전 / AREA 합산후" 라디오를
# 갖고 있다.
#
# [2026-09-23 현장 확인] AREA는 "01","02","11","12"처럼 항상 숫자 2자리이고
# 알파벳이 섞이는 경우는 없다 - 예전에 "여러 조가 나눠 맡으면 1A/1B처럼
# 알파벳 접미사를 붙인다"고 가정했던 것은 틀린 추측이었다. 그래서
# normalize_area()는 이제 알파벳을 떼는 처리를 하지 않고 숫자만 남겨 2자리로
# 맞추는 것만 한다 - merged 값과 상관없이 결과가 같다. "AREA 합산전/후"
# 라디오는 화면 구성을 바꾸지 않기 위해 그대로 남겨뒀지만, 지금은 두 선택
# 모두 같은 값을 보여준다(알파벳 접미사가 없으니 합칠 것이 없음).
def normalize_area(area, merged=True):
    """AREA를 숫자만 남겨 2자리로 맞춘다("1"->"01", "01"->"01"). AREA에는
    알파벳이 섞이지 않는다는 것이 확인되어 merged 값은 더 이상 결과에
    영향을 주지 않는다(화면 라디오버튼과의 하위 호환을 위해 인자만 남겨둠).
    빈 값이면 빈 문자열로 통일한다.
    [2026-10-01] 보고서 화면들이 30만 줄마다 이 함수를 부르는데 AREA 값 종류는 수십 개뿐이라,
    한 번 계산한 결과를 기억해 두고 다시 쓴다(결과는 같고, 30만 줄 기준 약 0.8~1초 단축 - 실측)."""
    return _normalize_area_text(str(area or "").strip())


@functools.lru_cache(maxsize=8192)
def _normalize_area_text(text):
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(2) if digits else ""


def digit_code_variants(keyword, width):
    """[2026-09-28] "AREA를 01로하면 조회가 안되고 1로 하면 조회가되네
    반대여야지" - AREA/SECTION은 화면에는 항상 0채움된 형태("01")로
    보이지만, 실제 DB에는 예전 데이터가 0채움 없이("1") 저장된 경우가
    섞여 있어서, 검색어를 있는 그대로 비교(=/LIKE)하면 저장된 형태와 안
    맞는 쪽은 못 찾는다(둘 중 하나만 되고 나머지는 안 되는 게 이 문제).
    숫자로만 된 검색어면 0채움한 형태와 0채움을 뗀 형태를 모두 후보로
    돌려줘서, SQL의 IN절 등으로 어느 쪽으로 저장돼 있어도 찾을 수 있게
    한다. AREA/SECTION으로 조회·조건검색하는 화면들(실적관리, 섹션별
    아이템 재고현황, 진행현황의 타일 인쇄 등)이 공용으로 쓴다."""
    keyword = (keyword or "").strip()
    variants = {keyword}
    if keyword.isdigit():
        variants.add(keyword.zfill(width))
        variants.add(str(int(keyword)))
    return sorted(variants)



_SCAN_DT_RE = re.compile(r"(\d{4})\D?(\d{2})\D?(\d{2})(?:\D+(\d{2}):?(\d{2}):?(\d{2})?)?")


def split_scan_datetime(received_at, fallback_date=""):
    """[2026-10-15] 스캔한 일시(received_at, 예 "2026-10-08 14:03:11")를 (일자 "20261008", 시간 "14:03:11")로
    나눈다. 표시할 때만 문자열을 자르므로 DB 조회/속도에는 영향이 없다. 일시가 비었거나 해석이 안 되면
    (fallback_date, "")를 돌려준다."""
    m = _SCAN_DT_RE.match(str(received_at or "").strip())
    if not m:
        return str(fallback_date or ""), ""
    y, mo, d, h, mi, se = m.groups()
    return f"{y}{mo}{d}", (f"{h}:{mi}:{se or '00'}" if h else "")


def area_section_code(area, section, section_width=3, sep=""):
    """[2026-09-23 현장 확인] Section Check/재고조사 진행 현황 화면의
    "A_SECTION" 코드 - AREA(2자리 숫자, normalize_area) + SECTION(기본
    3자리 0채움)을 이어붙인 값이다("01"+"101" -> "01101"). AREA/SECTION은
    화면 입력칸에서는 계속 따로 받고, 표에 보여줄 때만 이 함수로 합친다.
    SECTION이 숫자가 아니면(예외적인 값) 0채움 없이 그대로 이어붙인다.
    [2026-10-15] sep="-"를 주면 "10-100"처럼 AREA와 SECTION 사이에 하이픈을 넣는다
    (Section Check/재고조사 진행현황 화면 요청, 기본값은 예전처럼 붙여쓰기)."""
    area_2 = normalize_area(area, merged=True)
    sec = str(section).strip() if section is not None else ""
    try:
        sec_padded = str(int(sec)).zfill(section_width)
    except (TypeError, ValueError):
        sec_padded = sec
    return f"{area_2}{sep}{sec_padded}"


def parse_section_range(text):
    """"1~50", "1-50", "1" 처럼 적은 섹션 범위 문자열을 (시작, 끝) 정수
    튜플로 바꾼다. 하나만 적으면 시작=끝. 해석할 수 없으면 None."""
    if not text:
        return None
    t = str(text).strip().replace(" ", "")
    for sep in ("~", "-", "..", ":"):
        if sep in t:
            a, _, b = t.partition(sep)
            try:
                return (int(a), int(b))
            except ValueError:
                return None
    try:
        v = int(t)
        return (v, v)
    except ValueError:
        return None


def section_in_range(section, rng):
    """section 값이 숫자로 바뀌는 범위(rng=(start,end))안에 있는지 확인한다.
    section이 숫자가 아니면(문자 섞임 등) 문자열 그대로 시작~끝 사이인지
    비교한다."""
    if rng is None:
        return True
    start, end = rng
    try:
        v = int(_re_area.sub(r"[^0-9\-]", "", str(section)) or "0")
        return start <= v <= end
    except Exception:
        return str(start) <= str(section) <= str(end)
