// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.app.Application
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 앱 전역에서 잡히지 않은 예외(크래시)를 파일로 남긴다.
 *
 * 산업용 PDA 런처는 크래시가 나도 오류창을 안 띄우고 그냥 흰 화면만
 * 보여주는 경우가 있어서, 무슨 일이 있었는지 확인할 방법이 없다.
 * 이 로그 파일을 adb pull로 받아보면 정확한 원인을 알 수 있다.
 *
 * 로그 위치: /storage/emulated/0/Android/data/com.example.usbbridge/files/crash.log
 * 받는 방법: adb pull /storage/emulated/0/Android/data/com.example.usbbridge/files/crash.log
 */
class KointBookApp : Application() {

    override fun onCreate() {
        super.onCreate()
        val defaultHandler = Thread.getDefaultUncaughtExceptionHandler()

        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                val dir = getExternalFilesDir(null) ?: filesDir
                val logFile = File(dir, "crash.log")
                val sw = StringWriter()
                throwable.printStackTrace(PrintWriter(sw))
                val time = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())
                logFile.appendText("\n===== $time =====\n$sw\n")
            } catch (_: Exception) {
                // 로그 기록 자체가 실패해도 원래 크래시 처리 흐름은 막지 않는다.
            }
            defaultHandler?.uncaughtException(thread, throwable)
        }
    }
}
