# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
[자료생성]과 [AREA별 합산] 화면이 공통으로 쓰는 "자료 생성" 로직.

실제로 받은 결과물 샘플(도서납품데이터 TXT 폴더의 kyobo_data1.txt/
kyobo_data2.txt + 인천_결과확인리스트(20251017).xlsx + 인천_서가별
스캔데이터(20251017).xlsx)을 각 버튼과 하나씩 대응시켜서 다시 맞췄다.

[2026-10-13 개정] 서적/문구 분리 + 샘플 양식 재확인 (아래 옛 설명보다 이 블록이 우선)
  스캔 행이 문구 상품마스터(books.kind='문구')에 있으면 문구, 아니면 서적(미등록 포함)으로 본다.
  ── 서적 ──
   kyobo_data1.txt : 서가번호(11, [2026-10-16] 입력이 11자리를 넘으면 최대 20자리 그대로)+바코드(13)=24자~, (서가번호,바코드) 조합당 1줄(중복 제거), 정렬, CRLF
   kyobo_data2.txt : 바코드(13)+수량(5, 0채움)=18자, 바코드별 합계 1줄, 바코드순, CRLF
                     (이전 버전은 두 파일의 정의가 서로 바뀌어 있었다 - 받은 샘플 기준으로 바로잡음)
   서가번호(11) = 점포3+AREA2+SECTION3+3자리: PDA에 입력한 서가번호(11~20자리)를 그대로 쓴다
   결과확인리스트.xlsx / 서가별스캔데이터.xlsx (서적 행만)
  ── 문구 ── (UTF-8 텍스트, CRLF, 헤더 없음)
   납품로케이션데이터 : `위치,바코드,수량` - 위치 = AREA+SECTION(예 101), (위치,바코드)별 수량 합계
   납품상세데이터    : `조사일자,납품처(514),바코드,수량,구분코드(402),단가+종류코드(502)+위치,
                        페이지,줄번호,상품명` - 스캔 1건당 1줄. 구분코드/단가/종류코드는 문구
                        상품마스터(cmdt_dvsn_code/sale_unpr/cmdt_code_kind_code) 값.
                        페이지 = 한 위치 안에서 (서가번호,단,열)이 같은 스캔 묶음, 줄번호는 페이지마다 1부터.
   위치코드 = AREA 2자리 + SECTION 3자리 = 5자리 (예 01+001 -> 01001)
   납품처(514 등) = 문구 상품마스터 파일의 rdp_code 값 그대로
 ── 공통 ── 자료생성으로 나가는 모든 바코드는 13자리(앞 0 채움)로 통일 (마스터 파일 0000000000001, 스캔 1)

  (옛 설명) 자료①,②생성      : ① kyobo_data1.txt - 바코드별 전체 스캔수량 집계, 위치
                       정보 없이 "바코드(13)+수량(6, 0채움)"만 있는 19자리
                       고정폭 텍스트(줄바꿈 CRLF, 헤더 없음) - 아마 KYOBO
                       본사 시스템에 그대로 넘기는 EDI 피드
                     ② kyobo_data2.txt - 스캔된 (위치,바코드) 조합마다 한 줄,
                       "서가번호+바코드(13)" 텍스트(수량은 빠짐 - 위치 확인용).
                       받은 샘플에서는 서가번호가 11자리(전체 24자리)였지만,
                       서가번호 자체가 점포별로 임의 배정되는 값이라 이
                       자릿수가 항상 고정된다는 보장은 없다(28번 줄 참고)
  ③ 단품 리스트생성  : "결과확인리스트" - 상품마스터의 전체 품목(스캔 여부
                       상관없이 전부) + 이번 조사의 스캔재고/차이를 더한
                       비교표. 컬럼: 바코드,도서명,분야,출판사,전산재고,
                       실재고,누락재고,예외여부,스캔재고,차이
                       (차이 = 스캔재고 - 전산재고)
  ④ 서가별 생성      : "서가별스캔데이터" - 스캔 1건당 1행(집계하지 않음).
                       컬럼: 바코드,도서명,분야,출판사,서가번호,실사수량
  자료생성(미등록)   : 상품마스터에 없는(미등록) 바코드만 모은 리스트
  합산자료(AREA)     : AREA별 건수/수량 합계표 (AREA별 합산 화면의 결과와 동일)

