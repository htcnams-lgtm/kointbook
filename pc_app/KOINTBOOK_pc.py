# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
KOINTBOOK PC 프로그램 - 메인 실행 파일.

ZZOINT(일반 매장용 데모 프로그램)의 구조를 기반으로, RBSKOREA가 KYOBO
서점에서 쓰는 재고실사 프로그램 화면 구성을 재현했다.

    마스터관리   : 상품마스터 / 점포마스터 / 작업자마스터 / 장부마스터
                   ([2026-09-28] 장부마스터를 한 번 없앴다가 [2026-10-08]
                    다시 추가했다 - 상품마스터에서 불러온 값은 PDA 실사용,
                    전산재고가 필요한 PC 화면/엑셀은 장부마스터 값 기준)
    재고실사수신 : PDA Data 수신 / 실적관리 / 이상치 체크 확인
    매대등록     : Section Check 화면 / 재고조사 진행 현황
    집계표관리   : 섹션별 아이템 재고현황 /
                   섹션별 결과보고서 / 샘플링 결과보고서 / 샘플링 자료등록
    자료생성     : 재고조사 보고서 / 재고조사 차이내역 / 자료생성 / AREA별 합산
                   ([2026-10-13] 차이명세를 집계표관리에서 옮겨와 '차이내역'으로 이름 변경, AREA별 합산은 맨 아래)
                   (이 3개는 최종적으로 자료(엑셀 등)를 만들어내는 화면이라
                    자료생성 그룹으로 묶는다 - 집계표관리는 "조회/조사"가
                    주목적인 화면들만 남긴다)
    데이터백업   : 데이터백업 ([2026-09-28] ZZOINT 원본 기능을 그대로
                   가져왔다 - KOINTBOOK.db 파일 전체를 백업/복원한다)

PDA(안드로이드)와의 데이터 교환은 USB adb pull/push가 기본이며, 기기가
연결되어 있지 않으면 엑셀 파일로 대신 주고받을 수 있다.

실행 방법
---------
    python KOINTBOOK_pc.py

사전 준비
---------
- PC에 Android platform-tools(adb)가 있으면 pc_app 폴더 안에 platform-tools
  폴더를 넣어두면 PATH 설정 없이 자동으로 인식한다 (없어도 엑셀로 대신 쓸 수 있음).
- 엑셀(.xlsx) 가져오기/내보내기를 쓰려면 openpyxl이 필요하다.
      pip install openpyxl
