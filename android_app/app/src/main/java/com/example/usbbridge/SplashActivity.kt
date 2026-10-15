// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.TextView
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** 초기화면: KOINTBOOK 스플래시 */
class SplashActivity : BaseActivity() {

    private lateinit var db: DbHelper
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var tvDate: TextView
    private lateinit var tvTime: TextView
    private var btnStart: android.view.View? = null

    override fun primaryButton(): android.view.View? = btnStart

    private val clockRunnable = object : Runnable {
        override fun run() {
            val now = Date()
            tvDate.text = SimpleDateFormat("yyyy년 MM월 dd일", Locale.getDefault()).format(now)
            tvTime.text = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(now)
            handler.postDelayed(this, 1000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_splash)

        db = DbHelper.getInstance(this)
        AppState.ip = db.getSetting("ip", AppState.ip)
        db.findFirstStore()?.let { (code, name) ->
            AppState.storeCode = code
            AppState.storeName = name
        }

        // 마스터 파일 가져오기는 상품 수가 많으면 시간이 걸릴 수 있으므로
        // 화면이 먼저 뜨도록 백그라운드 스레드에서 처리한다.
        Thread {
            db.importMasterFilesIfPresent(getExternalFilesDir(null))
            db.findFirstStore()?.let { (code, name) ->
                AppState.storeCode = code
                AppState.storeName = name
            }
        }.start()

        findViewById<TextView>(R.id.tvTitleBarText).text = "KOINTBOOK"

        tvDate = findViewById(R.id.tvDate)
        tvTime = findViewById(R.id.tvTime)

        findViewById<android.widget.Button>(R.id.btnStart).also { btnStart = it }.setOnClickListener {
            startActivity(Intent(this, WorkPrepActivity::class.java))
        }
        findViewById<android.widget.Button>(R.id.btnSettings).setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
        findViewById<android.widget.Button>(R.id.btnExit).setOnClickListener {
            finishAffinity()
        }
        // 물리 엔터키를 한 번만 눌러도 확실히 '시작' 버튼이 눌리도록, 화면
        // 진입 즉시(다음 프레임까지 미루지 않고) 이 버튼에 포커스를 준다.
        // post{}로 미루면, 포커스가 실제로 옮겨지기 전에 사용자가 아주 빠르게
        // 엔터를 누르는 경우 첫 번째 입력이 무시되고 두 번째부터 먹히는
        // 문제가 있었다.
        //
        // 또한 앱은 기본적으로 "터치 모드"로 시작하는데, 터치 모드에서는
        // focusableInTouchMode가 true인 뷰만 실제로 포커스를 받을 수 있다
        // (버튼은 기본값이 false라 requestFocus()를 불러도 조용히 무시됨 -
        // 그래서 포커스 테두리가 처음엔 안 보이다가 방향키를 한 번 눌러야만
        // 나타났던 것). 코드에서도 명시적으로 켜서 XML 설정과 상관없이
        // 항상 보장되게 한다.
        btnStart?.isFocusableInTouchMode = true
        btnStart?.requestFocus()
    }

    override fun onResume() {
        super.onResume()
        handler.post(clockRunnable)
    }

    override fun onPause() {
        super.onPause()
        handler.removeCallbacks(clockRunnable)
    }
}