[2026-09-23 현장 확인] "서가번호"는 정해진 자릿수 공식이 없다 - 점포에서
구역(AREA/SECTION)별로 임의로 매겨놓은 번호일 뿐이다. 표본 파일을 자릿수
통계로 분석해서 "점포코드3+AREA2+SECTION2+서가번호2+단1+열1=11자리"라는
공식을 유추했던 것은 틀린 접근이었다. 확인된 규칙은 AREA가 항상 숫자
2자리(01,02,11,12...)라는 것 뿐이라, location_code()는 AREA만 2자리로
맞추고 나머지(SECTION/서가번호/단/열)는 입력된 값을 그대로 이어붙인다 -
임의로 자리수를 자르거나 늘리지 않는다(값을 잘라내면 실제 배정된 번호가
훼손될 수 있기 때문). KOINTBOOK DB에는 이 "서가번호" 원본 코드 자체를 저장하는
필드가 없어서(PDA/매대등록에서 AREA/SECTION/서가번호/단/열로 이미 나눠 받음)
이어붙인 값이 RBSKOREA가 실제로 쓰는 서가번호와 자릿수까지 완전히 같다는
보장은 없다 - RBSKOREA에서 원본 서가번호 값을 그대로 내려주면(또는 매대
등록 화면에서 직접 입력받으면) 계산 대신 그 값을 그대로 쓰는 것이 가장
정확하다.
"""

import re
from pathlib import Path
from . import db as dbmod
from .ui_common import file_date, normalize_area, short_store_label, write_text_lines_file, eof_crlf_enabled, split_scan_datetime
from .masters import norm_barcode, bc13, disp_qty, disp_exc
from . import scope


def output_dir(app, kind=None):
    """생성 폴더. kind가 '서적'/'문구'면 그 아래 '서적전용'/'문구전용' 하위 폴더."""
    date = file_date(app)
    store_name = app.state.store_name or "매장"
    safe_name = re.sub(r'[\\/:*?"<>|]', "", store_name).strip() or "매장"
    out_dir = Path("C:/KOINTBOOK") / f"{date}_{safe_name}"
    if kind in scope.KINDS:
        out_dir = out_dir / scope.tag(kind)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _digits_only(s, width, fallback="0"):
    """문자/숫자가 섞인 코드(예: 데모용 점포코드 "KYOBO01")에서 숫자만 뽑아
    width 자리로 맞춘다 - 실제 운영 점포코드("025")는 원래부터 숫자뿐이라
    그대로 통과한다."""
    digits = "".join(ch for ch in str(s or "") if ch.isdigit()) or fallback
    return digits[-width:].zfill(width)


def _raw_field(value):
    """SECTION/서가번호/단/열처럼 정해진 자릿수 공식이 없는 값은 자르거나
    늘리지 않고 입력된 그대로(앞뒤 공백만 제거) 쓴다."""
    return str(value).strip() if value is not None else ""


def location_code(store_code, area, section, shelf_no, dan, yeol):
    """서가별스캔데이터/kyobo_data2.txt의 "서가번호" 코드을 만든다.
    store(3자리, 숫자만) + AREA(2자리, 숫자만 - 확인된 유일한 고정 규칙) +
    SECTION + 서가번호 + 단 + 열(각 필드는 입력된 값 그대로 이어붙임, 자리수
    공식 없음 - 모듈 docstring 참고)."""
    return (
        _digits_only(store_code, 3)
        + normalize_area(area, merged=True)
        + _raw_field(section)
        + _raw_field(shelf_no)
        + _raw_field(dan)
        + _raw_field(yeol)
    )


def _fetch_counts(store_code, date):
    conn = dbmod.get_conn()
    rows = conn.execute(
        """SELECT id, survey_date, store_code, area, section, shelf_no, dan, yeol, isbn, book_name, qty,
                  worker_code, worker_name, received_at
           FROM stock_counts WHERE store_code=? AND survey_date=?
           ORDER BY CAST(area AS INTEGER), area, CAST(section AS INTEGER), section, CAST(dan AS INTEGER), dan, CAST(yeol AS INTEGER), yeol, shelf_no, id""",
        (store_code, date)
    ).fetchall()
    conn.close()
    return rows


def _fetch_books_map(store_code):
    conn = dbmod.get_conn()
    rows = conn.execute(
        "SELECT isbn, book_name, category, publisher, rcds_qty, real_qty, missing_qty, except_flag, kind, rcds_x, real_x, missing_x "
        "FROM books WHERE store_code=?",
        (store_code,)
    ).fetchall()
    conn.close()
    return {r["isbn"]: r for r in rows}


def _fetch_ledger_map(store_code):
    """[2026-10-08] 장부마스터(ledger_master) - 전산재고가 필요한 PC 쪽 화면/엑셀의 기준."""
    conn = dbmod.get_conn()
    rows = conn.execute(
        "SELECT isbn, book_name, category, publisher, rcds_qty, real_qty, missing_qty, except_flag, kind, rcds_x, real_x, missing_x "
        "FROM ledger_master WHERE store_code=?",
        (store_code,)
    ).fetchall()
    conn.close()
    return {r["isbn"]: r for r in rows}


def raw_rows(app, kind="전체"):
    """실사원자료: stock_counts를 그대로 (엑셀저장/재집계 그리드용 - 자료①,
    ②생성 버튼과는 별개다. 그 버튼은 아래 kyobo_data*_lines()를 쓴다).
    kind가 '서적'/'문구'면 그 구분 행만 (구분 기준은 split_counts 참고)."""
    if kind in scope.KINDS:
        b, s, _m = split_counts(app)
        rows = s if kind == "문구" else b
    else:
        rows = _fetch_counts(app.state.store_code, app.state.survey_date)
    # [2026-10-15] 조사일자 열은 뺐다(조회 기준일 뿐). 스캔한 일시는 실사일자/실사시간 두 열로 나눠 보여준다.
    headers = ("점포코드", "바코드", "상품명", "조사수량", "AREA", "SECTION", "서가번호", "단", "열",
               "작업자코드", "작업자명", "실사일자", "실사시간")
    data = [(r["store_code"], r["isbn"], r["book_name"], r["qty"], r["area"], r["section"], r["shelf_no"],
             r["dan"], r["yeol"], r["worker_code"], r["worker_name"],
             *split_scan_datetime(r["received_at"], r["survey_date"]))
            for r in rows]
    return headers, data


# [2026-10-08] AREA별 합산 화면이 엑셀로 불러온 행에만 붙는 표식(PC 수신/PDA 자료와 구분).
AREA_SRC_PREFIX = "합산:"


def _norm_area_code(v):
    s = str(v if v is not None else "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(2) if s.isdigit() else s


def _received_at_from_row(g, r):
    """합산자료 한 줄의 스캔 일시를 "YYYY-MM-DD HH:MM:SS"로 돌려준다. 예전 파일은 "실사일시" 한 열,
    새 파일(2026-10-15~)은 "실사일자"(YYYYMMDD) + "실사시간"(HH:MM:SS) 두 열이다."""
    old = str(g(r, "실사일시") or "").strip()
    if old:
        return old
    d = str(g(r, "실사일자") or "").strip()
    t = str(g(r, "실사시간") or "").strip()
    if d.isdigit() and len(d) == 8 and (g(r, "실사시간") is not None):
        return f"{d[:4]}-{d[4:6]}-{d[6:8]} {t or '00:00:00'}"
    return ""


def read_area_file(path):
    """[2026-10-08] 합산자료(AREA) 파일(자료생성 화면의 실사내역 전체를 저장한 엑셀)을
    읽어 dict 목록으로 돌려준다. 열 위치가 아니라 머리글 이름으로 찾는다."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    head = next(it, None)
    if not head:
        wb.close()
        raise ValueError("빈 파일입니다.")
    idx = {str(h).strip(): i for i, h in enumerate(head) if h is not None}
    need = ("AREA", "SECTION", "바코드", "조사수량")
    miss = [n for n in need if n not in idx]
    if miss:
        wb.close()
        raise ValueError("합산자료(AREA) 파일 형식이 아닙니다. 없는 열: " + ", ".join(miss))

    def g(r, name):
        i = idx.get(name)
        return r[i] if i is not None and i < len(r) else None

    out = []
    for r in it:
        if r is None or all(c is None or str(c).strip() == "" for c in r):
            continue
        isbn = str(g(r, "바코드") or "").strip()
        if isbn.endswith(".0"):
            isbn = isbn[:-2]
        if not isbn:
            continue
        try:
            qty = int(float(g(r, "조사수량") or 0))
        except (TypeError, ValueError):
            qty = 0
        out.append({
            "area": _norm_area_code(g(r, "AREA")),
            "section": str(g(r, "SECTION") or "").strip(),
            "shelf_no": str(g(r, "서가번호") or "").strip(),
            "dan": str(g(r, "단") or "").strip(),
            "yeol": str(g(r, "열") or "").strip(),
            "isbn": isbn,
            "book_name": str(g(r, "상품명") or ""),
            "qty": qty,
            "worker_code": str(g(r, "작업자코드") or ""),
            "worker_name": str(g(r, "작업자명") or ""),
            "received_at": _received_at_from_row(g, r),
        })
    wb.close()
    return out


