# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
점포/작업자/도서(상품) 마스터를 PDA로 보내는 공용 로직 (USB adb 전용).

ZZOINT의 master_sync.py에서 Firestore(인터넷) 전송 부분을 뺀 버전이다.
KOINTBOOK은 별도 서버 없이, 현장에서 USB로 연결한 PDA에만 adb pull/push로
자료를 주고받는 것을 기본 방식으로 삼는다. 각 함수는 progress(선택)를
받아 진행률 팝업과 연동할 수 있다 (progress_dialog.run_with_progress 참고).
이 모듈은 tkinter를 쓰지 않는다.
"""

import os
import sqlite3
import tempfile

from . import db as dbmod
from . import adb_utils
from .progress_core import Cancelled, report

_INSERT_BATCH = 5000


def _build_sqlite_file(tmp_path, create_sql, insert_sql, cursor, total, progress, label):
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    out = sqlite3.connect(tmp_path)
    try:
        out.execute("PRAGMA journal_mode=OFF")
        out.execute("PRAGMA synchronous=OFF")
        out.execute(create_sql)
        done = 0
        report(progress, message=label, done=0, total=total, unit="count")
        while True:
            rows = cursor.fetchmany(_INSERT_BATCH)
            if not rows:
                break
            out.executemany(insert_sql, rows)
            done += len(rows)
            report(progress, done=done, total=total)
            if progress is not None:
                progress.check_cancel()
        out.commit()
    finally:
        out.close()


def push_stores(progress=None):
    """점포마스터 전체를 STORE.db로 만들어 PDA에 전송. (성공여부, 메시지, 건수) 반환."""
    conn = dbmod.get_conn()
    conn.row_factory = None
    total = conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0]
    cur = conn.execute("SELECT store_code, store_name FROM stores")
    tmp_path = os.path.join(tempfile.gettempdir(), "STORE.db")
    try:
        _build_sqlite_file(
            tmp_path, "CREATE TABLE store_data (store_code TEXT, store_name TEXT)",
            "INSERT INTO store_data VALUES (?,?)", cur, total, progress, "점포마스터 파일 만드는 중..."
        )
    finally:
        conn.close()
    ok, msg = adb_utils.push_file(tmp_path, "STORE.db", progress)
    return ok, msg, total


def push_workers(progress=None):
    """작업자마스터 전체를 WORKER.db로 만들어 PDA에 전송."""
    conn = dbmod.get_conn()
    conn.row_factory = None
    total = conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
    cur = conn.execute("SELECT worker_code, worker_name FROM workers")
    tmp_path = os.path.join(tempfile.gettempdir(), "WORKER.db")
    try:
        _build_sqlite_file(
            tmp_path, "CREATE TABLE worker_data (worker_code TEXT, worker_name TEXT)",
            "INSERT INTO worker_data VALUES (?,?)", cur, total, progress, "작업자마스터 파일 만드는 중..."
        )
    finally:
        conn.close()
    ok, msg = adb_utils.push_file(tmp_path, "WORKER.db", progress)
    return ok, msg, total


class _PdaBookRows:
    """books 조회 결과를 PDA용 5열(book_data)로 바꿔 내보낸다.
    바코드는 13자리(0000000000001)로 보내고, 앞 0을 뗀 바코드(1)도 한 줄 더 보낸다
    (스캐너는 앞 0 없이 읽는 일이 있고, PDA는 바코드가 정확히 같아야 상품을 찾기 때문)."""

    def __init__(self, cursor):
        self._cur = cursor
        self._pending = []

    @staticmethod
    def _forms(isbn):
        from .masters import bc13
        s = bc13(isbn)
        t = s.lstrip("0")
        return [s] + ([t] if t and t != s else [])

    @staticmethod
    def extra_count(conn, store_code):
        n = 0
        for (isbn,) in conn.execute("SELECT isbn FROM books WHERE store_code=?", (store_code,)):
            n += len(_PdaBookRows._forms(isbn)) - 1
        return n

    def fetchmany(self, size):
        out = self._pending
        self._pending = []
        while len(out) < size:
            rows = self._cur.fetchmany(size)
            if not rows:
                break
            for sc, isbn, name, cat, pub, kind in rows:
                for f in self._forms(isbn):
                    out.append((sc, f, name, cat, pub))
        if len(out) > size:
            self._pending = out[size:]
            out = out[:size]
        return out


def push_books(store_code: str, progress=None):
    """지정한 점포의 상품(도서)마스터를 BOOK.db로 만들어 PDA에 전송.

    [2026-09-23 정정] 상품마스터를 아직 안 불러온 상태(0건)나 PDA가 연결되어
    있지 않은 상태에서 눌러도, adb 통신을 시도하지도 않은 채 "0건 전송
    되었습니다"처럼 성공한 것처럼 보이는 애매한 메시지가 나가는 문제가
    있었다 - 실제 파일 전송을 시도하기 전에 먼저 두 가지를 순서대로
    확인해서, 어느 쪽이 문제인지 명확하게 알려준다."""
    conn = dbmod.get_conn()
    conn.row_factory = None
    total = conn.execute("SELECT COUNT(*) FROM books WHERE store_code=?", (store_code,)).fetchone()[0]
    if total == 0:
        conn.close()
        return False, "상품마스터가 없습니다. 먼저 [파일선택변환]으로 상품마스터를 불러오세요.", 0

    ok_dev, msg_dev = adb_utils.check_device_connected()
    if not ok_dev:
        conn.close()
        return False, msg_dev, 0

    # [2026-09-29] "pda 복원(수신) 전송시 점포코드는 바뀌나 점포명이 pda에서
    # 바뀌지 않음" - 상품(도서)마스터만 따로 PDA전송하면(점포마스터를 같이
    # 안 보내면) PDA가 새 점포코드는 받아도 그 점포명을 몰라서, 화면에는
    # 전에 갖고 있던 엉뚱한 점포명이 그대로 남아있었다. 그래서 지금 보내는
    # store_code의 점포명을 BOOK.db 안에 작은 메타 표로 같이 담아 보내서,
    # 점포마스터를 따로 안 받았어도 PDA가 이 점포명을 바로 알 수 있게 한다.
    store_name_row = conn.execute(
        "SELECT store_name FROM stores WHERE store_code=?", (store_code,)
    ).fetchone()
    store_name = store_name_row[0] if store_name_row else ""

    # [2026-10-13] 서적+문구 상품마스터를 한 BOOK.db로 합쳐서 보낸다(PDA는 바코드+상품명만 있으면
    # 실사가 된다 - PDA 앱은 그대로). 바코드는 13자리 + 앞 0을 뗀 형태 둘 다 보낸다.
    cur = _PdaBookRows(conn.execute(
        "SELECT store_code, isbn, book_name, category, publisher, kind FROM books WHERE store_code=?",
        (store_code,)
    ))
    total = total + cur.extra_count(conn, store_code)
    tmp_path = os.path.join(tempfile.gettempdir(), "BOOK.db")
    try:
        _build_sqlite_file(
            tmp_path,
            "CREATE TABLE book_data (store_code TEXT, isbn TEXT, book_name TEXT, "
            "category TEXT, publisher TEXT)",
            "INSERT INTO book_data VALUES (?,?,?,?,?)",
            cur, total, progress, "상품마스터(도서) 파일 만드는 중..."
        )
        meta_conn = sqlite3.connect(tmp_path)
        try:
            meta_conn.execute(
                "CREATE TABLE book_store_meta (store_code TEXT PRIMARY KEY, store_name TEXT, survey_date TEXT, unreg_policy TEXT)"
            )
            # [2026-10-08] PC(상품마스터)에서 정한 조사일자를 같이 보내 PDA 조사일자를 고정시킨다
            # (자정을 넘겨도 PDA 조회 화면에서 앞선 자료가 사라지지 않게).
            survey_date = (dbmod.get_setting("last_survey_date", "") or "").strip()
            meta_conn.execute(
                "INSERT INTO book_store_meta VALUES (?,?,?,?)",
                (store_code, store_name, survey_date, {"허용": "allow", "차단": "block"}.get(dbmod.get_unreg_policy(), "warn"))
            )
            meta_conn.commit()
        finally:
            meta_conn.close()
    finally:
        conn.close()
    ok, msg = adb_utils.push_file(tmp_path, "BOOK.db", progress)
    return ok, msg, total


def push_all(store_code: str, progress=None):
    """점포 + 작업자 + 상품(지정 점포) 마스터를 한 번에 전송.
    (전체 성공 여부, 화면에 보여줄 결과 요약 텍스트) 반환."""
    report(progress, message="PDA 연결 확인 중...", done=0, total=0)
    ok_dev, msg_dev = adb_utils.check_device_connected()
    if not ok_dev:
        return False, msg_dev

    lines = []
    all_ok = True
    steps = (
        ("점포마스터", lambda: push_stores(progress)),
        ("작업자마스터", lambda: push_workers(progress)),
        ("상품마스터", lambda: push_books(store_code, progress)),
    )
    for name, func in steps:
        try:
            ok, msg, count = func()
        except Cancelled:
            raise  # [취소]를 누르면 다음 마스터로 넘어가지 않고 바로 멈춘다
        except Exception as e:  # noqa: BLE001
            lines.append(f"{name}: 실패 - {e}")
            all_ok = False
            continue
        lines.append(f"{name}: {'전송 완료 ' + format(count, ',') + '건' if ok else '실패 - ' + msg}")
        all_ok = all_ok and ok
    return all_ok, "\n".join(lines)
