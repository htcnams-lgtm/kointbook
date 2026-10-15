# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""데이터백업 화면. [2026-09-28] ZZOINT(원본)의 데이터백업 화면/기능을 그대로
가져왔다(파일/DB 이름만 KOINTBOOK 기준으로 바꿨다).

KOINTBOOK.db 파일 하나에 점포/작업자/상품마스터/실사데이터가 전부
들어있으므로, 이 파일 하나만 복사해두면 전체 백업이 되고, 그 파일로
덮어쓰면 전체 복원이 된다.
"""

import os
import sqlite3
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from . import db as dbmod
from .progress_dialog import run_with_progress
from .ui_common import setup_treeview, CL_BG, CL_NAVY, CL_TEXT_DIM, win_button

# 복원할 파일에 최소한 이 표들이 있어야 KOINTBOOK 백업 파일로 인정한다
# (엉뚱한 .db 파일 - 예: PDA에서 받은 KOINTBOOK.db 원본이 아닌 다른 파일 - 을
# 골라 프로그램을 망가뜨리는 걸 막는다).
REQUIRED_TABLES = {"stores", "workers", "books", "stock_counts"}


def _backup_dir() -> Path:
    d = Path("C:/KOINTBOOK/backup")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _copy_with_progress(src, dst, progress, label):
    """파일을 4MB씩 나눠 복사하면서 진행률을 알려준다 (백그라운드 스레드에서 호출)."""
    total = os.path.getsize(src)
    progress(message=label, done=0, total=total, unit="bytes")
    done = 0
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        while True:
            buf = fin.read(4 * 1024 * 1024)
            if not buf:
                break
            fout.write(buf)
            done += len(buf)
            progress(done=done)
            progress.check_cancel()
        fout.flush()
        os.fsync(fout.fileno())
    try:
        os.utime(dst, (os.path.getatime(src), os.path.getmtime(src)))
    except OSError:
        pass


def _check_backup_file(path: Path):
    """복원해도 되는 KOINTBOOK 백업 파일인지 확인. 문제가 없으면 None, 있으면 이유를 돌려준다."""
    try:
        conn = sqlite3.connect(str(path))
        try:
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            missing = REQUIRED_TABLES - names
            if missing:
                return ("KOINTBOOK 백업 파일이 아닌 것 같습니다.\n"
                        f"(없는 항목: {', '.join(sorted(missing))})")
            conn.execute("SELECT 1 FROM stock_counts LIMIT 1").fetchall()
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        return f"올바른 데이터베이스 파일이 아닙니다.\n({e})"
    except Exception as e:  # noqa: BLE001
        return f"파일을 확인하는 중 오류가 발생했습니다.\n({e})"
    return None


class DataBackupScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        tk.Label(self, text="데이터 백업 / 복원", bg=CL_BG, fg=CL_NAVY,
                 font=("", 14, "bold")).pack(anchor="w", padx=12, pady=(14, 2))
        tk.Label(
            self,
            text="점포·작업자·상품마스터·실사데이터가 담긴 KOINTBOOK.db 파일 하나를\n"
                 "통째로 백업하고, 필요할 때 그 백업으로 되돌릴 수 있습니다.",
            bg=CL_BG, fg=CL_TEXT_DIM, font=("", 10), justify="left"
        ).pack(anchor="w", padx=12, pady=(0, 14))

        # 세 버튼 모두 실적관리 상단 버튼(조회/등록/수정)과 같은 크기·글씨체.
        # 배경색은 ZZOINT와 동일하게(백업하기만 강조, 나머지는 기본색).
        btn_row = tk.Frame(self, bg=CL_BG)
        btn_row.pack(fill=tk.X, padx=12, pady=(0, 10))
        win_button(btn_row, text="지금 상태 백업하기", command=self.do_backup, kind="accent").pack(side=tk.LEFT)
        win_button(btn_row, text="다른 백업 파일 불러오기", command=self.restore_from_file, kind="normal").pack(side=tk.LEFT, padx=10)
        win_button(btn_row, text="백업 폴더 열기", command=self.open_backup_folder, kind="normal").pack(side=tk.LEFT)

        tk.Label(self, text="이 프로그램이 만든 백업 목록 (더블클릭하면 그 시점으로 복원)",
                 bg=CL_BG, fg=CL_TEXT_DIM, font=("", 9)).pack(anchor="w", padx=12, pady=(8, 2))

        columns = ("no", "filename", "when", "size")
        headings = ("NO", "파일명", "백업 시각", "용량")
        widths = (50, 300, 160, 90)
        container, self.tree = setup_treeview(self, columns, headings, widths, height=14)
        container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.tree.bind("<Double-Button-1>", self._on_double_click)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        files = sorted(_backup_dir().glob("KOINTBOOK_backup_*.db"), reverse=True)
        self._backup_paths = {}
        for i, path in enumerate(files, start=1):
            stat = path.stat()
            when = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size_kb = f"{stat.st_size / 1024:.0f} KB"
            iid = self.tree.insert("", tk.END, values=(i, path.name, when, size_kb),
                                    tags=("odd",) if i % 2 == 0 else ())
            self._backup_paths[iid] = path

    def do_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = _backup_dir() / f"KOINTBOOK_backup_{timestamp}.db"

        def work(progress):
            # WAL 모드라 최근에 저장된 내용이 아직 KOINTBOOK.db-wal 파일에만 있을 수 있다 -
            # 복사 전에 본 파일로 합쳐 두어야 백업에 빠짐없이 들어간다.
            try:
                c = dbmod.get_conn()
                try:
                    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                finally:
                    c.close()
            except Exception:
                pass
            _copy_with_progress(dbmod.DB_PATH, dest, progress, "백업 파일을 만드는 중...")

        def done(_result, error):
            if error is not None:
                messagebox.showerror("오류", f"백업 중 오류가 발생했습니다:\n{error}")
                try:
                    if dest.exists():
                        dest.unlink()  # 반쯤 만들어진 파일이 남지 않게 한다
                except OSError:
                    pass
                return
            self.refresh()
            messagebox.showinfo("완료", f"백업이 완료되었습니다:\n{dest}")

        run_with_progress(self, "지금 상태 백업", work, done, cancelable=True)

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        path = self._backup_paths.get(sel[0])
        if path:
            self._restore(path)

    def restore_from_file(self):
        path = filedialog.askopenfilename(filetypes=[("KOINTBOOK 백업 파일", "*.db")])
        if not path:
            return
        self._restore(Path(path))

    def _restore(self, path: Path):
        try:
            if path.resolve() == Path(dbmod.DB_PATH).resolve():
                messagebox.showinfo("알림", "지금 사용 중인 데이터 파일 자체입니다. 다른 백업 파일을 골라주세요.")
                return
        except OSError:
            pass

        problem = _check_backup_file(path)
        if problem:
            messagebox.showerror("복원할 수 없는 파일", f"{path.name}\n\n{problem}")
            return

        if not messagebox.askyesno(
            "복원 확인",
            f"선택한 백업으로 복원하시겠습니까?\n\n{path.name}\n\n"
            f"⚠ 지금 저장되어 있는 모든 데이터(점포/작업자/상품마스터/실사데이터)가\n"
            f"이 백업 시점의 내용으로 전부 바뀝니다. 되돌릴 수 없으니 신중하게 선택하세요."
        ):
            return

        db_path = Path(dbmod.DB_PATH)

        def work(progress):
            # 혹시 모를 실수에 대비해, 덮어쓰기 직전 현재 상태도 자동으로 한 번 백업해둔다.
            safety_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            _copy_with_progress(db_path, _backup_dir() / f"KOINTBOOK_backup_{safety_ts}_복원전자동백업.db",
                                progress, "복원 전에 현재 상태를 안전하게 백업하는 중...")
            # 임시 파일로 먼저 다 복사한 뒤 한 번에 바꿔치기한다 - 복사 도중 오류/취소가
            # 나도 현재 DB가 반쯤 덮어써져서 망가지는 일이 없다.
            tmp = db_path.with_name(db_path.name + ".restoring")
            try:
                _copy_with_progress(path, tmp, progress, "백업 파일을 복원하는 중...")
                progress.check_cancel()
                os.replace(tmp, db_path)
            finally:
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
            # 이전 DB가 남긴 찌꺼기 파일 정리
            for suffix in ("-journal", "-wal", "-shm"):
                leftover = db_path.with_name(db_path.name + suffix)
                if leftover.exists():
                    try:
                        leftover.unlink()
                    except OSError:
                        pass
            # 예전 버전 백업이면 새 항목이 없을 수 있어서, 최신 구조로 맞춘다.
            progress(message="데이터 구조를 확인하는 중...", done=0, total=0)
            dbmod.init_db()
            dbmod.bump_stock_version()

        def done(_result, error):
            if error is not None:
                messagebox.showerror("오류", f"복원 중 오류가 발생했습니다:\n{error}\n\n"
                                            "(현재 데이터는 그대로 유지되었습니다.)")
                return
            self._sync_app_state_after_restore()
            self._refresh_all_cached_screens()
            self.refresh()
            messagebox.showinfo(
                "복원 완료",
                f"복원이 완료되었습니다.\n\n"
                f"현재 기준: [{self.app.state.store_code} / {self.app.state.store_name}] "
                f"{self.app.state.survey_date}\n\n"
                f"이 기준이 원하시는 점포/날짜와 다르면, [상품마스터] 화면에서 다시 골라주세요."
            )

        run_with_progress(self, "백업 복원", work, done, cancelable=True)

    def _sync_app_state_after_restore(self):
        """복원된 DB 안에서 가장 최근에 쓰인 점포/조사일자를 찾아
        app.state에 반영한다 (재시작 없이 다른 화면들이 바로 맞는
        데이터를 보여줄 수 있도록).

        [2026-09-29] "데이터백업 복원후 프로그램을 껐다 키면 실적관리,
        자료생성 등 목록이 조회가 안되네" - 예전엔 여기서 app.state만
        바꾸고 저장은 안 해서, 복원 직후(같은 세션)엔 잘 보이다가
        프로그램을 껐다 켜면 다시 KYOBO01/오늘 날짜로 되돌아가 복원한
        데이터가 안 보였다. 이제 이 함수 끝에서 app.state.save()로
        DB(app_settings)에 저장까지 해서, 다음에 켤 때도 이어지게 한다.
        (복원한 백업 파일 자체에 이미 최신 "last_store_code" 등이 저장돼
        있는 경우 - 이 기능이 생긴 뒤에 만든 백업 - 는 그 값을 그대로
        쓰고, 옛날 백업(그런 값이 없는)이면 예전처럼 stock_counts에서
        가장 최근 점포/일자를 추측해서 쓴다.)"""
        saved_code = dbmod.get_setting("last_store_code")
        saved_date = dbmod.get_setting("last_survey_date")
        if saved_code and saved_date:
            self.app.state.store_code = saved_code
            self.app.state.store_name = dbmod.get_setting("last_store_name", "") or saved_code
            self.app.state.survey_date = saved_date
            return

        conn = dbmod.get_conn()
        row = conn.execute(
            "SELECT store_code, store_name, survey_date FROM stock_counts ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            self.app.state.store_code = row["store_code"]
            self.app.state.store_name = row["store_name"]
            self.app.state.survey_date = row["survey_date"]
        else:
            row2 = conn.execute("SELECT store_code, store_name FROM stores LIMIT 1").fetchone()
            if row2:
                self.app.state.store_code = row2["store_code"]
                self.app.state.store_name = row2["store_name"]
        conn.close()
        self.app.state.save()

        # 상품마스터 화면이 캐시되어 있다면, 점포/조사일자 표시도 새 상태로 맞춰준다
        # (KOINTBOOK의 상품마스터 화면은 refresh() 한 번으로 표시값이 전부 갱신된다).
        pm = self.app.frames_cache.get("상품마스터")
        if pm is not None:
            try:
                pm.refresh()
            except Exception:
                pass

    def _refresh_all_cached_screens(self):
        """복원한 데이터가 다른 화면에 바로 반영되게 한다.

        예전에는 한 번이라도 열어본 화면을 전부 여기서 한꺼번에 새로고침했는데,
        상품마스터/실적관리처럼 데이터가 많은 화면이 표를 통째로 다시 그리느라
        프로그램 전체가 한동안 멈춘 것처럼 보였다(먹통). 각 화면은 상단 메뉴로
        다시 들어갈 때마다 어차피 스스로 새로고침하므로, 여기서는 미리 하지 않고
        가벼운 것(PDA Data 수신 화면의 요약)만 잠시 뒤에 갱신한다."""
        pda = self.app.frames_cache.get("PDA Data 수신")
        if pda is not None:
            def light_refresh():
                try:
                    pda.refresh()
                    pda.recalc_summary()
                except Exception:
                    pass
            self.after(200, light_refresh)

    def open_backup_folder(self):
        import platform
        folder = str(_backup_dir())
        try:
            if platform.system() == "Windows":
                os.startfile(folder)
            elif platform.system() == "Darwin":
                import subprocess
                subprocess.run(["open", folder])
            else:
                import subprocess
                subprocess.run(["xdg-open", folder])
        except Exception:
            messagebox.showinfo("폴더 위치", folder)