def import_area_file(store_code, store_name, survey_date, path, areas):
    """합산자료(AREA) 파일에서 선택한 AREA의 행만 stock_counts에 넣는다.
    같은 파일명을 다시 불러오면 이전에 그 파일로 들어온 행을 먼저 지우고
    다시 넣는다(중복 누적 방지). 점포코드/실사일자는 PC 기준값으로 저장.
    반환: (넣은 건수, 선택 AREA가 아니라 건너뛴 건수, 파일 안의 AREA 집합)"""
    import os
    rows = read_area_file(path)
    fname = AREA_SRC_PREFIX + os.path.basename(path)
    want = {_norm_area_code(a) for a in areas}
    in_file = {r["area"] for r in rows}
    pick = [r for r in rows if r["area"] in want]
    conn = dbmod.get_conn()
    conn.execute("DELETE FROM stock_counts WHERE store_code=? AND survey_date=? AND source_file=?",
                 (store_code, survey_date, fname))
    conn.executemany(
        "INSERT INTO stock_counts(store_code, store_name, survey_date, area, section, shelf_no, dan, yeol, "
        "isbn, book_name, qty, worker_code, worker_name, received_at, source_file) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(store_code, store_name, survey_date, r["area"], r["section"], r["shelf_no"], r["dan"], r["yeol"],
          r["isbn"], r["book_name"], r["qty"], r["worker_code"], r["worker_name"], r["received_at"], fname)
         for r in pick])
    conn.commit()
    conn.close()
    dbmod.bump_stock_version()
    return len(pick), len(rows) - len(pick), in_file


def area_summary_rows(app, merged=True):
    """합산자료(AREA): AREA별 건수/수량 집계."""
    rows = _fetch_counts(app.state.store_code, app.state.survey_date)
    totals = {}
    for r in rows:
        area = normalize_area(r["area"], merged=merged) or "(미지정)"
        t = totals.setdefault(area, {"count": 0, "qty": 0})
        t["count"] += 1
        t["qty"] += r["qty"] or 0
    headers = ("AREA", "건수", "수량")
    data = [(area, t["count"], t["qty"]) for area, t in sorted(totals.items())]
    return headers, data


# ---- 서적/문구 구분 -------------------------------------------------------------------

