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
   kyobo_data1.txt : 서가번호(11)+바코드(13)=24자, (서가번호,바코드) 조합당 1줄(중복 제거), 정렬, CRLF
   kyobo_data2.txt : 바코드(13)+수량(5, 0채움)=18자, 바코드별 합계 1줄, 바코드순, CRLF
                     (이전 버전은 두 파일의 정의가 서로 바뀌어 있었다 - 받은 샘플 기준으로 바로잡음)
   서가번호(11) = 점포3+AREA2+SECTION3+3자리: PDA에 입력한 서가번호(11자리)를 그대로 쓴다
   결과확인리스트.xlsx / 서가별스캔데이터.xlsx (서적 행만)
  ── 문구 ── (UTF-8 텍스트, CRLF, 헤더 없음)
   납품로케이션데이터 : `위치,바코드,수량` - 위치 = AREA+SECTION(예 101), (위치,바코드)별 수량 합계
   납품상세데이터    : [2026-10-16 사용자 확정 11칸] `날짜,점포코드,바코드,수량,가격,구분코드,종류코드,
                        에리어+로케이션,단,열,상품명` - 스캔 1건당 1줄. 가격/구분코드/종류코드는 문구
                        상품마스터(sale_unpr/cmdt_dvsn_code/cmdt_code_kind_code) 값, 단(2자리)·열(3자리)은
                        스캔한 값(예전의 페이지·줄번호는 없앰). 정렬: 로케이션 -> 단 -> 열 -> 서가번호 -> 스캔 순서.
   위치코드 = AREA 2자리 + SECTION 3자리 = 5자리 (예 01+001 -> 01001)
   점포코드(591 등) = 문구 상품마스터 파일의 rdp_code 값 그대로(비어 있으면 선택된 점포코드)
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
from .ui_common import file_date, normalize_area, short_store_label, write_text_lines_file, write_rows_to_excel_file, \
    eof_crlf_enabled, split_scan_datetime
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


def _kind_sql(kind):
    """구분(kind)으로 마스터 행을 SQL에서 미리 거른다: '문구' | '서적'(문구가 아닌 것, 빈 값 포함) | None(전부)."""
    if kind == "문구":
        return " AND kind='문구'"
    if kind == "서적":
        return " AND (kind IS NULL OR kind<>'문구')"
    return ""


def _fetch_books_map(store_code, kind=None):
    conn = dbmod.get_conn()
    rows = conn.execute(
        "SELECT isbn, book_name, category, publisher, rcds_qty, real_qty, missing_qty, except_flag, kind, rcds_x, real_x, missing_x "
        "FROM books WHERE store_code=?" + _kind_sql(kind),
        (store_code,)
    ).fetchall()
    conn.close()
    return {r["isbn"]: r for r in rows}


def _fetch_ledger_map(store_code, kind=None):
    """[2026-10-08] 장부마스터(ledger_master) - 전산재고가 필요한 PC 쪽 화면/엑셀의 기준."""
    conn = dbmod.get_conn()
    rows = conn.execute(
        "SELECT isbn, book_name, category, publisher, rcds_qty, real_qty, missing_qty, except_flag, kind, rcds_x, real_x, missing_x "
        "FROM ledger_master WHERE store_code=?" + _kind_sql(kind),
        (store_code,)
    ).fetchall()
    conn.close()
    return {r["isbn"]: r for r in rows}


def _fetch_names_map(table, store_code, kind):
    """이름·분야·출판사만 필요한 곳용 가벼운 조회(table: 'books'|'ledger_master'). 13자리 바코드 -> 행."""
    assert table in ("books", "ledger_master")
    conn = dbmod.get_conn()
    rows = conn.execute(
        f"SELECT isbn, book_name, category, publisher FROM {table} WHERE store_code=?" + _kind_sql(kind),
        (store_code,)
    ).fetchall()
    conn.close()
    return {bc13(r["isbn"]): r for r in rows}


