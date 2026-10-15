# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""
진행 상황을 주고받는 공용 객체 (화면/tkinter와 무관한 순수 파이썬).

오래 걸리는 작업(파일 전송, 엑셀 읽기, 무선 전송 등)은 백그라운드
스레드에서 돌리고, 그 스레드가 이 Progress 객체를 호출해서 "지금 어디까지
했는지"를 알려준다. 화면(progress_dialog.py)은 이 값을 주기적으로 읽어서
진행률 팝업을 갱신한다. (tkinter 위젯은 스레드에서 직접 건드리면 안 되기
때문에, 이렇게 값만 공유하는 방식으로 분리했다.)

사용 예
-------
    def work(progress):
        progress(message="파일 만드는 중...", done=0, total=1000, unit="count")
        ...
        progress(done=500)
        progress.check_cancel()   # 사용자가 [취소]를 눌렀으면 Cancelled 예외
"""

import threading
import time


class Cancelled(Exception):
    """사용자가 진행률 팝업에서 [취소]를 눌렀을 때 작업을 중단시키는 예외."""


class Progress:
    def __init__(self):
        self._lock = threading.Lock()
        self.message = ""
        self.done = 0
        self.total = 0          # 0 이하이면 전체 크기를 모르는 상태(빙글빙글 표시)
        self.unit = "count"     # "count"(건) 또는 "bytes"(파일 크기)
        self.cancelled = False
        self._phase_started = time.time()

    def __call__(self, done=None, total=None, message=None, unit=None):
        """값을 바꾼다. 넘기지 않은 항목은 그대로 둔다.
        message/total/unit이 바뀌면 새 단계가 시작된 것으로 보고 남은 시간
        계산(속도)을 처음부터 다시 잰다."""
        with self._lock:
            changed = False
            if message is not None and message != self.message:
                self.message = message
                changed = True
            if unit is not None and unit != self.unit:
                self.unit = unit
                changed = True
            if total is not None and total != self.total:
                self.total = total
                changed = True
            if done is not None:
                self.done = done
            elif changed:
                self.done = 0
            if changed:
                self._phase_started = time.time()

    def snapshot(self):
        """(message, done, total, unit, phase_elapsed_seconds)"""
        with self._lock:
            return (self.message, self.done, self.total, self.unit,
                    time.time() - self._phase_started)

    def cancel(self):
        self.cancelled = True

    def check_cancel(self):
        if self.cancelled:
            raise Cancelled("사용자가 취소했습니다.")


def report(progress, **kwargs):
    """progress가 None이어도 안전하게 부를 수 있는 도우미."""
    if progress is not None:
        progress(**kwargs)


def format_seconds(sec):
    sec = int(max(0, sec))
    m, s = divmod(sec, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}시간 {m}분"
    if m:
        return f"{m}분 {s:02d}초"
    return f"{s}초"


def format_detail(done, total, unit, phase_elapsed, total_elapsed):
    """진행률 팝업 아래쪽에 보여줄 두 줄짜리 설명 문구를 만든다.
    (진행 수치, 경과/남은 시간)"""
    if unit == "bytes":
        def fmt(n):
            return f"{n / 1048576:.1f} MB"
    else:
        def fmt(n):
            return f"{int(n):,}건"

    if total and total > 0:
        pct = min(100.0, done * 100.0 / total)
        line1 = f"{fmt(done)} / {fmt(total)}  ({pct:.0f}%)"
        if done > 0 and phase_elapsed >= 1.0 and done < total:
            remain = phase_elapsed * (total - done) / done
            line2 = f"경과 {format_seconds(total_elapsed)}  ·  남은 시간 약 {format_seconds(remain)}"
        else:
            line2 = f"경과 {format_seconds(total_elapsed)}"
    else:
        line1 = f"{fmt(done)} 처리 중..." if done and done > 0 else ""
        line2 = f"경과 {format_seconds(total_elapsed)}"
    return line1, line2
