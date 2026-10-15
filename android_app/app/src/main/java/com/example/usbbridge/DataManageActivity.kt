// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.database.sqlite.SQLiteDatabase
import android.os.Bundle
import android.widget.TextView
import android.widget.Toast
import java.io.File
import java.text.NumberFormat
import java.util.Locale

/**
 * Data 관리 메뉴.
 *
 * "Data 전송"은 실시간 통신이 아니라, PDA에 쌓인 실사 데이터 전체를 외부
 * 저장소의 STOCK.db 파일(SQLite, 테이블명 stock_data)로 내보내는 것이다.
 * 이 파일을 PC가 USB 케이블(adb pull)로 가져가서 읽는다. 이미 한 번
 * 전송했더라도 PDA에는 데이터가 그대로 남아있으므로, 필요하면 몇 번이든
 * 다시 [Data 전송]을 눌러 재전송할 수 있다.
 *
 * ZZOINT에 있던 "무선전송"(Firebase) 메뉴는 KOINTBOOK에는 없다 - USB adb만
 * 쓰는 것으로 단순화했다 (숫자키 배정도 1=Data전송, 2=DATA조회,
 * 3=위치별 건수/수량 조회, 4=미전송확인 으로 한 칸씩 당겨졌다).
 *
 * [2026-10-15] "섹션별조회명을 data조회로, data조회를 data삭제로, 순서 서로 뒤바꿈" -
 * 2=DATA 조회(위치별 건수/수량, SectionQueryActivity), 3=DATA 삭제(위치 삭제,
 * DataQueryActivity)로 바꿨다. 화면 클래스 이름은 그대로다.
 */
class DataManageActivity : BaseActivity() {

