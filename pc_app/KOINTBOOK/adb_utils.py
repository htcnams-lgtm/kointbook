# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
adb(USB 디버깅) 명령을 감싸는 유틸리티.

PDA(안드로이드)와 PC 사이의 실제 데이터 교환은 실시간 통신이 아니라,
USB로 연결된 상태에서 adb pull/push로 파일을 주고받는 방식이다.

- PDA -> PC : STOCK.db 파일을 adb pull로 가져온다 (재고실사수신)
- PC -> PDA : STORE.db / WORKER.db / PRODUCT.db 파일을 adb push로 보낸다 (마스터관리 전송)

PDA 앱의 안드로이드 패키지명은 com.kointbook.app 이고,
앱 전용 외부 저장소 경로(/storage/emulated/0/Android/data/<패키지>/files/)는
루팅 없이 adb만으로 pull/push가 가능하다.

[2026-09-24 정정] 예전에는 ZZOINT PDA 앱과 똑같은 패키지명(com.example.usbbridge)을
그대로 썼는데(같은 기기에 ZZOINT/KOINTBOOK을 동시에 설치하지 않는다는 전제),
한 PC/한 PDA를 ZZOINT와 별도로 운영하려면 두 기기(앱)가 서로 다른 앱으로
인식돼야 해서 KOINTBOOK 전용 패키지명(com.kointbook.app)으로 바꿨다. 이 값은
android_app/app/build.gradle의 applicationId와 반드시 똑같아야 한다 - 다르면
adb가 PDA 앱의 파일 폴더를 못 찾는다."""

import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from .base_dir import get_base_dir, find_resource

PACKAGE_NAME = "com.kointbook.app"
DEVICE_FILES_DIR = f"/storage/emulated/0/Android/data/{PACKAGE_NAME}/files"


def find_adb_path() -> str:
    """
    adb(.exe)를 아래 순서로 찾는다.
    1. PyInstaller exe 안에 --add-data로 platform-tools를 함께 묶었다면,
       실행 시 그 안에 있는 adb를 찾는다 (exe 하나만 배포해도 동작).
    2. exe(또는 KOINTBOOK_pc.py)가 있는 폴더 옆의 platform-tools 폴더.
    3. 시스템 PATH에 등록된 adb.
    """
    candidates = []

    base_dir = get_base_dir()
    candidates.append(base_dir / "platform-tools" / "adb.exe")
    candidates.append(base_dir / "platform-tools" / "adb")

    if getattr(sys, "frozen", False):
        # PyInstaller가 --add-data로 묶은 파일은 실행 중 이 임시 폴더에서 풀린다.
        # (exe 옆에 platform-tools 폴더가 따로 없을 때의 대비책)
        bundled_root = getattr(sys, "_MEIPASS", None)
        if bundled_root:
            from pathlib import Path
            bundled = Path(bundled_root)
            candidates.append(bundled / "platform-tools" / "adb.exe")
            candidates.append(bundled / "platform-tools" / "adb")

    for c in candidates:
        if c.exists():
            return str(c)
    return "adb"


ADB_PATH = find_adb_path()


def _run(args, timeout=20):
    kwargs = {}
    if platform.system() == "Windows":
        # adb.exe를 실행할 때마다 검은 cmd 창이 잠깐씩 뜨는 걸 막는다.
        # (이게 안 켜져 있으면, 특히 1.5초마다 자동으로 확인하는 기능
        # 때문에 창이 계속 깜빡이는 것처럼 보인다.)
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(
        [ADB_PATH] + args,
        capture_output=True, text=True, timeout=timeout,
        **kwargs
    )


def kill_server():
    """adb 서버(백그라운드 프로세스)를 끈다.

    USB로 adb 명령을 한 번이라도 쓰면, adb는 이후 명령들을 빠르게 처리하려고
    스스로 "adb 서버"라는 백그라운드 프로세스를 띄워 계속 살려둔다 (adb의
    정상적인 동작이다). 문제는 이 exe가 adb.exe를 "자기 자신을 풀어놓은
    임시 폴더"(PyInstaller가 --onefile로 실행할 때 쓰는 _MEI 폴더) 안에서
    그대로 실행한다는 점이다 - adb 서버가 꺼지지 않은 채로 프로그램을 끄면,
    그 서버 프로세스가 물고 있는 adb.exe/DLL 파일 때문에 그 임시 폴더를
    끝까지 못 지우고 "Failed to remove temporary directory" 경고가 뜬다.

    그래서 프로그램이 완전히 끝나기 직전에(KOINTBOOK_pc.py에서 atexit로 등록)
    이 함수를 한 번 불러서 adb 서버를 확실히 꺼준다. USB로 한 번도 접속한
    적이 없어 서버가 애초에 떠 있지 않을 때도 그냥 조용히 끝난다."""
    try:
        kwargs = {}
        if platform.system() == "Windows":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.run([ADB_PATH, "kill-server"], capture_output=True, timeout=5, **kwargs)
    except Exception:
        pass  # 종료 직전 정리 작업이라, 실패해도 프로그램 종료 자체를 막지 않는다.


def check_device_connected():
    """기기가 연결되어 있고 인증되었는지 확인. (True/False, 메시지)"""
    try:
        result = _run(["devices"])
        lines = [l for l in result.stdout.splitlines()[1:] if l.strip()]
        if not lines:
            return False, "연결된 기기가 없습니다. USB 케이블과 USB 디버깅 허용 여부를 확인하세요."
        for line in lines:
            if "\tdevice" in line:
                return True, line.split("\t")[0]
        if any("unauthorized" in l for l in lines):
            return False, "기기에서 USB 디버깅 허용 팝업을 확인하세요 (unauthorized)."
        return False, "기기 상태를 확인할 수 없습니다: " + "; ".join(lines)
    except FileNotFoundError:
        return False, f"'{ADB_PATH}' 실행 파일을 찾을 수 없습니다. platform-tools 설치를 확인하세요."
    except Exception as e:
        return False, f"adb 확인 중 오류: {e}"


# 전송이 이 시간(초) 동안 조금도 진행되지 않으면 멈춘 것으로 보고 중단한다.
# (예전에는 "무조건 60초"였다 - 상품마스터가 1만~30만 건이면 파일이 커서
#  정상적으로 전송 중이어도 60초를 넘겨 오류가 났다. 이제는 전체 시간이 아니라
#  "진행이 멈춘 시간"만 본다.)
STALL_TIMEOUT_SEC = 90

_remote_dir_ready = False


def _remote_size(remote_path):
    """기기 쪽 파일 크기(바이트). 알 수 없으면 None."""
    try:
        result = _run(
            ["shell", f"stat -c %s {remote_path} 2>/dev/null || wc -c < {remote_path} 2>/dev/null"],
            timeout=8
        )
        lines = [l.strip() for l in (result.stdout or "").splitlines() if l.strip()]
        if lines:
            return int(lines[-1].split()[0])
    except Exception:
        pass
    return None


def _run_transfer(args, total_bytes, probe, progress=None, label="전송 중..."):
    """adb push/pull 같은 오래 걸릴 수 있는 명령을 실행하면서, 0.5초마다
    probe()로 지금까지 옮겨진 크기를 읽어 progress에 알려준다.
    - 고정된 시간 제한 대신 "진행이 멈춘 시간"으로 멈춤 여부를 판단한다.
    - progress.cancelled가 켜지면 즉시 중단한다.
    반환: (성공여부, 메시지)"""
    kwargs = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    # adb가 출력하는 내용(오류 메시지 등)을 파이프 대신 임시 파일로 받는다
    # (파이프는 안 읽으면 가득 차서 adb가 멈출 수 있다).
    log = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
    proc = None
    try:
        proc = subprocess.Popen(
            [ADB_PATH] + args, stdout=log, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, **kwargs
        )
        started = time.time()
        last_change = started
        last_size = -1
        seen_growth = False
        # 진행 크기를 못 읽는 기기/환경을 위한 대비용 전체 제한 시간 (파일이 클수록 넉넉하게)
        hard_timeout = max(300.0, (total_bytes or 0) / 1_000_000 * 20)

        if progress is not None:
            progress(done=0, total=total_bytes or 0, message=label, unit="bytes")

        while proc.poll() is None:
            if progress is not None and progress.cancelled:
                proc.kill()
                proc.wait()
                return False, "사용자가 취소했습니다."
            time.sleep(0.5)
            size = probe()
            now = time.time()
            if size is not None:
                if size != last_size:
                    last_size = size
                    last_change = now
                if size > 0:
                    seen_growth = True
                if progress is not None:
                    done = min(size, total_bytes) if total_bytes else size
                    progress(done=done, total=total_bytes or 0, message=label, unit="bytes")

            if seen_growth:
                # 크기가 늘어나는 게 눈에 보이는 경우: 늘어나다가 멈춘 시간만 본다.
                if now - last_change > STALL_TIMEOUT_SEC:
                    proc.kill()
                    proc.wait()
                    return False, f"전송이 {STALL_TIMEOUT_SEC}초 이상 진행되지 않아 중단했습니다. 케이블 연결을 확인하세요."
            elif now - started > hard_timeout:
                # 진행 크기를 아예 읽을 수 없는 경우(기기/저장소에 따라 가능): 넉넉한 전체 제한 시간만 적용한다.
                proc.kill()
                proc.wait()
                return False, "전송 시간이 너무 오래 걸려 중단했습니다."

        log.seek(0)
        output = log.read().strip()
        if proc.returncode == 0:
            if progress is not None and total_bytes:
                progress(done=total_bytes, total=total_bytes, message=label, unit="bytes")
            return True, "OK"
        return False, output or f"adb 종료 코드 {proc.returncode}"
    except Exception as e:
        return False, str(e)
    finally:
        try:
            if proc is not None and proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        log.close()


def pull_file(remote_filename: str, local_path: str, progress=None):
    """DEVICE_FILES_DIR 안의 파일을 로컬로 pull. 성공 여부와 메시지를 반환.
    progress(선택): 파일 크기 기준 진행률을 알려줄 Progress 객체."""
    remote_path = f"{DEVICE_FILES_DIR}/{remote_filename}"
    total = _remote_size(remote_path) or 0

    def probe():
        try:
            return os.path.getsize(local_path) if os.path.exists(local_path) else 0
        except OSError:
            return None

    return _run_transfer(["pull", remote_path, local_path], total, probe, progress,
                         label="PDA에서 파일을 받는 중...")


def push_file(local_path: str, remote_filename: str, progress=None):
    """로컬 파일을 DEVICE_FILES_DIR 안으로 push.

    처음부터 최종 이름으로 보내지 않고 '.part' 임시 이름으로 다 보낸 뒤에
    이름을 바꾼다. 이렇게 해야 (특히 큰 상품마스터를 보내는 중에) PDA가
    "마스터 수신" 버튼을 켜고 아직 덜 도착한 파일을 읽어버리는 일이 없다.
    progress(선택): 파일 크기 기준 진행률을 알려줄 Progress 객체."""
    global _remote_dir_ready
    remote_path = f"{DEVICE_FILES_DIR}/{remote_filename}"
    remote_tmp = remote_path + ".part"
    try:
        total = os.path.getsize(local_path)
    except OSError as e:
        return False, str(e)

    try:
        if not _remote_dir_ready:
            # 폴더가 없을 수 있으니 먼저 만들어본다 (이미 있으면 무시됨). 한 번만 하면 된다.
            _run(["shell", "mkdir", "-p", DEVICE_FILES_DIR], timeout=15)
            _remote_dir_ready = True
        _run(["shell", "rm", "-f", remote_tmp], timeout=15)

        def probe():
            return _remote_size(remote_tmp) or 0

        ok, msg = _run_transfer(["push", local_path, remote_tmp], total, probe, progress,
                                label="PDA로 파일을 보내는 중...")
        if not ok:
            _run(["shell", "rm", "-f", remote_tmp], timeout=15)
            _remote_dir_ready = False  # 다음번에는 폴더 확인부터 다시
            return False, msg

        result = _run(["shell", f"mv -f {remote_tmp} {remote_path}"], timeout=30)
        if result.returncode != 0:
            return False, (result.stderr.strip() or result.stdout.strip() or "파일 이름을 바꾸지 못했습니다.")
        return True, "OK"
    except Exception as e:
        _remote_dir_ready = False
        return False, str(e)


def remote_file_exists(remote_filename: str) -> bool:
    """DEVICE_FILES_DIR 안에 해당 파일이 있는지 확인한다.
    (예: STOCK.db가 있으면 PDA에서 PC로 보낼 실사 데이터가 준비된 것으로 판단)"""
    remote_path = f"{DEVICE_FILES_DIR}/{remote_filename}"
    try:
        result = _run(["shell", f"test -f {remote_path} && echo YES || echo NO"], timeout=10)
        return "YES" in result.stdout
    except Exception:
        return False


def start_remote_file_watcher(remote_filename: str, on_status_change):
    """adb.exe를 매번 새로 실행하는 대신, adb shell을 딱 한 번만 실행해서
    그 안에서(기기 쪽에서) 1초마다 파일 존재 여부를 계속 반복 확인하도록
    한다 - PC 쪽에서는 그 출력을 그냥 읽기만 하면 되니 adb.exe를 반복 실행할
    필요가 없다. 파일이 생기거나 없어질 때마다 on_status_change(True/False)를
    호출한다 (백그라운드 스레드에서 호출되니, 받는 쪽에서 UI를 직접 건드리지
    말고 스레드 안전한 방법으로 처리해야 한다).

    기기 연결이 끊기는 등으로 감시가 끊기면 자동으로 재연결을 시도한다.
    반환값(정지 함수)을 호출하면 감시를 완전히 멈춘다."""
    remote_path = f"{DEVICE_FILES_DIR}/{remote_filename}"
    # 안드로이드 기기 쪽 셸에서 도는 무한 반복문 - 이 한 줄짜리 스크립트를
    # 실행하는 adb shell 프로세스 하나만 떠 있으면 된다.
    shell_cmd = f"while true; do [ -f {remote_path} ] && echo __READY__ || echo __NOTREADY__; sleep 1; done"

    state = {"stop": False, "proc": None}

    def _worker():
        while not state["stop"]:
            try:
                kwargs = {}
                if platform.system() == "Windows":
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                proc = subprocess.Popen(
                    [ADB_PATH, "shell", shell_cmd],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, bufsize=1, **kwargs
                )
                state["proc"] = proc
                for line in proc.stdout:
                    if state["stop"]:
                        break
                    line = line.strip()
                    if line == "__READY__":
                        on_status_change(True)
                    elif line == "__NOTREADY__":
                        on_status_change(False)
                proc.wait()
            except Exception:
                pass
            if state["stop"]:
                break
            # 기기가 뽑혔거나 오류가 난 것 - 꺼짐으로 표시하고 2초 쉬었다 재시도
            # (이건 "연결 안 되어 있는 동안"에만 도는 거라, 항상 반복되던
            # 예전 방식과는 달리 케이블을 다시 꽂을 때 너무 오래 기다리지
            # 않도록 짧게 잡아도 괜찮다)
            try:
                on_status_change(False)
            except Exception:
                pass
            time.sleep(2)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    def stop():
        state["stop"] = True
        proc = state.get("proc")
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass

    return stop


def remove_remote_file(remote_filename: str):
    """pull 후 중복 수신을 막기 위해 기기 쪽 파일을 삭제 (실패해도 치명적이지 않음)."""
    remote_path = f"{DEVICE_FILES_DIR}/{remote_filename}"
    try:
        _run(["shell", "rm", "-f", remote_path], timeout=15)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# [2026-10-06] "pc프로그램 쪽에 pda에 저 앱을 설치하게 하는 기능" - PC 프로그램에서
# USB로 연결된 PDA에 KOINTBOOK 앱(APK)을 설치한다. PDA에서 APK 파일을 직접 눌러
# 설치할 때 뜨는 Play 프로텍트/설치 화면 문제 없이, adb로 바로 설치된다.
#
# 설치할 APK는 pc_app/apk 폴더(exe로 묶을 때는 exe 안에 같이 담긴다)에 둔 .apk
# 파일을 쓴다. 폴더에 없으면 화면에서 직접 파일을 고르게 한다.
# ---------------------------------------------------------------------------
APK_DIR_NAME = "apk"


def find_bundled_apk():
    """pc_app/apk(또는 exe 안의 apk) 폴더에서 가장 최근 .apk 파일 경로. 없으면 None."""
    try:
        folder = find_resource(APK_DIR_NAME)
        if not folder.is_dir():
            return None
        apks = sorted(folder.glob("*.apk"), key=lambda f: f.stat().st_mtime, reverse=True)
        return str(apks[0]) if apks else None
    except Exception:
        return None


def bundled_apk_info():
    """내장(또는 apk 폴더의) 설치파일 정보. 없으면 None.
    반환: {"path", "file", "date"(파일 날짜), "embedded_at"(exe에 내장한 날짜, 모르면 "")}
    exe로 만들 때 KOINTBOOK.spec이 apk_info.json에 적어 둔 날짜를 우선 쓰고(exe 안에서는
    파일 날짜가 풀린 시각으로 바뀌므로), 없으면(소스로 실행) 파일 자체의 수정 날짜를 쓴다."""
    path = find_bundled_apk()
    if not path:
        return None
    name = os.path.basename(path)
    info = {"path": path, "file": name, "date": "", "embedded_at": ""}
    try:
        import json
        jp = os.path.join(os.path.dirname(path), "apk_info.json")
        if os.path.isfile(jp):
            with open(jp, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("file") == name:
                info["date"] = data.get("apk_date", "")
                info["embedded_at"] = data.get("embedded_at", "")
    except Exception:
        pass
    if not info["date"]:
        try:
            info["date"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
        except Exception:
            pass
    return info


def install_apk(apk_path: str):
    """adb install -r -d -t 로 APK를 설치(기존 앱이 있으면 데이터 유지한 채 덮어씀).
    반환: (성공 여부, adb 출력 메시지)"""
    try:
        result = _run(["install", "-r", "-d", "-t", apk_path], timeout=300)
        out = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        return ("Success" in (result.stdout or "")), out
    except subprocess.TimeoutExpired:
        return False, "설치 시간이 너무 오래 걸려 중단했습니다."
    except Exception as e:  # noqa: BLE001
        return False, f"설치 중 오류: {e}"


def uninstall_app():
    """PDA에서 KOINTBOOK 앱을 삭제한다(앱 안의 데이터도 함께 지워진다).
    반환: (성공 여부, 메시지)"""
    try:
        result = _run(["uninstall", PACKAGE_NAME], timeout=60)
        out = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        return ("Success" in (result.stdout or "")), out
    except Exception as e:  # noqa: BLE001
        return False, f"삭제 중 오류: {e}"


def get_installed_info():
    """PDA에 KOINTBOOK 앱이 설치되어 있는지 확인한다.
    반환: (설치 여부, 버전 이름 또는 "")"""
    try:
        r = _run(["shell", "pm", "list", "packages", PACKAGE_NAME], timeout=20)
        lines = [l.strip() for l in (r.stdout or "").splitlines()]
        if f"package:{PACKAGE_NAME}" not in lines:
            return False, ""
        r2 = _run(["shell", "dumpsys", "package", PACKAGE_NAME], timeout=20)
        import re
        m = re.search(r"versionName=(\S+)", r2.stdout or "")
        return True, (m.group(1) if m else "")
    except Exception:
        return False, ""


def launch_app():
    """PDA에서 KOINTBOOK 앱을 바로 실행한다. 반환: 성공 여부"""
    try:
        r = _run(["shell", "monkey", "-p", PACKAGE_NAME,
                  "-c", "android.intent.category.LAUNCHER", "1"], timeout=20)
        return r.returncode == 0 and "No activities found" not in (r.stdout or "") + (r.stderr or "")
    except Exception:
        return False
