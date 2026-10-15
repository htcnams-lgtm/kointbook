# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
프로그램 기준 폴더(base dir)를 알려주는 공용 함수.

일반적으로 `python KOINTBOOK_pc.py`로 실행할 때는 pc_app 폴더가 기준이지만,
PyInstaller로 exe를 만들면 실행 중에는 파일들이 임시 폴더에 풀렸다가
프로그램이 꺼지면 사라지기 때문에, DB 파일이나 platform-tools 폴더를
"임시 폴더" 기준으로 찾으면 실행할 때마다 데이터가 초기화되거나 adb를
못 찾는 문제가 생긴다. 그래서 exe로 실행 중(getattr(sys, 'frozen', False))
일 때는 반드시 "exe 파일이 실제로 있는 폴더"를 기준으로 삼아야 한다.
"""

import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        # PyInstaller로 패키징된 exe로 실행 중: exe가 있는 실제 폴더
        return Path(sys.executable).resolve().parent
    # 일반 파이썬 스크립트로 실행 중: KOINTBOOK_pc.py가 있는 pc_app 폴더
    return Path(__file__).resolve().parent.parent


def find_resource(*parts) -> Path:
    """[2026-09-28] "exe파일하나로 다되게 만들어줘" - assets(로고 등)처럼
    읽기전용 리소스는 이제 exe 안(--onefile로 함께 묶임)에도 들어있고,
    옛날처럼 exe 옆에 폴더를 따로 두는 배포 방식도 계속 지원해야 한다.
    get_base_dir()은 DB처럼 "실행 후에도 남아있어야 하는 파일" 전용으로
    항상 exe가 실제로 있는 폴더만 가리키는데, --onefile로 묶은 리소스는
    실행 중 임시 폴더(sys._MEIPASS)에 풀린 채로만 존재해서 그 폴더로는
    못 찾는다 - adb_utils.find_adb_path()가 이미 쓰던 순서(① exe 옆
    폴더 → ② onefile 임시 폴더)를 로고 등 다른 리소스에도 공용으로 쓸 수
    있게 여기로 옮겼다.

    exe 옆(또는 소스 실행 시 pc_app) 폴더에 있으면 그 경로를, 없고 exe로
    packaging돼 있으면 onefile 임시 폴더(sys._MEIPASS) 쪽 경로를 돌려준다
    (둘 다 없으면 그냥 첫 번째 후보 경로를 그대로 돌려주고, 호출한 쪽에서
    .exists()로 확인해서 처리한다)."""
    external = get_base_dir().joinpath(*parts)
    if external.exists():
        return external
    if getattr(sys, "frozen", False):
        bundled_root = getattr(sys, "_MEIPASS", None)
        if bundled_root:
            bundled = Path(bundled_root).joinpath(*parts)
            if bundled.exists():
                return bundled
    return external