def _fetch_names_for(table, store_code, kind, codes):
    """장부마스터에 없는 바코드의 이름·분야·출판사를 상품마스터에서 보충할 때, 필요한 바코드만 조회한다
    (상품마스터 전체 48만 줄을 읽지 않으려고). codes = 13자리 바코드들. 마스터에 앞 0이 없는 모양으로 저장된
    옛 자료도 찾도록 앞 0을 뗀 값도 같이 찾는다. 결과는 13자리 바코드 -> 행."""
    assert table in ("books", "ledger_master")
    want = set()
    for c in codes:
        want.add(c)
        want.add(c.lstrip("0"))
    want = sorted(want)
    out = {}
    if not want:
        return out
    conn = dbmod.get_conn()
    try:
        for i in range(0, len(want), 500):
            chunk = want[i:i + 500]
            q = ",".join("?" * len(chunk))
            for r in conn.execute(
                    f"SELECT isbn, book_name, category, publisher FROM {table} WHERE store_code=? AND isbn IN ({q})" + _kind_sql(kind),
                    (store_code, *chunk)):
                out[bc13(r["isbn"])] = r
    finally:
        conn.close()
    return out


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


def shelf_code(r, store_code):
    """서가번호(11자리). PDA/PC에서 입력한 서가번호가 11자리 숫자면 그대로 쓴다
    ([2026-10-16 사용자 지시] 서가번호는 다시 11자리까지 - 1.5.19의 20자리는 되돌림).
    아니면(옛 자료·짧은 값) 점포3+AREA2+SECTION3 뒤에 입력값을 3자리로 맞춰 붙인다."""
    raw = _raw_field(r["shelf_no"])
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 11:
        return digits
    if len(digits) > 11:
        return digits[-11:]
    sec = "".join(ch for ch in _raw_field(r["section"]) if ch.isdigit())[-3:].zfill(3)
    return (_digits_only(store_code, 3) + normalize_area(r["area"], merged=True) + sec + digits[-3:].zfill(3))[:11]


def nonzero_rows(rows):
    """[2026-10-16] 실사수량 0인 스캔 줄은 txt(kyobo_data1·2, 납품로케이션·상세)와 스캔리스트(서가별스캔데이터,
    로케이션별스캔데이터)에서 뺀다. 결과확인리스트는 이 함수를 쓰지 않고 그대로 둔다(사용자 지시)."""
    return [r for r in rows if (r["qty"] or 0) != 0]


def kyobo_data1_lines(app, rows=None):
    """자료① (kyobo_data1.txt): 서가번호(11)+바코드(13)=24자, (서가번호,바코드)당 1줄, 정렬."""
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
STAT_DET_HEADERS = ("날짜", "점포코드", "바코드", "수량", "가격", "구분코드", "종류코드", "에리어+로케이션", "단", "열", "상품명")


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


def _pad_num(v, width):
    """단·열처럼 숫자면 앞 0을 채워 width자리로(예: 1 -> 01, 1 -> 001), 숫자가 아니면 입력된 그대로."""
    v = _raw_field(v)
    return v.zfill(width) if v.isdigit() else v


def _price_int(v):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return 0


