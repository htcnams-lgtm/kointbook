# -*- mode: python ; coding: utf-8 -*-
# KOINTBOOK PC 프로그램 - PyInstaller 빌드 설정 파일 (exe 파일 하나로 실행).
#
# [2026-09-28] "ZZOINT는 EXE 파일 하나로 모두 실행되게 platform-tools도
# 포함되는데? exe파일하나로 다되게 만들어줘" - ZZOINT와 똑같이 실행
# 파일 하나(KOINTBOOK_pc.exe)만 옮기면 되도록 --onefile 방식으로 만든다.
# assets(로고/아이콘 등)와 platform-tools(adb) 폴더도 이 exe 안에 그대로
# 같이 담기고, 실행될 때 임시 폴더에 풀렸다가 쓰인다(이미 base_dir.py/
# adb_utils.py가 그 "PyInstaller onefile 임시 폴더" 상황을 감안해서
# 만들어져 있다).
#
# [발행] 버튼의 인쇄 미리보기/인쇄 대화상자 기능(win32com/pywin32)도 exe
# 안에서 그대로 동작하도록, PyInstaller가 정적 분석만으로는 못 찾는
# pywin32 내부 모듈들(win32timezone 등)을 hiddenimports에 명시적으로
# 적어뒀다 - 그냥 `pyinstaller KOINTBOOK_pc.py`로 직접 빌드하면 이 모듈들이
# 빠져서, exe로 실행했을 때만 인쇄 미리보기가 안 뜨고 조용히 인쇄만 되는
# 문제가 생길 수 있다.
#
# 사용법 (Windows, 엑셀 설치된 PC, KOINTBOOK/pc_app 폴더 안에서):
#   pip install openpyxl pywin32 pyinstaller
#   pyinstaller KOINTBOOK.spec
#
# 빌드가 끝나면 dist\KOINTBOOK_pc.exe 파일 하나만 생긴다 - 이 파일 하나만
# 옮겨서 실행하면 된다(assets/platform-tools도 이미 exe 안에 들어있다).

import os

block_cipher = None

# 이 스펙 파일이 있는 폴더(=pc_app) 기준으로 데이터 폴더 경로를 잡는다 -
# 어느 위치에서 pyinstaller를 실행해도 항상 같은 폴더를 찾도록 한다.
BASE_DIR = os.path.dirname(os.path.abspath(SPEC))

# 프로그램이 실행 중에 읽는 폴더/파일들 - 실제로 존재하는 것만 exe 안에
# 함께 담는다(platform-tools가 없는 환경에서 빌드해도 빌드 자체는 되고,
# 그 경우 PDA는 엑셀로만 주고받게 된다).
datas = []
for name in ("assets", "platform-tools"):
    src = os.path.join(BASE_DIR, name)
    if os.path.isdir(src):
        datas.append((src, name))

# [2026-10-06] "exe를 생성할때 마지막 버전을 날짜와 함께 내장" - pc_app/apk 폴더의 가장
# 최근 .apk 파일 "하나만" exe 안에 담고, 그 파일 이름/날짜를 apk_info.json에 같이 적어
# 둔다(PDA 앱 설치 화면이 "내장 설치파일 있음 - 이름, 날짜"로 보여준다). 폴더에 .apk가
# 없으면 내장 없이 빌드된다(설치 화면에서 파일을 직접 골라야 한다).
import glob
import json
import time
_apk_dir = os.path.join(BASE_DIR, "apk")
_apks = sorted(glob.glob(os.path.join(_apk_dir, "*.apk")), key=os.path.getmtime, reverse=True)
if _apks:
    _latest = _apks[0]
    _info = {
        "file": os.path.basename(_latest),
        "apk_date": time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(_latest))),
        "embedded_at": time.strftime("%Y-%m-%d %H:%M", time.localtime()),
    }
    _info_path = os.path.join(_apk_dir, "apk_info.json")
    with open(_info_path, "w", encoding="utf-8") as _f:
        json.dump(_info, _f, ensure_ascii=False)
    datas.append((_latest, "apk"))
    datas.append((_info_path, "apk"))
    print("[KOINTBOOK.spec] 내장 설치파일:", _info["file"], _info["apk_date"])
else:
    print("[KOINTBOOK.spec] pc_app/apk 폴더에 .apk가 없어 설치파일 없이 빌드합니다.")

# [2026-09-28] pywin32(win32com)로 엑셀 인쇄 미리보기를 띄우는 기능 -
# PyInstaller가 정적 분석만으로는 못 찾는 pywin32 내부 모듈들을 직접
# 적어준다. pywin32가 설치돼 있지 않은 환경에서 빌드하면 이 모듈들이
# 없어서 빌드 자체가 실패할 수 있으니, 빌드 전에 반드시
# `pip install pywin32`를 먼저 해야 한다.
hiddenimports = [
    "win32timezone",
    "win32com",
    "win32com.client",
    "pythoncom",
    "pywintypes",
]

a = Analysis(
    ["KOINTBOOK_pc.py"],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon_path = os.path.join(BASE_DIR, "assets", "icon.ico")
icon_arg = icon_path if os.path.isfile(icon_path) else None

# [2026-09-28] --onefile: binaries/zipfiles/datas를 EXE 단계에 그대로
# 넘기고 별도 COLLECT 단계를 두지 않으면, dist 폴더 안에 exe 파일 하나만
# 생긴다(ZZOINT와 동일한 배포 방식).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="KOINTBOOK_pc",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 콘솔창 없이 프로그램 창만 뜨게 한다
    icon=icon_arg,
)