def _stat_map(store_code):
    """문구 상품마스터: 정규화 바코드 -> (이름, 단가, 구분코드, 종류코드)."""
    conn = dbmod.get_conn()
    try:
        rows = conn.execute(
            "SELECT isbn, book_name, price, dvsn_code, kind_code, rdp_code FROM books WHERE store_code=? AND kind='문구'",
            (store_code,)).fetchall()
    finally:
        conn.close()
    return {norm_barcode(r["isbn"]): (r["book_name"] or "", r["price"] or 0, r["dvsn_code"] or "",
                                      r["kind_code"] or "", r["rdp_code"] or "")
            for r in rows}


def split_counts(app):
    """이번 조사의 스캔 행을 (서적 행들, 문구 행들, 문구맵)으로 나눈다.
    AREA 번호 기준(scope.py: 문구 20~29·80~89, 그 밖은 서적)으로 나눈다."""
    store_code = app.state.store_code
    stat = _stat_map(store_code)
    book_rows, stat_rows = [], []
    for r in _fetch_counts(store_code, app.state.survey_date):
        is_stat = scope.classify(r["area"], r["section"]) == "문구"
        (stat_rows if is_stat else book_rows).append(r)
    return book_rows, stat_rows, stat


def missing_stat_master(stat_rows, stat):
    """문구로 분류됐지만 문구 상품마스터에 없는 바코드 수(납품상세의 단가·코드를 채울 수 없음)."""
    return len({norm_barcode(r["isbn"]) for r in stat_rows if norm_barcode(r["isbn"]) not in stat})


def summary(app):
    """자료생성 화면 미리보기: 구분별 (스캔 줄 수, 바코드 종류 수, 수량 합)."""
    book_rows, stat_rows, stat = split_counts(app)

    def calc(rows):
        codes = {norm_barcode(r["isbn"]) for r in rows if str(r["isbn"] or "").strip()}
        return len(rows), len(codes), sum((r["qty"] or 0) for r in rows)
    return {"서적": calc(book_rows), "문구": calc(stat_rows), "문구마스터": len(stat)}


SHELF_NO_MAX_LEN = 20   # PDA/PC 서가번호 최대 자릿수 ([2026-10-16] 예전 11자리 -> 20자리 이하)


def shelf_code(r, store_code):
    """서가번호. PDA/PC에서 입력한 서가번호가 숫자 11자리 이상(최대 20자리)이면 입력한 그대로 쓴다
    ([2026-10-16] 예전에는 12자리 이상이면 뒤 11자리만 잘라 썼다).
    그보다 짧은 값(옛 자료·짧은 값)은 점포3+AREA2+SECTION3 뒤에 입력값을 3자리로 맞춰 붙여 11자리로 만든다."""
    raw = _raw_field(r["shelf_no"])
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 11:
        return digits[-SHELF_NO_MAX_LEN:]
    sec = "".join(ch for ch in _raw_field(r["section"]) if ch.isdigit())[-3:].zfill(3)
    return (_digits_only(store_code, 3) + normalize_area(r["area"], merged=True) + sec + digits[-3:].zfill(3))[:11]


def nonzero_rows(rows):
    """[2026-10-16] 실사수량 0인 스캔 줄은 txt(kyobo_data1·2, 납품로케이션·상세)와 스캔리스트(서가별스캔데이터,
    로케이션별스캔리스트)에서 뺀다. 결과확인리스트는 이 함수를 쓰지 않고 그대로 둔다(사용자 지시)."""
    return [r for r in rows if (r["qty"] or 0) != 0]


def kyobo_data1_lines(app, rows=None):
    """자료① (kyobo_data1.txt): 서가번호(11자리, 입력이 11자리를 넘으면 그 자리수 그대로 최대 20)+바코드(13), (서가번호,바코드)당 1줄, 정렬."""
    if rows is None:
        rows = split_counts(app)[0]
    store_code = app.state.store_code
    pairs = set()
    for r in nonzero_rows(rows):
        isbn = str(r["isbn"] or "").strip()
        if not isbn:
            continue
        pairs.add(f"{shelf_code(r, store_code)}{isbn.rjust(13, '0')[-13:]}")
    return sorted(pairs)


def kyobo_data2_lines(app, rows=None):
    """자료② (kyobo_data2.txt): 바코드(13)+수량(5, 0채움)=18자, 바코드별 합계 1줄, 바코드순."""
    if rows is None:
        rows = split_counts(app)[0]
    totals = {}
    for r in nonzero_rows(rows):
        isbn = str(r["isbn"] or "").strip()
        if not isbn:
            continue
        k = isbn.rjust(13, "0")[-13:]
        totals[k] = totals.get(k, 0) + (r["qty"] or 0)
    return [f"{k}{min(max(q, 0), 99999):05d}" for k, q in sorted(totals.items()) if q != 0]


# ---- 문구 납품 자료 -----------------------------------------------------------------------

def stat_location(area, section):
    """문구 위치코드 = AREA 2자리 + SECTION 3자리 (5자리, 앞 0 채움). 예: 01 + 001 -> 01001"""
    def part(v, w):
        d = "".join(ch for ch in _raw_field(v) if ch.isdigit())
        return d[-w:].zfill(w)
    return part(area, 2) + part(section, 3)


def _loc_sort_key(loc):
    return (int(loc) if loc.isdigit() else 10 ** 12, loc)