def stat_detail_rows(app, stat_rows=None, stat=None):
    """납품상세데이터: 스캔 1건당 1행, 11칸.
    (날짜, 점포코드, 바코드, 수량, 가격, 구분코드, 종류코드, 에리어+로케이션, 단, 열, 상품명)
    [2026-10-16 사용자 확정] 가격 = 상품마스터 가격, 구분코드 = 상품마스터 cmdt_dvsn_code, 종류코드 = 상품마스터
    cmdt_code_kind_code, 에리어+로케이션 = AREA 2자리 + SECTION 3자리, 단(2자리)·열(3자리)은 스캔한 값 그대로
    (예전의 "페이지·줄번호"는 없앴다). 날짜 칸은 항상 상품마스터에서 세팅한 조사일자(스캔한 날짜가 아님).
    점포코드 = 상품마스터 파일의 rdp_code, 비어 있으면 화면에 선택된 점포코드. 수량·가격은 정수, 나머지는 글자.
    정렬 = 로케이션 -> 단 -> 열 -> 서가번호 -> 스캔 순서."""
    if stat_rows is None or stat is None:
        _b, stat_rows, stat = split_counts(app)
    date = file_date(app)
    ledger_names = _stat_ledger_map(app.state.store_code)  # [2026-10-16] 상품명은 문구 장부마스터 우선(가격·코드는 상품마스터만 줌)
    def n(v):
        v = str(v or "").strip()
        return (0, int(v)) if v.isdigit() else (1, 0)
    keyed = []
    for r in nonzero_rows(stat_rows):  # 수량 0 줄은 뺀다
        isbn = str(r["isbn"] or "").strip()
        if not isbn:
            continue
        loc = stat_location(r["area"], r["section"])
        dan, yeol, shelf = _raw_field(r["dan"]), _raw_field(r["yeol"]), _raw_field(r["shelf_no"])
        keyed.append(((_loc_sort_key(loc), n(dan), dan, n(yeol), yeol, n(shelf), shelf, r["id"]), loc, r, isbn, dan, yeol))
    keyed.sort(key=lambda x: x[0])
    rows = []
    for _k, loc, r, isbn, dan, yeol in keyed:
        name, price, dvsn, kcode, rdp = stat.get(norm_barcode(isbn), ("", 0, "", "", ""))
        lg = ledger_names.get(bc13(isbn))
        if lg is not None and lg["book_name"]:
            name = lg["book_name"]
        rows.append((date, rdp or str(app.state.store_code or "").strip(), bc13(isbn), r["qty"] or 0, _price_int(price),
                     dvsn, kcode, loc, _pad_num(dan, 2), _pad_num(yeol, 3), name))
    return rows


def stat_detail_lines(app, stat_rows=None, stat=None):
    """납품상세데이터 txt: 위 행을 쉼표로 이은 한 줄씩(상품명 안의 쉼표·줄바꿈은 공백으로)."""
    return [",".join([str(v) for v in r[:10]] + [_clean_text(r[10])]) for r in stat_detail_rows(app, stat_rows, stat)]


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


def item_list_rows(app, include_zero=True, book_rows=None):
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
    ledger_map = {bc13(k): v for k, v in _fetch_ledger_map(store_code, "서적").items()}
    counts = split_counts(app)[0] if book_rows is None else book_rows   # book_rows: 이미 나눈 서적 행(자료 한꺼번에 생성할 때 다시 안 읽으려고)
    scanned = {}
    for r in counts:
        isbn = bc13(r["isbn"])
        if not str(r["isbn"] or "").strip():
            continue
        scanned[isbn] = scanned.get(isbn, 0) + (r["qty"] or 0)
    # 장부마스터에 없는 스캔 바코드만 서적 상품마스터에서 이름을 보충한다(필요한 것만 조회).
    names_map = _fetch_names_for("books", store_code, "서적", [c for c in scanned if c not in ledger_map])

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


def shelf_rows(app, book_rows=None):
    """④ 서가별 생성 (서가별스캔데이터): 스캔 1건당 1행(집계하지 않음).
    컬럼: 바코드,도서명,분야,출판사,서가번호,실사수량.
    [2026-10-16] 도서명·분야·출판사는 서적 장부마스터 기준, 장부마스터에 없는 바코드만 서적 상품마스터로 보충한다
    (받은 쪽 서가별스캔데이터가 모두 장부마스터 값이었음). 둘 다 없으면 스캔 때 저장된 이름. 실사수량 0인 줄은 뺀다."""
    store_code = app.state.store_code
    ledger_map = _fetch_names_map("ledger_master", store_code, "서적")
    books_map = _fetch_names_map("books", store_code, "서적")
    rows = nonzero_rows(split_counts(app)[0] if book_rows is None else book_rows)  # 서적 행만, 실사수량 0 줄 제외
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


