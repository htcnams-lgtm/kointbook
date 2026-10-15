# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
KOINTBOOK PC 프로그램의 SQLite 데이터베이스 접근 모듈.

ZZOINT(일반 매장용 데모)의 구조를 기반으로, 첨부된 RBSKOREA-KYOBO 실사
프로그램 화면(재고조사 보고서/AREA별 합산/Section Check/샘플링 등)에
필요한 서점(도서) 전용 항목 - AREA/SECTION/서가번호/단/열, 바코드/도서명 -
을 반영해서 넓혔다.

테이블
------
stores          : 점포마스터 (store_code, store_name)
workers         : 작업자마스터 (worker_code, worker_name)
books           : 상품마스터/도서마스터. store_code/isbn/book_name/category/
                  publisher(=바코드/도서명/분야명/출판사) + rcds_qty/real_qty/
                  missing_qty/except_flag(=전산재고/실재고/누락재고/예외여부).
                  뒤 4개는 실제 "도서 마스터정보 업로드" CSV(cmdtCode,
                  cmdtName,jo_name,pbcm_name,rcdsInvnQntt,realInvnQntt,qntt,
                  exceptYsno)가 이미 값을 갖고 있는 필드라 KOINTBOOK이 다시
                  계산하지 않고 그대로 저장/표시한다.
ledger          : (예전) 바코드/수량만 있는 보조 테이블. [2026-10-08] 장부마스터
                  화면이 아래 ledger_master를 쓰면서 더 이상 읽지 않는다
                  (옛 DB 호환을 위해 테이블만 남겨둔다).
ledger_master   : [2026-10-08] 장부마스터 - books와 같은 컬럼. 전산재고(rcds_qty)가
                  필요한 모든 화면/엑셀(재고조사 차이명세, 결과확인리스트 등)은
                  이 테이블 기준이고, books(상품마스터)의 값은 PDA 실사용이다.
exceptions      : 상품마스터 화면에서 더블클릭으로 수동 지정한 "예외" 품목
                  (books.except_flag='Y'와는 별개로 추가/해제 가능 - 둘 중
                  하나라도 표시되면 화면의 예외여부 열에는 "Y"로 보인다.
                  [2026-09-23] 예전엔 둘 다 아니면 빈칸으로 뒀는데, 그러면
                  마스터 파일에 있는 "N"값 자체가 안 보여서 Y/N을 그대로
                  보여주도록 고쳤다)
stock_counts    : PDA(또는 엑셀)로부터 수신한 실사 데이터
                  (AREA/SECTION/서가번호/단/열 + 바코드/상품명/수량/작업자)
dup_ack         : "중복 Section인 걸 보고도 그대로 둔다"고 확인 처리한 기록
planned_sections: 매대등록 > Section Check에서 등록한 "조사 Section" 범위(From~To)
section_printed : Section Check > 조사완료 Section에서 "발행"(그 AREA-SECTION의
                  섹션별 아이템 재고현황을 인쇄)한 기록 - "발" 컬럼에 체크로 표시