STAT_LOC_HEADERS = ("위치", "바코드", "수량")
STAT_DET_HEADERS = ("조사일자", "납품처", "바코드", "수량", "구분코드", "단가+종류코드+위치", "페이지", "줄번호", "상품명")


def stat_location_rows(app, stat_rows=None):
    """납품로케이션데이터: (위치, 바코드, 수량) - (위치,바코드)별 수량 합계."""
    if stat_rows is None:
        stat_rows = split_counts(app)[1]
    tot = {}
    for r in nonzero_rows(stat_rows):
        isbn = str(r["isbn"] or "").strip()
        if not isbn:
            continue
        k = (stat_location(r["area"], r["section"]), bc13(isbn))
        tot[k] = tot.get(k, 0) + (r["qty"] or 0)
    return [(loc, isbn, q) for (loc, isbn), q in sorted(tot.items(), key=lambda kv: (_loc_sort_key(kv[0][0]), kv[0][1])) if q != 0]


def stat_location_lines(app, stat_rows=None):
    """납품로케이션데이터 txt: `위치,바코드,수량`."""
    return [f"{loc},{isbn},{q}" for loc, isbn, q in stat_location_rows(app, stat_rows)]


def _clean_text(s):
    return str(s or "").replace(",", " ").replace("\r", " ").replace("\n", " ").strip()


def stat_detail_rows(app, stat_rows=None, stat=None):
    """납품상세데이터: 스캔 1건당 1행.
    (조사일자, 납품처, 바코드, 수량, 구분코드, 단가+종류코드+위치, 페이지, 줄번호, 상품명)
    조사일자 칸은 항상 상품마스터에서 세팅한 조사일자(스캔한 날짜가 아님). 수량·페이지·줄번호는 정수, 나머지는 글자."""
    if stat_rows is None or stat is None:
        _b, stat_rows, stat = split_counts(app)
    date = file_date(app)
    ledger_names = _stat_ledger_map(app.state.store_code)  # [2026-10-16] 상품명은 문구 장부마스터 우선(단가·코드는 상품마스터만 줌)
    by_loc = {}
    for r in nonzero_rows(stat_rows):  # 수량 0 줄은 빼고 페이지·줄번호를 매긴다(번호가 비지 않게)
        isbn = str(r["isbn"] or "").strip()
        if not isbn:
            continue
        loc = stat_location(r["area"], r["section"])
        by_loc.setdefault(loc, []).append(r)
    rows = []
    for loc in sorted(by_loc, key=_loc_sort_key):
        pages = {}
        for r in by_loc[loc]:
            pages.setdefault((_raw_field(r["shelf_no"]), _raw_field(r["dan"]), _raw_field(r["yeol"])), []).append(r)
        def _page_key(k):
            # k = (서가번호, 단, 열) -> 정렬은 단, 열, 서가번호 순(숫자 기준, 글자는 뒤)
            def n(v):
                v = str(v or "").strip()
                return (0, int(v)) if v.isdigit() else (1, 0)
            return (n(k[1]), k[1], n(k[2]), k[2], n(k[0]), k[0])
        for pno, key in enumerate(sorted(pages, key=_page_key), start=1):
            for seq, r in enumerate(sorted(pages[key], key=lambda x: x["id"]), start=1):
                isbn = str(r["isbn"]).strip()
                name, price, dvsn, kcode, rdp = stat.get(norm_barcode(isbn), ("", 0, "", "", ""))
                lg = ledger_names.get(bc13(isbn))
                if lg is not None and lg["book_name"]:
                    name = lg["book_name"]
                rows.append((date, rdp, bc13(isbn), r["qty"] or 0, dvsn, f"{price}{kcode}{loc}", pno, seq, name))
    return rows


def stat_detail_lines(app, stat_rows=None, stat=None):
    """납품상세데이터 txt: 위 행을 쉼표로 이은 한 줄씩(상품명 안의 쉼표·줄바꿈은 공백으로)."""
    return [",".join([str(v) for v in r[:8]] + [_clean_text(r[8])]) for r in stat_detail_rows(app, stat_rows, stat)]


def write_text_lines(lines, path):
    """문구 상세 자료: UTF-8(BOM 없음), 줄 사이 CRLF, 헤더 없음. 마지막 줄 뒤 줄바꿈(EOF)은 eof_crlf_enabled()(항상 켬)에 따른다.
    [2026-10-16] "이제 모든 txt는 utf-8로 세팅, 선택하는 기능은 없애줘" - 예전의 CP949 고정(10-14 12차)과 글자 선택(1.5.21 초안)을
    없애고 항상 UTF-8로 쓴다(어제 CP949로 만든 파일을 받은 쪽이 "깨진 글자가 있다"고 했고, 같은 시스템이 내려주는 상품마스터·
    장부마스터 CSV도 UTF-8(BOM)이다). UTF-8이라 é, ü, 이모지도 ?로 바뀌지 않는다."""
    from pathlib import Path
    path = path if isinstance(path, Path) else Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(("\r\n".join(lines) + ("\r\n" if (lines and eof_crlf_enabled()) else "")).encode("utf-8"))


