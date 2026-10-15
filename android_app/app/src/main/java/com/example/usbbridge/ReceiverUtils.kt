// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build

/**
 * 안드로이드 13(API 33) 이상에서는 registerReceiver 호출 시
 * RECEIVER_EXPORTED 또는 RECEIVER_NOT_EXPORTED를 반드시 지정해야 하며,
 * 지정하지 않으면 SecurityException으로 즉시 앱이 죽는다.
 * (기기 런처에 따라 이 크래시가 흰 화면 멈춤처럼 보일 수 있다.)
 *
 * 이 함수는 SDK 버전에 관계없이 안전하게 스캐너 브로드캐스트를 등록한다.
 * 스캐너 브로드캐스트는 기기 자체(펌웨어)에서 보내는 것이라 EXPORTED로 등록한다.
 */
fun Context.registerScanReceiverCompat(receiver: BroadcastReceiver, filter: IntentFilter) {
    try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            registerReceiver(receiver, filter)
        }
    } catch (_: Exception) {
        // 화면을 나갔다 들어오는 과정에서 이미 등록되어 있는 등의 예외로
        // 앱이 멈추거나 죽지 않도록 방어한다. (스캔은 잠시 안 될 수 있지만
        // 다음 화면 재진입 시 다시 정상 등록된다)
    }
}
