// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.os.Bundle
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast

/** 환경설정: IP 설정 / 비밀번호설정
 * [2026-09-30] "환경설정 화면 시간 설정 항목 및 내용을 없애고 비밀번호설정
 * 버튼이 바로 보이게" - 기기 날짜/시각을 보여주던 "시간 설정" 그룹을 통째로
 * 없앴다(activity_settings.xml 참고). */
class SettingsActivity : BaseActivity() {

    private lateinit var db: DbHelper
    private lateinit var etIp: EditText
    private var btnSave: android.view.View? = null

    override fun primaryButton(): android.view.View? = btnSave

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)
        db = DbHelper.getInstance(this)

        findViewById<TextView>(R.id.tvTitleBarText).text = "KOINTBOOK [환경설정]"

        etIp = findViewById(R.id.etIp)
        etIp.setText(db.getSetting("ip", AppState.ip))

        findViewById<android.widget.Button>(R.id.btnPasswordSetting).setOnClickListener {
            showPasswordDialog()
        }

        findViewById<android.widget.Button>(R.id.btnSave).also { btnSave = it }.setOnClickListener {
            val ip = etIp.text.toString().trim()
            db.setSetting("ip", ip)
            AppState.ip = ip
            Toast.makeText(this, "저장되었습니다.", Toast.LENGTH_SHORT).show()
            finish()
        }
        findViewById<android.widget.Button>(R.id.btnCancel).setOnClickListener { finish() }
    }

    private fun showPasswordDialog() {
        val input = EditText(this)
        input.hint = "새 비밀번호 (숫자)"
        input.setHintTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.text_secondary))
        input.setTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.text_primary))
        input.inputType = android.text.InputType.TYPE_CLASS_NUMBER or android.text.InputType.TYPE_NUMBER_VARIATION_PASSWORD

        Dialogs.prompt(
            activity = this,
            title = "비밀번호설정",
            inputView = input,
            positiveText = "저장",
            negativeText = "취소",
            onPositive = {
                db.setSetting("password", input.text.toString())
                Toast.makeText(this, "비밀번호가 설정되었습니다.", Toast.LENGTH_SHORT).show()
            }
        )
    }
}
