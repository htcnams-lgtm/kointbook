# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""테스트용 실사 데이터를 KOINTBOOK.db에 대량으로 만들어 넣는 스크립트.

요청한 조건:
  - 작업자 40명
  - 작업자 1명당 조사(스캔) 건수 5000건
  - 작업자 1명당 그 5000건의 수량(qty) 합계가 정확히 10,000개
    (건당 수량은 평균 2개가 되도록 무작위로 나눠서 만든다 - 전부 똑같이
    2개씩이 아니라 1~4개 사이에서 들쭉날쭉하게 흩어지고, 마지막에 부족한/
    남는 만큼을 무작위 위치에 1개씩 더해서 합계를 정확히 10,000으로 맞춘다)

바코드로 쓸 상품마스터가 현재 점포에 하나도 없으면(빈 상태로 테스트하는
경우), 스캔할 대상이 있어야 하므로 샘플 도서 1,000종도 같이 만들어 넣는다
(이미 상품마스터가 있으면 그 실제 도서들 중에서 무작위로 골라 스캔한다).

실행 방법
---------
    cd KOINTBOOK/pc_app        (KOINTBOOK_pc.py가 있는 폴더)
    python generate_test_data.py

몇 번을 실행하든 프로그램이 망가지지 않도록, 작업자/샘플도서는 이미
있으면 새로 만들지 않고 건너뛴다(중복 생성 안 함). 다만 실사데이터
(stock_counts)는 실행할 때마다 "새로 스캔한 것"으로 계속 추가되므로,
여러 번 실행하면 그만큼 계속 쌓인다 - 다시 깨끗하게 시작하려면
[데이터백업] 화면에서 미리 백업해두거나, KOINTBOOK.db를 지우고 다시
실행하세요.
"""

import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from KOINTBOOK import db as dbmod  # noqa: E402


def today_str():
    # KOINTBOOK.ui_common.today_str()와 동일한 형식(YYYYMMDD)이지만, 이
    # 스크립트는 화면(tkinter)이 없어도 돌아가야 해서 따로 정의한다
    # (ui_common은 tkinter를 불러오므로, 화면 없는 서버/터미널 환경에서도
    # 이 스크립트가 그대로 실행되게 하기 위함).
    return datetime.now().strftime("%Y%m%d")

NUM_WORKERS = 40
RECORDS_PER_WORKER = 5000
TOTAL_QTY_PER_WORKER = 10000
NUM_SAMPLE_BOOKS = 1000

DEFAULT_STORE_CODE = "KYOBO01"
DEFAULT_STORE_NAME = "교보문고 광화문점"

CATEGORIES = ["소설/시/희곡", "인문", "경제경영", "자기계발", "역사", "과학", "만화", "청소년", "유아", "컴퓨터/IT"]
PUBLISHERS = ["코인트출판사", "북라이프", "한빛미디어", "위즈덤하우스", "창비", "민음사", "김영사", "문학동네"]


def _random_isbn(i):
    # 실제 ISBN 형식(13자리)을 흉내낸 테스트용 바코드. 앞자리는 978(도서 접두)로
    # 통일하고, 뒤 9자리는 순번을 채워 겹치지 않게 한다.
    return f"978{i:09d}"


def ensure_store(conn):
    row = conn.execute("SELECT store_code, store_name FROM stores ORDER BY store_code LIMIT 1").fetchone()
    if row:
        return row["store_code"], row["store_name"]
    conn.execute(
        "INSERT OR IGNORE INTO stores(store_code, store_name) VALUES (?,?)",
        (DEFAULT_STORE_CODE, DEFAULT_STORE_NAME)
    )
    conn.commit()
    return DEFAULT_STORE_CODE, DEFAULT_STORE_NAME


def ensure_workers(conn):
    codes = [f"W{n:02d}" for n in range(1, NUM_WORKERS + 1)]
    rows = [(code, f"테스트작업자{n:02d}") for n, code in enumerate(codes, start=1)]
    conn.executemany(
        "INSERT OR IGNORE INTO workers(worker_code, worker_name) VALUES (?,?)", rows
    )
    conn.commit()
    return codes


def ensure_sample_books(conn, store_code):
    existing = conn.execute("SELECT COUNT(*) AS c FROM books WHERE store_code=?", (store_code,)).fetchone()["c"]
    if existing > 0:
        print(f"[상품마스터] 이미 {existing}종이 있어서 새로 만들지 않고 그대로 사용합니다.")
        return

    print(f"[상품마스터] 스캔할 상품이 없어서 테스트용 샘플 도서 {NUM_SAMPLE_BOOKS}종을 만듭니다...")
    rows = []
    for i in range(1, NUM_SAMPLE_BOOKS + 1):
        isbn = _random_isbn(i)
        rows.append((
            store_code, isbn, f"테스트도서 {i:05d}",
            random.choice(CATEGORIES), random.choice(PUBLISHERS),
            random.randint(0, 20), 0, 0, "N"
        ))
    conn.executemany(
        """INSERT INTO books(store_code, isbn, book_name, category, publisher,
                              rcds_qty, real_qty, missing_qty, except_flag)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(store_code, isbn) DO NOTHING""",
        rows
    )
    conn.commit()


def _qty_list_summing_to(total, count):
    """count개의 정수를 무작위로 흩어서 만들되, 합계가 정확히 total이 되게 한다
    (기본 1개씩 깔고, 남는 만큼을 무작위 위치에 1개씩 더 얹는 방식)."""
    if total < count:
        # 요청한 총수량이 건수보다 적으면(이 조건에서는 안 생기지만 방어적으로)
        # 앞에서부터 1씩 채우고 나머지는 0으로 둔다.
        return [1] * total + [0] * (count - total)
    qtys = [1] * count
    remaining = total - count
    for _ in range(remaining):
        qtys[random.randrange(count)] += 1
    random.shuffle(qtys)
    return qtys


def generate_stock_counts(conn, store_code, store_name, survey_date, worker_codes, worker_names):
    conn.execute("SELECT isbn, book_name FROM books WHERE store_code=?", (store_code,))
    books = conn.execute("SELECT isbn, book_name FROM books WHERE store_code=?", (store_code,)).fetchall()
    if not books:
        raise RuntimeError("상품마스터(books)가 비어 있어 스캔할 바코드가 없습니다.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_inserted = 0

    for w_code, w_name in zip(worker_codes, worker_names):
        qtys = _qty_list_summing_to(TOTAL_QTY_PER_WORKER, RECORDS_PER_WORKER)
        rows = []
        for qty in qtys:
            book = random.choice(books)
            area = str(random.randint(1, 5))
            section = f"{random.randint(1, 99):03d}"
            shelf_no = str(random.randint(1, 300))
            dan = str(random.randint(1, 5))
            yeol = str(random.randint(1, 10))
            rows.append((
                store_code, store_name, survey_date, area, section, shelf_no, dan, yeol,
                book["isbn"], book["book_name"], qty, w_code, w_name, now
            ))
        conn.executemany(
            """INSERT INTO stock_counts
               (store_code, store_name, survey_date, area, section, shelf_no, dan, yeol,
                isbn, book_name, qty, worker_code, worker_name, received_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows
        )
        total_inserted += len(rows)
        print(f"  {w_name}({w_code}): {len(rows):,}건 생성 (수량 합계 {sum(qtys):,}개)")

    conn.commit()
    return total_inserted


def main():
    dbmod.init_db()
    conn = dbmod.get_conn()

    store_code, store_name = ensure_store(conn)
    survey_date = today_str()
    print(f"점포: {store_code} / {store_name}, 조사일자: {survey_date}")

    worker_codes = ensure_workers(conn)
    worker_names = [f"테스트작업자{n:02d}" for n in range(1, NUM_WORKERS + 1)]
    print(f"[작업자] {NUM_WORKERS}명 준비 완료.")

    ensure_sample_books(conn, store_code)

    print(f"[실사데이터] 작업자 {NUM_WORKERS}명 x 1인당 {RECORDS_PER_WORKER:,}건"
          f"(1인당 수량 합계 {TOTAL_QTY_PER_WORKER:,}개) 생성 중...")
    total = generate_stock_counts(conn, store_code, store_name, survey_date, worker_codes, worker_names)
    conn.close()

    print(f"\n완료: 총 {total:,}건의 실사데이터를 만들었습니다.")
    print(f"(점포 {store_code} / 조사일자 {survey_date} 기준 - KOINTBOOK_pc.py를 그 점포/날짜로 실행하면 바로 보입니다)")


if __name__ == "__main__":
    main()
