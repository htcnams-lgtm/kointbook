# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""상품마스터/장부마스터 화면이 같이 쓰는 [서적 불러오기]/[문구 불러오기] 동작."""

from tkinter import filedialog, messagebox
from . import db as dbmod
from . import masters
from .progress_core import Cancelled
from .progress_dialog import run_with_progress


def import_master_dialog(screen, table, label, kind):
    """screen: 상품/장부마스터 화면(app, refresh() 필요). table: 'books'|'ledger_master'.
    label: '상품마스터'|'장부마스터'. kind: '서적'|'문구'."""
    app = screen.app
    store_code = app.state.store_code
    date = app.state.survey_date
    if not store_code:
        messagebox.showwarning("알림", f"점포코드를 먼저 선택해야 {label}를 불러올 수 있습니다.")
        return
    conn = dbmod.get_conn()
    exists = conn.execute("SELECT 1 FROM stores WHERE store_code=?", (store_code,)).fetchone()
    conn.close()
    if not exists:
        messagebox.showwarning("알림", "선택된 점포가 점포마스터에 없습니다(삭제됨). 점포검색에서 다시 선택하세요.")
        app.state.store_code = ""
        app.state.store_name = ""
        app.state.save()
        screen.refresh()
        return
    if not date:
        messagebox.showwarning("알림", f"조사일자를 먼저 선택해야 {label}를 불러올 수 있습니다.")
        return
    path = filedialog.askopenfilename(
        title=f"{kind} {label} 파일 선택",
        filetypes=[("마스터 파일(CSV/Excel)", "*.csv;*.xlsx"), ("CSV 파일", "*.csv"), ("Excel 파일", "*.xlsx")])
    if not path:
        return
    is_ledger = (table == "ledger_master")

    def work(progress):
        rows = masters.read_master(path, kind, is_ledger, progress)
        return masters.save_master(table, store_code, kind, rows, progress)

    def done(count, error):
        if error is not None:
            if isinstance(error, ImportError):
                messagebox.showerror("오류", "엑셀을 읽으려면 openpyxl이 필요합니다.\npip install openpyxl")
            elif isinstance(error, Cancelled):
                messagebox.showinfo("취소", "불러오기를 취소했습니다.")
            elif isinstance(error, ValueError):
                messagebox.showwarning("파일 양식 확인", str(error))
            else:
                messagebox.showerror("오류", f"불러오는 중 오류: {error}")
            screen.refresh()
            return
        screen.refresh()
        messagebox.showinfo("완료", f"{kind} {label} {count:,}건을 불러왔습니다.\n"
                                    f"(같은 점포의 기존 {kind} 자료만 교체했고, 다른 구분은 그대로입니다)")

    run_with_progress(screen, f"{kind} {label} 불러오기", work, done, cancelable=True)