area_sum        : 집계표관리 > AREA별 합산에서 계산해둔 AREA별 건수/수량 합계
sampling_miss   : 매대등록 > 샘플링 자료등록에서 등록한 샘플링 미스 건
"""

import os
import sqlite3
import threading
from .base_dir import get_base_dir

DB_PATH = get_base_dir() / "KOINTBOOK.db"


def _migrate_old_db_file_if_needed():
    """[2026-09-23 정정] 프로그램 이름이 KYOINT -> KOINT-BOOK -> KOINTBOOK
    순서로 바뀌면서 DB 파일명도 같이 바뀌었다. 새 파일(KOINTBOOK.db)이 아직
    없고 예전 이름(KYOINT.db 또는 KOINT-BOOK.db)의 파일이 있는 경우(기존에
    쓰던 개발/테스트 자료), 그 파일을 그대로 새 이름으로 옮겨서 기존 자료가
    사라지지 않게 한다."""
    if DB_PATH.exists():
        return
    for old_name in ("KYOINT.db", "KOINT-BOOK.db"):
        old_path = get_base_dir() / old_name
        if old_path.exists():
            try:
                os.rename(str(old_path), str(DB_PATH))
            except OSError:
                pass
            return


_migrate_old_db_file_if_needed()

# 샘플링 자료등록 화면의 [미스유형] 드롭다운 항목과, 그 책임 소재
# (KOINT=실사 대행사 측 실수 / KYOBO=매장 측 사전 준비 문제).
# 샘플링 결과보고서 화면에서 이 매핑으로 두 그룹 합계를 나눠서 보여준다.
# [2026-09-24 정정] 화면에 보이는 책임소재 표시를 "RBSKOREA" -> "KOINT"로
# 바꿨다(실사 대행사 자체 명칭 변경).
MISS_TYPES = [
    ("카운터누락", "KOINT"),
    ("입력미스", "KOINT"),
    ("카운터미스", "KOINT"),
    ("스캔미스", "KOINT"),
    ("혼합카운터", "KOINT"),
    ("사전정리미스", "KYOBO"),
    ("진열정보미스", "KYOBO"),
]
MISS_TYPE_OWNER = dict(MISS_TYPES)


# ---- DB 변경 번호 (data_version) --------------------------------------------
# get_conn()으로 연 연결이 실제로 데이터를 바꾸고(INSERT/UPDATE/DELETE) 커밋하거나
# 닫힐 때마다 1씩 올라가는 번호. 차이내역처럼 계산이 무거운 화면이 "데이터가
# 그대로면 정렬/필터/화면 전환 때 다시 계산하지 않고, 바뀌었을 때만 다시 계산"하기
# 위해 쓴다. 표 만들기(CREATE TABLE IF NOT EXISTS 등)처럼 데이터가 안 바뀌는
# 작업은 번호를 올리지 않는다(sqlite total_changes 기준).
_data_version = 0
_data_version_lock = threading.Lock()


def data_version():
    return _data_version


def _bump_data_version():
    global _data_version
    with _data_version_lock:
        _data_version += 1


class _TrackedConnection(sqlite3.Connection):
    def _note_changes(self):
        try:
            tc = self.total_changes
        except sqlite3.ProgrammingError:
            return
        if tc != getattr(self, "_seen_changes", 0):
            self._seen_changes = tc
            _bump_data_version()

    def commit(self):
        super().commit()
        self._note_changes()

    def close(self):
        self._note_changes()
        super().close()


def get_conn():
    # timeout: 다른 곳(백그라운드 목록 읽기 등)이 DB를 쓰는 중이면 바로 "database is locked"를
    # 내지 않고 기다렸다가 재시도한다.
    conn = sqlite3.connect(str(DB_PATH), timeout=30, factory=_TrackedConnection)
    conn.row_factory = sqlite3.Row
    try:
        # WAL 모드: 읽기(가상 스크롤 목록을 백그라운드에서 읽는 중 등)와 쓰기(수정/삭제/PDA 저장)가
        # 서로 막지 않고, 저장도 더 빠르다. 강제 종료돼도 다음에 열 때 자동 복구된다(ZZOINT와 같음).
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        # 정렬/묶기용 임시 작업은 메모리에서, 연결당 캐시 약 32MB.
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-32000")
    except sqlite3.Error:
        pass
    return conn


def _add_column_if_missing(cur, table, column, coltype):
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    if column not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


# 실사 데이터(stock_counts)가 바뀔 때마다 올라가는 번호. 실적관리처럼 큰 목록을 들고 있는
# 화면이 "화면 전환 때마다 다시 읽지 않고, 바뀌었을 때만 다시 읽기" 위해 쓴다.
# stock_counts를 쓰는(추가/삭제/복원) 곳은 끝나고 bump_stock_version()을 불러준다.
_stock_version = 0


def stock_version():
    return _stock_version


def bump_stock_version():
    global _stock_version
    _stock_version += 1


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            store_code TEXT PRIMARY KEY,
            store_name TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            worker_code TEXT PRIMARY KEY,
            worker_name TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS books (
            store_code TEXT,
            isbn TEXT,
            book_name TEXT,
            category TEXT,
            publisher TEXT,
            rcds_qty INTEGER DEFAULT 0,
            real_qty INTEGER DEFAULT 0,
            missing_qty INTEGER DEFAULT 0,
            except_flag TEXT DEFAULT 'N',
            PRIMARY KEY (store_code, isbn)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            isbn TEXT PRIMARY KEY,
            qty INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ledger_master (
            store_code TEXT,
            isbn TEXT,
            book_name TEXT,
            category TEXT,
            publisher TEXT,
            rcds_qty INTEGER DEFAULT 0,
            real_qty INTEGER DEFAULT 0,
            missing_qty INTEGER DEFAULT 0,
            except_flag TEXT DEFAULT 'N',
            PRIMARY KEY (store_code, isbn)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exceptions (
            store_code TEXT,
            survey_date TEXT,
            isbn TEXT,
            note TEXT,
            created_at TEXT,
            PRIMARY KEY (store_code, survey_date, isbn)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_counts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_code TEXT,
            store_name TEXT,
            survey_date TEXT,
            area TEXT,
            section TEXT,
            shelf_no TEXT,
            dan TEXT,
            yeol TEXT,
            isbn TEXT,
            book_name TEXT,
            qty INTEGER,
            worker_code TEXT,
            worker_name TEXT,
            received_at TEXT,
            source_file TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dup_ack (
            store_code TEXT,
            survey_date TEXT,
            area TEXT,
            section TEXT,
            acked_at TEXT,
            PRIMARY KEY (store_code, survey_date, area, section)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS section_printed (
            store_code TEXT,
            survey_date TEXT,
            area TEXT,
            section TEXT,
            printed_at TEXT,
            PRIMARY KEY (store_code, survey_date, area, section)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS planned_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_code TEXT,
            survey_date TEXT,
            area TEXT,
            section_from TEXT,
            section_to TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS area_sum (
            store_code TEXT,
            survey_date TEXT,
            area TEXT,
            count_total INTEGER,
            qty_total INTEGER,
            summed_at TEXT,
            PRIMARY KEY (store_code, survey_date, area)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sampling_miss (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_code TEXT,
            survey_date TEXT,
            area TEXT,
            section TEXT,
            miss_qty INTEGER,
            miss_count INTEGER,
            miss_type TEXT,
            created_at TEXT
        )
    """)
    # [2026-09-29] "데이터백업 복원후 프로그램을 껐다 키면 실적관리, 자료생성
    # 등 목록이 조회가 안되네" - 원인은 프로그램을 새로 켤 때마다 "지금 어느
    # 점포/조사일자를 보고 있는지"(AppState)가 저장돼있지 않고 매번
    # store_code="KYOBO01" + 오늘 날짜로 초기화되고 있었던 것이었다. 복원
    # 직후(같은 세션)에는 화면이 알아서 방금 복원한 데이터의 점포/일자로
    # 맞춰주지만, 그 상태는 메모리에만 있어서 프로그램을 껐다 켜면 사라지고
    # 다시 KYOBO01/오늘 날짜로 돌아가버려서 - 복원한 데이터의 점포/일자가
    # 그것과 다르면 목록에 아무 것도 안 보였다(버그가 아니라 애초에 그
    # 점포/일자로 조회를 안 하고 있었던 것). 이 표에 "마지막으로 쓰던
    # 점포/조사일자"를 저장해두고, 프로그램을 켤 때 이 값부터 읽어오게
    # 고친다 - DB 파일 안에 있으니 백업/복원할 때도 자동으로 같이
    # 백업/복원된다.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()

    # 예전 DB(필드가 없는 버전)에도 새 필드를 추가해준다.
    _add_column_if_missing(cur, "stock_counts", "source_file", "TEXT")
    # 실제 "도서 마스터정보 업로드" CSV(cmdtCode,cmdtName,jo_name,pbcm_name,
    # rcdsInvnQntt,realInvnQntt,qntt,exceptYsno)를 보면 전산재고/실재고/
    # 누락재고/예외여부가 이미 마스터 파일 자체에 들어있는 값이었다(KOINTBOOK이
    # 매번 다시 계산하는 값이 아니었다) - 그래서 이 4개를 books에 그대로
    # 저장해두고 상품마스터/자료생성 화면에서는 계산 없이 그대로 보여준다.
    _add_column_if_missing(cur, "books", "rcds_qty", "INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "books", "real_qty", "INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "books", "missing_qty", "INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "books", "except_flag", "TEXT DEFAULT 'N'")
    # [2026-10-13] 서적/문구 마스터 분리: 두 양식이 달라서 같은 표에 구분(kind)으로 같이 담는다.
    #  kind      = '서적' | '문구' (옛 DB의 기존 행은 모두 '서적')
    #  price     = 문구 상품마스터 sale_unpr (납품 상세 자료의 단가)
    #  dvsn_code = 문구 상품마스터 cmdt_dvsn_code (401/402/403 - 납품 상세 자료의 구분코드)
    #  kind_code = 문구 상품마스터 cmdt_code_kind_code (502 - 납품 상세 자료의 종류코드)
    for _tbl in ("books", "ledger_master"):
        _add_column_if_missing(cur, _tbl, "kind", "TEXT DEFAULT '서적'")
        _add_column_if_missing(cur, _tbl, "price", "INTEGER DEFAULT 0")
        _add_column_if_missing(cur, _tbl, "dvsn_code", "TEXT DEFAULT ''")
        _add_column_if_missing(cur, _tbl, "kind_code", "TEXT DEFAULT ''")
        # [2026-10-13] 마스터 파일의 'X'(해당 없음) 표시를 그대로 보여주기 위한 표시 플래그(숫자는 계산용으로 0).
        _add_column_if_missing(cur, _tbl, "rcds_x", "INTEGER DEFAULT 0")
        _add_column_if_missing(cur, _tbl, "real_x", "INTEGER DEFAULT 0")
        _add_column_if_missing(cur, _tbl, "missing_x", "INTEGER DEFAULT 0")
        _add_column_if_missing(cur, _tbl, "rdp_code", "TEXT DEFAULT ''")  # 문구 상품마스터 rdp_code(납품처) - 파일 값 그대로
        cur.execute(f"UPDATE {_tbl} SET kind='서적' WHERE kind IS NULL OR kind=''")
    conn.commit()

    # 실사 데이터가 수십만 건이어도 (점포+조사일자) 조회와 AREA/SECTION/서가/단/열 정렬이
    # 빠르도록 색인을 만든다(이미 있으면 건너뜀). 실적관리/자료생성 등 화면 진입 속도용.
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_store_date_loc ON stock_counts "
                "(store_code, survey_date, area, section, shelf_no, dan, yeol)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stock_store_date_isbn ON stock_counts "
                "(store_code, survey_date, isbn)")
    conn.commit()

    # 데모용 샘플 점포/작업자 (없을 때만 삽입)
    cur.execute("SELECT COUNT(*) FROM stores")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO stores(store_code, store_name) VALUES (?,?)",
            [("KYOBO01", "교보문고 광화문점")]
        )
    cur.execute("SELECT COUNT(*) FROM workers")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO workers(worker_code, worker_name) VALUES (?,?)",
            [("1", "이정현"), ("2", "박고을"), ("3", "오성택")]
        )
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    """app_settings에서 값 하나를 읽어온다. 없으면(처음 실행이거나 예전 DB라
    표가 방금 막 생겼을 때) default를 그대로 돌려준다."""
    try:
        conn = get_conn()
        row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        conn.close()
        return row["value"] if row is not None else default
    except sqlite3.Error:
        return default


