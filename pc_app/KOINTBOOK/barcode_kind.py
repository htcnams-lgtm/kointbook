# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
도서 AREA에 문구 상품, 문구 AREA에 도서 상품이 들어가는 것을 막기 위한 바코드 종류 판정. [2026-10-16]

PDA(BarcodeKind.kt)와 같은 규칙이다: 상품마스터를 [도서 불러오기]/[문구 불러오기]로 따로 불러오면
books.kind에 '도서'/'문구'가 붙는다. 이 구분을 AREA의 구분과 비교한다.
  - 마스터에 없는 바코드(미등록)는 도서인지 문구인지 알 수 없으므로 여기서는 막지 않는다
    (기존 [미등록상품] 설정 허용/경고/차단이 처리한다).
AREA의 구분은 scope.kind_of_area(도서 10~19·90~99 / 문구 20~29·80~89)를 쓴다. 허용 밖 AREA는
구분할 수 없으므로 통과시킨다(그쪽은 AREA 검사가 따로 막는다).
이 모듈은 tkinter를 쓰지 않는다.
"""

from . import scope
from .masters import bc13, norm_barcode

KIND_BOOK = "도서"
KIND_STAT = "문구"


def _variants(code):
    """마스터 조회용 바코드 표기들: 그대로 / 13자리 0채움 / 앞 0 뗀 형태."""
    c = str(code or "").strip()
    out = []
    for v in (c, bc13(c), norm_barcode(c)):
        if v and v not in out:
            out.append(v)
    return out


def master_kinds(conn, store_code, code):
    """상품마스터에서 이 바코드의 구분 집합({'도서'}, {'문구'}, 둘 다, 또는 없으면 빈 집합)."""
    vs = _variants(code)
    if not vs:
        return set()
    q = ",".join("?" * len(vs))
    rows = conn.execute(
        f"SELECT DISTINCT kind FROM books WHERE store_code=? AND isbn IN ({q})", (store_code, *vs)
    ).fetchall()
    if not rows and any(ch.isalpha() for ch in vs[0]):
        # ISBN-10 끝자리 X 같은 영문은 대소문자만 다르게 들어올 수 있다(PK 색인은 대소문자 구분이라 따로 한 번 더).
        rows = conn.execute(
            f"SELECT DISTINCT kind FROM books WHERE store_code=? AND isbn COLLATE NOCASE IN ({q})",
            (store_code, *vs)
        ).fetchall()
    return {r[0] or KIND_BOOK for r in rows}


def bulk_master_kinds(conn, store_code, codes):
    """여러 바코드의 마스터 구분을 한꺼번에 찾는다(수신 자료처럼 수만 건을 검사할 때 조회 횟수를 줄이려고).
    돌려주는 값: {바코드: 구분 집합} (마스터에 없으면 빈 집합)."""
    codes = {str(c or "").strip() for c in codes}
    codes.discard("")
    var_of = {c: _variants(c) for c in codes}
    all_vars = sorted({v for vs in var_of.values() for v in vs})
    found = {}
    for i in range(0, len(all_vars), 800):
        chunk = all_vars[i:i + 800]
        q = ",".join("?" * len(chunk))
        for isbn, kind in conn.execute(
                f"SELECT isbn, kind FROM books WHERE store_code=? AND isbn IN ({q})", (store_code, *chunk)):
            found.setdefault(isbn, set()).add(kind or KIND_BOOK)
    out = {}
    for c, vs in var_of.items():
        ks = set()
        for v in vs:
            ks |= found.get(v, set())
        if not ks and any(ch.isalpha() for ch in c):
            ks = master_kinds(conn, store_code, c)   # 대소문자만 다른 경우
        out[c] = ks
    return out


def _evaluate(area, code, kinds):
    """AREA 구분과 바코드 구분이 다르면 정보 dict, 아니면 None. kinds는 마스터에서 찾은 구분 집합.
    마스터에 없으면(빈 집합) 구분할 수 없어 None(통과)."""
    area_kind = scope.kind_of_area(area)
    if area_kind is None or not code or not kinds:
        return None
    if area_kind in kinds:
        return None
    return dict(area=str(area or ""), area_kind=area_kind, item_kind=sorted(kinds)[0], code=code)


def check(conn, store_code, area, code):
    """AREA의 구분과 바코드의 구분이 다르면 정보 dict, 맞으면(또는 AREA 구분 불가면) None."""
    code = str(code or "").strip()
    return _evaluate(area, code, master_kinds(conn, store_code, code))


def check_many(conn, store_code, pairs):
    """pairs = [(area, code), ...] -> 같은 순서의 [정보 dict 또는 None, ...]."""
    codes = [str(c or "").strip() for _a, c in pairs]
    km = bulk_master_kinds(conn, store_code, codes)
    return [_evaluate(a, c, km.get(c, set())) for (a, _c), c in zip(pairs, codes)]


def master_name(conn, store_code, code):
    """안내문에 보여줄 상품명(마스터에 있으면), 없으면 빈 문자열."""
    vs = _variants(code)
    if not vs:
        return ""
    q = ",".join("?" * len(vs))
    row = conn.execute(
        f"SELECT book_name FROM books WHERE store_code=? AND isbn IN ({q}) LIMIT 1", (store_code, *vs)
    ).fetchone()
    return (row[0] or "") if row else ""


def basis_text(m):
    return f"판정 근거: 상품마스터({m['item_kind']})"


def message(m, name=""):
    """등록/수정 화면에 띄울 안내문."""
    lines = [f"{m['item_kind']} 상품입니다. 입력 금지",
             "",
             f"{m['area_kind']} AREA({m['area']})에는 {m['item_kind']} 상품을 입력할 수 없습니다.",
             f"바코드: {m['code']}"]
    if name:
        lines.append(f"상품명: {name}")
    lines.append(basis_text(m))
    return "\n".join(lines)


def short(m):
    """목록/요약용 한 줄: '도서 AREA 10 ← 문구 상품'"""
    return f"{m['area_kind']} AREA {m['area']} ← {m['item_kind']} 상품({m['code']})"
