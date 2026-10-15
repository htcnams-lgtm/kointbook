# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
[2026-10-13] 서적/문구 구분 범위 (자료생성 그룹의 모든 화면이 같이 쓴다).

서적과 문구는 매장에서 AREA 또는 SECTION 범위로 나뉘어 있다. 그래서 구분마다
"AREA 몇 번~몇 번 / SECTION 몇 번~몇 번"을 한 번 정해 두면(자료생성 화면들의 [범위설정]),
재고조사 보고서·재고조사 차이내역·자료생성·AREA별 합산에서 구분(전체/서적/문구)만
고르는 것으로 그 범위의 자료만 조회·출력·엑셀저장·생성한다. 범위는 DB(app_settings)에
저장되어 백업/복원에도 같이 따라간다.

 - 범위 칸을 비우면 그 방향은 제한 없음(AREA만 정하거나 SECTION만 정해도 된다).
 - AREA와 SECTION을 둘 다 정하면 둘 다 만족하는 자료만(AND).
 - 한 구분만 범위를 정했으면 나머지 구분은 "그 범위 밖 전부"로 본다.
 - 둘 다 정하지 않았으면 구분을 알 수 없어서, 자료생성은 바코드가 문구 상품마스터에
   있는지로 나누고, 다른 화면은 범위 설정을 먼저 요청한다.
"""

from . import db as dbmod

KINDS = ("서적", "문구")
FIELDS = ("af", "at", "sf", "st")  # AREA 시작/끝, SECTION 시작/끝


def _key(kind, f):
    return f"scope_{kind}_{f}"


def get_range(kind):
    return {f: (dbmod.get_setting(_key(kind, f), "") or "").strip() for f in FIELDS}


def set_range(kind, **vals):
    for f in FIELDS:
        v = "".join(ch for ch in str(vals.get(f, "")) if ch.isdigit())
        dbmod.set_setting(_key(kind, f), v)


def is_defined(kind):
    return any(get_range(kind).values())


def _num(v, default=None):
    return int(v) if str(v).isdigit() else default


def _digits(v):
    d = "".join(ch for ch in str(v or "") if ch.isdigit())
    return int(d) if d else None


def in_range(rng, area, section):
    """rng 범위 안에 (area, section)이 있나. 숫자가 아닌 AREA/SECTION은 범위 밖으로 본다."""
    a, s = _digits(area), _digits(section)
    af, at, sf, st = (_num(rng[k]) for k in FIELDS)
    if (af is not None or at is not None) and a is None:
        return False
    if (sf is not None or st is not None) and s is None:
        return False
    if af is not None and a < af:
        return False
    if at is not None and a > at:
        return False
    if sf is not None and s < sf:
        return False
    if st is not None and s > st:
        return False
    return True


def classify(area, section):
    """범위만으로 구분을 정한다: '서적' | '문구' | None(범위가 하나도 없어 알 수 없음)."""
    d = {k: is_defined(k) for k in KINDS}
    if not any(d.values()):
        return None
    if d["문구"] and in_range(get_range("문구"), area, section):
        return "문구"
    if d["서적"] and in_range(get_range("서적"), area, section):
        return "서적"
    return "서적" if d["문구"] else "문구"


def matches(kind, area, section):
    """kind가 '전체'면 항상 True. 범위가 없어 알 수 없으면 True(걸러내지 않음)."""
    if kind not in KINDS:
        return True
    c = classify(area, section)
    return True if c is None else (c == kind)


def _cond_for(rng):
    conds, params = [], []
    af, at, sf, st = (_num(rng[k]) for k in FIELDS)
    if af is not None:
        conds.append("CAST(area AS INTEGER) >= ?"); params.append(af)
    if at is not None:
        conds.append("CAST(area AS INTEGER) <= ?"); params.append(at)
    if sf is not None:
        conds.append("CAST(section AS INTEGER) >= ?"); params.append(sf)
    if st is not None:
        conds.append("CAST(section AS INTEGER) <= ?"); params.append(st)
    return conds, params


def sql_cond(kind):
    """stock_counts WHERE 뒤에 붙일 (' AND ...', params). kind가 '전체'이거나 범위로 알 수
    없으면 ('', [])를 돌려준다. (SQL로는 숫자 아닌 AREA/SECTION도 숫자 0으로 읽히는 점은 감수)"""
    if kind not in KINDS or not any(is_defined(k) for k in KINDS):
        return "", []
    other = "서적" if kind == "문구" else "문구"
    if is_defined(kind):
        conds, params = _cond_for(get_range(kind))
        # 문구/서적 둘 다 정했고 겹치면 문구 우선 (classify와 같은 규칙)
        if kind == "서적" and is_defined("문구"):
            oc, op = _cond_for(get_range("문구"))
            if oc:
                conds = conds + [f"NOT ({' AND '.join(oc)})"]
                params = params + op
        return (" AND " + " AND ".join(conds), params) if conds else ("", [])
    oc, op = _cond_for(get_range(other))
    return (f" AND NOT ({' AND '.join(oc)})", op) if oc else ("", [])


def describe(kind):
    r = get_range(kind)
    parts = []
    if r["af"] or r["at"]:
        parts.append(f"AREA {r['af'] or '처음'}~{r['at'] or '끝'}")
    if r["sf"] or r["st"]:
        parts.append(f"SECTION {r['sf'] or '처음'}~{r['st'] or '끝'}")
    return ", ".join(parts) if parts else "범위 미설정"


def tag(kind):
    """파일명에 붙일 표시: 서적전용 / 문구전용 / ''(전체)"""
    return f"{kind}전용" if kind in KINDS else ""


def matches_area(kind, area):
    """AREA만 보고 구분에 속하는지(AREA별 합산처럼 SECTION이 없는 화면용).
    구분 범위가 SECTION으로만 정해져 있으면 AREA로는 가를 수 없어 True."""
    if kind not in KINDS:
        return True
    d = {k: is_defined(k) for k in KINDS}
    if not any(d.values()):
        return True

    def area_only(k):
        r = dict(get_range(k)); r["sf"] = r["st"] = ""
        return r, bool(r["af"] or r["at"])
    rk, has_k = area_only(kind)
    other = "서적" if kind == "문구" else "문구"
    ro, has_o = area_only(other)
    if d[kind]:
        if not has_k:
            return True
        if kind == "서적" and d["문구"] and has_o and in_range(ro, area, 0):
            return False
        return in_range(rk, area, 0)
    return True if not has_o else not in_range(ro, area, 0)
