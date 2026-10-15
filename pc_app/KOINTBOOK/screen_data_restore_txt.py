# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""데이터백업 > 실사데이터 복원(txt) 화면.

[2026-10-11] "데이터백업 하위메뉴로 복원하는 기능으로 재집계 txt 양식을 불러서 실사데이터로
복구하고 싶다. 파일에는 점포코드와 점포명이 없다"(요청). 읽기/검사/저장 규칙은
restore_txt_core.py에 있고, 이 파일은 그 기능을 쓰는 화면이다.

사용 순서: [txt 파일 선택] -> 점포/조사일자 확인 -> 미리보기 숫자 확인 -> [복원 실행].
- 점포코드/점포명은 파일에 없으면 여기서 고르거나 직접 입력한다(처음 보는 점포면 점포마스터에 새로 등록).
- 복원 직전에 현재 DB를 자동 백업하고(C:/KOINTBOOK/backup), 한 번에 반영하며 오류가 나면 전부 되돌린다.
- 같은 점포+조사일자에 이미 실사데이터가 있으면 [복원 실행]을 눌렀을 때 "새로 엎을지(지우고 복원) /
  기존에 추가할지 / 취소"를 물어본다(없으면 묻지 않는다). 조사일자는 달력에서 고른다.
"""

import re
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from . import db as dbmod
from . import restore_txt_core as core
from .progress_core import Cancelled
from .progress_dialog import run_with_progress
from .screen_data_backup import _backup_dir, _copy_with_progress
from .ui_common import CL_BG, CL_NAVY, CL_TEXT_DIM, open_calendar_picker, win_button

class DataRestoreTxtScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self.parsed = None
        self._after_id = None
        self.path_var = tk.StringVar(value="")
        self.pick_var = tk.StringVar(value="")
        self.code_var = tk.StringVar(value="")
        self.name_var = tk.StringVar(value="")
        self.date_var = tk.StringVar(value="")
        self.add_workers_var = tk.BooleanVar(value=True)
        self.add_products_var = tk.BooleanVar(value=True)
        self._build_ui()

    # ---- 화면 ----
    def _build_ui(self):
        tk.Label(self, text="실사데이터 복원 (txt)", bg=CL_BG, fg=CL_NAVY,
                 font=("맑은 고딕", 13, "bold")).pack(anchor="w", padx=12, pady=(12, 2))
        tk.Label(self, bg=CL_BG, fg=CL_TEXT_DIM, justify="left", anchor="w",
                 text="재집계 txt(탭으로 나뉜 16열: AREA, SECTION, 단, 열, 바코드, 수량, … 상품명, 점포코드, 작업자코드/명, 날짜, 시각)를 "
                      "불러와 실사데이터로 복구합니다.\n서가번호는 파일에 없어서 빈칸으로 저장합니다. 이미 있는 마스터 값은 고치지 않습니다."
                 ).pack(anchor="w", padx=12)

        row = tk.Frame(self, bg=CL_BG)
        row.pack(fill=tk.X, padx=12, pady=(10, 4))
        win_button(row, text="txt 파일 선택", command=self.choose_file, kind="accent").pack(side=tk.LEFT)
        tk.Label(row, textvariable=self.path_var, bg=CL_BG, anchor="w").pack(side=tk.LEFT, padx=10)

        box = tk.LabelFrame(self, text=" 저장할 기준 ", bg=CL_BG)
        box.pack(fill=tk.X, padx=12, pady=6)
        tk.Label(box, text="점포 선택", bg=CL_BG).grid(row=0, column=0, sticky="e", padx=6, pady=4)
        self.pick_cb = ttk.Combobox(box, textvariable=self.pick_var, width=34, state="readonly")
        self.pick_cb.grid(row=0, column=1, columnspan=3, sticky="w", pady=4)
        self.pick_cb.bind("<<ComboboxSelected>>", self._on_pick_store)
        tk.Label(box, text="점포코드", bg=CL_BG).grid(row=1, column=0, sticky="e", padx=6, pady=4)
        tk.Entry(box, textvariable=self.code_var, width=14).grid(row=1, column=1, sticky="w")
        tk.Label(box, text="점포명", bg=CL_BG).grid(row=1, column=2, sticky="e", padx=6)
        tk.Entry(box, textvariable=self.name_var, width=24).grid(row=1, column=3, sticky="w")
        tk.Label(box, text="조사일자", bg=CL_BG).grid(row=2, column=0, sticky="e", padx=6, pady=4)
        self.btn_date = win_button(box, text="날짜 선택", command=self._open_calendar, kind="normal")
        self.btn_date.grid(row=2, column=1, sticky="w")
        tk.Label(box, text="(달력에서 고릅니다. 파일을 고르면 파일 안 날짜가 기본으로 들어갑니다)", bg=CL_BG,
                 fg=CL_TEXT_DIM).grid(row=2, column=2, columnspan=2, sticky="w", padx=6)
        for v in (self.code_var, self.name_var, self.date_var):
            v.trace_add("write", lambda *a: self._schedule_preview())
        self.date_var.trace_add("write", lambda *a: self._sync_date_button())

        opt = tk.LabelFrame(self, text=" 마스터 ", bg=CL_BG)
        opt.pack(fill=tk.X, padx=12, pady=6)
        tk.Checkbutton(opt, text="작업자마스터에 없는 작업자를 추가 (파일의 작업자코드/작업자명)",
                       variable=self.add_workers_var, bg=CL_BG, command=self._schedule_preview).pack(anchor="w", padx=8)
        tk.Checkbutton(opt, text="상품마스터에 없는 바코드를 추가 (바코드/상품명, 전산재고·실재고는 0)",
                       variable=self.add_products_var, bg=CL_BG, command=self._schedule_preview).pack(anchor="w", padx=8)
        tk.Label(opt, bg=CL_BG, fg=CL_TEXT_DIM, anchor="w", justify="left",
                 text="같은 점포·날짜에 실사데이터가 이미 있으면, [복원 실행]을 눌렀을 때 새로 엎을지/추가할지 물어봅니다."
                 ).pack(anchor="w", padx=8, pady=(2, 4))

        self.preview = tk.Text(self, height=15, wrap="word", state="disabled", bg="#FFFFFF")
        self.preview.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        bar = tk.Frame(self, bg=CL_BG)
        bar.pack(fill=tk.X, padx=12, pady=(0, 12))
        self.btn_run = win_button(bar, text="복원 실행", command=self.restore, kind="accent")
        self.btn_run.pack(side=tk.RIGHT)
        self._set_run_enabled(False)
        self._write_preview("먼저 [txt 파일 선택]으로 복원할 파일을 골라 주세요.")

    def refresh(self):
        """화면에 들어올 때마다 점포 목록만 다시 읽는다(파일/입력값은 그대로 둔다)."""
        self._load_stores()

    # ---- 조사일자 (달력) ----
    def _sync_date_button(self):
        d = self.date_var.get().strip()
        try:
            self.btn_date.config(text=(f"{d[:4]}-{d[4:6]}-{d[6:8]}" if re.fullmatch(r"\d{8}", d) else (d or "날짜 선택")))
        except Exception:
            pass

    def _open_calendar(self):
        initial = self.date_var.get().strip()
        if not re.fullmatch(r"\d{8}", initial):
            initial = datetime.now().strftime("%Y%m%d")
        open_calendar_picker(self, initial, lambda picked: self.date_var.set(picked))

    # ---- 점포 ----
    def _load_stores(self):
        try:
            conn = dbmod.get_conn()
            rows = conn.execute("SELECT store_code, store_name FROM stores ORDER BY store_code").fetchall()
            conn.close()
        except Exception:
            rows = []
        self._stores = {r["store_code"]: r["store_name"] or "" for r in rows}
        self.pick_cb["values"] = [f"{c} | {n}" for c, n in self._stores.items()]

    def _on_pick_store(self, _event=None):
        code = (self.pick_var.get().split("|")[0] or "").strip()
        if code:
            self.code_var.set(code)
            self.name_var.set(self._stores.get(code, ""))

    # ---- 파일 ----
    def choose_file(self):
        path = filedialog.askopenfilename(title="복원할 txt 파일", filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")])
        if not path:
            return
        try:
            parsed = core.parse_file(path)
        except core.RestoreError as e:
            messagebox.showerror("파일을 읽을 수 없습니다", str(e))
            return
        except OSError as e:
            messagebox.showerror("파일을 읽을 수 없습니다", str(e))
            return
        self.parsed = parsed
        self.path_var.set(path)
        self._load_stores()
        rows = parsed["rows"]
        if rows:
            # 파일 안에서 가장 많이 나온 날짜를 기본 조사일자로
            dates = {}
            for r in rows:
                dates[r["date"]] = dates.get(r["date"], 0) + 1
            self.date_var.set(max(dates, key=dates.get))
            codes = sorted({r["file_store_code"] for r in rows if r["file_store_code"]})
            if len(codes) == 1:  # 파일에 점포코드가 한 개 들어 있으면 그것을 기본으로 (나중 양식 대비)
                self.code_var.set(codes[0])
                self.name_var.set(self._stores.get(codes[0], ""))
            elif not self.code_var.get():
                # 아직 고른 점포가 없으면 지금 프로그램이 보고 있는 점포를 기본으로
                self.code_var.set(self.app.state.store_code or "")
                self.name_var.set(self.app.state.store_name or "")
        self.update_preview()

    # ---- 미리보기 ----
    def _schedule_preview(self):
        if self.parsed is None:
            return
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.after(300, self.update_preview)

    def _write_preview(self, text):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _set_run_enabled(self, on):
        try:
            self.btn_run.state(["!disabled"] if on else ["disabled"])
        except Exception:
            pass

    def update_preview(self):
        self._after_id = None
        if self.parsed is None:
            return
        code = self.code_var.get().strip()
        date = self.date_var.get().strip()
        info = core.analyze(self.parsed, code, date if re.fullmatch(r"\d{8}", date) else "")
        L = [f"파일: {info['file']} ({info['encoding']})",
             f"읽은 줄 {info['n_rows']:,}건 · 총수량 {info['total_qty']:,} · AREA {info['n_area']}개 · "
             f"SECTION {info['n_section']}개 · 바코드 {info['n_products']:,}종"]
        if info["n_errors"]:
            L.append(f"\n⚠ 형식이 맞지 않는 줄 {info['n_errors']}건 - 고친 뒤 다시 불러와야 복원할 수 있습니다:")
            L += [f"   {n}번째 줄: {why}" for n, why in info["errors"]]
            if info["n_errors"] > len(info["errors"]):
                L.append("   …")
        fd = ", ".join(f"{d} ({n:,}건)" for d, n in sorted(info["dates"].items()))
        L.append(f"파일 안 조사일자: {fd}")
        m = re.search(r"(20\d{6})", info["file"])
        if m and m.group(1) not in info["dates"]:
            L.append(f"⚠ 파일 이름의 날짜({m.group(1)})와 파일 안 날짜가 다릅니다. 아래 조사일자를 확인해 주세요.")
        if date and not re.fullmatch(r"\d{8}", date):
            L.append("⚠ 조사일자는 YYYYMMDD 8자리로 입력해 주세요.")
        L.append("")
        if not code:
            L.append("⚠ 점포코드를 입력하거나 점포를 골라 주세요. (파일에 점포코드가 없습니다)")
        else:
            nm = self.name_var.get().strip()
            L.append(f"저장 기준: [{code} / {nm or '(점포명 없음)'}] {date or '(조사일자 미입력)'}"
                     + ("" if info["store_known"] else "  → 점포마스터에 새로 등록됩니다"))
            if info["existing_rows"]:
                L.append(f"⚠ 이 점포·날짜에 이미 실사데이터 {info['existing_rows']:,}건(수량 {info['existing_qty']:,})이 있습니다."
                         + (f" 그중 {info['same_source_rows']:,}건은 같은 파일에서 복원한 것입니다." if info["same_source_rows"] else "")
                         + " [복원 실행]을 누르면 새로 엎을지/추가할지 물어봅니다.")
        L.append("")
        w = info["workers"]
        L.append("작업자: " + (", ".join(f"{c} {n}" for c, n in w.items()) if w else "(없음)"))
        if info["workers_new"]:
            L.append(f"  · 작업자마스터에 없는 {len(info['workers_new'])}명은 "
                     + ("새로 추가됩니다" if self.add_workers_var.get() else "추가하지 않습니다 (실사 줄에는 그대로 저장)"))
        for c, old, new in info["workers_name_diff"]:
            L.append(f"  · ⚠ 작업자 {c}: 마스터 '{old}' / 파일 '{new}' - 마스터 이름을 유지합니다")
        for c in info["workers_multi_name"]:
            L.append(f"  · ⚠ 작업자코드 {c}가 파일에서 이름이 여러 개입니다")
        if code:
            L.append(f"상품마스터: 이 점포에 없는 바코드 {info['products_new']:,}종은 "
                     + ("바코드/상품명으로 추가됩니다 (전산재고 0)" if self.add_products_var.get() else "추가하지 않습니다"))
        L.append("\n서가번호는 빈칸으로 저장됩니다. 복원 전에 현재 DB를 자동 백업합니다.")
        self._write_preview("\n".join(L))
        self._set_run_enabled(not info["n_errors"] and bool(info["n_rows"]))

    # ---- 복원 ----
    def restore(self):
        if self.parsed is None:
            messagebox.showinfo("알림", "먼저 txt 파일을 골라 주세요.")
            return
        code = self.code_var.get().strip()
        name = self.name_var.get().strip()
        date = self.date_var.get().strip()
        if not code:
            messagebox.showwarning("점포코드 필요", "점포코드를 입력하거나 점포를 골라 주세요.")
            return
        if not re.fullmatch(r"\d{8}", date):
            messagebox.showwarning("조사일자 확인", "조사일자는 YYYYMMDD 8자리로 입력해 주세요.")
            return
        info = core.analyze(self.parsed, code, date)
        if info["n_errors"]:
            messagebox.showerror("복원할 수 없음", "형식이 맞지 않는 줄이 있어 복원할 수 없습니다.")
            return
        head = (f"{info['n_rows']:,}건 (총수량 {info['total_qty']:,})을\n"
                f"[{code} / {name or code}] {date}로 복원합니다.")
        if info["existing_rows"]:
            # 같은 점포·날짜에 이미 실사데이터가 있으면: 새로 엎을지 / 추가할지 / 취소
            ans = messagebox.askyesnocancel(
                "기존 실사데이터가 있습니다",
                f"{head}\n\n이 점포·날짜에는 이미 실사데이터 {info['existing_rows']:,}건(수량 {info['existing_qty']:,})이 있습니다.\n\n"
                f"[예]       기존 데이터를 지우고 새로 복원 (새로 엎기)\n"
                f"[아니오]  기존 데이터는 두고 이어서 추가 (수량이 합쳐집니다)\n"
                f"[취소]    복원하지 않음\n\n"
                f"어느 쪽이든 복원 직전에 현재 DB를 자동 백업합니다.")
            if ans is None:
                return
            mode = "replace" if ans else "append"
        else:
            mode = "stop"  # 기존 데이터가 없으면 그냥 넣는다(그 사이 생기면 중단)
            if not messagebox.askyesno("복원 확인", f"{head}\n\n복원 전에 현재 DB를 자동 백업합니다. 진행할까요?"):
                return

        add_w, add_p = self.add_workers_var.get(), self.add_products_var.get()
        parsed = self.parsed

        def work(progress):
            try:
                c = dbmod.get_conn()
                try:
                    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                finally:
                    c.close()
            except Exception:
                pass
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            _copy_with_progress(dbmod.DB_PATH, _backup_dir() / f"KOINTBOOK_backup_{ts}_txt복원전자동백업.db",
                                progress, "복원 전에 현재 상태를 백업하는 중...")
            progress(message="실사데이터를 복원하는 중...", done=0, total=0)
            return core.apply_restore(parsed, code, name, date, mode=mode,
                                      add_workers=add_w, add_products=add_p, progress=progress)

        def done(result, error):
            if error is not None:
                if isinstance(error, Cancelled):
                    messagebox.showinfo("취소됨", "복원을 취소했습니다. (데이터는 바뀌지 않았습니다)")
                else:
                    messagebox.showerror("복원 실패", f"{error}\n\n(데이터는 바뀌지 않았습니다.)")
                return
            self._sync_state_after_restore(code, result.get("store_name") or name or code, date)
            self.update_preview()
            parts = [f"실사데이터 {result['inserted']:,}건 (총수량 {result['qty']:,}) 복원"]
            if result["deleted"]:
                parts.append(f"기존 {result['deleted']:,}건 삭제")
            if result["store_added"]:
                parts.append("점포마스터에 점포 등록")
            if result["workers_added"]:
                parts.append(f"작업자 {result['workers_added']}명 추가")
            if result["products_added"]:
                parts.append(f"상품마스터 {result['products_added']:,}종 추가(전산재고 0)")
            messagebox.showinfo("복원 완료", "\n".join(parts) +
                                f"\n\n현재 기준이 [{code} / {self.app.state.store_name}] {date}로 맞춰졌습니다.")

        run_with_progress(self, "실사데이터 복원", work, done, cancelable=True)

    def _sync_state_after_restore(self, code, name, date):
        """복원한 점포/조사일자로 프로그램 기준을 맞춘다(실적관리·자료생성 등이 바로 이 데이터를 보이도록)."""
        st = self.app.state
        st.store_code, st.store_name, st.survey_date = code, name, date
        st.save()
        pm = self.app.frames_cache.get("상품마스터")
        if pm is not None:
            try:
                pm.refresh()
            except Exception:
                pass
        pda = self.app.frames_cache.get("PDA Data 수신")
        if pda is not None:
            def light():
                try:
                    pda.refresh()
                    pda.recalc_summary()
                except Exception:
                    pass
            self.after(200, light)