def item_list_rows(app, include_zero=True):
    """③ 단품 리스트생성 (결과확인리스트): 상품마스터 전체 품목에 이번
    조사의 스캔재고/차이를 더한 비교표.
    컬럼: 바코드,도서명,분야,출판사,전산재고,실재고,누락재고,예외여부,
    스캔재고,차이 (차이 = 스캔재고 - 전산재고)."""
    store_code = app.state.store_code
    # [2026-10-08] 전산재고/실재고/누락재고/예외여부는 장부마스터 기준(상품마스터는 PDA용).
    # 장부마스터에 없는 바코드는 상품마스터의 이름 정보만 빌리고 수량은 0으로 본다.
    # [2026-10-13] 서적만: 문구 행은 문구 납품 자료 쪽에서 다룬다.
    # [2026-10-13] 바코드는 모두 13자리(bc13)로 맞춰 비교한다(마스터 0000000000001 / 스캔 1).
    # include_zero=True(기본) 이면 전산재고·실재고·스캔이 모두 0인 품목도 넣는다(화면의 체크 옵션, 받은 쪽 파일도 장부 전체 행).
    # [2026-10-16] 기본값을 False -> True로(AREA별 합산 화면에서도 전체 행).
    ledger_map = {bc13(k): v for k, v in _fetch_ledger_map(store_code).items() if (v["kind"] or "서적") != "문구"}
    names_map = {bc13(k): v for k, v in _fetch_books_map(store_code).items() if (v["kind"] or "서적") != "문구"}
    counts = split_counts(app)[0]
    scanned = {}
    for r in counts:
        isbn = bc13(r["isbn"])
        if not str(r["isbn"] or "").strip():
            continue
        scanned[isbn] = scanned.get(isbn, 0) + (r["qty"] or 0)

    headers = ("바코드", "도서명", "분야", "출판사", "전산재고", "실재고", "누락재고", "예외여부",
               "스캔재고", "차이")
    data = []
    # [2026-10-08] 대상은 "장부마스터 + 이번에 수신한 실사 바코드"뿐이다(장부마스터가 비어 있으면
    # 수신한 실사 바코드만, 그것도 없으면 빈 결과). 상품마스터(PDA용)만 있는 바코드는 넣지 않는다.
    # 장부마스터 전산재고·실재고와 수신 실사수량이 모두 0 인 항목은 제외한다.
    count_names = {}
    for r in counts:
        k = bc13(r["isbn"]) if str(r["isbn"] or "").strip() else ""
        if k and k not in count_names:
            count_names[k] = r["book_name"] or ""
    for isbn in sorted(set(ledger_map) | set(scanned)):
        b = ledger_map.get(isbn)
        nm = names_map.get(isbn)
        if b is not None:
            nb = b
        elif nm is not None:
            nb = nm
        else:
            nb = {"book_name": count_names.get(isbn, ""), "category": "", "publisher": ""}
        rcds = (b["rcds_qty"] if b is not None else 0) or 0
        real = (b["real_qty"] if b is not None else 0) or 0
        scan_qty = scanned.get(isbn, 0)
        if not include_zero and rcds == 0 and real == 0 and scan_qty == 0:  # 셋 다 0이면 제외(옵션으로 포함)
            continue
        is_exc = disp_exc(b["except_flag"]) if b is not None else "N"
        miss = (b["missing_qty"] if b is not None else 0) or 0
        if b is not None:
            d_rcds, d_real, d_miss = disp_qty(rcds, b["rcds_x"]), disp_qty(real, b["real_x"]), disp_qty(miss, b["missing_x"])
        else:
            d_rcds, d_real, d_miss = rcds, real, miss
        data.append((isbn, nb["book_name"], nb["category"], nb["publisher"],
                    d_rcds, d_real, d_miss, is_exc,
                    scan_qty, scan_qty - rcds))
    return headers, data


def shelf_rows(app):
    """④ 서가별 생성 (서가별스캔데이터): 스캔 1건당 1행(집계하지 않음).
    컬럼: 바코드,도서명,분야,출판사,서가번호,실사수량.
    [2026-10-16] 도서명·분야·출판사는 서적 장부마스터 기준, 장부마스터에 없는 바코드만 서적 상품마스터로 보충한다
    (받은 쪽 서가별스캔데이터가 모두 장부마스터 값이었음). 둘 다 없으면 스캔 때 저장된 이름. 실사수량 0인 줄은 뺀다."""
    store_code = app.state.store_code
    ledger_map = {bc13(k): v for k, v in _fetch_ledger_map(store_code).items() if (v["kind"] or "서적") != "문구"}
    books_map = {bc13(k): v for k, v in _fetch_books_map(store_code).items() if (v["kind"] or "서적") != "문구"}
    rows = nonzero_rows(split_counts(app)[0])  # 서적 행만, 실사수량 0 줄 제외
    data = []
    for r in sorted(rows, key=lambda x: (bc13(x["isbn"]), shelf_code(x, store_code))):
        isbn = str(r["isbn"] or "").strip()
        if not isbn:
            continue
        b = ledger_map.get(bc13(isbn))
        if b is None:
            b = books_map.get(bc13(isbn))
        book_name = (b["book_name"] if b else "") or (r["book_name"] or "")
        category = b["category"] if b else ""
        publisher = b["publisher"] if b else ""
        loc = shelf_code(r, store_code)
        data.append((bc13(isbn), book_name, category, publisher, loc, r["qty"] or 0))
    headers = ("바코드", "도서명", "분야", "출판사", "서가번호", "실사수량")
    return headers, data


