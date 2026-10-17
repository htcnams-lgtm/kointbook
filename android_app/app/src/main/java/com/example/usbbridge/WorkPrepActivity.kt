// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.TextWatcher
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast

/**
 * 작업준비: 매장/작업자/품목수량 확인, 마스터 수신/초기화, [다음]으로 메뉴 진입.
 *
 * ZZOINT에 있던 "서버 마스터 수신"(Firebase 무선 수신) 버튼/팝업은 KOINTBOOK에는
 * 없다 - USB adb로 STORE.db/WORKER.db/BOOK.db를 받는 [마스터 수신] 한 가지
 * 방법만 쓴다.
 */
class WorkPrepActivity : BaseActivity() {

    private lateinit var db: DbHelper
    private lateinit var etWorkerCode: EditText
    private lateinit var tvWorkerName: TextView
    private lateinit var tvItemCount: TextView
    private lateinit var btnMasterReceive: Button
    private lateinit var tvMasterReceiveStatus: TextView
    private var btnGoToMenu: Button? = null

    // 화면에 머무는 동안에도(다른 화면으로 안 나갔다 와도) PC가 마스터를 보내면
    // 실시간으로 [마스터 수신] 버튼이 활성화되도록 주기적으로 확인한다.
    private val pollHandler = Handler(Looper.getMainLooper())
    private var isReceiving = false
    private val pollRunnable = object : Runnable {
        override fun run() {
            if (!isReceiving) {
                val pending = db.hasPendingMasterFiles(getExternalFilesDir(null))
                if (btnMasterReceive.isEnabled != pending) {
                    btnMasterReceive.isEnabled = pending
                }
                if (pending) {
                    // PC가 점포 -> 작업자 -> 상품 순서로 보내는 중이면 도착한 것이 하나씩 늘어난다.
                    val msg = pendingMessage()
                    if (tvMasterReceiveStatus.text.toString() != msg) tvMasterReceiveStatus.text = msg
                }
            }
            pollHandler.postDelayed(this, 1500)
        }
    }

    override fun primaryButton(): android.view.View? = btnGoToMenu