def shelf_sum_rows(app, book_rows=None, base=None):
    """서가별스캔데이터(서가별 합산): 서가별스캔데이터와 같은 컬럼·이름 기준인데, 같은 바코드 + 같은 서가번호는 한 줄로 합산한다
    ([2026-10-16] 사용자 요청). 컬럼: 바코드,도서명,분야,출판사,서가번호,실사수량(합계). 합계가 0이면 뺀다. 정렬: 바코드 -> 서가번호."""
    headers, data = base if base is not None else shelf_rows(app, book_rows)   # base = 이미 만든 서가별스캔데이터 (headers, data)
    tot, first = {}, {}
    for r in data:
        k = (r[0], r[4])
        tot[k] = tot.get(k, 0) + r[5]
        first.setdefault(k, r)
    return headers, [first[k][:5] + (q,) for k, q in tot.items() if q != 0]


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
    return {bc13(k): v for k, v in _fetch_ledger_map(store_code, "문구").items()}


def stat_item_list_rows(app, include_zero=True, stat_rows=None):
    """문구 결과확인리스트: 문구 장부마스터 전 품목 + 이번 조사의 문구 스캔재고/차이(차이 = 스캔재고 - 장부재고).
    컬럼: 바코드,상품명,상품구분,매입처,장부재고,X,X,X,스캔재고,차이 (F·G·H는 제목·값 모두 "X").
    include_zero=False면 장부재고와 스캔재고가 모두 0인 품목은 뺀다. 장부재고 칸이 마스터에서 X면 X로 보이고 차이 계산엔 0."""
    store_code = app.state.store_code
    ledger = _stat_ledger_map(store_code)
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
    # 장부마스터에 없거나 이름이 빈 바코드만 문구 상품마스터에서 이름을 보충한다(필요한 것만 조회).
    names = _fetch_names_for("books", store_code, "문구",
                             [c for c in (set(ledger) | set(scanned)) if c not in ledger or not ledger[c]["book_name"]])
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
    """문구 로케이션별 스캔데이터(서적의 서가별스캔데이터 자리): (바코드, 로케이션)마다 1행, 스캔총수량은 그 합계(사용자가 준 실제 파일과 같은 방식).
    로케이션(서가번호 자리) = AREA 2자리 + SECTION 3자리(예 20101). 컬럼: 바코드,상품명,분야,거래처,로케이션,스캔총수량. 바코드순 → 로케이션순."""
    store_code = app.state.store_code
    ledger = _stat_ledger_map(store_code)
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
    # 장부마스터에 없거나 이름이 빈 바코드만 문구 상품마스터에서 이름을 보충한다(필요한 것만 조회).
    names = _fetch_names_for("books", store_code, "문구",
                             [k[0] for k in tot if k[0] not in ledger or not ledger[k[0]]["book_name"]])
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
    return f"{short_store_label(app.state.store_name)}_{scope.tag('문구')}_로케이션별스캔데이터({file_date(app)}).xlsx"


STAT_FILE_KEYS = ("loc", "det", "loc_x", "det_x", "stat_scan", "stat_list")  # 화면에 보이는 순서(txt 밑에 같은 내용 xlsx, 그 아래 로케이션별스캔데이터, 결과확인리스트)


def step_begin(progress, label):
    """[2026-10-16] 자료를 한꺼번에 만들 때 진행률 팝업용: [취소]를 눌렀으면 여기서 멈추고(이미 만든 파일은 남음),
    지금 만드는 파일 이름을 보여 준다. progress가 None이면 아무것도 하지 않는다."""
    if progress is not None:
        progress.check_cancel()
        progress(message=f"{label} 만드는 중...", done=progress.done)


def step_end(progress):
    """파일 하나를 다 만들었을 때 진행 개수를 하나 올린다."""
    if progress is not None:
        progress(done=progress.done + 1)


def write_stat_xlsx(path, headers, rows, qty_cols=()):
    """문구 자료 엑셀: 바코드·위치·코드류는 글자 그대로(앞자리 0 보존), qty_cols 칸만 숫자 + 3자리 콤마. 열 너비는 자동."""
    from . import fast_xlsx
    fast_xlsx.write_xlsx(path, list(headers), rows, amount_cols=list(qty_cols))