# ---- 문구 결과확인리스트 / 로케이션별 스캔리스트 -------------------------------------------------
# [2026-10-16] 서적 결과확인리스트·서가별스캔데이터와 같은 모양의 문구판. 기준 마스터가 서적 쪽(장부 서적 행)이
# 아니라 문구 장부마스터(ledger_master.kind='문구')와 문구 스캔 행(AREA 20~29·80~89)이다.
# 문구는 실재고·누락재고·예외여부를 쓰지 않으므로 F·G·H열은 제목도 값도 고정 "X".
# 항목 제목은 사용자가 준 실제 문구 파일(수원 결과확인리스트·로케이션별 스캔리스트, 2026-10-15)과 똑같이 맞췄다:
# 서적과 달리 상품명 / 상품구분 / 매입처 / 장부재고, 로케이션별은 분야 / 거래처 / 스캔총수량.
STAT_ITEM_LIST_HEADERS = ("바코드", "상품명", "상품구분", "매입처", "장부재고", "X", "X", "X", "스캔재고", "차이")
STAT_SCAN_HEADERS = ("바코드", "상품명", "분야", "거래처", "로케이션", "스캔총수량")


def _stat_ledger_map(store_code):
    """문구 장부마스터만: 13자리 바코드 -> 행."""
    return {bc13(k): v for k, v in _fetch_ledger_map(store_code).items() if (v["kind"] or "서적") == "문구"}


def _stat_names_map(store_code):
    """문구 상품마스터만: 13자리 바코드 -> 행(이름 보충용)."""
    return {bc13(k): v for k, v in _fetch_books_map(store_code).items() if (v["kind"] or "서적") == "문구"}


def stat_item_list_rows(app, include_zero=True, stat_rows=None):
    """문구 결과확인리스트: 문구 장부마스터 전 품목 + 이번 조사의 문구 스캔재고/차이(차이 = 스캔재고 - 장부재고).
    컬럼: 바코드,상품명,상품구분,매입처,장부재고,X,X,X,스캔재고,차이 (F·G·H는 제목·값 모두 "X").
    include_zero=False면 장부재고와 스캔재고가 모두 0인 품목은 뺀다. 장부재고 칸이 마스터에서 X면 X로 보이고 차이 계산엔 0."""
    store_code = app.state.store_code
    ledger = _stat_ledger_map(store_code)
    names = _stat_names_map(store_code)
    if stat_rows is None:
        stat_rows = split_counts(app)[1]
    scanned, count_names = {}, {}
    for r in stat_rows:
        if not str(r["isbn"] or "").strip():
            continue
        k = bc13(r["isbn"])
        scanned[k] = scanned.get(k, 0) + (r["qty"] or 0)
        if k not in count_names:
            count_names[k] = r["book_name"] or ""
    data = []
    for isbn in sorted(set(ledger) | set(scanned)):
        b = ledger.get(isbn)
        nm = names.get(isbn)
        rcds = (b["rcds_qty"] if b is not None else 0) or 0
        scan_qty = scanned.get(isbn, 0)
        if not include_zero and rcds == 0 and scan_qty == 0:
            continue
        name = (b["book_name"] if b is not None and b["book_name"] else None) or (nm["book_name"] if nm is not None else "") \
            or count_names.get(isbn, "")
        category = (b["category"] if b is not None else "") or ""
        publisher = (b["publisher"] if b is not None else "") or ""
        d_rcds = disp_qty(rcds, b["rcds_x"]) if b is not None else rcds
        data.append((isbn, name, category, publisher, d_rcds, "X", "X", "X", scan_qty, scan_qty - rcds))
    return STAT_ITEM_LIST_HEADERS, data


def stat_scan_rows(app, stat_rows=None):
    """문구 로케이션별 스캔리스트: (바코드, 로케이션)마다 1행, 스캔총수량은 그 합계(사용자가 준 실제 파일과 같은 방식).
    로케이션 = AREA 2자리 + SECTION 3자리. 컬럼: 바코드,상품명,분야,거래처,로케이션,스캔총수량. 바코드순 → 로케이션순."""
    store_code = app.state.store_code
    ledger = _stat_ledger_map(store_code)
    names = _stat_names_map(store_code)
    if stat_rows is None:
        stat_rows = split_counts(app)[1]
    tot, first = {}, {}
    for r in nonzero_rows(stat_rows):
        isbn = str(r["isbn"] or "").strip()
        if not isbn:
            continue
        key = (bc13(isbn), stat_location(r["area"], r["section"]))
        tot[key] = tot.get(key, 0) + (r["qty"] or 0)
        first.setdefault(key, r)
    data = []
    for key in sorted((k for k in tot if tot[k] != 0), key=lambda k: (k[0], _loc_sort_key(k[1]))):
        k, loc = key
        b, nm = ledger.get(k), names.get(k)
        # [2026-10-16] 상품명은 문구 장부마스터 기준, 장부에 없을 때만 문구 상품마스터로 보충
        name = (b["book_name"] if b is not None and b["book_name"] else None) or (nm["book_name"] if nm is not None else "") \
            or (first[key]["book_name"] or "")
        data.append((k, name, (b["category"] if b is not None else "") or "", (b["publisher"] if b is not None else "") or "",
                     loc, tot[key]))
    return STAT_SCAN_HEADERS, data


