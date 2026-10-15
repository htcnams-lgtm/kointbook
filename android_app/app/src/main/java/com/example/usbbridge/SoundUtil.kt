// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager

/**
 * [2026-09-30] "마스터에없는 미등록바코드 입력되어 팝업창이 나올시 경고소리를
 * 나게 해주고" - 별도 사운드 파일(mp3 등)을 앱에 새로 추가하지 않고도, 안드로이드
 * 내장 ToneGenerator로 짧은 경고음을 낸다(기기마다 다른 알림음 파일을 찾을
 * 필요가 없어 모든 PDA 기종에서 동일하게 동작한다).
 *
 * [2026-09-30 정정] "미등록 팝업창 경고음 짧고 현재보다 소리 작고 진동까지
 * 추가" - 톤 길이를 400ms -> 120ms로 짧게, 음량도 90 -> 45(0~100 중 절반
 * 이하)로 줄였고, 짧은 진동(200ms)을 함께 준다(AndroidManifest.xml에
 * VIBRATE 권한 추가됨).
 */
object SoundUtil {
    /** 마스터에 없는(미등록) 바코드 확인 팝업이 뜨기 직전에 호출한다. */
    fun warningBeep(context: Context? = null) {
        try {
            val tg = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 45)
            tg.startTone(ToneGenerator.TONE_CDMA_ABBR_ALERT, 120)
            // ToneGenerator는 재생이 끝나도 스스로 release되지 않으므로, 소리가
            // 다 나온 뒤(120ms + 여유)에 리소스를 정리한다.
            Handler(Looper.getMainLooper()).postDelayed({
                try { tg.release() } catch (_: Exception) {}
            }, 300)
        } catch (_: Exception) {
            // 일부 기기/상황(오디오 포커스 없음 등)에서 ToneGenerator 생성이
            // 실패할 수 있는데, 경고음은 부가 기능이므로 조용히 무시하고
            // 팝업 자체는 정상적으로 뜨게 둔다.
        }
        if (context != null) vibrateShort(context)
    }

    /** [2026-10-01] ZZOINT의 미등록 스캔 경고와 똑같은 소리/진동 (알람 볼륨 45,
     * TONE_CDMA_EMERGENCY_RINGBACK 250ms + 진동 300ms). 위치입력 화면에서 AREA/SECTION 칸에
     * 상품바코드로 의심되는 값이 스캔됐을 때 쓴다. */
    fun zzointWarning(context: Context) {
        try {
            val tone = ToneGenerator(AudioManager.STREAM_ALARM, 45)
            tone.startTone(ToneGenerator.TONE_CDMA_EMERGENCY_RINGBACK, 250)
            Handler(Looper.getMainLooper()).postDelayed({
                try { tone.release() } catch (_: Exception) {}
            }, 600)
        } catch (_: Exception) {
            // 소리를 못 내는 기기여도 입력 흐름에는 영향이 없도록 무시한다.
        }
        vibrate(context, 300)
    }

    private fun vibrateShort(context: Context) = vibrate(context, 200)

    private fun vibrate(context: Context, ms: Long) {
        try {
            val vibrator: Vibrator? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
                vm?.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
            }
            if (vibrator == null || !vibrator.hasVibrator()) return
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                vibrator.vibrate(ms)
            }
        } catch (_: Exception) {
            // 진동 역시 부가 기능이므로 실패해도 팝업 동작에는 지장이 없다.
        }
    }
}