UNREG_POLICIES = ("허용", "경고 후 허용", "차단")


def get_unreg_policy():
    """[2026-10-08] 상품마스터에 없는 미등록 상품 입력 정책: 허용 / 경고 후 허용(기본) / 차단.
    PC 실적관리 입력·수정과 PDA 재고입력이 같은 값을 쓴다(PDA는 상품마스터 전송 때 같이 받는다)."""
    v = get_setting("unreg_policy", "경고 후 허용")
    return v if v in UNREG_POLICIES else "경고 후 허용"


def set_setting(key, value):
    """app_settings에 값 하나를 저장한다(있으면 덮어쓰기). 실패해도(예: DB
    파일이 잠겨있는 순간) 프로그램이 멈추지 않도록 조용히 넘어간다 - "마지막
    점포/조사일자 기억하기"는 있으면 편한 기능이지 실사 자체를 막아서는 안
    되는 기능이라서다."""
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass


def analyze_in_background():
    """DB 통계(sqlite_stat1)를 백그라운드에서 갱신한다. SQLite가 통계를 보고 "색인을 쓸지,
    표를 통째로 읽을지"를 더 잘 고르게 되어 큰 조회가 빨라진다(30만 건 기준 실측: 집계 쿼리
    약 30~80% 단축). analysis_limit로 표본만 보므로 데이터가 많아도 0.1초 안팎이고,
    데이터 내용은 바꾸지 않는다. 프로그램 시작 때와 대량 저장(PDA 수신 저장 등) 뒤에 부른다."""
    def work():
        try:
            conn = get_conn()
            try:
                conn.execute("PRAGMA analysis_limit=2000")
                conn.execute("ANALYZE")
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass
    threading.Thread(target=work, daemon=True).start()
