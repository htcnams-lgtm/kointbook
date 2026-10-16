# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""집계표관리 > 재고조사 차이명세 화면.

[2026-09-28] "재고조사 차이명세 바코드별 차이내역 나타내는게 아니라 스캔한
에리어 섹션별 데이터를 보여주고 (이건 기존과동일하나, 전산재고와 비교 불필요)
소계로 바코드별 총수량과 전산재고를 비교" - RBSKOREA[KYOBO] 원본 화면 구조로
변경했다.

한 바코드가 여러 위치(AREA/SECTION/서가번호/단/열)에서 스캔됐으면 그 위치별로
한 줄씩(그 줄의 실사수량만 채우고 전산재고/실재고/누락재고/차이수량은 빈칸으로
비워둔다 - 위치별로는 전산재고와 비교할 필요가 없다) 보여주고, 그 바코드의
마지막에 "소  계" 줄을 하나 추가한다. 소계 줄에는 전산재고/실재고/누락재고
(상품마스터 books.rcds_qty/real_qty/missing_qty - 실제 "도서 마스터정보
업로드" 파일에 이미 들어있던 값을 그대로 쓴다)와, 그 바코드의 이번 조사
스캔수량 합계(위치별 줄들의 실사수량 합), 차이수량(스캔수량 합계-전산재고)을
보여준다. 맨 아래(마지막 페이지)에는 조회된 전체를 합산한 "합  계" 줄을 하나
더 보여준다(원본 화면과 동일한 구성).

[2026-09-28 추가] "상품마스터에 전산재고 수량은 있고 스캔기록이 없어도
목록에는 나와야지 전산재고 총수량과 비교를 해야되니까" - 이번 조사에서 한
번도 스캔되지 않은 상품마스터 항목도 목록에 포함한다. 이 경우 위치별 상세
줄은 없이(스캔한 적이 없으니) 도서명/바코드만 채운 헤더 줄 하나와, 곧바로
그 소계 줄(실사수량=0, 차이수량=-전산재고)이 이어진다.

차이수량(±) 입력칸에 숫자를 넣으면 바코드(소계) 기준 |차이수량| 이 그 값
이상인 바코드만 걸러서 보여준다 (비워두면 전체). 위치별 줄은 자기 바코드의
소계가 걸러지지 않는 한 그대로 따라온다.

[2026-09-28 추가 2] "조회 버튼 옆에 합계 조회 버튼, 소계와 합계만 보여주는
기능" - [합계조회]를 누르면 위치별 상세 줄(과 미스캔 항목의 헤더 줄)은 표에
넣지 않고 "소  계"/"합  계" 줄만 보여준다(엑셀저장/발행도 지금 보이는 모드
그대로 반영). [조회]/AREA 합산 라디오/Enter는 계속 평소의 상세 모드로
돌아온다.

[2026-09-28 추가 3] "재고조사 차이명세 목록이 현저하게 버벅거려 스크롤도
느리다" - 이 화면은 실적관리(screen_performance.py)와 달리 조회 결과 전체를
한 번에 표(ttk.Treeview)에 다 그려 넣고 있었다(위치별 줄 + 소계 줄까지
합치면 실사 건수가 많은 매장은 표 안에 수만 개 항목이 그대로 쌓인다) - 이게
스크롤이 느려지는 직접적인 원인이라, 실적관리에 이미 적용해둔 "페이지 단위로
표시" 방식을 여기서도 그대로 적용했다. 다만 단위는 "줄" 수가 아니라 "바코드
(그룹)" 수로 페이지를 나눈다(한 바코드의 위치별 줄+소계는 항상 붙어 있어야
하므로 중간에서 페이지를 끊으면 안 된다). 페이지를 넘겨도 조회 결과 "전체"는
메모리(self._groups)에 그대로 있어서, 엑셀저장/발행/합계는 항상 전체 기준
그대로다.

[2026-10-10] 예외여부 열 + 차이수량 기준 선택.
  - "상품마스터/장부마스터처럼 누락재고 다음에 예외여부 값도 추가" - 누락재고와
    실사수량 사이에 "예외여부"(Y/N) 열을 넣었다(조회화면/조회엑셀저장/엑셀저장/출력
    모두 같은 행 데이터를 쓰므로 한 번에 반영). 값은 장부마스터 화면과 같은 규칙
    (장부마스터 except_flag='Y' 이거나 exceptions 표에 있으면 Y, 아니면 N).
    소계 줄에만 채우고 위치별 상세 줄/합계 줄은 빈칸.
  - "조회버튼 앞에 실사-전산재고 / 실사-실재고 중 하나를 골라 조회하면 그 기준으로
    차이수량" - 기본은 실사-전산재고(실사수량-전산재고). 실사-실재고를 고르고
    [조회]하면 차이수량=실사수량-실재고. 차이수량(±) 조건 필터, 합계 줄도 같은
    기준을 따른다. 라디오만 바꾸고 [조회]를 안 누르면 표는 그대로다.