    /** 건수 표시용 - 천단위 콤마(예: 212948 -> "212,948"). */
    private fun fmtCount(n: Int): String = "%,d".format(n)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_work_prep)
        db = DbHelper.getInstance(this)

        findViewById<TextView>(R.id.tvTitleBarText).text = "KOINTBOOK [작업준비]"

        findViewById<TextView>(R.id.tvStore).text = AppState.storeLabel()

        etWorkerCode = findViewById(R.id.etWorkerCode)
        tvWorkerName = findViewById(R.id.tvWorkerName)
        tvItemCount = findViewById(R.id.tvItemCount)
        btnMasterReceive = findViewById(R.id.btnMasterReceive)
        tvMasterReceiveStatus = findViewById(R.id.tvMasterReceiveStatus)

        etWorkerCode.setText(AppState.workerCode)

        // [2026-10-17] "pda 작업자코드 입력칸이 항상 전체선택되어있도록, 새로운 입력값을 넣기 편하게" -
        // 칸에 들어갈 때(화면이 열릴 때·다른 칸에서 돌아올 때)와 눌러서 커서가 옮겨질 때 모두 값 전체를 선택해 둔다.
        // 선택된 채로 숫자를 치면 이전 값이 지워지고 새 값으로 바뀐다.
        etWorkerCode.setSelectAllOnFocus(true)
        etWorkerCode.setOnFocusChangeListener { v, hasFocus ->
            if (hasFocus) v.post { etWorkerCode.selectAll() }
        }
        etWorkerCode.setOnClickListener { etWorkerCode.post { etWorkerCode.selectAll() } }

        etWorkerCode.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                val code = s.toString().trim()
                val name = if (code.isNotEmpty()) db.findWorkerName(code) else null
                tvWorkerName.text = name ?: ""
            }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })
        if (AppState.workerCode.isNotEmpty()) {
            tvWorkerName.text = db.findWorkerName(AppState.workerCode) ?: ""
        }

        updateItemCountLabel()

        btnMasterReceive.setOnClickListener { receiveMaster() }
        val btnReset = findViewById<Button>(R.id.btnMasterReset)
        btnReset.setOnClickListener { confirmResetMaster() }

        btnGoToMenu = findViewById<Button>(R.id.btnGoToMenu)
        // 방향키(D-pad) 이동 순서: 작업자번호 -> 마스터수신 -> 초기화 -> 다음.
        etWorkerCode.nextFocusDownId = R.id.btnMasterReceive
        btnMasterReceive.nextFocusDownId = R.id.btnMasterReset
        btnGoToMenu?.nextFocusDownId = R.id.btnMasterReset

        // 작업자번호에서 엔터를 누르면 바로 다음 화면으로 넘기지 않고,
        // 우선 [다음] 버튼으로 포커스만 이동시킨다.
        etWorkerCode.setOnEditorActionListener { _, actionId, event ->
            val isEnter = actionId == android.view.inputmethod.EditorInfo.IME_ACTION_DONE ||
                actionId == android.view.inputmethod.EditorInfo.IME_ACTION_NEXT ||
                (event != null && event.keyCode == android.view.KeyEvent.KEYCODE_ENTER &&
                    event.action == android.view.KeyEvent.ACTION_DOWN)
            if (isEnter) {
                btnGoToMenu?.requestFocus()
                true
            } else false
        }

        btnGoToMenu!!.setOnClickListener {
            val code = etWorkerCode.text.toString().trim()
            val name = if (code.isNotEmpty()) db.findWorkerName(code) else null
            if (code.isEmpty() || name == null) {
                Toast.makeText(this, "등록된 작업자 번호를 입력하세요. (샘플: 1, 2, 3)", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            AppState.workerCode = code
            AppState.workerName = name
            // [2026-09-30] 화면이 꺼진 사이 프로세스가 죽었다 살아나도 작업자
            // 번호를 잃지 않도록 DB에도 같이 저장한다(AppState.kt 참고).
            AppState.persistWorker(this)
            startActivity(Intent(this, MenuActivity::class.java))
        }
    }

    override fun onResume() {
        super.onResume()
        val pending = db.hasPendingMasterFiles(getExternalFilesDir(null))
        btnMasterReceive.isEnabled = pending
        tvMasterReceiveStatus.text = if (pending) {
            pendingMessage()
        } else {
            "받은 마스터: 상품 ${fmtCount(db.bookCountForStore(AppState.storeCode))}건"
        }
        pollHandler.post(pollRunnable)
        // 다른 화면에서 돌아왔을 때 이 칸에 커서가 있으면 다시 전체 선택
        if (etWorkerCode.hasFocus()) etWorkerCode.post { etWorkerCode.selectAll() }
    }

    override fun onPause() {
        super.onPause()
        pollHandler.removeCallbacks(pollRunnable)
    }

    /** [2026-10-02] 어떤 마스터가 도착해 있는지 이름까지 보여준다(예: "점포·작업자·상품"). */
    private fun pendingMessage(): String {
        val names = db.pendingMasterNames(getExternalFilesDir(null))
        return "PC에서 보낸 마스터(${names.joinToString("·")})가 있습니다. 아래 버튼을 누르세요."
    }

    private fun receiveMaster() {
        isReceiving = true
        btnMasterReceive.isEnabled = false
        tvMasterReceiveStatus.text = "수신 중..."
        // 상품(도서)마스터가 수십만 건일 수 있어서, 저장하는 동안 진행률을 보여준다.
        val progress = Dialogs.progress(this, "마스터 수신", "받은 파일을 읽는 중...")
        Thread {
            val (storeCount, workerCount, bookCount) =
                db.importMasterFilesIfPresent(getExternalFilesDir(null)) { label, done, total ->
                    progress.update(label, done, total)
                }
            runOnUiThread {
                progress.dismiss()
                isReceiving = false
                // 받은 뒤에는 다시 대기 상태로 - 새로 보낼 때만 다시 활성화된다.
                btnMasterReceive.isEnabled = db.hasPendingMasterFiles(getExternalFilesDir(null))
                if (storeCount == 0 && workerCount == 0 && bookCount == 0) {
                    Toast.makeText(this, "받을 마스터 데이터가 없습니다. PC에서 [PDA 전송]을 먼저 눌러주세요.", Toast.LENGTH_LONG).show()
                    tvMasterReceiveStatus.text = "받은 마스터: 상품 ${fmtCount(db.bookCountForStore(AppState.storeCode))}건"
                    return@runOnUiThread
                }

                // 방금 받은 상품(도서)마스터가 실제로 어느 점포코드로 들어왔는지를
                // 우선한다 (점포마스터를 안 받았거나 다른 점포일 수 있어서).
                if (bookCount > 0) {
                    db.findAnyBookStoreCode()?.let { code ->
                        AppState.storeCode = code
                        AppState.storeName = db.findStoreName(code) ?: AppState.storeName
                    }
                } else {
                    db.findFirstStore()?.let { (code, name) ->
                        AppState.storeCode = code
                        AppState.storeName = name
                    }
                }
                findViewById<TextView>(R.id.tvStore).text = AppState.storeLabel()

                val parts = mutableListOf<String>()
                if (storeCount > 0) parts.add("점포 ${fmtCount(storeCount)}건")
                if (workerCount > 0) parts.add("작업자 ${fmtCount(workerCount)}건")
                if (bookCount > 0) parts.add("상품 ${fmtCount(bookCount)}건")
                val summary = parts.joinToString(", ") + " 수신완료"

                tvMasterReceiveStatus.text = summary
                updateItemCountLabel()

                // [2026-10-02] PC 상품마스터 화면의 [PDA전송]은 점포/작업자/상품 마스터를 한 번에 보낸다 -
                // 세 가지를 각각 몇 건 받았는지 확인 팝업으로 분명하게 보여준다(안 온 것은 "받지 않음").
                fun line(label: String, n: Int) = "$label : " + (if (n > 0) "${fmtCount(n)}건" else "받지 않음")
                val allThree = storeCount > 0 && workerCount > 0 && bookCount > 0
                val message = line("점포마스터", storeCount) + "\n" +
                    line("작업자마스터", workerCount) + "\n" +
                    line("상품마스터", bookCount) + "\n\n" +
                    (if (allThree) "점포·작업자·상품 마스터를 모두 받았습니다." else "받은 마스터만 반영했습니다.")
                Dialogs.info(this, "마스터 수신 완료", message)
            }
        }.start()
    }

    private fun confirmResetMaster() {
        Dialogs.confirm(
            activity = this,
            title = "마스터 초기화",
            message = "받은 점포/작업자/상품 마스터를 모두 지우고 처음 상태로 되돌릴까요?\n" +
                    "(PC에서 다시 [PDA 전송]을 눌러서 새로 받을 수 있습니다)",
            positiveText = "초기화",
            negativeText = "취소",
            focusPositive = false, // 되돌릴 수 없는 동작이라 기본 포커스는 안전하게 '취소'
            onPositive = {
                db.resetMasterData()
                AppState.storeCode = ""
                AppState.storeName = ""
                findViewById<TextView>(R.id.tvStore).text = AppState.storeLabel()
                updateItemCountLabel()
                tvMasterReceiveStatus.text = "마스터가 초기화되었습니다. PC에서 다시 전송해주세요."
                Toast.makeText(this, "마스터 데이터를 초기화했습니다.", Toast.LENGTH_SHORT).show()
            }
        )
    }

    /** [2026-09-30] "품목수량 입력칸 N (상품마스터 수신됨) 숫자는 3자리 콤마" */
    private fun updateItemCountLabel() {
        val count = db.bookCountForStore(AppState.storeCode)
        tvItemCount.text = if (count > 0) {
            "${fmtCount(count)}  (상품마스터 수신됨)"
        } else {
            "0  (상품마스터 미수신\n전체 바코드 스캔 허용)"
        }
    }
}