"""

import atexit
import os
import tkinter as tk
from pathlib import Path

from KOINTBOOK.version import APP_VERSION
from KOINTBOOK import big_messagebox

def _fatal_start_error():
    """[2026-10-13] 시작 중(불러오기 단계)에 오류가 나도 창이 바로 닫히지 않게, 오류 내용을 화면에
    보여주고 error_log.txt에도 저장한 뒤 Enter를 기다린다. (파일이 일부만 교체됐거나 빠졌을 때 등)"""
    import sys
    import traceback
    text = traceback.format_exc()
    print("=" * 60)
    print("KOINTBOOK를 시작하지 못했습니다:")
    print(text)
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_log.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        print("(같은 내용이 pc_app 폴더의 error_log.txt에 저장되었습니다)")
    except Exception:
        pass
    print("=" * 60)
    try:
        input("Enter 키를 누르면 창이 닫힙니다...")
    except Exception:
        pass
    sys.exit(1)


try:
    from KOINTBOOK import db as dbmod
    from KOINTBOOK import adb_utils
    from KOINTBOOK.ui_common import CL_NAVY, CL_NAVY_DARK, CL_GOLD, CL_BG, CL_TEXT, CL_TEXT_DIM
    from KOINTBOOK.screen_product_master import ProductMasterScreen
    from KOINTBOOK.screen_store_master import StoreMasterScreen
    from KOINTBOOK.screen_worker_master import WorkerMasterScreen
    from KOINTBOOK.screen_ledger_master import LedgerMasterScreen
    from KOINTBOOK.screen_pda_receive import PdaReceiveScreen
    from KOINTBOOK.screen_performance import PerformanceScreen
    from KOINTBOOK.screen_section_check import SectionCheckScreen
    from KOINTBOOK.screen_sampling_register import SamplingRegisterScreen
    from KOINTBOOK.screen_stock_report import StockReportScreen
    from KOINTBOOK.screen_area_sum import AreaSumScreen
    from KOINTBOOK.screen_diff_detail import DiffDetailScreen
    from KOINTBOOK.screen_section_item_status import SectionItemStatusScreen
    from KOINTBOOK.screen_section_result_report import SectionResultReportScreen
    from KOINTBOOK.screen_progress_status import ProgressStatusScreen
    from KOINTBOOK.screen_sampling_report import SamplingReportScreen
    from KOINTBOOK.screen_outlier_check import OutlierCheckScreen
    from KOINTBOOK.screen_data_generate import DataGenerateScreen
    from KOINTBOOK.screen_data_backup import DataBackupScreen
    from KOINTBOOK.screen_data_restore_txt import DataRestoreTxtScreen
    from KOINTBOOK.screen_pda_install import PdaInstallScreen
except Exception:
    _fatal_start_error()


class AppState:
    """여러 화면이 공유하는 현재 선택 점포/조사일자 정보.

    [2026-09-29] "데이터백업 복원후 프로그램을 껐다 키면 실적관리, 자료생성
    등 목록이 조회가 안되네" - 예전엔 프로그램을 켤 때마다 무조건
    store_code="KYOBO01" + 오늘 날짜로 초기화했다. 복원 직후에는(같은 세션
    안에서) 화면이 알아서 복원한 데이터의 점포/일자로 맞춰주지만, 그건
    메모리에만 있는 값이라 프로그램을 다시 켜면 사라지고 도로 KYOBO01/오늘
    날짜로 돌아가버렸다 - 복원한 데이터가 그 점포/일자가 아니면 목록에
    아무 것도 안 보이는 게 당연했던 것(버그로 보였지만 사실 "조회 기준"
    자체가 엉뚱했던 것). 이제 마지막으로 쓰던 점포/조사일자를 DB 안
    app_settings에 저장해두고, 켤 때 그 값부터 읽어온다(DB 파일 안에
    있으니 백업/복원해도 같이 백업/복원된다) - 저장된 값이 없으면(처음
    설치했을 때) 예전처럼 KYOBO01/오늘 날짜로 시작한다."""
    def __init__(self):
        from KOINTBOOK import db as dbmod
        from KOINTBOOK.ui_common import today_str
        self.store_code = dbmod.get_setting("last_store_code", "KYOBO01")
        self.store_name = dbmod.get_setting("last_store_name", "교보문고 광화문점")
        self.survey_date = dbmod.get_setting("last_survey_date", today_str())

    def save(self):
        """지금 점포/조사일자를 DB에 저장해서, 다음에 프로그램을 켤 때도
        이 상태로 이어지게 한다. 점포/조사일자가 바뀌는 자리(상품마스터의
        점포/일자 선택, 백업 복원 후 자동 반영)에서 불러준다."""
        from KOINTBOOK import db as dbmod
        dbmod.set_setting("last_store_code", self.store_code or "")
        dbmod.set_setting("last_store_name", self.store_name or "")
        dbmod.set_setting("last_survey_date", self.survey_date or "")


class KointBookPcApp:
    NAV_GROUPS = [
        # [2026-10-08] "작업자마스터 밑에 장부마스터 메뉴 추가"(요청).
        ("마스터관리", ["상품마스터", "점포마스터", "작업자마스터", "장부마스터"]),
        ("재고실사수신", ["PDA Data 수신", "실적관리", "이상치 체크 확인"]),
        ("매대등록", ["Section Check 화면", "재고조사 진행 현황"]),
        # [2026-10-13] 메뉴 개편(요청): "재고조사 차이명세"는 자료생성 그룹으로 옮기고 이름을
        # "재고조사 차이내역"으로 바꿨다. "AREA별 합산"은 메뉴 맨 아래로 내렸다.
        ("집계표관리", ["섹션별 아이템 재고현황", "섹션별 결과보고서",
                     "샘플링 결과보고서", "샘플링 자료등록"]),
        ("자료생성", ["재고조사 보고서", "재고조사 차이내역", "자료생성", "AREA별 합산"]),
        # [2026-09-28] ZZOINT(원본)의 데이터백업 화면/기능을 가져왔다. ZZOINT는
        # 이 메뉴에 "서버마스터"(Firebase 서버 동기화)도 같이 두지만,
        # KOINTBOOK은 Firebase 연동이 전혀 없는 구조라 그 화면은 가져오지
        # 않았다.
        # [2026-10-11] 데이터백업 하위메뉴로 "실사데이터 복원(txt)" 추가 - 재집계 txt를
        # 불러와 실사데이터로 복구한다(점포코드/점포명은 화면에서 고른다).
        ("데이터백업", ["데이터백업", "실사데이터 복원(txt)"]),
        # [2026-10-06] USB로 연결된 PDA에 KOINTBOOK 앱을 설치하는 메뉴.
        ("PDA 앱 설치", ["PDA 앱 설치"]),
    ]

    SCREENS = {
        "상품마스터": ProductMasterScreen,
        "점포마스터": StoreMasterScreen,
        "작업자마스터": WorkerMasterScreen,
        "장부마스터": LedgerMasterScreen,
        "PDA Data 수신": PdaReceiveScreen,
        "실적관리": PerformanceScreen,
        "Section Check 화면": SectionCheckScreen,
        "샘플링 자료등록": SamplingRegisterScreen,
        "재고조사 보고서": StockReportScreen,
        "AREA별 합산": AreaSumScreen,
        "재고조사 차이내역": DiffDetailScreen,
        "섹션별 아이템 재고현황": SectionItemStatusScreen,
        "섹션별 결과보고서": SectionResultReportScreen,
        "재고조사 진행 현황": ProgressStatusScreen,
        "샘플링 결과보고서": SamplingReportScreen,
        "이상치 체크 확인": OutlierCheckScreen,
        "자료생성": DataGenerateScreen,
        "데이터백업": DataBackupScreen,
        "실사데이터 복원(txt)": DataRestoreTxtScreen,
        "PDA 앱 설치": PdaInstallScreen,
    }

    # 화면 전환 때 "데이터가 그대로면 다시 계산하지 않는" 화면들 (DB만 보고 그리는 보고서/조회 화면).
    # 현재 시각을 보여주는 진행현황, PDA 연결 상태를 보는 수신 화면 등은 넣지 않는다.
    REFRESH_CACHE_SCREENS = {
        "재고조사 보고서", "AREA별 합산", "재고조사 차이내역", "섹션별 아이템 재고현황",
        "섹션별 결과보고서", "샘플링 결과보고서", "이상치 체크 확인", "Section Check 화면",
    }

    def __init__(self, root):
        self.root = root
        self.state = AppState()
        self.current_frame = None
        self.current_name = None
        self.frames_cache = {}
        self.menu_buttons = {}

        # 화면 이름 -> 그 화면이 속한 상단 메뉴(NAV_GROUPS의 그룹명). 활성 메뉴
        # 강조표시에 쓴다.
        self._group_of = {}
        for group_label, items in self.NAV_GROUPS:
            for name in items:
                self._group_of[name] = group_label

        root.title(f"KOINTBOOK v{APP_VERSION}")
        try:
            root.state("zoomed")
        except Exception:
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            w = min(1400, sw - 80)
            h = min(900, sh - 80)
            root.geometry(f"{w}x{h}")
        root.minsize(1000, 650)

        root.configure(bg=CL_BG)
        self._build_menubar()
        self.content = tk.Frame(root, bg=CL_BG)
        self.content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.show_screen("PDA Data 수신")

    def _build_menubar(self):
        """원본 RBSKOREA/KYOBO 프로그램처럼 좌측 세로 사이드메뉴가 아니라,
        상단에 가로로 늘어선 메뉴바(마스터관리/재고실사수신/매대등록/
        집계표관리/자료생성)와 드롭다운으로 화면을 고른다.

        세로 폭을 전혀 쓰지 않기 때문에, 하위 항목이 많은 그룹(집계표관리
        8개)이 있어도 화면이 잘리거나 스크롤이 필요해지는 문제가 구조적으로
        없다.

        [2026-09-28] "대메뉴 밑에 소메뉴가 보일때 디자인을 바꾸고싶어" -
        그동안은 tk.Menubutton + tk.Menu(운영체제 기본 회색 드롭다운)를
        썼는데, 이러면 프로그램 색(남색/금색) 톤과 안 맞았다. 지금 여기
        누른 대메뉴 바로 밑에 뜨는 위치/동작은 그대로 두고, 그 뜨는
        레이어만 직접 그린 커스텀 팝업(Toplevel)으로 바꿨다 - 예시 중
        "3번: 화이트 카드 + 왼쪽 골드바" 디자인을 그대로 적용한 것.
        (Menubutton 대신 그냥 Label을 버튼처럼 쓰고, 클릭하면
        _toggle_group_dropdown()이 그 Label 바로 밑에 흰 배경 팝업을
        띄운다 - 지금 화면이 속한 항목에는 왼쪽에 얇은 금색 바를 붙인다.)
        """
        bar = tk.Frame(self.root, bg=CL_NAVY_DARK, height=36)
        bar.pack(side=tk.TOP, fill=tk.X)

        brand = tk.Label(bar, text="  KOINTBOOK", bg=CL_NAVY_DARK, fg="white",
                          font=("", 12, "bold"))
        brand.pack(side=tk.LEFT, padx=(4, 12), pady=6)

        tk.Frame(bar, bg=CL_GOLD, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=6)

        self._dropdown = None  # 지금 떠 있는 커스텀 드롭다운(Toplevel) - 한 번에 하나만
        self._dropdown_group = None  # 그 드롭다운이 어느 그룹 것인지(같은 버튼 다시 누르면 닫기용)

        for group_label, items in self.NAV_GROUPS:
            mb = tk.Label(
                bar, text=group_label, bg=CL_NAVY_DARK, fg="#D8DCEA",
                font=("", 11, "bold"), padx=16, pady=8, cursor="hand2",
            )
            mb.pack(side=tk.LEFT)
            mb.bind("<Button-1>", lambda e, g=group_label, it=items, w=mb: self._toggle_group_dropdown(g, it, w))
            self.menu_buttons[group_label] = mb

        # 우측: 원본 화면 우상단의 "활성화면 바로가기" - 현재 화면을 다시
        # 앞으로 불러온다(팝업/대화상자에 가려졌을 때 등 용도).
        self.quicklink_label = tk.Label(
            bar, text="활성화면 바로가기", bg=CL_NAVY_DARK, fg=CL_GOLD,
            font=("", 10, "underline"), cursor="hand2",
        )
        self.quicklink_label.pack(side=tk.RIGHT, padx=16)
        self.quicklink_label.bind("<Button-1>", lambda e: self._jump_to_active())
        # [2026-10-15] "활성화면 바로가기" 왼쪽에 PDA 초기화면처럼 버전과 카피라이트를 표시한다.
        self.version_label = tk.Label(
            bar, text=f"VER. {APP_VERSION}   © 2026 namsman", bg=CL_NAVY_DARK, fg="#C9CED8",
            font=("", 9),
        )
        self.version_label.pack(side=tk.RIGHT, padx=(0, 4))

        # 드롭다운 밖(다른 메뉴 버튼도 아닌 곳)을 클릭하면 닫는다. 클릭이
        # 메뉴 버튼 자신 위에서 일어난 경우는 각 버튼의 <Button-1>(토글)이
        # 알아서 처리하니 여기서는 건드리지 않는다.
        self.root.bind_all("<Button-1>", self._on_global_click_for_dropdown, add="+")

    def _toggle_group_dropdown(self, group_label, items, anchor_widget):
        # 같은 버튼을 다시 누르면 닫기만 한다(토글).
        if self._dropdown is not None and self._dropdown_group == group_label:
            self._close_dropdown()
            return
        self._close_dropdown()

        anchor_widget.update_idletasks()
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()

        DROPDOWN_BORDER = "#DEE0E6"
        DROPDOWN_HOVER = "#E8ECF5"
        ROW_H = 36
        text_w = max((len(name) for name in items), default=0)
        width = max(200, min(320, 24 + text_w * 12))

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=DROPDOWN_BORDER)
        win.geometry(f"{width}x{ROW_H * len(items) + 8}+{x}+{y}")
        win.bind("<Escape>", lambda e: self._close_dropdown())

        inner = tk.Frame(win, bg="white")
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        for name in items:
            active = name == self.current_name
            row = tk.Frame(inner, bg=DROPDOWN_HOVER if active else "white", height=ROW_H)
            row.pack(fill=tk.X)
            row.pack_propagate(False)
            # 지금 보고 있는 화면이면 왼쪽에 얇은 금색 바를 붙인다.
            bar_w = 4 if active else 0
            if active:
                tk.Frame(row, bg=CL_GOLD, width=bar_w).pack(side=tk.LEFT, fill=tk.Y)
            lbl = tk.Label(row, text=name, bg=row["bg"], fg=CL_NAVY if active else CL_TEXT,
                           font=("", 10, "bold" if active else "normal"), anchor="w", cursor="hand2")
            lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(16 if not active else 12, 8))

            def on_select(_e=None, n=name):
                self._close_dropdown()
                self.show_screen(n)

            def on_enter(_e=None, r=row, lb=lbl, a=active):
                if not a:
                    r.configure(bg=DROPDOWN_HOVER)
                    lb.configure(bg=DROPDOWN_HOVER)

            def on_leave(_e=None, r=row, lb=lbl, a=active):
                if not a:
                    r.configure(bg="white")
                    lb.configure(bg="white")

            for widget in (row, lbl):
                widget.bind("<Button-1>", on_select)
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)

        self._dropdown = win
        self._dropdown_group = group_label
        # overrideredirect 창은 저절로 키보드 포커스를 받지 않아서, ESC
        # 바인딩이 실제로 눌리려면 포커스를 직접 넘겨줘야 한다.
        win.focus_set()

    def _close_dropdown(self):
        if self._dropdown is not None:
            try:
                self._dropdown.destroy()
            except tk.TclError:
                pass
        self._dropdown = None
        self._dropdown_group = None

    def _on_global_click_for_dropdown(self, event):
        if self._dropdown is None:
            return
        # 클릭한 위젯이 드롭다운(및 그 안의 모든 자식) 소속이면 그대로 둔다
        # (드롭다운 안의 항목 클릭은 각 행의 <Button-1>이 이미 처리한다).
        # 메뉴 버튼 자신을 클릭한 경우도 그 버튼의 토글 핸들러가 처리하므로
        # 여기서 또 닫아버리면 토글이 "닫혔다가 바로 다시 열리는" 것처럼
        # 안 열리는 문제가 생긴다 - 그래서 메뉴 버튼들도 제외한다.
        w = event.widget
        try:
            if str(w).startswith(str(self._dropdown)):
                return
        except Exception:
            pass
        if w in self.menu_buttons.values():
            return
        self._close_dropdown()

    def _jump_to_active(self):
        if self.current_name:
            self.show_screen(self.current_name)

    def _highlight_nav(self, active_name):
        active_group = self._group_of.get(active_name)
        for group_label, mb in self.menu_buttons.items():
            if group_label == active_group:
                mb.configure(bg=CL_NAVY, fg="white")
            else:
                mb.configure(bg=CL_NAVY_DARK, fg="#D8DCEA")

    def show_screen(self, name):
        if self.current_frame is not None:
            self.current_frame.pack_forget()

        if name not in self.frames_cache:
            screen_cls = self.SCREENS[name]
            self.frames_cache[name] = screen_cls(self.content, self)
        frame = self.frames_cache[name]
        frame.pack(fill=tk.BOTH, expand=True)
        self.current_frame = frame
        self.current_name = name
        self._highlight_nav(name)
        if hasattr(frame, "refresh"):
            # [2026-10-01] 보고서 화면은 들어올 때마다 수십만 건을 다시 계산했다(30만 건 기준
            # 차이명세 약 2.4초, 재고조사 보고서 약 0.8초 등). 점포/조사일자가 같고 마지막으로
            # 그린 뒤 DB가 바뀌지 않았으면(data_version) 이미 그려진 화면이 그대로 정답이므로
            # 다시 계산하지 않는다. 데이터가 바뀌었거나 점포/일자가 바뀌면 예전처럼 다시 계산하고,
            # 화면 안의 [조회] 버튼 등은 지금처럼 항상 다시 계산한다.
            key = (self.state.store_code, self.state.survey_date)
            cached = (name in self.REFRESH_CACHE_SCREENS
                      and getattr(frame, "_show_key", None) == key + (dbmod.data_version(),))
            if not cached:
                try:
                    frame.refresh()
                except Exception:
                    pass
                frame._show_key = key + (dbmod.data_version(),)

        self.root.title(f"KOINTBOOK v{APP_VERSION} - [{name}]")


def _set_app_icon(root: tk.Tk) -> None:
    """[2026-09-23] PC 프로그램 아이콘을 PDA 초기화면과 같은 책장 이미지(5번
    - 크게 키운 버전)로 설정한다. assets/icon.ico는 창 제목줄/작업표시줄
    (윈도우), assets/icon.png는 그 외 환경(Tk PhotoImage)을 위한 것이다.
    두 방식 다 실패해도(운영체제 차이 등) 프로그램 실행에는 영향이 없도록
    각각 조용히 무시한다."""
    assets_dir = Path(__file__).resolve().parent / "assets"
    ico_path = assets_dir / "icon.ico"
    try:
        if ico_path.exists():
            root.iconbitmap(default=str(ico_path))
    except Exception:
        pass
    try:
        # 여러 크기를 같이 넘겨서 제목줄/작업표시줄/Alt+Tab 등 상황에 맞는
        # 크기를 운영체제가 고르게 한다. 큰 것부터 넘기는 게 관례.
        photo_sizes = (256, 128, 64, 48, 32, 16)
        icon_imgs = []
        for s in photo_sizes:
            p = assets_dir / f"icon_{s}.png"
            if p.exists():
                icon_imgs.append(tk.PhotoImage(file=str(p)))
        if icon_imgs:
            root.iconphoto(True, *icon_imgs)
            root._app_icon_imgs = icon_imgs  # PhotoImage가 가비지컬렉션되지 않도록 참조 유지
    except Exception:
        pass


_single_instance_handle = None  # 프로그램이 끝날 때까지 뮤텍스 핸들을 붙잡아 둔다


def _ensure_single_instance() -> bool:
    """[2026-10-08] "KOINTBOOK.EXE 단독 실행, 두 번 실행해도 두 번 뜨지 않게" - Windows 이름 있는
    뮤텍스로 이미 실행 중인지 확인한다. 이미 떠 있으면 그 창을 앞으로 가져오고(최소화돼 있으면
    복원) False를 돌려줘서 새 프로세스는 바로 끝난다. 처음 실행이면 True.
    Windows가 아니거나 확인에 실패하면 막지 않고 True(그냥 실행)."""
    global _single_instance_handle
    if os.name != "nt":
        return True
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel32.CreateMutexW(None, False, "Local\\KOINTBOOK_PC_SINGLE_INSTANCE")
        already = kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
        if not already:
            _single_instance_handle = handle
            return True

        # 이미 실행 중: KOINTBOOK 창(Tk 최상위 창, 제목이 KOINTBOOK로 시작)을 찾아 앞으로.
        found = []
        EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _enum(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            if cls.value != "TkTopLevel":
                return True
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value.startswith("KOINTBOOK"):
                found.append(hwnd)
                return False
            return True

        user32.EnumWindows(EnumProc(_enum), 0)
        if found:
            hwnd = found[0]
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
        else:
            user32.MessageBoxW(None, "KOINTBOOK가 이미 실행 중입니다.", "KOINTBOOK", 0x40)
        return False
    except Exception:
        return True


def main():
    if not _ensure_single_instance():
        return
    dbmod.init_db()
    atexit.register(adb_utils.kill_server)
    root = tk.Tk()
    big_messagebox.install()  # 알림창 글씨 크게
    _set_app_icon(root)
    KointBookPcApp(root)
    dbmod.analyze_in_background()  # 큰 조회가 빨라지도록 DB 통계를 화면 뒤에서 갱신
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        error_text = traceback.format_exc()
        try:
            from KOINTBOOK.base_dir import get_base_dir
            log_path = get_base_dir() / "error_log.txt"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(error_text)
        except Exception:
            log_path = None

        print("=" * 60)
        print("프로그램 실행 중 오류가 발생했습니다:")
        print(error_text)
        if log_path:
            print(f"(같은 내용이 다음 파일에도 저장되었습니다: {log_path})")
        print("=" * 60)
        try:
            input("Enter 키를 누르면 창이 닫힙니다...")
        except Exception:
            pass
