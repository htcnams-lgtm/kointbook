# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""실사데이터 txt 복원 - 파일 읽기 / 미리보기 / DB 반영 (화면 없는 순수 로직).

[2026-10-11] "데이터백업 하위메뉴로 복원하는 기능으로 재집계 txt 양식을 불러서
실사데이터로 복구하고 싶다"(요청). 이 파일은 그 화면(screen_data_restore_txt.py)이
쓰는 읽기/검사/저장 부분이다.

파일 양식 (탭 구분, 줄바꿈 CRLF, 글자 CP949 또는 UTF-8, 머리글 없음, 16열)
--------------------------------------------------------------------------
 열(0부터)  내용
   0       AREA
   1       SECTION
   2       단
   3       열
   4       바코드
   5       수량 (1.0 처럼 소수점이 붙어 있어도 정수로 읽는다)
   6       (비어 있음 - 쓰지 않음)
   7       자사코드 (쓰지 않음)
   8       상품명
   9       점포코드 (비어 있을 수 있다 - 비어 있으면 화면에서 직접 고른다)
  10       (비어 있음 - 쓰지 않음)
  11       (조사 연도로 보이는 값, 예 2026 - 쓰지 않음)
  12       작업자코드
  13       작업자명
  14       날짜 (YYYYMMDD)
  15       시각 (HHMMSS)
서가번호 정보는 파일에 없으므로 서가번호는 빈칸으로 저장한다.

저장 규칙
---------
- 실사 줄은 파일의 줄 수 그대로(수량 합계도 그대로) stock_counts에 넣는다.
- 점포마스터/작업자마스터/상품마스터는 "없는 것만 추가"하고 이미 있는 값은 절대
  고치지 않는다(전산재고·실재고·예외여부도 건드리지 않는다. 장부마스터도 안 건드림).
- 같은 점포+조사일자에 이미 실사데이터가 있으면 mode로 정한다:
    stop    : 중단(기본) / replace : 기존 것을 지우고 복원 / append : 기존 것에 추가