def generate_stat_files(app, out_dir, only=None, include_zero=True, progress=None, counts=None):
    """문구 자료를 쓰고 (파일이름, 줄 수) 리스트를 돌려준다. only = STAT_FILE_KEYS 중 만들 것(None이면 전부):
    loc/det = 납품로케이션·납품상세 txt, loc_x/det_x = 같은 내용의 xlsx(납품상세 txt 밑, [2026-10-16] 사용자 요청으로 복구),
    stat_scan = 문구 로케이션별스캔데이터.xlsx, stat_list = 문구 결과확인리스트.xlsx. 문구 스캔이 없으면 빈 리스트. txt는 모두 UTF-8."""
    only = set(STAT_FILE_KEYS if only is None else only)
    _b, stat_rows, stat = split_counts(app) if counts is None else counts   # counts = 이미 나눈 (서적, 문구, 문구맵)
    if not stat_rows:
        return []
    out = []
    if "loc" in only:
        step_begin(progress, "문구 · " + stat_location_filename(app))
        lines = stat_location_lines(app, stat_rows)
        write_text_lines_file(lines, out_dir / stat_location_filename(app))  # 숫자/ASCII뿐
        out.append((stat_location_filename(app), len(lines)))
        step_end(progress)
    if "det" in only:
        step_begin(progress, "문구 · " + stat_detail_filename(app))
        lines = stat_detail_lines(app, stat_rows, stat)
        write_text_lines(lines, out_dir / stat_detail_filename(app))
        out.append((stat_detail_filename(app), len(lines)))
        step_end(progress)
    if "loc_x" in only:
        step_begin(progress, "문구 · " + stat_location_filename(app, "xlsx"))
        rows = stat_location_rows(app, stat_rows)
        write_stat_xlsx(out_dir / stat_location_filename(app, "xlsx"), STAT_LOC_HEADERS, rows, qty_cols=(2,))
        out.append((stat_location_filename(app, "xlsx"), len(rows)))
        step_end(progress)
    if "det_x" in only:
        step_begin(progress, "문구 · " + stat_detail_filename(app, "xlsx"))
        rows = stat_detail_rows(app, stat_rows, stat)
        write_stat_xlsx(out_dir / stat_detail_filename(app, "xlsx"), STAT_DET_HEADERS, rows, qty_cols=(3, 4))
        out.append((stat_detail_filename(app, "xlsx"), len(rows)))
        step_end(progress)
    if "stat_scan" in only:
        step_begin(progress, "문구 · " + stat_scan_filename(app))
        headers, rows = stat_scan_rows(app, stat_rows)
        write_stat_xlsx(out_dir / stat_scan_filename(app), headers, rows, qty_cols=(5,))
        out.append((stat_scan_filename(app), len(rows)))
        step_end(progress)
    if "stat_list" in only:
        step_begin(progress, "문구 · " + item_list_filename(app, "문구"))
        headers, rows = stat_item_list_rows(app, include_zero=include_zero, stat_rows=stat_rows)
        write_stat_xlsx(out_dir / item_list_filename(app, "문구"), headers, rows, qty_cols=(4, 8, 9))
        out.append((item_list_filename(app, "문구"), len(rows)))
        step_end(progress)
    return out


BOOK_FILE_KEYS = ("d1", "d2", "list", "shelf", "shelf_sum")   # 서적 카드의 순서


