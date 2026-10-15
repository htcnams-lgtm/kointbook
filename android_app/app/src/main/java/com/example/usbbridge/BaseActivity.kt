// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.os.Bundle
import android.view.KeyEvent
import android.view.View
import androidx.appcompat.app.AppCompatActivity

/**
 * 모든 화면이 상속하는 기본 액티비티.
 *
 * 물리 엔터키(하드웨어 키패드/스캐너 키패드)를 눌렀을 때, 현재 포커스가
 * 있는 입력창이 자기만의 처리(예: 바코드 입력 후 다음 칸으로 이동)를
 * 이미 소비했다면 그대로 두고, 아무도 처리하지 않았다면 이 화면의
 * "대표 버튼"(다음/완료/저장/조회 등)을 대신 눌러준다.
 *
 * onKeyDown은 dispatchKeyEvent와 달리, 포커스를 가진 뷰가 키 이벤트를
 * 스스로 소비(return true)하지 않았을 때만 호출되는 "최후 처리" 지점이라
 * 각 화면의 입력창별 엔터 동작(예: EditText의 editorActionListener)을
 * 방해하지 않는다.
 *
 * 방향키(D-pad)는 안드로이드 기본 포커스 탐색을 그대로 사용하되,
 * 화면별로 필요한 곳에 nextFocusDown/Right 등을 지정해 이동 순서를 보정한다.
 */
abstract class BaseActivity : AppCompatActivity() {

    /** 이 화면에서 엔터키를 누르면 대신 클릭될 버튼. 없으면 null. */
    open fun primaryButton(): View? = null

    // [2026-09-30] "화면을 껐다 키면 점포코드, 날짜가 최초로 바뀌거나 다른거로
    // 바뀌어서 전송에 문제" - 백그라운드에서 프로세스가 죽었다가 스플래시를
    // 거치지 않고 아무 화면으로나 바로 되살아나는 경우에도, AppState가 그
    // 화면에서 값을 쓰기 전에 먼저 DB에 저장해둔 마지막 상태로 복원되도록
    // 모든 화면의 공통 진입점(onCreate)에서 한 번 호출한다(AppState.kt 참고).
    override fun onCreate(savedInstanceState: Bundle?) {
        AppState.ensureRestored(this)
        super.onCreate(savedInstanceState)
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_ENTER || keyCode == KeyEvent.KEYCODE_NUMPAD_ENTER) {
            val btn = primaryButton()
            if (btn != null && btn.isEnabled && btn.visibility == View.VISIBLE) {
                btn.performClick()
                return true
            }
        }
        return super.onKeyDown(keyCode, event)
    }
}