def unregistered_rows(app):
    """자료생성(미등록): 상품마스터(books)에 없는 바코드이 스캔된 것만 모은다."""
    store_code = app.state.store_code
    rows = _fetch_counts(store_code, app.state.survey_date)
    conn = dbmod.get_conn()
    registered = {norm_barcode(r["isbn"]) for r in conn.execute("SELECT isbn FROM books WHERE store_code=?", (store_code,))}
    conn.close()
    headers = ("AREA", "SECTION", "서가번호", "단", "열", "바코드", "상품명", "조사수량", "작업자명", "실사일자", "실사시간")
    data = [(r["area"], r["section"], r["shelf_no"], r["dan"], r["yeol"], bc13(r["isbn"]), r["book_name"],
             r["qty"], r["worker_name"], *split_scan_datetime(r["received_at"], r["survey_date"]))
            for r in rows if norm_barcode(r["isbn"]) not in registered]
    return headers, data


def generate_kyobo_data_1_2(app, out_dir):
    """자료①,②생성(서적): kyobo_data1.txt + kyobo_data2.txt를 out_dir에 쓰고
    (파일이름, 줄 수) 2개짜리 리스트를 돌려준다."""
    results = []
    rows = split_counts(app)[0]
    lines1 = kyobo_data1_lines(app, rows)
    write_text_lines_file(lines1, out_dir / "kyobo_data1.txt")
    results.append(("kyobo_data1.txt", len(lines1)))
    lines2 = kyobo_data2_lines(app, rows)
    write_text_lines_file(lines2, out_dir / "kyobo_data2.txt")
    results.append(("kyobo_data2.txt", len(lines2)))
    return results


def stat_location_filename(app, ext="txt"):
    return f"문구전용_납품로케이션데이터_{file_date(app)}.{ext}"


def stat_detail_filename(app, ext="txt"):
    return f"문구전용_납품상세데이터_{file_date(app)}.{ext}"


def stat_scan_filename(app):
    return f"{short_store_label(app.state.store_name)}_{scope.tag('문구')}_로케이션별스캔리스트({file_date(app)}).xlsx"


STAT_FILE_KEYS = ("loc", "det", "loc_x", "det_x", "stat_list", "stat_scan")


def write_stat_xlsx(path, headers, rows, qty_cols=()):
    """문구 자료 엑셀: 바코드·위치·코드류는 글자 그대로(앞자리 0 보존), qty_cols 칸만 숫자 + 3자리 콤마. 열 너비는 자동."""
    from . import fast_xlsx
    fast_xlsx.write_xlsx(path, list(headers), rows, amount_cols=list(qty_cols))


def generate_stat_files(app, out_dir, only=None, include_zero=True):
    """문구 자료를 쓰고 (파일이름, 줄 수) 리스트를 돌려준다. only = STAT_FILE_KEYS 중 만들 것(None이면 전부):
    loc/det = 납품로케이션·납품상세 txt, loc_x/det_x = 같은 내용의 xlsx, stat_list = 문구 결과확인리스트.xlsx,
    stat_scan = 문구 로케이션별스캔리스트.xlsx. 문구 스캔이 없으면 빈 리스트. txt는 모두 UTF-8."""
    only = set(STAT_FILE_KEYS if only is None else only)
    _b, stat_rows, stat = split_counts(app)
    if not stat_rows:
        return []
    out = []
    if "loc" in only:
        lines = stat_location_lines(app, stat_rows)
        write_text_lines_file(lines, out_dir / stat_location_filename(app))  # 숫자/ASCII뿐
        out.append((stat_location_filename(app), len(lines)))
    if "det" in only:
        lines = stat_detail_lines(app, stat_rows, stat)
        write_text_lines(lines, out_dir / stat_detail_filename(app))
        out.append((stat_detail_filename(app), len(lines)))
    if "loc_x" in only:
        rows = stat_location_rows(app, stat_rows)
        write_stat_xlsx(out_dir / stat_location_filename(app, "xlsx"), STAT_LOC_HEADERS, rows, qty_cols=(2,))
        out.append((stat_location_filename(app, "xlsx"), len(rows)))
    if "det_x" in only:
        rows = stat_detail_rows(app, stat_rows, stat)
        write_stat_xlsx(out_dir / stat_detail_filename(app, "xlsx"), STAT_DET_HEADERS, rows, qty_cols=(3,))
        out.append((stat_detail_filename(app, "xlsx"), len(rows)))
    if "stat_list" in only:
        headers, rows = stat_item_list_rows(app, include_zero=include_zero, stat_rows=stat_rows)
        write_stat_xlsx(out_dir / item_list_filename(app, "문구"), headers, rows, qty_cols=(4, 8, 9))
        out.append((item_list_filename(app, "문구"), len(rows)))
    if "stat_scan" in only:
        headers, rows = stat_scan_rows(app, stat_rows)
        write_stat_xlsx(out_dir / stat_scan_filename(app), headers, rows, qty_cols=(5,))
        out.append((stat_scan_filename(app), len(rows)))
    return out


def item_list_filename(app, kind="서적"):
    return f"{short_store_label(app.state.store_name)}_{scope.tag(kind)}_결과확인리스트({file_date(app)}).xlsx"


def shelf_filename(app, kind="서적"):
    return f"{short_store_label(app.state.store_name)}_{scope.tag(kind)}_서가별스캔데이터({file_date(app)}).xlsx"
