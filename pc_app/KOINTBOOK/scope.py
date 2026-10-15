# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
서적/문구 구분. [2026-10-15 개편] 예전에는 자료생성 화면마다 [범위설정]으로 AREA/SECTION 범위를
정했지만, 이제 AREA 번호로 고정한다(PDA·PC 공통):

    서적 : AREA 10~19, 90~99
    문구 : AREA 20~29, 80~89
    그 외 AREA는 쓸 수 없다(PDA 위치입력, PC 실적관리 등록/수정에서 경고 후 불가).

문구는 서가번호가 없어 PDA가 고정값 X로 저장한다. SECTION은 구분에 쓰지 않는다.
재고조사 보고서·차이내역·자료생성·AREA별 합산의 [구분: 전체/서적/문구]는 이 기준으로
조회·출력·생성한다. (함수 이름과 인자는 예전과 같게 두어 화면 코드는 그대로 쓴다.)
"""

KINDS = ("서적", "문구")
FIELDS = ("af", "at", "sf", "st")  # (예전 호환용, 쓰지 않음)

AREA_RANGES = {
    "서적": ((10, 19), (90, 99)),
    "문구": ((20, 29), (80, 89)),
}
AREA_RULE_TEXT = "서적 10~19, 90~99 / 문구 20~29, 80~89"
STATIONERY_SHELF_NO = "X"


def _area_num(area):
    d = "".join(ch for ch in str(area or "") if ch.isdigit())
    return int(d) if d else None


def kind_of_area(area):
    """AREA로 '서적' | '문구' | None(허용되지 않는 AREA)."""
    a = _area_num(area)
    if a is None:
        return None
    for kind, ranges in AREA_RANGES.items():
        if any(lo <= a <= hi for lo, hi in ranges):
            return kind
    return None


def is_valid_area(area):
    return kind_of_area(area) is not None


def invalid_area_message():
    return f"사용할 수 없는 AREA입니다.\n({AREA_RULE_TEXT})"


def is_defined(kind):
    return True


def classify(area, section=None):
    """'서적' | '문구' | None(허용 안 되는 AREA — 예전에 입력된 자료일 수 있음)."""
    return kind_of_area(area)


def matches(kind, area, section=None):
    """kind가 '전체'면 항상 True."""
    if kind not in KINDS:
        return True
    return kind_of_area(area) == kind


def matches_area(kind, area):
    return matches(kind, area)


def _cond_for(kind):
    parts, params = [], []
    for lo, hi in AREA_RANGES[kind]:
        parts.append("(CAST(area AS INTEGER) BETWEEN ? AND ?)")
        params += [lo, hi]
    return "(" + " OR ".join(parts) + ")", params


def sql_cond(kind):
    """stock_counts WHERE 뒤에 붙일 (' AND ...', params). 전체면 ('', [])."""
    if kind not in KINDS:
        return "", []
    cond, params = _cond_for(kind)
    return " AND " + cond, params


def describe(kind):
    rs = AREA_RANGES.get(kind)
    return "AREA " + ", ".join(f"{lo}~{hi}" for lo, hi in rs) if rs else ""


def tag(kind):
    """파일명에 붙일 표시: 서적전용 / 문구전용 / ''(전체)"""
    return f"{kind}전용" if kind in KINDS else ""