"""

import tkinter as tk
import unicodedata as _ud
from collections import defaultdict
from tkinter import filedialog, messagebox, ttk
from .masters import norm_barcode
from . import scope
from .scope_ui import ScopeBar
from . import db as dbmod
from .progress_core import Cancelled
from .progress_dialog import run_with_progress
from .masters import disp_qty, disp_exc
from .ui_common import setup_treeview, print_rows_to_excel, print_excel_file, file_date, friendly_save_error, \
    normalize_area, digit_code_variants, CL_BG, CL_NAVY, CL_TEXT_DIM, win_button

# [2026-09-28] "엑셀저장할때 오래걸려도 진행률 다이얼로그가 안뜨는데?" - 이
# 화면이 특히 항목 수가 많아서 문의가 들어온 화면이다. 행이 이 값보다 많을
# 때만 진행률 팝업(run_with_progress)으로 감싸고, 적을 때는 굳이 팝업을
# 띄우지 않고 예전처럼 바로 저장한다(깜빡임 방지).
PROGRESS_ROW_THRESHOLD = 300


def _delete_partial_file(path):
    """[취소]로 중단했거나 저장 중 오류가 났을 때, 다 만들다 만 파일이
    그대로 남아있으면 나중에 헷갈리니 지운다(있으면 지우고, 없거나 지울
    수 없으면 조용히 넘어간다)."""
    import os
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

# [2026-09-28] 한 페이지에 보여줄 바코드(그룹) 수 - 실적관리의 PAGE_ROWS와
# 같은 목적(표에 쌓이는 항목 수를 늘 일정 수준으로 묶어 스크롤이 느려지지
# 않게 함). 한 그룹은 위치별 줄(0개 이상) + 소계 줄 1개로 구성되어 그룹당
# 여러 줄이 될 수 있으므로, 실적관리(줄 단위 PAGE_ROWS=300)보다 더 작게
# 잡아 실제 표에 쌓이는 총 줄 수를 비슷한 수준으로 맞춘다.
GROUP_PAGE_SIZE = 150

# 14개 컬럼(도서명,바코드,AREA,SECTION,단,열,서가번호,전산재고,실재고,누락재고,
# 예외여부,실사수량,차이수량,비고) 중 숫자(3자리 콤마) 서식을 적용할 컬럼의
# 0-based 인덱스(예외여부=10은 Y/N 글자라 제외).
_NUMERIC_COL_INDEXES = {7, 8, 9, 11, 12}


def _visual_len(value):
    """엑셀 열 너비를 "타이트하게"(내용에 맞춰 딱 맞게) 계산하기 위한 글자
    폭 근사치. 한글/한자 등 넓은 문자는 2, 나머지(숫자/영문)는 1로 센다."""
    s = "" if value is None else str(value)
    total = 0
    for ch in s:
        total += 2 if _ud.east_asian_width(ch) in ("W", "F") else 1
    return total


# [2026-09-29] "조회시 도서명, 바코드 항목 내용은 왼쪽정렬하고 한칸 들여쓰기 /
# 전산재고, 실재고, 누락재고, 실사수량, 차이수량 항목 내용은 우정렬하고
# 한칸 들여쓰기" - ttk.Treeview는 칼럼에 indent 옵션이 없어서, 화면에
# 보여줄 값 앞(왼쪽정렬 칸)/뒤(우정렬 칸)에 진짜 공백 한 칸을 붙여
# "들여쓰기"를 흉내낸다. 엑셀저장/발행에 쓰이는 원본 row(그룹/소계/합계
# 데이터)는 그대로 두고, Treeview에 넣기 직전에만 이 함수로 감싼다.
_LEFT_INDENT_COL_IDX = (0, 1)          # 도서명, 바코드
_RIGHT_INDENT_COL_IDX = (7, 8, 9, 11, 12)  # 전산재고/실재고/누락재고/실사수량/차이수량 (10=예외여부 제외)


def _indent_row(row):
    row = list(row)
    for idx in _LEFT_INDENT_COL_IDX:
        v = row[idx]
        if v not in ("", None):
            row[idx] = " " + str(v)
    for idx in _RIGHT_INDENT_COL_IDX:
        v = row[idx]
        if v not in ("", None):
            row[idx] = str(v) + " "
    return tuple(row)


def _write_diff_detail_workbook(path, rows, headers, progress=None, report_header=None, summary_only=False,
                                title=None, info_center_text=None, row_kinds=None, left_align_cols=_LEFT_INDENT_COL_IDX,
                                center_align_cols=(2, 3, 4, 5, 6, 10), numeric_cols=None, equal_width_headers=None):
    """[2026-10-16] "섹션별 아이템 재고현황" 엑셀도 이 재고조사 차이내역 양식(상단 정보 블록 + 페이지
    머리글/바닥글)을 그대로 쓰도록, 아래 선택 인자를 추가했다. 모두 비워 두면(재고조사 차이내역) 예전과 똑같다.
      - title: 페이지 머리글 제목(기본 "재고조사 차이내역").
      - info_center_text: 정보 블록 3행 가운데 칸 글자(기본 "차이수량(±) : 0 이상" 같은 차이수량 조건).
      - row_kinds: rows와 같은 길이의 목록. None=일반 줄, "sub"=소계(단소계), "sec"=한 단계 큰 소계(섹션소계),
        "total"=합계. 주면 소계/합계 줄을 열 값으로 추정하지 않고 이 값대로 칠한다.
      - left_align_cols / center_align_cols / numeric_cols: 왼쪽 정렬(들여쓰기)·가운데 정렬·수량 서식(3자리 콤마) 열 번호(0부터).
      - equal_width_headers: 너비를 같게 맞출 열 머리글들(기본은 전산재고~비고).

    [2026-09-28] "엑셀저장시 엑셀 내용에 맞게 열너비를 타이트하게, 헤더와
    소계 합계등 프로그램 디자인에 맞게 셀배경색/글씨굵기등 조절, 수량란은
    꼭 세자리 콤마" - 기존 export_rows_to_excel()/print_rows_to_excel()은
    모든 화면이 공용으로 쓰는 "글자만 있는" 단순한 서식(헤더만 굵게, 열
    너비는 전부 16 고정)이라, 이 화면 전용으로 KOINTBOOK 팔레트(ui_common의
    CL_NAVY 남색 / COLOR_SUBTOTAL_CYAN·GREEN 골드톤)에 맞춘 서식을 여기서
    직접 만든다. openpyxl이 없으면 ImportError를 그대로 올려서(호출하는 쪽이
    처리) 폴백 경로(기존 단순 저장)로 넘어가게 한다.

    [2026-09-28 추가] "엑셀저장할때 오래걸려도 진행률 다이얼로그가 안뜨는데?" -
    progress(progress_core.Progress)를 넘기면 행을 쓸 때마다 진행률을
    보고한다(안 넘기면 예전처럼 조용히 저장 - 다른 곳에서 쓰는 기본 호출은
    그대로 동작).

    [2026-09-29] "발행시 이 양식으로 출력, 페이지마다 상단/헤더는 고정,
    페이지수는 변동값, 하단 (주)코인트써비스도 고정" - report_header에
    {"store_code", "store_name", "survey_date"(YYYYMMDD), "threshold_text"}
    를 담아 넘기면([발행]에서만 넘긴다 - 엑셀저장은 예전처럼 표만 있는
    단순한 파일 그대로 유지) 맨 위에 기업명/점포코드/점포명/차이수량 조건/
    검수자/조사일자/출력일자 정보 블록을 추가하고:
      - 진짜 엑셀 "페이지 머리글"에 제목("재고조사 차이명세")과 페이지
        번호("N of 총페이지" - 인쇄될 때마다 자동으로 계산됨)를 넣어 모든
        페이지 위에 반복되게 하고,
      - 정보 블록 + 표 헤더줄을 "인쇄 제목행"(Print Titles/반복할 행)
        으로 지정해 모든 페이지 상단에 같이 반복되게 하고,
      - 진짜 엑셀 "페이지 바닥글" 오른쪽에 "(주)코인트써비스"를 넣어 모든
        페이지 아래에 고정으로 나오게 한다.
    None이면(기본값) 예전처럼 표(헤더+데이터)만 있는 단순한 파일을 만든다.

    [2026-09-29 재디자인] "모든 칼라 인쇄가 불가하니 회색음영으로" 이하 -
    발행(report_header 있음) 전용으로 디자인을 전면 새로 잡았다(엑셀저장은
    예전 남색/골드 디자인 그대로 유지 - 아래 분기 참고). LibreOffice로 실제
    렌더링해서 한 줄씩 확인하며 확정한 사항들:
      - 정보 블록: 1행 기업명/검수자, 2행 점포코드/조사일자, 3행 점포명/
        출력일자(점포명과 "동일선상"), 4행 차이수량(±) - 제목처럼 표 전체
        폭 가운데 정렬. 검수자/조사일자/출력일자는 오른쪽 정렬(오른쪽 끝이
        표 마지막 칸=헤더 "비고" 오른쪽 끝과 자동으로 일치)이고, 셋의
        왼쪽 끝도 서로 맞도록 가장 긴 줄(출력일자) 기준으로 짧은 줄 앞에
        공백을 채워 시각적 폭을 맞춘다.
      - 정보 블록과 표 헤더 사이에 2행짜리 빈 여백(낮은 행높이)을 두고,
        표 헤더 바로 아래에는 빈 줄 없이 바로 데이터가 이어지게 한다
        (openpyxl의 ws.append()는 "지금까지 셀을 쓴 마지막 행"만 기준으로
        다음 행을 정하기 때문에, 셀을 쓰지 않은 빈 여백 행을 만들려면
        ws.append() 대신 ws.cell(row=.., ...)로 표 헤더 행 번호를 직접
        지정해서 써야 한다 - 안 그러면 여백이 사라지고 헤더 스타일이
        엉뚱한 행에 입혀지는 버그가 생긴다).
      - 헤더: 옅은 회색(F2F2F2) 배경 + 얇은(Bold 아닌) 글씨 + 가운데 정렬,
        칼럼마다 아주 옅은 회색 세로 구분선(hairline).
      - 제목("재고조사 차이명세")도 얇은(Bold 아닌) 글씨로.
      - 소계/합계/짝수줄 음영도 골드톤 대신 회색 톤으로.
      - freeze_panes는 쓰지 않는다(고정틀 선이 인쇄 시 헤더 바로 아래에
        남색 줄처럼 보이는 렌더링 문제가 있었다 - 정적으로 인쇄만 되는
        발행 용도에는 어차피 필요 없다).
      - 제목/헤더를 뺀 모든 글씨 크기를 80%로 축소.
      - 차이수량(±) 조건이 비어 있으면 "이상"이 아니라 "0 이상"으로.
      - 여백은 좌우를 기본값의 1/3로 줄이고, 상하단도 최대한 줄이되
        (실제 렌더링으로 확인한 결과) 18pt 제목/바닥글이 페이지 위아래
        끝에서 잘리지 않는 최소값(상단 0.6", 하단 0.35")까지만 줄인다.
      - 열 너비는 내용 비율은 그대로 유지한 채, 좌우 여백을 줄여서 넓어진
        용지 폭을 전부 채우도록 비례해서 확대한다(세로도 마찬가지로 표
        헤더/데이터 행 높이를 비례해서 키운다)."""
    import openpyxl
    from datetime import datetime as _dt
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from .progress_core import report as _report

    total = len(rows)
    numeric_set = set(numeric_cols) if numeric_cols is not None else _NUMERIC_COL_INDEXES
    _report(progress, message="엑셀 파일을 만드는 중...", done=0, total=total, unit="count")

    wb = openpyxl.Workbook()
    ws = wb.active

    # [2026-09-29] 열 너비를 내용(헤더+실제 데이터 포함)에 맞춰 미리 계산해
    # 둔다 - 원래는 표를 다 쓴 뒤에 계산했는데, report_header 정보 블록의
    # 좌/우 구역을 나눌 때도 "실제 컬럼이 얼마나 넓어질지"가 필요해서
    # (도서명 컬럼은 실제 책 제목 때문에 헤더보다 훨씬 넓어지는 게 보통이라,
    # 헤더 글자 수만으로 나누면 실제보다 훨씬 좁게 잡혀 정보 블록 글자가
    # 옆 구역과 겹쳐 보일 수 있다) rows를 이미 통째로 받는 이 함수 특성상
    # 미리 계산해도 상관없다. 아래(열 너비 지정)에서 그대로 재사용한다.
    widths = [_visual_len(h) for h in headers]
    for row in rows:
        for i, v in enumerate(row):
            widths[i] = max(widths[i], _visual_len(v))
    n_cols = len(headers)

    # [2026-09-29] "전산재고, 실재고,누락재고, 실사수량,차이수량,비고는
    # 너비가 동일하게" - 발행 전용으로 이 6칸을 그 중 가장 넓은 폭에
    # 맞춰 통일한다(엑셀저장은 예전처럼 칼럼마다 내용에 맞춘 너비 그대로).
    if report_header:
        _EQUAL_WIDTH_HEADERS = equal_width_headers or \
            ("전산재고", "실재고", "누락재고", "예외여부", "실사수량", "차이수량", "비고")
        _equal_idx = [i for i, h in enumerate(headers) if h in _EQUAL_WIDTH_HEADERS]
        if _equal_idx:
            _equal_w = max(widths[i] for i in _equal_idx)
            for i in _equal_idx:
                widths[i] = _equal_w

    # [2026-09-29 재배치] 열 너비(scale_h로 페이지 폭에 맞춰 키우고, 비고
    # 칸에는 여백 절반 축소분을 더해주는 계산)를 원래 표를 다 쓴 뒤(페이지
    # 설정 시점)에 했었는데, 그러면 정보 블록(검수자/조사일자/출력일자)의
    # "값" 칸을 몇 칸이나 차지해야 하는지 계산할 때 비고 칸이 이미 이만큼
    # 넓어질 걸 미리 알 수 없어서, 비고 칸이 꼭 필요한 것보다 훨씬 넓게
    # (원래의 좁은 nominal 폭만 보고) 계산되는 바람에 값이 ":" 뒤에서 한참
    # 떨어져 보이는 버그가 있었다 - 그래서 여기(정보 블록 계산보다 먼저)로
    # 앞당겨서, 실제로(비고 칸 확장 포함) 얼마나 넓어질지 final_widths로
    # 미리 구해두고 정보 블록 계산에도 그대로 활용한다.
    # 열 너비를 내용(헤더+데이터 포함)에 맞춰 타이트하게 - widths는 위에서
    # 이미 계산해 뒀다(정보 블록 구역 나누기와 공유).
    base_widths = [min(45, max(6, w + 2)) for w in widths]

    if report_header:
        PAGE_W_IN = 11.69   # A4 가로(landscape) 폭
        # [2026-09-29] 사용자가 발행양식 엑셀을 직접 열어 좌우 여백을
        # 0.4cm로 다시 맞춰서 올려준 것을 그대로 반영한다.
        LEFT_IN = 0.4 / 2.54
        RIGHT_IN_FULL = 0.7 / 3 + 0.08  # 비고 칸 확장폭 계산 기준(기존과 동일하게 유지)
        RIGHT_IN = 0.4 / 2.54
        PRINT_W_IN = PAGE_W_IN - LEFT_IN - RIGHT_IN_FULL
        TARGET_PX = PRINT_W_IN * 96.0
        MDW = 7.0  # 근사치(Calibri 11 @ 96dpi 기준 문자 폭)
        target_sum_units = (TARGET_PX - 5 * n_cols) / MDW
        cur_sum_units = sum(base_widths) or 1
        scale_h = max(1.0, target_sum_units / cur_sum_units)
        final_widths = [w * scale_h for w in base_widths]

        # [2026-09-29] "비고너비를 차이수량 너비 2배로 맞추고 비고너비
        # 줄어든만큼 도서명너비를 넓게" - 예전에는 여백을 반으로 줄여서
        # 생긴 여유폭(reclaimed_in)을 그대로 비고에 몰아줬는데(=old_remark_
        # width), 이제는 비고 너비를 "차이수량 너비의 정확히 2배"로
        # 고정한다. 예전 방식보다 비고가 줄어드는 만큼은 그대로 버리지
        # 않고 도서명 칸에 더해준다.
        reclaimed_in = RIGHT_IN_FULL - RIGHT_IN  # 반으로 줄여서 늘어난 폭
        extra_units = (reclaimed_in * 96.0) / MDW * 8.5
        remark_idx = headers.index("비고") if "비고" in headers else (n_cols - 1)
        diff_qty_idx = headers.index("차이수량") if "차이수량" in headers else None
        book_name_idx = headers.index("도서명") if "도서명" in headers else 0
        old_remark_width = final_widths[remark_idx] + extra_units
        if diff_qty_idx is not None:
            new_remark_width = final_widths[diff_qty_idx] * 2
        else:
            new_remark_width = old_remark_width
        final_widths[remark_idx] = new_remark_width
        final_widths[book_name_idx] += max(0.0, old_remark_width - new_remark_width)

    # [2026-09-29] report_header가 있으면(발행 전용) 표 헤더 앞에 정보
    # 블록 3줄 + 1줄 여백을 먼저 넣어서, 표 헤더 자체가 그만큼 아래로
    # 밀리게 만든다(그래야 아래 모든 "몇 번째 행"에 관한 계산이 이
    # 오프셋만큼 같이 밀린다). [2026-09-29 정정] "점포명, 차이수량,
    # 출력일자 아래 정렬이 동일선상이고, 밑에 헤더와 한칸차이" - 차이수량을
    # 점포명/출력일자와 같은 줄(3행)로 합치고, 표 헤더 앞 여백도 2행→1행.
    info_rows = 3 if report_header else 0
    spacer_rows = 1 if report_header else 0
    header_row = info_rows + spacer_rows + 1

    if report_header:
        # 정보 블록의 좌/우 구역 폭을 "실제로 들어갈 글자 수"에 맞춰
        # 뒤(우)/앞(좌)에서부터 컬럼을 채워나간다 - 균등 3등분 대신 이
        # 방식을 쓰면 오른쪽 구역이 "출력일자 : YYYY-MM-DD HH:MM:SS"
        # (약 34자 폭)를, 왼쪽 구역이 "기업명 : (주)XXX"(약 22자 폭)를
        # 넉넉히 담을 만큼만 차지해서, 가운데(차이수량)와 겹치지 않는다.
        def _accumulate(indices, target):
            acc = 0
            cnt = 0
            for i in indices:
                acc += widths[i] + 2
                cnt += 1
                if acc >= target:
                    break
            return max(1, cnt)

        right_cols = _accumulate(range(n_cols - 1, -1, -1), 34)
        left_cols = _accumulate(range(0, n_cols), 22)
        if left_cols + right_cols >= n_cols:
            left_cols = max(1, n_cols // 3)
            right_cols = max(1, n_cols // 3)
        left_start = 1
        mid_start = left_start + left_cols
        right_start = n_cols - right_cols + 1

        survey_date = (report_header.get("survey_date") or "").strip()
        if len(survey_date) == 8 and survey_date.isdigit():
            survey_date_disp = f"{survey_date[:4]}년 {survey_date[4:6]}월 {survey_date[6:]}일"
        else:
            survey_date_disp = survey_date or "-"
        threshold_text = (report_header.get("threshold_text") or "").strip()
        diff_disp = f"{threshold_text} 이상" if threshold_text else "0 이상"
        # [2026-09-29] "출력일자값을 2026년 9월 29일이 아닌 09월로 두자리로
        # 통일" - 한 번은 "월/일 앞에 0을 채우지 않는 표기"로 바꿨었는데,
        # 다시 월/일 모두 2자리로 고정하는 쪽으로 되돌린다(연도는 그대로 4자리).
        _now = _dt.now()
        printed_at = _now.strftime("%Y년 %m월 %d일 %H:%M:%S")

        # [2026-09-29] 사용자가 발행양식 엑셀을 직접 열어 손으로 다시
        # 배치한 결과를 그대로 반영한다: 라벨 칸(검수자:/조사일자:/
        # 출력일자:)과 값 칸(값/값/값) 모두 각각 칼럼 하나씩(병합 없이)만
        # 쓴다 - 이전에 있던 "블록 전체를 오른쪽으로 이동" 계산(값 칸
        # 폭을 줄여서 라벨 칸을 오른쪽으로 미는 방식)은 결국 값 칸이
        # 마지막 칼럼 1개, 라벨 칸이 그 바로 앞 칼럼 1개로 정리됐다.
        value_end = n_cols
        value_start = n_cols
        label_end = value_start - 1
        label_start = label_end
        # [2026-09-29] 사용자가 직접 조정해서 올려준 값 - 차이수량(±) 칸이
        # (right_start 기준이 아니라) 라벨 칸 바로 앞까지 꽉 채워지도록.
        mid_end = label_start - 1

        info_pt = max(7, round(11 * 0.8))
        info_font = Font(size=info_pt, name="맑은 고딕")
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")
        # [2026-09-29] "(인) 내어쓰기 2칸" - 기존 들여쓰기 5칸에서 2칸을
        # 내어써서(바깥쪽, 즉 오른쪽 끝 방향으로 2칸 덜 들어가게) 3칸으로.
        align_right_indent2 = Alignment(horizontal="right", vertical="center", indent=3)
        align_center = Alignment(horizontal="center", vertical="center")

        def _info_cell(row, col_start, col_end, text, align=align_left, font=info_font):
            if col_end > col_start:
                ws.merge_cells(start_row=row, start_column=col_start,
                                end_row=row, end_column=col_end)
            cell = ws.cell(row=row, column=col_start, value=text)
            cell.font = font
            cell.alignment = align

        store_name = report_header.get("store_name") or ""

        _info_cell(1, left_start, mid_start - 1, "기업명 : (주)교보문고")
        _info_cell(1, label_start, label_end, "검수자 :", align=align_right)
        _info_cell(1, value_start, value_end, "(인)", align=align_right_indent2)

        _info_cell(2, left_start, mid_start - 1, f"점포코드 : {report_header.get('store_code') or ''}")
        _info_cell(2, label_start, label_end, "조사일자 :", align=align_right)
        _info_cell(2, value_start, value_end, survey_date_disp, align=align_left)

        # [2026-09-29] "점포명, 차이수량, 출력일자 아래 정렬이 동일선상" -
        # 셋을 같은 줄(3행)에: 점포명(좌)/차이수량(남는 가운데 구간)/
        # 출력일자(우).
        # [2026-09-29] 사용자가 손으로 조정해 올려준 파일에서 차이수량(±)
        # 글자가 굵게 되어 있었다 - 그대로 반영(굵게).
        diff_font = Font(size=info_pt, name="맑은 고딕", bold=True)
        _info_cell(3, left_start, mid_start - 1, f"점포명 : {store_name}")
        _info_cell(3, mid_start, mid_end, info_center_text if info_center_text is not None
                   else f"차이수량(±) : {diff_disp}", align=align_center, font=diff_font)
        _info_cell(3, label_start, label_end, "출력일자 :", align=align_right)
        _info_cell(3, value_start, value_end, printed_at, align=align_left)

        # [2026-09-29] "밑에 헤더와 한칸차이" - 정보블록 바로 다음, 표
        # 헤더 사이에 1행짜리 여백(낮은 행높이)만 둔다.
        ws.row_dimensions[info_rows + 1].height = 6

        # [발행] 전용: 진짜 엑셀 페이지 머리글/바닥글 - 표(worksheet) 안의
        # 셀이 아니라 인쇄될 때 모든 페이지 위/아래에 독립적으로 반복되는
        # 엑셀 고유 영역이라, "페이지 수는 인쇄 시점에 자동 계산"되는
        # &N(총 페이지)/&P(현재 페이지)를 그대로 쓸 수 있다.
        ws.oddHeader.center.text = title or "재고조사 차이내역"
        ws.oddHeader.center.size = 18
        ws.oddHeader.center.font = "맑은 고딕"  # [2026-09-29] "글씨는 굵기 얇게" - Bold 제거
        ws.oddHeader.right.text = "&P of &N"
        ws.oddHeader.right.size = 11
        ws.oddFooter.right.text = "(주)코인트써비스"
        ws.oddFooter.right.size = 10
        # 화면에서 미리보기 없이 바로 공용 프린터 대화상자로 인쇄하는
        # 경로(print_excel_file)를 쓰므로, 짝수 페이지도 홀수 페이지와
        # 똑같은 머리글/바닥글을 쓰도록 evenHeader/evenFooter도 맞춰준다.
        try:
            ws.evenHeader.center.text = ws.oddHeader.center.text
            ws.evenHeader.center.size = ws.oddHeader.center.size
            ws.evenHeader.center.font = ws.oddHeader.center.font
            ws.evenHeader.right.text = ws.oddHeader.right.text
            ws.evenHeader.right.size = ws.oddHeader.right.size
            ws.evenFooter.right.text = ws.oddFooter.right.text
            ws.evenFooter.right.size = ws.oddFooter.right.size
        except Exception:
            pass

    # [2026-09-29] 표 헤더 행을 ws.append(headers)가 아니라 명시적으로
    # header_row에 쓴다 - report_header가 있을 때 위에서 만든 2행짜리
    # 여백(스타일 없는 빈 셀)은 ws.append()의 "다음 행" 기준(지금까지
    # 셀을 쓴 마지막 행+1)에 포함되지 않아서, append()를 그대로 쓰면
    # 여백이 사라지고 헤더 스타일이 엉뚱한 행(여백 중 하나)에 입혀지는
    # 버그가 있었다(디자인 미리보기 단계에서 실제 렌더링으로 확인).
    center = Alignment(horizontal="center", vertical="center")
    for i, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=i, value=h)

    if report_header:
        # 헤더: 옅은 회색 배경 + 얇은(Bold 아닌) 글씨 + 칼럼마다 아주 옅은
        # 회색 세로 구분선(hairline) - "모든 칼라 인쇄가 불가하니
        # 회색음영으로" / "헤더 항목 글씨는 가운데 정렬" / "항목마다
        # 세로선을 엷게".
        header_fill = PatternFill("solid", fgColor="F2F2F2")
        header_font = Font(bold=False, size=info_pt, name="맑은 고딕")
        vline = Side(style="hair", color="D9D9D9")
        thin_bottom = Side(style="thin", color="808080")
        for col_i in range(1, n_cols + 1):
            cell = ws.cell(row=header_row, column=col_i)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center
            cell.border = Border(left=vline, right=vline, bottom=thin_bottom)
        # 정적으로 인쇄만 되는 발행용 파일에는 고정틀이 필요 없고,
        # freeze_panes를 쓰면 인쇄 시 헤더 바로 아래에 남색 줄처럼 보이는
        # 렌더링 문제가 있었다(-> "헤더 밑에 남색칸 한줄 삭제").
        ws.freeze_panes = None
        # [2026-09-29] "페이지마다 상단, 헤더는 고정" - 인쇄 제목행(모든
        # 페이지 위에 반복해서 다시 찍히는 행)을 정보 블록+여백+표
        # 헤더(header_row)까지로 지정한다.
        ws.print_title_rows = f"1:{header_row}"
    else:
        # 엑셀저장(예전 남색/골드 디자인 그대로 유지) - 발행 전용 재디자인은
        # report_header가 있을 때만 적용한다.
        header_fill = PatternFill("solid", fgColor="172C5E")
        header_font = Font(bold=True, color="FFFFFF")
        for cell in ws[header_row]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center
        ws.freeze_panes = f"A{header_row + 1}"  # 스크롤해도 헤더가 고정되게

    if report_header:
        # 소계/합계/짝수줄 음영 - 회색 톤("모든 칼라 인쇄가 불가하니
        # 회색음영으로").
        subtotal_fill = PatternFill("solid", fgColor="EFEFEF")
        section_fill = PatternFill("solid", fgColor="E0E0E0")  # 섹션소계(단소계보다 한 단계 진한 회색)
        total_fill = PatternFill("solid", fgColor="D9D9D9")
        odd_fill = PatternFill("solid", fgColor="F7F7F7")
        gold_top = Border(top=Side(style="thin", color="9E9E9E"))
        navy_top = Border(top=Side(style="medium", color="595959"))
        data_font = Font(size=info_pt, name="맑은 고딕")
        bold_font = Font(bold=True, size=info_pt, name="맑은 고딕")
        vline = Side(style="hair", color="D9D9D9")
        data_vborder = Border(left=vline, right=vline)
    else:
        # 소계/합계: 화면(tag_configure)의 골드톤과 맞춘 채우기색(예전 그대로).
        subtotal_fill = PatternFill("solid", fgColor="F3EAD3")   # COLOR_SUBTOTAL_CYAN과 동일
        section_fill = subtotal_fill
        total_fill = PatternFill("solid", fgColor="E8D9B0")      # COLOR_SUBTOTAL_GREEN과 동일
        odd_fill = PatternFill("solid", fgColor="F6F7F9")        # 표의 "odd" 줄무늬와 동일
        gold_top = Border(top=Side(style="thin", color="B08D3E"))
        navy_top = Border(top=Side(style="medium", color="172C5E"))
        data_font = None
        bold_font = Font(bold=True)  # 소계/합계 굵은 글씨 - 셀마다 새로 만들지 않고 하나만 재사용
        data_vborder = None
    code_center = Alignment(horizontal="center")
    num_right = Alignment(horizontal="right")
    # [2026-09-29] "전산재고,실재고,누락재고,실사수량,차이수량 항목 내용은
    # 우정렬후 한칸 들여쓰기" - 발행 전용(엑셀저장은 기존 그대로 들여쓰기 없이).
    num_right_indent = Alignment(horizontal="right", vertical="center", indent=1)

    # [2026-09-28] "엑셀저장 시간이 30분이 넘는다, 이전에는 2분도 안됐다" -
    # 원인을 찾아보니 매 행마다 `ws[ws.max_row]`로 방금 추가한 줄의 셀들을
    # 다시 가져오고 있었는데, openpyxl의 max_row/max_column은 "지금까지
    # 들어간 모든 셀" 중 최댓값을 매번 새로 훑어서 계산한다(캐시 안 됨) -
    # 즉 행이 늘어날수록 그 행을 가져오는 데 걸리는 시간도 같이 늘어나서
    # 전체적으로는 행 수의 제곱에 비례해서 느려지는 구조였다(바코드가 적은
    # 매장에서는 표가 안 났는데, 스캔 항목이 많은 매장에서 유독 오래 걸린
    # 이유). 대신 지금 쓰고 있는 행 번호를 직접 세서 ws.cell(row=.., ..)로
    # 바로 그 셀만 가져오게 고쳤다 - 이러면 행 수에 비례해서만 걸린다.
    data_row_i = 0
    step = max(1, total // 300)  # 300번 정도만 갱신(너무 자주 갱신하면 스레드 잠금 왕복만 늘어난다)
    for row in rows:
        ws.append(list(row))
        data_row_i += 1
        excel_row_num = data_row_i + header_row  # header_row행이 표 헤더라 데이터는 그 다음 행부터 시작
        if progress is not None and (data_row_i % step == 0 or data_row_i == total):
            _report(progress, done=data_row_i)
            progress.check_cancel()  # [취소] 눌렀으면 여기서 Cancelled 예외로 중단
        excel_row = [ws.cell(row=excel_row_num, column=c) for c in range(1, len(row) + 1)]
        kind = row_kinds[data_row_i - 1] if row_kinds is not None else None
        is_total = (kind == "total") if row_kinds is not None else row[0] == "합  계"
        # [2026-09-28] 소계 줄의 첫 칸이 이제 "소  계" 고정 문구가 아니라
        # [합계조회] 모드에서는 도서명으로 바뀔 수 있어(요청: "합계조회만
        # 눌렀을땐 소계대신 바코드에 맞는 도서명을 보여줘"), 문구로 판별할
        # 수 없다. 대신 소계/합계 줄만 전산재고/실재고/누락재고(7,8,9번
        # 칸)가 전부 채워져 있다는 점으로 판별한다(위치별 상세 줄은 실사
        # 수량 칸만 채워지고 이 세 칸은 항상 비어 있다).
        # [2026-09-29] "합계조회후 조회하거나 발행할땐 목록 내용 음영을
        # 없애주고 아랫면 선도 안긋도록" - [합계조회] 모드는 상세줄 없이
        # 바코드마다 한 줄(전산재고/실재고/누락재고가 항상 채워짐)만 나오는데,
        # 그러면 위 판별식으로는 "전부 다" 소계로 인식돼 모든 줄에 소계
        # 음영/아랫선이 그대로 붙어버렸다. summary_only일 때는 합계 줄만
        # 강조하고 소계 음영/선은 아예 적용하지 않는다.
        if row_kinds is not None:
            is_subtotal = kind in ("sub", "sec")
        else:
            is_subtotal = (not summary_only) and (not is_total) and all(
                row[i] != "" and row[i] is not None for i in (7, 8, 9)
            )
        for col_i, cell in enumerate(excel_row):
            if data_font is not None:
                cell.font = data_font
            if data_vborder is not None:
                cell.border = data_vborder
            if is_total:
                cell.fill = total_fill
                cell.font = bold_font
                cell.border = Border(left=data_vborder.left, right=data_vborder.right,
                                      top=navy_top.top) if data_vborder else navy_top
            elif is_subtotal:
                cell.fill = section_fill if kind == "sec" else subtotal_fill
                cell.font = bold_font
                # [2026-09-29] "소계 줄 윗면에 선이 아직도 그어져있어, 아랫면에
                # 선을 그어주고" - 화면(Treeview)은 이미 옵션 A(아랫선만)로
                # 바꿨는데, 이 발행용 엑셀에는 소계 줄 자기 자신의 윗선
                # (top=gold_top.top)만 그리고 있었다. 윗선을 빼고 아랫선
                # (bottom)으로 바꾼다.
                cell.border = Border(left=data_vborder.left, right=data_vborder.right,
                                      bottom=gold_top.top) if data_vborder else Border(bottom=gold_top.top)
            elif data_row_i % 2 == 0:
                cell.fill = odd_fill
            if report_header and col_i in left_align_cols:
                # [2026-09-29] "도서명, 바코드 항목 내용은 왼쪽정렬후
                # 들여쓰기 한칸" (발행 전용 - 엑셀저장은 기존 기본 정렬 그대로).
                cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            if col_i in center_align_cols:  # AREA/SECTION/단/열/서가번호/예외여부 - 짧은 코드값은 가운데 정렬
                # [2026-10-16] 섹션별 아이템 재고현황(row_kinds를 넘기는 경우)은 같은 줄의 글자 높이가 어긋나 보이지
                # 않도록 세로도 가운데로 맞춘다(재고조사 차이내역은 예전 그대로).
                cell.alignment = Alignment(horizontal="center", vertical="center") if row_kinds is not None else code_center
            if col_i in numeric_set:
                value = row[col_i]
                if isinstance(value, (int, float)):
                    cell.number_format = "#,##0"  # [요청] 수량란은 꼭 3자리 콤마
                    cell.alignment = num_right_indent if report_header else num_right

    # 열 너비(base_widths/final_widths 등)는 위(정보 블록 계산보다도 앞)에서
    # 이미 다 계산해 뒀다 - 정보 블록의 값 칸 크기 계산과 공유하기 위해
    # 앞당겨졌다. 여기서는 그 결과를 실제로 워크시트에 적용만 한다.

    # 인쇄/미리보기 시 12개 컬럼이 한 페이지 가로 폭에 다 들어오도록(용지가
    # 좁으면 일부 컬럼이 다음 페이지로 잘려 넘어가 버린다) 가로 방향 +
    # 폭 기준 한 페이지 맞춤으로 설정한다.
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    if report_header:
        for i, w in enumerate(final_widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = min(60, w)

        # "세로도 마찬가지" - 표 헤더/데이터 행 높이도 같은 비율로(단,
        # 너무 늘어지지 않게 최대 1.3배로 제한해서) 키운다.
        row_scale = min(1.3, scale_h)
        ws.row_dimensions[header_row].height = 20 * row_scale
        data_row_h = 17 * row_scale
        for r in range(header_row + 1, header_row + 1 + len(rows)):
            ws.row_dimensions[r].height = data_row_h

        ws.page_margins.left = LEFT_IN
        ws.page_margins.right = RIGHT_IN
        # [2026-09-29] 사용자가 발행양식 엑셀 파일을 직접 손으로 열어
        # 페이지설정 여백을 깔끔한 cm 단위 값으로 다시 맞춰서 올려준 것을
        # 그대로 반영한다(상단 1.5cm/하단 0.9cm/머리글 0.8cm/바닥글 0.4cm).
        ws.page_margins.top = 1.5 / 2.54
        ws.page_margins.bottom = 0.9 / 2.54
        ws.page_margins.header = 0.8 / 2.54
        ws.page_margins.footer = 0.4 / 2.54
    else:
        for i, w in enumerate(base_widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # [2026-09-28] "진행률이 100% 된뒤 파일에 쓰는중이라고 나오면서 10초간
    # 딜레이되네?" - progress_core.Progress.__call__()은 message가 바뀌면
    # "새 단계가 시작됐다"고 보고 done을 넘기지 않으면 0으로 되돌려버린다.
    # 여기서 done 없이 message만 넘겼더니 다 채운 진행률이 도로 0%로
    # 보였던 것 - done=total을 같이 넘겨서 꽉 찬 상태 그대로 유지한 채
    # 문구만 바뀌게 한다(wb.save() 자체는 openpyxl이 한 번에 처리하는
    # 호출이라 그 안에서 더 잘게 진행률을 쪼갤 수는 없다 - 그래서 저장하는
    # 몇 초~몇십 초 동안은 100%로 멈춰 있는 게 정상이다).
    _report(progress, message="파일에 쓰는 중...", done=total)
    wb.save(path)


class DiffDetailScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._summary_only = False  # [합계조회] 상태 유지(조회/라디오는 상세 모드로 되돌아감)
        self._groups = []           # 조회된 전체(바코드별 그룹) - 페이지를 넘겨도 유지
        self._grand = (0, 0, 0, 0, 0)  # (전산재고,실재고,누락재고,실사수량,차이수량) 전체 합
        self._view_page = 0
        self._view_total_pages = 1
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = tk.Frame(self, bg=CL_BG)
        top.pack(fill=tk.X, padx=8, pady=(10, 2))
        # [2026-10-01] "버튼이 많아 화면을 넘어가 안 보임" - 한 줄에 다 넣으면 1366px 화면에서 오른쪽
        # 버튼(발행/엑셀발행/엑셀저장)이 잘렸다. 두 줄로 나눈다: 위 줄(top) = 조회기준/입력칸/AREA 합산전·후,
        # 아래 줄(actions) = 차이수량(±)/[조회]/[합계조회] ... [발행] [엑셀발행] [엑셀저장].
        actions = tk.Frame(self, bg=CL_BG)
        actions.pack(fill=tk.X, padx=8, pady=(0, 6))

        # [2026-09-29] "AREA합산전 앞에 전체, AREA, SECTION, AREA+SECTION,
        # 서가번호, 바코드, 도서명 선택해서 조회할수있게 항목 생성" - 실적관리
        # (screen_performance.py)의 조회 항목 라디오와 같은 패턴(같은 항목
        # 구성, "AREA+SECTION"만 입력칸이 두 개로 바뀌는 것까지)을 그대로
        # 가져왔다. 여기서는 실적관리처럼 팝업을 새로 띄우지 않고, 지금
        # 화면의 조회 조건(차이수량(±) 조건과 동일하게)에 얹어서 바로 이
        # 목록/엑셀저장/발행에 반영한다 - 값을 비워두면("전체"를 고른 것과
        # 동일하게) 조건 없이 기존과 똑같이 전체가 나온다.
        tk.Label(top, text="조회기준", bg=CL_BG, fg=CL_TEXT_DIM).pack(side=tk.LEFT, padx=(0, 4))
        self.filter_mode = tk.StringVar(value="전체")
        for label in ("전체", "AREA", "SECTION", "AREA+SECTION", "서가번호", "바코드", "도서명"):
            tk.Radiobutton(top, text=label, variable=self.filter_mode, value=label, bg=CL_BG,
                           command=self._on_filter_mode_changed).pack(side=tk.LEFT)

        # 조회 모드에 따라 "입력칸 하나"(e_filter) 또는 "AREA/SECTION 칸 두
        # 개"(filter_area_section_frame)가 이 고정된 자리 안에서 번갈아
        # 보이게 한다(실적관리와 같은 이유 - 오른쪽 위젯들 위치가 안 흔들림).
        self.filter_value_frame = tk.Frame(top, bg=CL_BG)
        self.filter_value_frame.pack(side=tk.LEFT, padx=(4, 0))

        self.e_filter = tk.Entry(self.filter_value_frame, width=14)
        self.e_filter.bind("<Return>", lambda ev: self.refresh(summary_only=False))

        self.filter_area_section_frame = tk.Frame(self.filter_value_frame, bg=CL_BG)
        tk.Label(self.filter_area_section_frame, text="AREA", bg=CL_BG, fg=CL_TEXT_DIM).pack(side=tk.LEFT)
        self.e_filter_area = tk.Entry(self.filter_area_section_frame, width=6)
        self.e_filter_area.bind("<Return>", lambda ev: self.refresh(summary_only=False))
        self.e_filter_area.pack(side=tk.LEFT, padx=(2, 10))
        tk.Label(self.filter_area_section_frame, text="SECTION", bg=CL_BG, fg=CL_TEXT_DIM).pack(side=tk.LEFT)
        self.e_filter_section = tk.Entry(self.filter_area_section_frame, width=6)
        self.e_filter_section.bind("<Return>", lambda ev: self.refresh(summary_only=False))
        self.e_filter_section.pack(side=tk.LEFT, padx=(2, 0))

        # 기본 모드("전체")는 입력칸이 필요 없으니 처음엔 둘 다 안 보이게.
        self._on_filter_mode_changed(initial=True)

        self.merge_mode = tk.StringVar(value="합산전")
        tk.Radiobutton(top, text="AREA 합산전", variable=self.merge_mode, value="합산전", bg=CL_BG,
                       command=lambda: self.refresh(summary_only=False)).pack(side=tk.LEFT, padx=(20, 0))
        tk.Radiobutton(top, text="AREA 합산후", variable=self.merge_mode, value="합산후", bg=CL_BG,
                       command=lambda: self.refresh(summary_only=False)).pack(side=tk.LEFT)
        tk.Label(actions, text="차이수량(±)", bg=CL_BG).pack(side=tk.LEFT, padx=(0, 4))
        self.e_diff = tk.Entry(actions, width=10)
        self.e_diff.pack(side=tk.LEFT)
        self.e_diff.bind("<Return>", lambda ev: self.refresh(summary_only=False))
        # [2026-10-10] "조회버튼앞에 체크버튼 두개 실사-전산재고, 실사-실재고 배치해서
        # 둘중하나 체크해서 조회하면 그 기준으로 차이수량" - 둘 중 하나만 고르는 선택
        # (라디오). 기본은 실사-전산재고. 라디오를 바꾸는 것만으로는 다시 조회하지
        # 않고, [조회]/Enter를 눌러야 그 기준으로 차이수량이 다시 계산된다.
        self.diff_basis = tk.StringVar(value="ledger")
        tk.Radiobutton(actions, text="실사-전산재고", variable=self.diff_basis, value="ledger",
                       bg=CL_BG).pack(side=tk.LEFT, padx=(12, 0))
        tk.Radiobutton(actions, text="실사-실재고", variable=self.diff_basis, value="real",
                       bg=CL_BG).pack(side=tk.LEFT, padx=(0, 0))
        # [2026-10-13] 서적/문구 구분(AREA·SECTION 범위). 구분을 바꾸면 바로 다시 조회한다.
        self.bar = ScopeBar(actions, on_change=lambda: self.refresh(summary_only=False))
        self.bar.pack(side=tk.LEFT, padx=(14, 0))
        win_button(actions, text="조회", command=lambda: self.refresh(summary_only=False),
                   kind="normal").pack(side=tk.LEFT, padx=8)
        # [2026-09-28] "조회 버튼 옆에 합계 조회 버튼 생성, 소계와 합계만
        # 보여주는 기능" - 위치별 상세 줄/미스캔 헤더 줄을 빼고 소계+합계만.
        win_button(actions, text="합계조회", command=lambda: self.refresh(summary_only=True),
                   kind="normal").pack(side=tk.LEFT, padx=(0, 8))
        # [2026-09-29] "발행과 엑셀저장 사이에 엑셀발행 버튼을 추가해서,
        # 발행 양식 그대로 엑셀 저장 가능할까" - side=tk.RIGHT로 팩킹되는
        # 순서상, 먼저 패킹된 위젯이 더 오른쪽에 놓이므로, 화면에서
        # [발행] [엑셀발행] [엑셀저장] 순서(왼쪽->오른쪽)가 되도록 반대
        # 순서(엑셀저장 -> 엑셀발행 -> 발행)로 패킹한다.
        # [2026-10-08] 버튼 이름 변경(요청): 발행 -> 출력, 엑셀발행 -> 엑셀저장(발행 양식으로
        # 저장), 엑셀저장 -> 조회엑셀저장(조회 화면 그대로 저장). 기능은 그대로다.
        win_button(actions, text="조회엑셀저장", command=self.export_excel, kind="accent").pack(side=tk.RIGHT, padx=4)
        win_button(actions, text="엑셀저장", command=self.export_print_excel, kind="normal").pack(side=tk.RIGHT, padx=4)
        win_button(actions, text="출력", command=self.print_report, kind="normal").pack(side=tk.RIGHT, padx=4)

        # [2026-09-29] "차이수량 옆에 비고 열 추가" - 발행 양식(종이 원본)에
        # 있던 비고 칸을 화면/엑셀저장/발행 전부에 실제 칼럼으로 추가한다
        # (내용은 항상 빈칸 - 인쇄 후 손으로 메모하는 용도).
        # [2026-09-29] "서가번호가 단, 열 항목 뒤로 가도록" - 위치 항목
        # 순서를 AREA/SECTION/서가번호/단/열 -> AREA/SECTION/단/열/서가번호로
        # 변경(조회화면/엑셀저장/발행 전부 동일하게).
        columns = ("book_name", "isbn", "area", "section", "dan", "yeol", "shelf_no",
                   "ledger_qty", "real_qty", "missing_qty", "exception", "counted_qty", "diff_qty", "remark")
        headings = ("도서명", "바코드", "AREA", "SECTION", "단", "열", "서가번호",
                    "전산재고", "실재고", "누락재고", "예외여부", "실사수량", "차이수량", "비고")
        # [2026-09-23 정정] "SECTION" 헤더가 폭에 밀려 마지막 글자(N)가
        # 잘려 보였다 - 그 컬럼만 폭을 넉넉하게 늘렸다.
        widths = (220, 120, 60, 95, 40, 40, 65, 70, 70, 70, 70, 70, 70, 70)
        container, self.tree = setup_treeview(self, columns, headings, widths, height=20)
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))
        # [2026-09-29] "조회시 도서명, 바코드 항목 내용은 왼쪽정렬하고 한칸
        # 들여쓰기 / 전산재고, 실재고, 누락재고, 실사수량, 차이수량 항목
        # 내용은 우정렬하고 한칸 들여쓰기" - setup_treeview는 모든 칼럼을
        # 기본 가운데 정렬로 두므로, 이 화면만 해당 칼럼들의 정렬을
        # 덮어쓴다. ttk.Treeview는 칼럼에 padding 옵션이 따로 없어(indent를
        # 직접 줄 수 없어), "들여쓰기 한 칸"은 화면에 표시할 값 앞/뒤에
        # 진짜 공백 한 칸을 붙이는 방식으로 흉내낸다(_indent_row 참고 -
        # 엑셀저장/발행에 쓰이는 원본 데이터에는 손대지 않고 화면 표시용
        # 값에만 적용).
        for _col in ("book_name", "isbn"):
            self.tree.column(_col, anchor="w")
        for _col in ("ledger_qty", "real_qty", "missing_qty", "counted_qty", "diff_qty"):
            self.tree.column(_col, anchor="e")
        self.tree.column("exception", anchor="center")  # [2026-10-10] 예외여부(Y/N)
        # [2026-09-28] 소계/합계 줄 강조용 태그. 참고화면의 하늘색(소계)/
        # 연두색(합계) 강조를 흉내낸다.
        # [2026-09-29] "조회화면에서 소계 합계 줄 색상을 소계 회색음영,
        # 합계 좀더 진한 회색음영으로 변경" - 예전 하늘색/연두색 대신
        # 회색 톤 2단계로(합계가 소계보다 더 진하게).
        self.tree.tag_configure("subtotal", background="#EAEAEA", font=("", 9, "bold"))
        self.tree.tag_configure("grandtotal", background="#C9C9C9", font=("", 9, "bold"))
        # [2026-09-29 정정] "소계색이 아직도 분홍색 같은건데?" - 기존 "diff"
        # 태그가 배경색(#F8E3E3, 분홍)을 칠해서 위 회색 배경을 덮어써버리는
        # 게 원인이었다(ttk.Treeview는 같은 항목에 여러 태그가 있으면 뒤에
        # 적용된 태그의 옵션이 우선함) - 배경색 지정 태그는 없앴다.
        # [2026-09-29] "음수는 빨간색으로" 이후 "소계, 합계줄 모든 글자,
        # 숫자가 빨간색으로 나와" - ttk.Treeview는 태그 색을 줄 전체
        # 단위로만 입힐 수 있어(도서명 같은 다른 칸까지 같이 빨개짐) 차이
        # 수량 한 칸만 따로 빨갛게 칠할 수 없었다 - 확인 결과 "빨간색 없이
        # 회색 음영만 유지"로 결정 - 음수 전용 글자색 태그는 두지 않는다.

        # [2026-09-28] 페이지 이동 버튼 - 실적관리 _load_page와 같은 목적
        # (표에는 항상 한 페이지만 그려서 스크롤이 느려지지 않게 한다).
        pager = tk.Frame(self, bg=CL_BG)
        pager.pack(fill=tk.X, padx=8, pady=(4, 8))
        win_button(pager, text="◀◀ 처음", command=lambda: self._load_page(0), kind="normal").pack(side=tk.LEFT)
        win_button(pager, text="◀ 이전", command=lambda: self._load_page(self._view_page - 1),
                   kind="normal").pack(side=tk.LEFT, padx=4)
        self.lbl_page = tk.Label(pager, text="0 / 0 페이지", bg=CL_BG, fg=CL_NAVY, font=("", 10, "bold"))
        self.lbl_page.pack(side=tk.LEFT, padx=12)
        win_button(pager, text="다음 ▶", command=lambda: self._load_page(self._view_page + 1),
                   kind="normal").pack(side=tk.LEFT, padx=4)
        win_button(pager, text="끝 ▶▶", command=lambda: self._load_page(self._view_total_pages - 1),
                   kind="normal").pack(side=tk.LEFT)
        self.lbl_total = tk.Label(pager, text="(총 0개 바코드)", bg=CL_BG, fg=CL_TEXT_DIM)
        self.lbl_total.pack(side=tk.LEFT, padx=12)

    def _on_filter_mode_changed(self, initial=False):
        """조회기준 라디오가 바뀔 때, filter_value_frame 안에서 "입력칸
        하나(e_filter)" 또는 "AREA/SECTION 칸 두 개(filter_area_section_frame)"
        중 지금 모드에 맞는 쪽만 보이게 바꿔 끼운다(실적관리의
        _on_search_mode_changed와 같은 방식). initial=True면(화면을 처음
        만들 때) 위젯만 맞춰두고 조회는 새로 하지 않는다(_build_ui가 이미
        끝나기 전이라 self.tree 등이 아직 없을 수 있음)."""
        mode = self.filter_mode.get()
        if mode == "AREA+SECTION":
            self.e_filter.pack_forget()
            self.filter_area_section_frame.pack(side=tk.LEFT)
        else:
            self.filter_area_section_frame.pack_forget()
            if mode == "전체":
                self.e_filter.pack_forget()
            else:
                self.e_filter.pack(side=tk.LEFT)
        if not initial:
            self.refresh(summary_only=False)

    def _ktag(self):
        t = self.bar.tag()
        return f"_{t}" if t else ""

    def refresh(self, summary_only=None):
        """조회 조건으로 DB를 다시 읽어 self._groups(바코드별 그룹 전체)를
        새로 만들고 첫 페이지를 그린다. summary_only를 넘기면 그 값으로
        [합계조회]/[조회] 상태를 갱신하고, 안 넘기면(라디오 변경 등 특별히
        모드를 바꿀 필요 없는 경우) 지금 상태를 그대로 유지한다."""
        if summary_only is not None:
            self._summary_only = summary_only

        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        merged = self.merge_mode.get() == "합산후"
        threshold_text = self.e_diff.get().strip()
        try:
            threshold = abs(int(threshold_text)) if threshold_text else None
        except ValueError:
            threshold = None

        # [2026-09-29] "AREA합산전 앞에 전체, AREA, SECTION, AREA+SECTION,
        # 서가번호, 바코드, 도서명 선택해서 조회" - 조회기준(filter_mode)과
        # 그 입력값으로 SQL WHERE 조건을 만든다(실적관리 조회 팝업과 같은
        # 방식: AREA/SECTION은 0채움 여부가 데이터마다 다를 수 있어
        # digit_code_variants로 후보를 다 넣은 정확히 일치, 서가번호/바코드/
        # 도서명은 부분검색). AREA/SECTION/AREA+SECTION/서가번호는 위치
        # 정보라 상품마스터(books)에는 없는 값이라, 이 조건이 걸리면
        # "스캔기록이 없는 책"은 애초에 위치가 없으니 결과에서 빠진다
        # (restrict_to_scanned). 바코드/도서명은 상품마스터에도 있는 값이라
        # 그쪽 조회도 같이 걸어서, 스캔기록이 없어도 조건에 맞는 책은 그대로
        # 나온다(기존 동작과 같음).
        filter_mode = self.filter_mode.get()
        counts_where = ""
        counts_params = []
        books_where = ""
        books_params = []
        restrict_to_scanned = False
        if filter_mode == "AREA+SECTION":
            area_kw = self.e_filter_area.get().strip()
            section_kw = self.e_filter_section.get().strip()
            conds = []
            if area_kw:
                variants = digit_code_variants(area_kw, 2)
                conds.append(f"area IN ({','.join('?' for _ in variants)})")
                counts_params += variants
            if section_kw:
                variants = digit_code_variants(section_kw, 3)
                conds.append(f"section IN ({','.join('?' for _ in variants)})")
                counts_params += variants
            if conds:
                counts_where = " AND " + " AND ".join(conds)
                restrict_to_scanned = True
        elif filter_mode in ("AREA", "SECTION"):
            keyword = self.e_filter.get().strip()
            if keyword:
                column = "area" if filter_mode == "AREA" else "section"
                width = 2 if filter_mode == "AREA" else 3
                variants = digit_code_variants(keyword, width)
                counts_where = f" AND {column} IN ({','.join('?' for _ in variants)})"
                counts_params = variants
                restrict_to_scanned = True
        elif filter_mode == "서가번호":
            keyword = self.e_filter.get().strip()
            if keyword:
                counts_where = " AND shelf_no LIKE ?"
                counts_params = [f"%{keyword}%"]
                restrict_to_scanned = True
        elif filter_mode in ("바코드", "도서명"):
            keyword = self.e_filter.get().strip()
            if keyword:
                column = "isbn" if filter_mode == "바코드" else "book_name"
                counts_where = f" AND {column} LIKE ?"
                counts_params = [f"%{keyword}%"]
                books_where = f" AND {column} LIKE ?"
                books_params = [f"%{keyword}%"]

        if not self.bar.ready():
            return
        _sc, _sp = self.bar.sql()
        if _sc:
            counts_where += _sc
            counts_params = list(counts_params) + _sp
            restrict_to_scanned = True  # 구분(범위)을 고르면 위치가 있는(스캔된) 자료만
        elif self.bar.kind() in scope.KINDS:
            restrict_to_scanned = True

        conn = dbmod.get_conn()
        counts = conn.execute(
            f"""SELECT area, section, shelf_no, dan, yeol, isbn, book_name, qty
               FROM stock_counts WHERE store_code=? AND survey_date=?{counts_where}
               ORDER BY isbn, CAST(area AS INTEGER), area, CAST(section AS INTEGER), section, CAST(dan AS INTEGER), dan, CAST(yeol AS INTEGER), yeol, shelf_no""",
            (store_code, date, *counts_params)
        ).fetchall()
        books_map = {
            r["isbn"]: r for r in conn.execute(
                f"SELECT isbn, book_name, rcds_qty, real_qty, missing_qty, kind FROM books WHERE store_code=?{books_where}",
                (store_code, *books_params)
            )
        }
        # [2026-10-08] 전산재고/실재고/누락재고는 장부마스터(ledger_master) 기준.
        # 상품마스터(books)는 PDA용이라 도서명/목록 보강에만 쓴다.
        ledger_map = {
            r["isbn"]: r for r in conn.execute(
                f"SELECT isbn, book_name, rcds_qty, real_qty, missing_qty, except_flag, kind, rcds_x, real_x, missing_x FROM ledger_master WHERE store_code=?{books_where}",
                (store_code, *books_params)
            )
        }
        # [2026-10-10] 예외여부 열: 장부마스터 화면과 같은 규칙(except_flag='Y' 이거나
        # 수동 지정한 exceptions 표에 있으면 Y).
        exc_set = {
            r["isbn"] for r in conn.execute(
                "SELECT isbn FROM exceptions WHERE store_code=? AND survey_date=?", (store_code, date)
            )
        }
        conn.close()
        use_real = self.diff_basis.get() == "real"  # 차이수량 기준: 실사-실재고 / 실사-전산재고(기본)

        # [2026-09-28] 스캔기록이 없어도 상품마스터에 있는 항목은 목록에
        # 나와야 하므로, 스캔된 바코드(counts)뿐 아니라 상품마스터(books_map)
        # 바코드까지 합쳐서 훑는다. [2026-09-29] 단, 위치 기준(AREA류) 조회
        # 조건이 걸려 있으면 위치가 없는(스캔 안 된) 책은 제외한다.
        # [2026-10-13] 문구 마스터는 바코드가 13자리 0채움(0051141931609)인데 스캔값은 앞 0 없이
        # 들어오는 일이 있어(51141931609), 마스터에 같은 바코드(앞 0 무시)가 있으면 그 표기로 합친다.
        _norm_master = {}
        for _k in list(ledger_map) + list(books_map):
            _norm_master.setdefault(norm_barcode(_k), _k)

        def _canon(code):
            if code in ledger_map or code in books_map:
                return code
            return _norm_master.get(norm_barcode(code), code)

        counts_by_isbn = defaultdict(list)
        for r in counts:
            counts_by_isbn[_canon(r["isbn"])].append(r)
        if restrict_to_scanned:
            all_isbns = sorted(counts_by_isbn.keys())
        else:
            # [2026-10-08] 장부마스터 + 수신 실사 바코드만(상품마스터만 있는 바코드는 넣지 않는다).
            all_isbns = sorted(set(ledger_map.keys()) | set(counts_by_isbn.keys()))

        blank = ""
        groups = []
        grand_ledger = grand_real = grand_missing = grand_scanned = grand_diff = 0

        for isbn in all_isbns:
            group = counts_by_isbn.get(isbn, [])
            b = books_map.get(isbn)
            lg = ledger_map.get(isbn)
            ledger_qty = (lg["rcds_qty"] if lg else 0) or 0
            real_qty = (lg["real_qty"] if lg else 0) or 0
            missing_qty = (lg["missing_qty"] if lg else 0) or 0
            scanned_total = sum((r["qty"] or 0) for r in group)
            # [2026-10-08] 장부마스터 전산재고 0 + 실재고 0 + 수신 실사수량 0, 셋 다 0이면 목록에서 제외.
            if ledger_qty == 0 and real_qty == 0 and scanned_total == 0:
                continue
            # [2026-10-10] 차이수량 기준 선택: 기본 실사수량-전산재고, 선택 시 실사수량-실재고.
            diff_qty = scanned_total - (real_qty if use_real else ledger_qty)
            is_exc = disp_exc(lg["except_flag"] if lg is not None else "N", isbn in exc_set)
            if threshold is not None and abs(diff_qty) < threshold:
                continue

            # [2026-10-16] 도서명은 장부마스터 기준, 장부에 없으면 상품마스터로 보충, 둘 다 없으면 스캔 때 저장된 이름.
            master_name = (lg["book_name"] if lg and lg["book_name"] else None) or (b["book_name"] if b and b["book_name"] else None)
            book_name = master_name or (group[0]["book_name"] if group else "")

            detail_rows = []
            if group:
                # 위치별 상세 줄: 실사수량만 채우고 전산재고류는 빈칸.
                for r in group:
                    area = normalize_area(r["area"], merged=merged)
                    detail_rows.append((master_name or r["book_name"], isbn, area, r["section"], r["dan"], r["yeol"], r["shelf_no"],
                                         blank, blank, blank, blank, r["qty"], blank, blank))
            else:
                # 스캔기록이 아예 없는 상품마스터 항목: 도서명/바코드만 채운
                # 헤더 줄 하나만 두고, 바로 소계 줄(실사수량 0)로 이어진다.
                detail_rows.append((book_name, isbn, blank, blank, blank, blank, blank,
                                     blank, blank, blank, blank, blank, blank, blank))

            # [2026-09-28] "합계조회만 눌렀을땐 소계대신 바코드에 맞는
            # 도서명을 보여줘" - 상세 줄이 안 보이는 [합계조회] 모드에서는
            # 소계 줄만 남으므로, 그 줄이 어느 바코드의 소계인지 한눈에
            # 보이게 첫 칸을 "소  계" 대신 도서명으로 채운다. 상세 모드에서는
            # 바로 위에 위치별 줄들이 있어 어느 책인지 알 수 있으니 그대로
            # "소  계"를 쓴다.
            subtotal_label = book_name if self._summary_only else "소  계"
            subtotal_row = (subtotal_label, isbn, blank, blank, blank, blank, blank,
                             (disp_qty(ledger_qty, lg["rcds_x"]) if lg else ledger_qty),
                             (disp_qty(real_qty, lg["real_x"]) if lg else real_qty),
                             (disp_qty(missing_qty, lg["missing_x"]) if lg else missing_qty),
                             is_exc, scanned_total, diff_qty, blank)

            groups.append({
                "isbn": isbn,
                "detail_rows": detail_rows,
                "subtotal_row": subtotal_row,
                "diff_qty": diff_qty,
            })

            grand_ledger += ledger_qty
            grand_real += real_qty
            grand_missing += missing_qty
            grand_scanned += scanned_total
            grand_diff += diff_qty

        self._groups = groups
        self._grand = (grand_ledger, grand_real, grand_missing, grand_scanned, grand_diff)
        self._view_total_pages = max(1, (len(groups) + GROUP_PAGE_SIZE - 1) // GROUP_PAGE_SIZE)
        self._load_page(0)

    def _build_full_rows(self):
        """엑셀저장/발행용 - 지금 조회된 전체(페이지 제한 없이)를 지금
        모드([합계조회]면 소계+합계만, 아니면 상세까지) 그대로 한 번에
        만든다."""
        blank = ""
        rows = []
        for g in self._groups:
            if not self._summary_only:
                rows.extend(g["detail_rows"])
            rows.append(g["subtotal_row"])
        if self._groups:
            ledger, real, missing, scanned, diff = self._grand
            rows.append(("합  계", blank, blank, blank, blank, blank, blank,
                         ledger, real, missing, blank, scanned, diff, blank))
        return rows

    def _load_page(self, page):
        """표에 page번째 페이지(0부터 시작, 바코드 GROUP_PAGE_SIZE개 단위)만
        새로 그린다 - 실적관리의 _load_page와 같은 목적."""
        if self._view_total_pages <= 0:
            page = 0
        else:
            page = max(0, min(page, self._view_total_pages - 1))
        self._view_page = page

        self.tree.delete(*self.tree.get_children())
        start = page * GROUP_PAGE_SIZE
        chunk = self._groups[start:start + GROUP_PAGE_SIZE]

        # [2026-09-29] "소계 윗선에 선을 주지말고 소계 아랫선에 선을 줘" -
        # 소계 줄 바로 "아래"에만 가로 구분선을 그린다(윗선은 없음). 각
        # 소계 줄을 넣을 때 그 item id를 모아뒀다가, 한 페이지를 다 그린
        # 뒤에 setup_treeview()가 만들어준 set_bottom_border_items()로
        # 한꺼번에 넘겨준다.
        subtotal_item_ids = []

        # [2026-09-29] "합계조회후 조회하거나 발행할땐 목록 내용 음영을
        # 없애주고 아랫면 선도 안긋도록" - [합계조회] 모드에서는 상세줄 없이
        # 바코드(도서)당 한 줄만 나오는데, 이 줄은 원래 "소계" 역할이라
        # 회색 음영(tags=("subtotal",))과 아랫선이 그대로 붙어 있었다.
        # [합계조회] 모드에서는 그 한 줄 한 줄이 그냥 "목록의 한 행"이므로
        # 음영도, 아랫선도 주지 않고 일반 줄(홀/짝 교대)처럼 그린다.
        i = 0
        for g in chunk:
            if not self._summary_only:
                for row in g["detail_rows"]:
                    i += 1
                    self.tree.insert("", tk.END, values=_indent_row(row), tags=("odd",) if i % 2 == 0 else ())
                subtotal_item_ids.append(
                    self.tree.insert("", tk.END, values=_indent_row(g["subtotal_row"]), tags=("subtotal",))
                )
            else:
                i += 1
                self.tree.insert("", tk.END, values=_indent_row(g["subtotal_row"]),
                                  tags=("odd",) if i % 2 == 0 else ())

        is_last_page = (page >= self._view_total_pages - 1)
        if is_last_page and self._groups:
            blank = ""
            ledger, real, missing, scanned, diff = self._grand
            total_row = ("합  계", blank, blank, blank, blank, blank, blank,
                         ledger, real, missing, blank, scanned, diff, blank)
            self.tree.insert("", tk.END, values=_indent_row(total_row), tags=("grandtotal",))

        if hasattr(self.tree, "set_bottom_border_items"):
            self.tree.set_bottom_border_items(subtotal_item_ids)

        total_groups = len(self._groups)
        total_pages = self._view_total_pages if total_groups else 0
        shown_page = (page + 1) if total_groups else 0
        self.lbl_page.config(text=f"{shown_page} / {total_pages} 페이지")
        self.lbl_total.config(text=f"(총 {total_groups:,}개 바코드)")

    def export_excel(self):
        rows = self._build_full_rows()
        if not rows:
            messagebox.showinfo("알림", "저장할 데이터가 없습니다.")
            return
        headers = ("도서명", "바코드", "AREA", "SECTION", "단", "열", "서가번호",
                  "전산재고", "실재고", "누락재고", "예외여부", "실사수량", "차이수량", "비고")
        # [2026-09-28] "조회와 합계조회의 엑셀저장 파일명이 똑같아서 그런거
        # 같은데?" - 맞다. [조회]로 한 번 저장한 뒤 그 파일을 열어둔 채로
        # [합계조회]로 다시 저장하면, 기본 파일명(initialfile)이 똑같아서
        # 그대로 저장을 누르면 윈도우가 "이미 열려있는 같은 파일"에 덮어쓰려다
        # Permission denied가 났던 것. 모드별로 기본 파일명을 다르게 줘서
        # 이런 충돌 가능성을 줄인다(그래도 같은 이름으로 두 번 저장하면
        # 여전히 열려있는 파일과 충돌할 수 있다 - 그건 앞서 고친 안내
        # 메시지가 잡아준다).
        mode_tag = "_합계" if self._summary_only else ""
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 파일", "*.xlsx")],
            initialfile=f"재고조사차이내역{self._ktag()}{mode_tag}_{file_date(self.app)}.xlsx",
        )
        if not path:
            return

        # [2026-09-28] "엑셀저장할때 오래걸려도 진행률 다이얼로그가 안뜨는데?" -
        # 행이 많으면(=시간이 걸릴 만하면) 백그라운드 스레드 + ZZOINT와 같은
        # 진행률 팝업(run_with_progress)으로 저장한다. 적으면 예전처럼 바로
        # 저장(깜빡임 방지).
        if len(rows) < PROGRESS_ROW_THRESHOLD:
            try:
                _write_diff_detail_workbook(path, rows, headers, summary_only=self._summary_only)
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
            _write_diff_detail_workbook(path, rows, headers, progress=progress, summary_only=self._summary_only)
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

        # [2026-09-28] "진행률 다이얼로그에 X표시를 눌러도 취소도 불가" -
        # cancelable=False로 두면 [취소] 버튼도 없고 X(창닫기)도 일부러 막아둬서
        # (progress_dialog.py 참고 - 작업 도중 끊기지 않게 하려는 의도) 정말로
        # 빠져나갈 방법이 없었다. 저장이 오래 걸릴 수 있는 화면이니
        # cancelable=True로 바꿔 [취소] 버튼(과 그 버튼에 연결된 ESC)으로
        # 빠져나갈 수 있게 한다.
        run_with_progress(self, "엑셀로 저장하는 중", work, on_done, cancelable=True)

    def export_print_excel(self):
        """[엑셀발행] 버튼: [2026-09-29] "발행과 엑셀저장 사이에 엑셀발행
        버튼을 추가해서, 발행 양식 그대로 엑셀 저장 가능할까" - [발행]은
        임시 파일을 만들어 곧바로 인쇄 대화상자로 넘기고, [엑셀저장]은
        report_header 없이 표만 있는 단순한 서식으로 저장한다 - 이 버튼은
        그 사이: [발행]과 똑같은 서식(report_header 포함 - 기업명/점포코드/
        점포명/차이수량 조건/검수자/조사일자/출력일자 정보블록 + 페이지
        머리글/바닥글)으로, [엑셀저장]처럼 저장 위치를 물어 실제 .xlsx
        파일로 남긴다(직접 열어서 셀 위치/서식을 손으로 마저 조정하고
        싶을 때 사용)."""
        rows = self._build_full_rows()
        if not rows:
            messagebox.showinfo("알림", "저장할 데이터가 없습니다.")
            return
        headers = ("도서명", "바코드", "AREA", "SECTION", "단", "열", "서가번호",
                  "전산재고", "실재고", "누락재고", "예외여부", "실사수량", "차이수량", "비고")
        report_header = {
            "store_code": self.app.state.store_code,
            "store_name": self.app.state.store_name,
            "survey_date": self.app.state.survey_date,
            "threshold_text": self.e_diff.get().strip(),
        }
        mode_tag = "_합계" if self._summary_only else ""
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 파일", "*.xlsx")],
            initialfile=f"재고조사차이내역_발행양식{self._ktag()}{mode_tag}_{file_date(self.app)}.xlsx",
        )
        if not path:
            return

        if len(rows) < PROGRESS_ROW_THRESHOLD:
            try:
                _write_diff_detail_workbook(path, rows, headers, report_header=report_header, summary_only=self._summary_only)
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
            _write_diff_detail_workbook(path, rows, headers, progress=progress, report_header=report_header, summary_only=self._summary_only)
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
        """[발행] 버튼: [2026-09-28] "발행버튼을 누르면 왜 엑셀저장이 뜨냐" -
        저장 위치를 묻는 export_rows_to_excel() 대신 조용히 임시 파일을
        만든다. [2026-09-28 재수정] "인쇄전 설정창같은게 하나 뜨잖아?
        그렇게 해줘" -> "ZZOINT 참고해서 인쇄 대화상자 똑같이" - 프린터/매수를
        고를 수 있는 진짜 윈도우 인쇄 대화상자(print_excel_file)로 이어진다.
        [2026-09-28 추가] 엑셀저장과 같은 서식(_write_diff_detail_workbook)을
        그대로 써서 인쇄물도 화면/엑셀저장과 똑같은 디자인으로 나온다."""
        rows = self._build_full_rows()
        if not rows:
            messagebox.showinfo("알림", "인쇄할 데이터가 없습니다.")
            return
        headers = ("도서명", "바코드", "AREA", "SECTION", "단", "열", "서가번호",
                  "전산재고", "실재고", "누락재고", "예외여부", "실사수량", "차이수량", "비고")
        import os
        import tempfile
        from datetime import datetime as _dt
        tmp_dir = os.path.join(tempfile.gettempdir(), "kointbook_print")
        os.makedirs(tmp_dir, exist_ok=True)
        path = os.path.join(tmp_dir, f"{_dt.now().strftime('%Y%m%d_%H%M%S_%f')}_재고조사차이내역_{file_date(self.app)}.xlsx")

        # [2026-09-29] "발행시 이 양식으로 출력, 페이지마다 상단/헤더는
        # 고정, 페이지수는 변동값, 하단 (주)코인트써비스도 고정" - [발행]에서
        # 만드는 파일에만 report_header를 넘겨서, 정보 블록(기업명/점포코드/
        # 점포명/차이수량 조건/검수자/조사일자/출력일자) + 페이지마다 반복되는
        # 머리글/바닥글이 붙게 한다([엑셀저장]은 예전처럼 표만 있는 단순한
        # 파일 그대로 유지 - 화면에 안 보여주고 요청도 없었던 부분까지
        # 바꾸지 않는다).
        report_header = {
            "store_code": self.app.state.store_code,
            "store_name": self.app.state.store_name,
            "survey_date": self.app.state.survey_date,
            "threshold_text": self.e_diff.get().strip(),
        }

        # [2026-09-28] 엑셀저장과 같은 이유로, 행이 많은 인쇄물도 파일을
        # 만드는 동안(인쇄 대화상자가 뜨기 전) 진행률 팝업을 보여준다.
        if len(rows) < PROGRESS_ROW_THRESHOLD:
            try:
                _write_diff_detail_workbook(path, rows, headers, report_header=report_header, summary_only=self._summary_only)
            except ImportError:
                path = print_rows_to_excel(rows, headers, default_name=f"재고조사차이내역{self._ktag()}_{file_date(self.app)}.xlsx")
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
                _write_diff_detail_workbook(path, rows, headers, progress=progress, report_header=report_header, summary_only=self._summary_only)
                return path
            except ImportError:
                return print_rows_to_excel(rows, headers, default_name=f"재고조사차이내역{self._ktag()}_{file_date(self.app)}.xlsx")

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

        # [취소] 버튼/ESC로 중간에 빠져나올 수 있게 (엑셀저장과 같은 이유).

        run_with_progress(self, "인쇄 파일을 만드는 중", work, on_done, cancelable=True)
