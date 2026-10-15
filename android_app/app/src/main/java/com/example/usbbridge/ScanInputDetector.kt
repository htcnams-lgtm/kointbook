// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.os.Handler
import android.os.Looper
import android.os.SystemClock

/**
 * [2026-10-02] 물리 스캔버튼으로 찍은 값이 "키보드로 친 것처럼" 입력칸에 들어오는데
 * 끝에 엔터가 안 붙는 스캐너 설정이면, 엔터를 직접 눌러야만 처리되던 문제를 막는다
 * ("자동모드인데 스캔해도 목록에 안 들어가고 멈춰 있고, 엔터를 눌러야 입력됨").
 *
 * 사람이 손으로 누르는 글자는 한 글자에 보통 0.1초 이상 걸리지만, 스캐너는 몇 ms 간격으로
 * 한꺼번에 쏟아 넣는다. 짧은 간격(maxGapMs)으로 연달아 들어온 글자가 minChars개 이상이고,
 * 그 뒤로 idleMs 동안 더 들어오지 않으면 "스캔이 끝났다"고 보고 onScanned를 한 번 부른다.
 * (스캐너가 엔터까지 붙여 보내는 설정이면 엔터 처리 쪽에서 cancel()을 불러 두 번 처리되지 않게 한다.)
 */
class ScanInputDetector(
    private val onScanned: () -> Unit,
    private val minChars: Int = 3,
    private val maxGapMs: Long = 60,
    private val idleMs: Long = 150
) {
    private val handler = Handler(Looper.getMainLooper())
    private var lastInputAt = 0L
    private var burstChars = 0

    /** 프로그램이 setText 등으로 값을 넣는 동안에는 true로 두어 스캔으로 오인하지 않게 한다. */
    var suppressed = false

    /** 방금 들어온 입력이 스캐너의 연속 입력(버스트)인지. */
    val isBurst: Boolean get() = burstChars >= minChars

    private val fire = Runnable {
        if (burstChars >= minChars) {
            burstChars = 0
            onScanned()
        } else {
            burstChars = 0
        }
    }

    /** 입력칸에 글자가 chars개 새로 들어올 때마다 부른다(잘려서 버려지는 글자도 포함). */
    fun noteInput(chars: Int) {
        if (suppressed || chars <= 0) return
        val now = SystemClock.uptimeMillis()
        if (now - lastInputAt > maxGapMs) burstChars = 0
        burstChars += chars
        lastInputAt = now
        handler.removeCallbacks(fire)
        handler.postDelayed(fire, idleMs)
    }

    /** 엔터로 이미 처리했거나 화면을 떠날 때: 대기 중인 자동 처리를 취소한다. */
    fun cancel() {
        handler.removeCallbacks(fire)
        burstChars = 0
    }
}
