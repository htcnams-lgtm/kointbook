# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""PDA 앱 설치 화면. [2026-10-06] USB로 연결된 PDA에 KOINTBOOK 앱(APK)을 adb로 설치한다.

- 화면에 들어오면(또는 [연결 확인]) PDA 연결 여부와 PDA에 앱이 설치되어 있는지(버전)를 보여준다.
- 설치할 APK는 pc_app/apk 폴더(exe로 묶을 때는 exe 안에 같이 담긴다)의 가장 최근 .apk를 쓰고,
  없으면 [파일 선택]으로 직접 고른다.
- [PDA에 앱 설치]: 연결 확인 -> 설치(기존 앱이 있으면 데이터는 그대로 두고 덮어씀) -> 설치 결과 안내
  -> 설치가 끝나면 PDA에서 앱을 바로 실행한다. 서명이 달라 덮어쓸 수 없을 때만(데이터 삭제 경고 후
  동의하면) 기존 앱을 삭제하고 다시 설치한다.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from . import adb_utils
from .progress_dialog import run_with_progress
from .ui_common import CL_BG, CL_NAVY, CL_TEXT_DIM, COLOR_HEADER_BG, win_button


class PdaInstallScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self.apk_path = None
        self._build_ui()

    def _build_ui(self):
        tk.Label(self, text="PDA 앱 설치", bg=CL_BG, fg=CL_NAVY, font=("", 14, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(self, text="USB로 연결된 PDA에 KOINTBOOK 앱을 설치합니다. (PDA의 USB 디버깅이 켜져 있어야 합니다)",
                 bg=CL_BG, fg=CL_TEXT_DIM).pack(anchor="w", padx=16, pady=(0, 10))

        box = tk.Frame(self, bg=COLOR_HEADER_BG, highlightbackground="#C4C8D0", highlightthickness=1)
        box.pack(fill=tk.X, padx=16, pady=4)
        box.columnconfigure(1, weight=1)

        tk.Label(box, text="PDA 연결", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=0, column=0, padx=(14, 10), pady=(12, 6), sticky="w")
        self.lbl_conn = tk.Label(box, text="확인 중...", bg=COLOR_HEADER_BG, font=("", 11, "bold"), anchor="w")
        self.lbl_conn.grid(row=0, column=1, sticky="we", pady=(12, 6))

        tk.Label(box, text="앱 설치 상태", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=1, column=0, padx=(14, 10), pady=6, sticky="w")
        self.lbl_installed = tk.Label(box, text="-", bg=COLOR_HEADER_BG, font=("", 11, "bold"), anchor="w")
        self.lbl_installed.grid(row=1, column=1, sticky="we", pady=6)

        tk.Label(box, text="내장 설치파일", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=2, column=0, padx=(14, 10), pady=6, sticky="w")
        self.lbl_bundled = tk.Label(box, text="-", bg=COLOR_HEADER_BG, font=("", 11, "bold"), anchor="w")
        self.lbl_bundled.grid(row=2, column=1, sticky="we", pady=6)

        tk.Label(box, text="설치할 파일", bg=COLOR_HEADER_BG, fg=CL_TEXT_DIM).grid(row=3, column=0, padx=(14, 10), pady=(6, 12), sticky="w")
        self.lbl_apk = tk.Label(box, text="-", bg=COLOR_HEADER_BG, anchor="w")
        self.lbl_apk.grid(row=3, column=1, sticky="we", pady=(6, 12))
        fbtn = tk.Frame(box, bg=COLOR_HEADER_BG)
        fbtn.grid(row=3, column=2, padx=14, pady=(6, 12))
        win_button(fbtn, text="파일 선택", command=self.choose_apk).pack(side=tk.LEFT)
        win_button(fbtn, text="내장 파일 사용", command=self.use_bundled).pack(side=tk.LEFT, padx=(6, 0))

        btns = tk.Frame(self, bg=CL_BG)
        btns.pack(fill=tk.X, padx=16, pady=10)
        win_button(btns, text="🔄 연결 확인", command=self.refresh).pack(side=tk.LEFT, padx=(0, 8))
        win_button(btns, text="📲 PDA에 앱 설치", command=self.install, kind="accent").pack(side=tk.LEFT)

        self.lbl_msg = tk.Label(self, text="", bg=CL_BG, anchor="w", justify="left", wraplength=700)
        self.lbl_msg.pack(fill=tk.X, padx=16, pady=(4, 0))

    # ---- 상태 표시 ------------------------------------------------------
    def _apk(self):
        """설치할 파일: 직접 고른 파일이 있으면 그것, 없으면 내장된 설치파일."""
        if self.apk_path:
            return self.apk_path
        info = adb_utils.bundled_apk_info()
        return info["path"] if info else None

    @staticmethod
    def _fmt_info(info):
        text = f"{info['file']}"
        if info.get("date"):
            text += f"  (파일 날짜 {info['date']})"
        if info.get("embedded_at"):
            text += f"  / exe 내장 {info['embedded_at']}"
        return text

    def _show_apk(self):
        info = adb_utils.bundled_apk_info()
        if info:
            self.lbl_bundled.config(text="있음 - " + self._fmt_info(info), fg="#1E7A3C")
        else:
            self.lbl_bundled.config(text="없음 (exe를 만들 때 pc_app\\apk 폴더에 .apk가 없었음)", fg="#B03030")
        if self.apk_path:
            self.lbl_apk.config(text="직접 선택: " + self.apk_path, fg="black")
        elif info:
            self.lbl_apk.config(text="내장 설치파일 사용 (" + info["file"] + ")", fg="black")
        else:
            self.lbl_apk.config(text="없음 - [파일 선택]으로 .apk 파일을 고르세요", fg="#B03030")

    def use_bundled(self):
        self.apk_path = None
        self._show_apk()

    def choose_apk(self):
        path = filedialog.askopenfilename(
            parent=self, title="PDA에 설치할 KOINTBOOK 앱(APK) 선택",
            filetypes=[("Android 앱", "*.apk"), ("모든 파일", "*.*")])
        if path:
            self.apk_path = path
            self._show_apk()

    def refresh(self):
        """화면에 들어올 때/[연결 확인]: PDA 연결과 앱 설치 여부를 확인해 표시한다."""
        self._show_apk()
        self.lbl_conn.config(text="확인 중...", fg="black")
        self.lbl_installed.config(text="-", fg="black")
        self.lbl_msg.config(text="")

        def worker():
            ok, msg = adb_utils.check_device_connected()
            info = adb_utils.get_installed_info() if ok else (False, "")
            try:
                self.after(0, lambda: self._apply_status(ok, msg, info))
            except Exception:
                pass  # 확인하는 동안 화면이 닫힌 경우

        threading.Thread(target=worker, daemon=True).start()

    def _apply_status(self, ok, msg, info):
        if not ok:
            self.lbl_conn.config(text="연결 안 됨", fg="#B03030")
            self.lbl_installed.config(text="-", fg="black")
            self.lbl_msg.config(text=msg)
            return
        self.lbl_conn.config(text=f"연결됨 ({msg})", fg="#1E7A3C")
        installed, ver = info
        if installed:
            self.lbl_installed.config(text="설치됨" + (f" (버전 {ver})" if ver else ""), fg="#1E7A3C")
        else:
            self.lbl_installed.config(text="설치 안 됨", fg="#B03030")

    # ---- 설치 -----------------------------------------------------------
    def install(self):
        apk = self._apk()
        if not apk:
            self.choose_apk()
            apk = self._apk()
            if not apk:
                return

        def check(progress):
            progress(message="PDA 연결 확인 중...", done=0, total=0)
            return adb_utils.check_device_connected()

        def after_check(result, error):
            if error is not None:
                messagebox.showerror("오류", f"PDA 연결 확인 중 오류: {error}")
                return
            ok, msg = result
            if not ok:
                self._apply_status(False, msg, (False, ""))
                messagebox.showerror("PDA 연결 안 됨", "PDA가 연결되어 있지 않아 설치할 수 없습니다.\n\n" + msg)
                return
            if not messagebox.askyesno(
                    "PDA 앱 설치",
                    f"PDA({msg})에 KOINTBOOK 앱을 설치합니다.\n\n"
                    f"설치 파일: {os.path.basename(apk)}" + ("  (직접 선택)" if self.apk_path else "  (내장)") + "\n\n"
                    "이미 설치된 앱이 있으면 데이터는 그대로 두고 덮어씁니다.\n계속할까요?"):
                return
            self._do_install(apk, reinstall=False)

        run_with_progress(self, "PDA 앱 설치", check, after_check, cancelable=False,
                          initial_message="PDA 연결 확인 중...")

    def _do_install(self, apk, reinstall):
        def work(progress):
            if reinstall:
                progress(message="기존 앱 삭제 중...", done=0, total=0)
                adb_utils.uninstall_app()
            progress(message="PDA에 앱 설치 중... (PDA 화면에 허용/설치 팝업이 뜨면 눌러 주세요)", done=0, total=0)
            ok, out = adb_utils.install_apk(apk)
            if not ok:
                return ("failed", out, (False, ""))
            progress(message="설치 확인 및 앱 실행 중...", done=0, total=0)
            info = adb_utils.get_installed_info()
            launched = adb_utils.launch_app()
            return ("ok", launched, info)

        def done(result, error):
            if error is not None:
                messagebox.showerror("오류", f"PDA 앱 설치 중 오류: {error}")
                return
            kind, payload, info = result
            if kind == "ok":
                ok_conn, conn_msg = adb_utils.check_device_connected()
                self._apply_status(ok_conn, conn_msg, info)
                ver = f" (버전 {info[1]})" if info[0] and info[1] else ""
                text = ("기존 앱을 삭제하고 새로 설치했습니다." if reinstall else "PDA에 앱 설치가 완료되었습니다.") + ver
                text += "\nPDA에서 앱을 실행했습니다." if payload else "\nPDA에서 앱을 직접 실행해 주세요."
                self.lbl_msg.config(text=text, fg="#1E7A3C")
                messagebox.showinfo("PDA 앱 설치", text)
            elif (not reinstall) and (("UPDATE_INCOMPATIBLE" in payload) or ("signatures do not match" in payload)):
                if messagebox.askyesno(
                        "PDA 앱 설치",
                        "PDA에 이미 설치된 앱과 서명이 달라 덮어쓸 수 없습니다.\n\n"
                        "기존 앱을 삭제하고 다시 설치할까요?\n"
                        "※ 삭제하면 PDA 앱 안에 남아있는 실사 데이터도 함께 지워집니다.\n"
                        "   필요한 데이터는 먼저 [PDA Data 수신]으로 받아두세요.", icon="warning"):
                    self._do_install(apk, reinstall=True)
            else:
                self.lbl_msg.config(text="PDA 앱 설치에 실패했습니다.\n" + payload, fg="#B03030")
                messagebox.showerror("오류", "PDA 앱 설치에 실패했습니다.\n\n" + payload)

        run_with_progress(self, "PDA 앱 설치", work, done, cancelable=False,
                          initial_message="PDA에 앱 설치 준비 중...")
