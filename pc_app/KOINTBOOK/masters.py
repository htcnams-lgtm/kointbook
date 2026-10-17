# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
[2026-10-13] 도서/문구 마스터 공용 불러오기 모듈 (상품마스터·장부마스터 화면 공용).

도서와 문구는 파일 양식이 서로 다르다.

  도서 상품마스터·장부마스터  cmdtCode, cmdtName, jo_name, pbcm_name,
                              rcdsInvnQntt, realInvnQntt, qntt, exceptYsno
  문구 상품마스터             rdp_code, cmdt_code, sale_unpr, cmdt_dvsn_code,
                              cmdt_code_kind_code, cmdt_name
  문구 장부마스터             도서와 같은 헤더(cmdtCode...) - 값이 "X"인 칸이 있다(없음 = 0)

두 마스터 모두 books / ledger_master 표에 kind('도서'|'문구')로 같이 저장한다
(같은 점포에서 도서만 / 문구만 / 둘 다 불러올 수 있고, 불러올 때는 같은 구분의 행만
교체한다). 문구 상품마스터에서만 price/dvsn_code/kind_code가 채워진다 - 문구
납품 자료(generation.py)가 그 값을 쓴다.

PDA는 바코드+상품명만 있으면 실사가 가능하므로 PDA 전송(pda_transfer.push_books)은
도서·문구를 한 BOOK.db로 합쳐서 보낸다.
"""

import csv

KIND_BOOK = "도서"
KIND_STAT = "문구"
KINDS = (KIND_BOOK, KIND_STAT)

BOOK_COLS = [
    ["cmdtCode", "ISBN", "바코드"],
    ["cmdtName", "도서명", "상품명", "품명"],
    ["jo_name", "분야명", "분야"],
    ["pbcm_name", "출판사"],
    ["rcdsInvnQntt", "전산재고"],
    ["realInvnQntt", "실재고"],
    ["qntt", "누락재고", "누락수량"],
    ["exceptYsno", "예외여부"],
]
STAT_COLS = [
    ["rdp_code", "납품처"],
    ["cmdt_code", "cmdtCode", "바코드"],
    ["cmdt_name", "cmdtName", "상품명", "품명"],
    ["sale_unpr", "판매가", "단가"],
    ["cmdt_dvsn_code", "구분코드"],
    ["cmdt_code_kind_code", "종류코드"],
]


def norm_barcode(s):
    """바코드 비교용: 앞뒤 공백·앞쪽 0 제거. 문구 마스터는 13자리 0채움(0051141931609)인데
    스캐너는 51141931609처럼 0 없이 읽는 일이 있어서, 비교는 항상 이 값으로 한다."""
    return str(s if s is not None else "").strip().lstrip("0")


def bc13(s):
    """바코드를 13자리(앞 0 채움)로 맞춘다. 마스터 파일(메모장)은 0000000000001, 엑셀/스캐너는 1이라
    자료생성으로 나가는 모든 바코드는 이 함수로 13자리로 통일한다. 13자리를 넘으면 그대로 둔다."""
    t = str(s if s is not None else "").strip()
    if t.endswith(".0") and t[:-2].isdigit():  # 엑셀 숫자 셀
        t = t[:-2]
    return t.zfill(13) if len(t) < 13 else t


def is_x(v):
    """마스터 칸 값이 'X'(해당 없음 표시)인지."""
    return str(v or "").strip().upper() == "X"


def disp_qty(n, x):
    """화면/출력용: X 표시된 칸은 숫자 대신 'X', 아니면 숫자."""
    return "X" if x else (n or 0)


def disp_exc(flag, manual=False):
    """예외여부 표시: 수동 지정이거나 Y면 Y, 파일 값이 X면 X, 아니면 N."""
    if manual or flag == "Y":
        return "Y"
    return "X" if flag == "X" else "N"


def to_int(v):
    try:
        return int(float(str(v).strip().replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _read_csv_all(path):
    last = None
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                return list(csv.reader(f))
        except UnicodeDecodeError as e:
            last = e
    raise last


def _read_xlsx_all(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        try:
            ws.reset_dimensions()
        except Exception:
            pass
        return [["" if c is None else str(c) for c in r] for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()


def header_kind(header):
    """헤더만 보고 양식을 알아본다: 'stat_product'(문구 상품마스터) / 'book'(cmdtCode 양식) / None."""
    h = {str(x).strip() for x in header}
    if "cmdt_code" in h and ("sale_unpr" in h or "cmdt_dvsn_code" in h):
        return "stat_product"
    if "cmdtCode" in h:
        return "book"
    return None


def read_master(path, kind, is_ledger, progress=None):
    """파일을 읽어 저장용 dict 목록을 돌려준다.
    kind: '도서'|'문구'. 양식이 고른 구분과 안 맞으면 ValueError(사용자에게 그대로 보여줄 문장)."""
    allrows = _read_xlsx_all(path) if path.lower().endswith(".xlsx") else _read_csv_all(path)
    if not allrows:
        return []
    header = [str(x).strip() for x in allrows[0]]
    fmt = header_kind(header)
    if kind == KIND_STAT and not is_ledger and fmt != "stat_product":
        raise ValueError("문구 상품마스터 양식이 아닙니다.\n(헤더: rdp_code, cmdt_code, sale_unpr, cmdt_dvsn_code, cmdt_code_kind_code, cmdt_name)\n"
                         "도서 파일이면 '도서' 버튼으로 불러오세요.")
    if kind == KIND_BOOK and fmt == "stat_product":
        raise ValueError("문구 상품마스터 양식입니다. '문구' 버튼으로 불러오세요.")
    if fmt is None:
        raise ValueError("마스터 양식을 알 수 없습니다. 첫 줄(헤더)을 확인하세요.")

    use_stat_cols = (fmt == "stat_product")
    cols = STAT_COLS if use_stat_cols else BOOK_COLS
    idx = []
    for cands in cols:
        found = None
        for i, h in enumerate(header):
            if h in cands:
                found = i
                break
        idx.append(found)
    # 문구는 rdp_code가 맨 앞에 추가돼 있으므로 바코드 칸 번호를 따로 잡는다.
    bi = 1 if use_stat_cols else 0
    if idx[bi] is None:
        raise ValueError("바코드 열(cmdtCode / cmdt_code)을 찾지 못했습니다.")

    def g(r, k):
        i = idx[k]
        return r[i].strip() if (i is not None and i < len(r) and r[i] is not None) else ""

    out = []
    n = 0
    for r in allrows[1:]:
        n += 1
        if progress is not None and n % 5000 == 0:
            progress.check_cancel()
            progress(done=n, total=0)
        if not r:
            continue
        code = g(r, bi)
        if not code:
            continue
        code = bc13(code)
        if use_stat_cols:
            out.append(dict(isbn=code, book_name=g(r, 2), category="", publisher="",
                            rcds=0, real=0, missing=0, rcds_x=0, real_x=0, missing_x=0, exc="N", rdp=g(r, 0),
                            price=to_int(g(r, 3)), dvsn=g(r, 4), kcode=g(r, 5)))
        else:
            exc = g(r, 7).upper()
            out.append(dict(isbn=code, book_name=g(r, 1), category=g(r, 2), publisher=g(r, 3),
                            rcds=to_int(g(r, 4)), real=to_int(g(r, 5)), missing=to_int(g(r, 6)),
                            rcds_x=int(is_x(g(r, 4))), real_x=int(is_x(g(r, 5))), missing_x=int(is_x(g(r, 6))),
                            exc=exc if exc in ("Y", "X") else "N", rdp="", price=0, dvsn="", kcode=""))
    return out


def save_master(table, store_code, kind, rows, progress=None):
    """table: 'books' | 'ledger_master'. 같은 점포의 같은 구분(kind) 행만 지우고 새로 넣는다."""
    from . import db as dbmod
    assert table in ("books", "ledger_master")
    total = len(rows)
    conn = dbmod.get_conn()
    try:
        if progress is not None:
            progress(message=f"{kind} 마스터 저장 중...", done=0, total=total, unit="count")
        conn.execute(f"DELETE FROM {table} WHERE store_code=? AND kind=?", (store_code, kind))
        sql = (f"INSERT INTO {table}(store_code, isbn, book_name, category, publisher, rcds_qty, real_qty, "
               "missing_qty, except_flag, kind, price, dvsn_code, kind_code, rdp_code, rcds_x, real_x, missing_x) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
               "ON CONFLICT(store_code, isbn) DO UPDATE SET book_name=excluded.book_name, "
               "category=excluded.category, publisher=excluded.publisher, rcds_qty=excluded.rcds_qty, "
               "real_qty=excluded.real_qty, missing_qty=excluded.missing_qty, except_flag=excluded.except_flag, "
               "kind=excluded.kind, price=excluded.price, dvsn_code=excluded.dvsn_code, kind_code=excluded.kind_code, rdp_code=excluded.rdp_code, "
               "rcds_x=excluded.rcds_x, real_x=excluded.real_x, missing_x=excluded.missing_x")
        BATCH = 5000
        for i in range(0, total, BATCH):
            if progress is not None:
                progress.check_cancel()
            chunk = [(store_code, r["isbn"], r["book_name"], r["category"], r["publisher"], r["rcds"], r["real"],
                      r["missing"], r["exc"], kind, r["price"], r["dvsn"], r["kcode"], r["rdp"],
                      r.get("rcds_x", 0), r.get("real_x", 0), r.get("missing_x", 0)) for r in rows[i:i + BATCH]]
            conn.executemany(sql, chunk)
            if progress is not None:
                progress(done=min(i + BATCH, total))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return total


def kind_counts(table, store_code):
    from . import db as dbmod
    conn = dbmod.get_conn()
    try:
        return {r[0] or KIND_BOOK: r[1] for r in conn.execute(
            f"SELECT kind, COUNT(*) FROM {table} WHERE store_code=? GROUP BY kind", (store_code,))}
    finally:
        conn.close()
