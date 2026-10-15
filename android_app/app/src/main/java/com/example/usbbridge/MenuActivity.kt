// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.content.Intent
import android.os.Bundle
import android.view.KeyEvent
import android.widget.TextView

/** 실사메뉴: Data 입력 / Data 관리 진입점 (숫자키 1, 2로도 진입 가능) */
class MenuActivity : BaseActivity() {
    private var btnDataInput: android.view.View? = null

    override fun primaryButton(): android.view.View? = btnDataInput

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_menu)

        findViewById<TextView>(R.id.tvTitleBarText).text = "KOINTBOOK [메뉴]"
        // [2026-10-02] "점포코드 / 점포명 / 작업자" 형식, 글씨 1사이즈 크게(15sp -> 16sp, activity_menu.xml)
        findViewById<TextView>(R.id.tvHeader).text = "${AppState.storeCode} / ${AppState.storeName} / ${AppState.workerName}"

        btnDataInput = findViewById<android.widget.Button>(R.id.btnDataInput).also {
            it.setOnClickListener { goDataInput() }
        }
        findViewById<android.widget.Button>(R.id.btnDataManage).setOnClickListener { goDataManage() }
    }

    private fun goDataInput() {
        startActivity(Intent(this, LocationInputActivity::class.java))
    }

    private fun goDataManage() {
        startActivity(Intent(this, DataManageActivity::class.java))
    }

    /** 물리/소프트 숫자키 1, 2 를 눌러도 각각 Data 입력 / Data 관리로 진입 */
    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        when (keyCode) {
            KeyEvent.KEYCODE_1, KeyEvent.KEYCODE_NUMPAD_1 -> {
                goDataInput()
                return true
            }
            KeyEvent.KEYCODE_2, KeyEvent.KEYCODE_NUMPAD_2 -> {
                goDataManage()
                return true
            }
        }
        return super.onKeyDown(keyCode, event)
    }
}