def generate_selected(app, do_book, do_stat, files, zero_book=True, zero_stat=True, progress=None):
    """[자료생성] [선택한 자료 생성]: 체크한 서적/문구 자료를 한 번에 만든다. 화면(tkinter)을 건드리지 않아
    백그라운드 스레드에서 돌릴 수 있다. files = {파일 키: 체크 여부}(서적 BOOK_FILE_KEYS + 문구 STAT_FILE_KEYS).
    (만든 파일 [(폴더/이름, 줄 수)], 확인할 항목 [글]) 을 돌려준다.
    [2026-10-16] "서적자료, 문구자료 동시 생성시 시간이 걸리니 진행률을" - 파일 하나를 만들 때마다 progress로
    알린다(단위 files). 실사 자료는 한 번만 읽어서 파일마다 다시 읽지 않는다. [취소]는 파일과 파일 사이에서 받는다."""
    book_dir = output_dir(app, "서적")
    stat_dir = output_dir(app, "문구")
    done, skipped = [], []
    if progress is not None:
        progress(message="실사 자료를 불러오는 중...", done=0, total=0, unit="files")
        progress.check_cancel()
    counts = split_counts(app)
    book_rows, stat_rows, stat = counts
    book_keys = [k for k in BOOK_FILE_KEYS if files.get(k)] if do_book and book_rows else []
    stat_keys = [k for k in STAT_FILE_KEYS if files.get(k)] if do_stat and stat_rows else []
    if progress is not None:
        progress(total=1 + len(book_keys) + len(stat_keys), done=1)
    if do_book:
        if not book_rows:
            skipped.append("서적: 서적 실사 자료가 없습니다")
        else:
            shelf = None
            for key in book_keys:
                if key == "d1":
                    step_begin(progress, "서적 · kyobo_data1.txt")
                    lines = kyobo_data1_lines(app, book_rows)
                    write_text_lines_file(lines, book_dir / "kyobo_data1.txt")
                    done.append(("서적전용/kyobo_data1.txt", len(lines)))
                elif key == "d2":
                    step_begin(progress, "서적 · kyobo_data2.txt")
                    lines = kyobo_data2_lines(app, book_rows)
                    write_text_lines_file(lines, book_dir / "kyobo_data2.txt")
                    done.append(("서적전용/kyobo_data2.txt", len(lines)))
                elif key == "list":
                    name = item_list_filename(app, "서적")
                    step_begin(progress, "서적 · " + name)
                    headers, rows = item_list_rows(app, include_zero=zero_book, book_rows=book_rows)
                    write_rows_to_excel_file(rows, headers, book_dir / name)
                    done.append(("서적전용/" + name, len(rows)))
                elif key == "shelf":
                    name = shelf_filename(app, "서적")
                    step_begin(progress, "서적 · " + name)
                    shelf = shelf_rows(app, book_rows)   # 서가별 합산에서 다시 계산하지 않도록 기억해 둔다
                    write_rows_to_excel_file(shelf[1], shelf[0], book_dir / name)
                    done.append(("서적전용/" + name, len(shelf[1])))
                elif key == "shelf_sum":
                    name = shelf_sum_filename(app, "서적")
                    step_begin(progress, "서적 · " + name)
                    headers, rows = shelf_sum_rows(app, book_rows, base=shelf)
                    write_rows_to_excel_file(rows, headers, book_dir / name)
                    done.append(("서적전용/" + name, len(rows)))
                step_end(progress)
    if do_stat:
        if not stat_rows:
            skipped.append("문구: 문구 실사 자료가 없습니다")
        else:
            for name, n in generate_stat_files(app, stat_dir, only=stat_keys, include_zero=zero_stat,
                                               progress=progress, counts=counts):
                done.append(("문구전용/" + name, n))
            if "det" in stat_keys or "det_x" in stat_keys:
                miss = missing_stat_master(stat_rows, stat)
                if miss:
                    skipped.append(f"참고: 문구 범위의 바코드 {miss:,}종이 문구 상품마스터에 없어 단가·구분코드·납품처가 비어 있습니다")
    return done, skipped


def item_list_filename(app, kind="서적"):
    return f"{short_store_label(app.state.store_name)}_{scope.tag(kind)}_결과확인리스트({file_date(app)}).xlsx"


def shelf_filename(app, kind="서적"):
    return f"{short_store_label(app.state.store_name)}_{scope.tag(kind)}_서가별스캔데이터({file_date(app)}).xlsx"


def shelf_sum_filename(app, kind="서적"):
    return f"{short_store_label(app.state.store_name)}_{scope.tag(kind)}_서가별스캔데이터(서가별합산)({file_date(app)}).xlsx"