- 한 번에(트랜잭션) 반영하고, 중간에 오류가 나면 전부 되돌린다.
"""

import os
import re
from collections import Counter, OrderedDict

from . import db as dbmod

EXPECTED_COLS = 16
COL_AREA, COL_SECTION, COL_DAN, COL_YEOL, COL_BARCODE, COL_QTY = 0, 1, 2, 3, 4, 5
COL_NAME, COL_STORE, COL_WCODE, COL_WNAME, COL_DATE, COL_TIME = 8, 9, 12, 13, 14, 15

MODES = ("stop", "replace", "append")


class RestoreError(Exception):
    """사용자에게 그대로 보여줘도 되는 오류 설명."""


def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise RestoreError("글자 인코딩을 읽을 수 없습니다. (UTF-8 또는 CP949 텍스트 파일만 지원합니다)")


def _norm_area(v):
    v = (v or "").strip()
    return v.zfill(2) if v.isdigit() and len(v) < 2 else v


def parse_file(path):
    """txt를 읽어서 {"rows": [...], "errors": [(줄번호, 이유)], "encoding": ..., "file": 파일명}.

    잘못된 줄은 rows에 넣지 않고 errors에 모아 둔다(화면에서 오류 줄이 있으면 복원을 막는다 -
    일부만 조용히 빠지는 것보다 알려주고 멈추는 쪽이 안전하다)."""
    text, enc = read_text(path)
    rows, errors = [], []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        f = line.split("\t")
        if len(f) < COL_TIME:  # 시각 열 앞까지는 있어야 한다
            errors.append((n, f"열이 {len(f)}개입니다 ({EXPECTED_COLS}열 양식이 아닙니다)"))
            continue
        f += [""] * (EXPECTED_COLS - len(f))
        isbn = f[COL_BARCODE].strip()
        if not isbn:
            errors.append((n, "바코드가 비어 있습니다"))
            continue
        try:
            q = float(f[COL_QTY].strip())
        except ValueError:
            errors.append((n, f"수량을 읽을 수 없습니다: {f[COL_QTY]!r}"))
            continue
        if abs(q - round(q)) > 1e-9:
            errors.append((n, f"수량이 정수가 아닙니다: {f[COL_QTY]!r}"))
            continue
        d = f[COL_DATE].strip()
        if not re.fullmatch(r"\d{8}", d):
            errors.append((n, f"날짜가 YYYYMMDD 형식이 아닙니다: {d!r}"))
            continue
        t = f[COL_TIME].strip()
        if t and not re.fullmatch(r"\d{1,6}", t):
            errors.append((n, f"시각이 HHMMSS 형식이 아닙니다: {t!r}"))
            continue
        t = (t or "0").zfill(6)
        rows.append({
            "area": _norm_area(f[COL_AREA]),
            "section": f[COL_SECTION].strip(),
            "shelf_no": "",
            "dan": f[COL_DAN].strip(),
            "yeol": f[COL_YEOL].strip(),
            "isbn": isbn,
            "book_name": f[COL_NAME].strip(),
            "qty": int(round(q)),
            "file_store_code": f[COL_STORE].strip(),
            "worker_code": f[COL_WCODE].strip(),
            "worker_name": f[COL_WNAME].strip(),
            "date": d,
            "received_at": f"{d[:4]}-{d[4:6]}-{d[6:8]} {t[:2]}:{t[2:4]}:{t[4:6]}",
        })
    return {"rows": rows, "errors": errors, "encoding": enc, "file": os.path.basename(str(path))}


def file_workers(rows):
    """파일에 나온 작업자: {코드: 이름}(코드마다 처음 나온 이름) + 이름이 여러 개인 코드 목록."""
    names = OrderedDict()
    for r in rows:
        c = r["worker_code"]
        if not c:
            continue
        names.setdefault(c, Counter())[r["worker_name"]] += 1
    out, multi = OrderedDict(), []
    for c, cnt in names.items():
        nm = [k for k, _ in cnt.most_common() if k]
        out[c] = nm[0] if nm else ""
        if len(nm) > 1:
            multi.append(c)
    return out, multi


def file_products(rows):
    """파일에 나온 바코드: {바코드: 상품명(처음 나온 비어 있지 않은 이름)}."""
    out = OrderedDict()
    for r in rows:
        if r["isbn"] not in out or (not out[r["isbn"]] and r["book_name"]):
            out[r["isbn"]] = r["book_name"]
    return out


def analyze(parsed, store_code, survey_date, conn=None):
    """미리보기 숫자. DB와 비교하는 값(새 작업자/새 바코드/기존 실사 건수)은 점포코드가 있을 때만 채운다."""
    rows = parsed["rows"]
    own = conn is None
    if own:
        conn = dbmod.get_conn()
    try:
        info = {
            "file": parsed["file"], "encoding": parsed["encoding"], "n_rows": len(rows),
            "n_errors": len(parsed["errors"]), "errors": parsed["errors"][:20],
            "total_qty": sum(r["qty"] for r in rows),
            "n_area": len({r["area"] for r in rows}), "n_section": len({(r["area"], r["section"]) for r in rows}),
            "dates": Counter(r["date"] for r in rows),
            "file_store_codes": sorted({r["file_store_code"] for r in rows if r["file_store_code"]}),
        }
        workers, multi = file_workers(rows)
        products = file_products(rows)
        info["workers"], info["workers_multi_name"] = workers, multi
        info["n_products"] = len(products)
        db_workers = {r["worker_code"]: r["worker_name"] for r in conn.execute("SELECT worker_code, worker_name FROM workers")}
        info["workers_new"] = [c for c in workers if c not in db_workers]
        info["workers_name_diff"] = [(c, db_workers[c], workers[c]) for c in workers
                                     if c in db_workers and workers[c] and (db_workers[c] or "") != workers[c]]
        info["products_new"] = 0
        info["existing_rows"] = info["existing_qty"] = info["same_source_rows"] = 0
        info["store_known"] = False
        if store_code:
            known = {r[0] for r in conn.execute("SELECT isbn FROM books WHERE store_code=?", (store_code,))}
            info["products_new"] = sum(1 for b in products if b not in known)
            info["store_known"] = conn.execute("SELECT 1 FROM stores WHERE store_code=?", (store_code,)).fetchone() is not None
            if survey_date:
                r = conn.execute("SELECT COUNT(*), COALESCE(SUM(qty),0) FROM stock_counts WHERE store_code=? AND survey_date=?",
                                 (store_code, survey_date)).fetchone()
                info["existing_rows"], info["existing_qty"] = r[0], r[1]
                info["same_source_rows"] = conn.execute(
                    "SELECT COUNT(*) FROM stock_counts WHERE store_code=? AND survey_date=? AND source_file=?",
                    (store_code, survey_date, parsed["file"])).fetchone()[0]
        return info
    finally:
        if own:
            conn.close()


def apply_restore(parsed, store_code, store_name, survey_date, mode="stop",
                  add_workers=True, add_products=True, progress=None):
    """파일 내용을 DB에 반영한다. 반환: 처리 결과 숫자 딕셔너리. 실패하면 전부 되돌리고 예외."""
    if mode not in MODES:
        raise RestoreError(f"알 수 없는 방식입니다: {mode}")
    if parsed["errors"]:
        raise RestoreError(f"형식이 맞지 않는 줄이 {len(parsed['errors'])}건 있어 복원하지 않았습니다.")
    rows = parsed["rows"]
    if not rows:
        raise RestoreError("복원할 줄이 없습니다.")
    store_code = (store_code or "").strip()
    store_name = (store_name or "").strip()
    if not store_code:
        raise RestoreError("점포코드를 입력해 주세요.")
    if not re.fullmatch(r"\d{8}", survey_date or ""):
        raise RestoreError("조사일자는 YYYYMMDD 8자리로 입력해 주세요.")

    conn = dbmod.get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        res = {"deleted": 0, "inserted": 0, "qty": 0, "workers_added": 0, "products_added": 0, "store_added": False}

        existing = cur.execute("SELECT COUNT(*) FROM stock_counts WHERE store_code=? AND survey_date=?",
                               (store_code, survey_date)).fetchone()[0]
        if existing and mode == "stop":
            raise RestoreError(f"[{store_code}] {survey_date}에 이미 실사데이터 {existing:,}건이 있습니다. "
                               "'기존 데이터 삭제 후 복원' 또는 '기존 데이터에 추가'를 골라 주세요.")
        if existing and mode == "replace":
            cur.execute("DELETE FROM stock_counts WHERE store_code=? AND survey_date=?", (store_code, survey_date))
            res["deleted"] = cur.rowcount

        if cur.execute("SELECT 1 FROM stores WHERE store_code=?", (store_code,)).fetchone() is None:
            cur.execute("INSERT INTO stores(store_code, store_name) VALUES (?,?)", (store_code, store_name or store_code))
            res["store_added"] = True
        elif not store_name:
            r = cur.execute("SELECT store_name FROM stores WHERE store_code=?", (store_code,)).fetchone()
            store_name = (r[0] if r else "") or store_code
        if not store_name:
            store_name = store_code

        if add_workers:
            for code, name in file_workers(rows)[0].items():
                if cur.execute("SELECT 1 FROM workers WHERE worker_code=?", (code,)).fetchone() is None:
                    cur.execute("INSERT INTO workers(worker_code, worker_name) VALUES (?,?)", (code, name))
                    res["workers_added"] += 1

        if add_products:
            known = {r[0] for r in cur.execute("SELECT isbn FROM books WHERE store_code=?", (store_code,))}
            new = [(store_code, b, nm, "", "", 0, 0, 0, "N") for b, nm in file_products(rows).items() if b not in known]
            if new:
                cur.executemany("INSERT INTO books(store_code, isbn, book_name, category, publisher, rcds_qty, real_qty, "
                                "missing_qty, except_flag) VALUES (?,?,?,?,?,?,?,?,?)", new)
            res["products_added"] = len(new)

        total = len(rows)
        if progress is not None:
            progress(message="실사데이터를 저장하는 중...", done=0, total=total, unit="건")
        src = parsed["file"]
        step = 2000
        for i in range(0, total, step):
            chunk = rows[i:i + step]
            cur.executemany(
                "INSERT INTO stock_counts(store_code, store_name, survey_date, area, section, shelf_no, dan, yeol, isbn, "
                "book_name, qty, worker_code, worker_name, received_at, source_file) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(store_code, store_name, survey_date, r["area"], r["section"], r["shelf_no"], r["dan"], r["yeol"], r["isbn"],
                  r["book_name"], r["qty"], r["worker_code"], r["worker_name"], r["received_at"], src) for r in chunk])
            if progress is not None:
                progress(done=min(total, i + step))
                progress.check_cancel()
        res["inserted"] = total
        res["qty"] = sum(r["qty"] for r in rows)
        res["store_name"] = store_name
        conn.commit()
    except BaseException:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()
    dbmod.bump_stock_version()
    dbmod.analyze_in_background()
    return res