    private lateinit var db: DbHelper

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_data_manage)
        db = DbHelper.getInstance(this)

        findViewById<TextView>(R.id.tvTitleBarText).text = "KOINTBOOK [Data 관리]"

        findViewById<android.widget.Button>(R.id.btnSend).setOnClickListener { confirmSend() }
        // 2. DATA 조회 (위치별 건수/수량)
        findViewById<android.widget.Button>(R.id.btnSectionQuery).setOnClickListener {
            startActivity(android.content.Intent(this, SectionQueryActivity::class.java))
        }
        // 3. DATA 삭제
        findViewById<android.widget.Button>(R.id.btnQuery).setOnClickListener {
            startActivity(android.content.Intent(this, DataQueryActivity::class.java))
        }
        findViewById<android.widget.Button>(R.id.btnUnsentCheck).setOnClickListener { showUnsentInfo() }
    }

    /** 숫자키 1~4로도 각 메뉴에 바로 들어갈 수 있게 한다.
     * (1=Data전송, 2=DATA 조회(위치별 건수/수량), 3=DATA 삭제, 4=미전송확인) */
    override fun onKeyDown(keyCode: Int, event: android.view.KeyEvent?): Boolean {
        when (keyCode) {
            android.view.KeyEvent.KEYCODE_1, android.view.KeyEvent.KEYCODE_NUMPAD_1 -> {
                confirmSend(); return true
            }
            android.view.KeyEvent.KEYCODE_2, android.view.KeyEvent.KEYCODE_NUMPAD_2 -> {
                startActivity(android.content.Intent(this, SectionQueryActivity::class.java)); return true
            }
            android.view.KeyEvent.KEYCODE_3, android.view.KeyEvent.KEYCODE_NUMPAD_3 -> {
                startActivity(android.content.Intent(this, DataQueryActivity::class.java)); return true
            }
            android.view.KeyEvent.KEYCODE_4, android.view.KeyEvent.KEYCODE_NUMPAD_4 -> {
                showUnsentInfo(); return true
            }
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onResume() {
        super.onResume()
        refreshHeader()
    }

    /** 건수 표시용 - 천단위 콤마(예: 212948 -> "212,948"). */
    private fun fmtCount(n: Int): String = NumberFormat.getNumberInstance(Locale.US).format(n)

    private fun refreshHeader() {
        // "PC 미전송 데이터" = 지금 [Data 전송]을 눌러서 STOCK.db로 내보내져
        // PC가 아직 안 가져간 데이터 건수.
        // [2026-09-30] "DATA관리 화면 상단 PC 미전송 데이터 [N건] 글자,숫자
        // 크기 2사이즈 크게 굵게 검은색으로, 수량 콤마" - 숫자에도 천단위 콤마.
        val pendingForPc = db.countPendingStockDbRows(getExternalFilesDir(null))
        findViewById<TextView>(R.id.tvUnsentHeader).text = "PC 미전송 데이터 [${fmtCount(pendingForPc)}건]"
    }

    private fun confirmSend() {
        val (totalCount, _) = db.countAllStock()
        if (totalCount == 0) {
            Toast.makeText(this, "전송할 실사 데이터가 없습니다.", Toast.LENGTH_SHORT).show()
            return
        }
        // [2026-09-30] "무선전송 팝업창에 수량 3자리 콤마" - KOINTBOOK에는
        // ZZOINT의 "무선전송"(Firebase) 화면이 따로 없고, 이 [Data 전송] 확인
        // 팝업이 그 역할을 대신한다. 전송 건수를 콤마와 함께 보여준다.
        Dialogs.confirm(
            activity = this,
            title = "선택",
            message = "[${AppState.storeName}] 실사 Data ${fmtCount(totalCount)}건을 전송하시겠습니까?",
            positiveText = "예(Y)",
            negativeText = "아니요(N)",
            focusPositive = true,
            onPositive = { doSend() }
        )
    }

    private fun doSend() {
        // Data 전송을 이미 했더라도, PDA에 남아있는 실사 데이터는 몇 번이든
        // 다시 STOCK.db로 내보낼 수 있다.
        val progress = Dialogs.progress(this, "Data 전송", "전송 파일을 만드는 중...")
        Thread {
            var errorMessage: String? = null
            try {
                exportAllToStockDb { done, total -> progress.update(null, done, total) }
            } catch (e: Exception) {
                errorMessage = e.message ?: "알 수 없는 오류"
            }
            runOnUiThread {
                progress.dismiss()
                refreshHeader()
                if (errorMessage == null) {
                    Dialogs.info(this, "확인", "전송완료.")
                } else {
                    Toast.makeText(this, "전송 중 오류: $errorMessage", Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }

    /**
     * 미전송 확인: 화면 이동 없이 팝업으로 바로 보여준다.
     * - 미전송데이터: 실사 후 PDA에 쌓인 전체 데이터 건수/수량
     * - PC 미전송데이터: 지금 Data전송을 눌러서 STOCK.db에 담겨있는 데이터.
     *   PC가 adb pull로 가져가면(파일이 삭제되면) 0이 된다.
     */
    private fun showUnsentInfo() {
        val (totalCount, _) = db.countAllStock()
        val pendingForPc = db.countPendingStockDbRows(getExternalFilesDir(null))
        // [2026-09-30] "미전송확인 팝업창 속 글자,숫자크기 지금에 2사이즈 크게,
        // 수량 3자리 콤마" - 메시지 글씨 14sp -> 16sp, 숫자 천단위 콤마.
        Dialogs.info(
            this,
            "알림",
            "미전송데이터 : ${fmtCount(totalCount)}건\nPC 미전송데이터 : ${fmtCount(pendingForPc)}건",
            messageTextSize = 18f
        )
    }

    /**
     * PDA에 쌓인 실사 데이터 전체를 외부 저장소의 STOCK.db 로 내보낸다 (매번 전체를 다시 씀,
     * PC가 adb pull로 가져감). 백그라운드 스레드에서 불러야 한다.
     *
     * 컬럼 이름은 KOINTBOOK PC(screen_pda_receive.py)가 그대로 dict 키로 읽어가는
     * 이름과 맞춰야 한다: area, section, shelf_no, dan, yeol, isbn, book_name,
     * qty, worker_code, worker_name, received_at (+ store_code/store_name/
     * survey_date는 PC가 굳이 쓰진 않지만 참고용으로 함께 내려준다).
     */
    private fun exportAllToStockDb(onProgress: (done: Int, total: Int) -> Unit) {
        val outDir = getExternalFilesDir(null) ?: filesDir
        val outFile = File(outDir, "STOCK.db")
        val tmpFile = File(outDir, "STOCK.db.tmp")
        if (tmpFile.exists()) tmpFile.delete()
        File(outDir, "STOCK.db.tmp-journal").let { if (it.exists()) it.delete() }

        val (total, _) = db.countAllStock()
        onProgress(0, total)

        val outDb = SQLiteDatabase.openOrCreateDatabase(tmpFile, null)
        try {
            outDb.execSQL(
                """
                CREATE TABLE IF NOT EXISTS stock_data (
                    store_code TEXT,
                    store_name TEXT,
                    survey_date TEXT,
                    area TEXT,
                    section TEXT,
                    shelf_no TEXT,
                    dan TEXT,
                    yeol TEXT,
                    isbn TEXT,
                    book_name TEXT,
                    qty INTEGER,
                    worker_code TEXT,
                    worker_name TEXT,
                    received_at TEXT
                )
                """.trimIndent()
            )

            val srcDb = db.readableDatabase
            srcDb.rawQuery(
                """
                SELECT store_code, store_name, survey_date, area, section, shelf_no, dan, yeol,
                       isbn, book_name, qty, worker_code, worker_name, scanned_at
                FROM stock_counts
                """.trimIndent(), null
            ).use { c ->
                outDb.beginTransaction()
                try {
                    val stmt = outDb.compileStatement(
                        "INSERT INTO stock_data VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                    )
                    var done = 0
                    while (c.moveToNext()) {
                        stmt.clearBindings()
                        for (i in 0..13) {
                            val col = i + 1
                            when {
                                c.isNull(i) -> stmt.bindNull(col)
                                i == 10 -> stmt.bindLong(col, c.getLong(i)) // qty
                                else -> stmt.bindString(col, c.getString(i))
                            }
                        }
                        stmt.executeInsert()
                        done++
                        if (done % 1000 == 0) onProgress(done, total)
                    }
                    stmt.close()
                    outDb.setTransactionSuccessful()
                    onProgress(done, total)
                } finally {
                    outDb.endTransaction()
                }
            }
        } finally {
            outDb.close()
        }

        // 다 만들어진 뒤에 최종 이름으로 바꾼다.
        if (outFile.exists()) outFile.delete()
        if (!tmpFile.renameTo(outFile)) {
            throw java.io.IOException("STOCK.db 파일 이름을 바꾸지 못했습니다.")
        }
    }
}
