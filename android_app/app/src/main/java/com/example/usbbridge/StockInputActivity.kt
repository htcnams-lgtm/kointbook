// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Color
import android.graphics.Rect
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.LayerDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.widget.LinearLayout
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.content.ContextCompat
import java.text.NumberFormat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 재고입력화면 (스캔 화면).
 * - 수동: ISBN 스캔/입력 후 수량을 직접 입력하고 확정
 * - 자동: 스캔 즉시 수량 1로 자동 등록
 * - 위치(단-열)는 수동/자동 관계없이 스캔할 때마다 항상 1씩 증가한다.
 * - AREA/SECTION/서가번호는 위치입력화면에서 이미 정해진 값을 그대로 쓰고,
 *   이 화면에서는 단/열만 조정한다 (ZZOINT와 동일한 구조).
 *
 * ZZOINT의 재고입력화면과 가장 큰 차이는, 도서는 "같은 바코드에 자사코드가
 * 여러 개"인 경우가 없어서(ISBN은 도서를 1:1로 특정한다) 스캔 시 여러 건 중
 * 고르는 단계가 필요 없다는 점이다 - 그래서 pendingCompanyCode/자사코드
 * 선택 다이얼로그 로직은 통째로 뺐다.
 *
 * 목록(리스트) 방향키 탐색에 대한 메모
 * --------------------------------
 * 안드로이드의 기본 포커스 탐색에 맡기지 않고, 지금 몇 번째 줄이 선택되어
 * 있는지(selectedRowIndex)를 직접 관리하면서 방향키/엔터를 여기서 전부
 * 처리한다 (ZZOINT와 동일한 방식).
 */
class StockInputActivity : BaseActivity() {

    companion object {
        const val SCAN_ACTION = "nlscan.action.SCANNER_RESULT"
    }

    // 확인/선택 팝업을 닫자마자, 그 터치가 아래에 있던 목록 줄로 새어들어가
    // "누르지도 않은" 수정/삭제 팝업이 곧바로 뜨는 문제가 있었다. 팝업이
    // 막 닫힌 시각을 기록해두고, 그 직후 짧은 시간 동안은 목록 줄의 터치를
    // 무시하는 방식으로 막는다.
    private var dialogClosedAt = 0L
    private fun markDialogClosed() {
        dialogClosedAt = System.currentTimeMillis()
    }

    private lateinit var db: DbHelper
    private lateinit var rgMode: RadioGroup
    private lateinit var tvLoc: TextView
    private lateinit var etDan: android.widget.EditText
    private lateinit var etYeol: android.widget.EditText
    private lateinit var etIsbn: android.widget.EditText
    private lateinit var etQty: android.widget.EditText
    private lateinit var tvBookName: TextView
    private lateinit var llList: LinearLayout
    private lateinit var scrollList: ScrollView
    private lateinit var tvItemCount: TextView
    private lateinit var tvTotalQty: TextView

    // 목록 행 뷰/데이터 및 현재 선택 상태 (-1 = 목록에 아무것도 선택 안 됨)
    private val rowViews = mutableListOf<LinearLayout>()
    private val rowData = mutableListOf<StockRow>()
    // [2026-10-10] 목록 총수량(화면에 보이는 줄들의 수량 합). 스캔할 때 새 줄 1개만 더하려고 들고 있는다.
    private var listTotalQty = 0
    private var selectedRowIndex = -1

    // [2026-10-02] 키보드처럼 들어오는(엔터 없는) 스캔 입력 감지 - ScanInputDetector.kt 참고
    private val scanDetector = ScanInputDetector(onScanned = {
        val code = etIsbn.text.toString().trim()
        if (code.isNotEmpty()) onIsbnConfirmed(code)
    })

    // [2026-10-02] 물리 Fn 키를 누른 시각 - Fn 다음에 3을 빨리(0.8초 안에) 누르면 재고수정 화면으로 간다.
    private var fnPressedAt = 0L

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        // [2026-10-02] "물리키 Fn + 3을 순차적으로 빨리 누르거나 동시에 누르면 재고수정 화면으로 이동" -
        // Fn을 누른 채 3(동시), Fn을 뗀 뒤 0.8초 안에 3(순차), 기기에 따라 Fn+3이 F3 키로 오는 경우 모두 처리한다.
        if (event.keyCode == KeyEvent.KEYCODE_FUNCTION) {
            if (event.action == KeyEvent.ACTION_DOWN) fnPressedAt = android.os.SystemClock.uptimeMillis()
            return true
        }
        val isThree = event.keyCode == KeyEvent.KEYCODE_3 || event.keyCode == KeyEvent.KEYCODE_NUMPAD_3
        val fnCombo = (isThree && (event.isFunctionPressed ||
                android.os.SystemClock.uptimeMillis() - fnPressedAt < 800)) || event.keyCode == KeyEvent.KEYCODE_F3
        if (fnCombo) {
            if (event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0) {
                fnPressedAt = 0L
                scanDetector.cancel()
                goToEditScreen()
            }
            return true
        }
        if (event.action == KeyEvent.ACTION_DOWN) {
            when (event.keyCode) {
                // UV-MT30은 #과 *이 물리적으로 한 개의 키라, 두 코드 모두 같은 동작(단 올리기)
                KeyEvent.KEYCODE_POUND, KeyEvent.KEYCODE_STAR -> {
                    increaseDan()
                    return true
                }
                KeyEvent.KEYCODE_DPAD_DOWN -> {
                    if (handleDpadDown()) return true
                    if (moveFocusDownFromModeRow()) return true
                }
                KeyEvent.KEYCODE_DPAD_UP -> {
                    if (handleDpadUp()) return true
                    if (moveFocusUpFromInputRow()) return true
                    if (currentFocus?.id == R.id.btnGoEdit) {
                        findViewById<View>(R.id.rbAuto).requestFocus()
                        return true
                    }
                }
                KeyEvent.KEYCODE_DPAD_LEFT -> {
                    if (currentFocus?.id == R.id.btnGoEdit) {
                        findViewById<View>(R.id.rbAuto).requestFocus()
                        return true
                    }
                }
                // [2026-09-30] "재고수정 버튼 ... 엔터버튼만 작동하게" - DPAD_CENTER는
                // 여기 포함하지 않는다(그 키는 아래 목록 줄 선택/수정 팝업에만 쓰이고,
                // 재고수정 버튼은 물리 엔터(ENTER/NUMPAD_ENTER)로만 실행된다).
                KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_NUMPAD_ENTER -> {
                    if (currentFocus?.id == R.id.btnGoEdit) {
                        goToEditScreen()
                        return true
                    }
                    if (selectedRowIndex in rowData.indices) {
                        showRowEditDialog(rowData[selectedRowIndex])
                        return true
                    }
                }
                KeyEvent.KEYCODE_DPAD_CENTER -> {
                    if (currentFocus?.id == R.id.btnGoEdit) {
                        // 터치와 마찬가지로 DPAD 가운데 키로도 실행되지 않게 그냥 소비만 한다.
                        return true
                    }
                    if (selectedRowIndex in rowData.indices) {
                        showRowEditDialog(rowData[selectedRowIndex])
                        return true
                    }
                }
            }
        }
        return super.dispatchKeyEvent(event)
    }

    /** [2026-09-30] "재고수정 버튼 ... 엔터버튼만 작동하게" - 재고수정화면으로
     * 넘어가는 유일한 경로. 예전엔 버튼 터치(setOnClickListener)로 실행했지만,
     * 이제 버튼은 clickable="false"라 터치로는 아무 반응이 없고, 이 버튼에
     * 방향키로 포커스를 옮긴 뒤 물리 엔터 키를 눌렀을 때만 dispatchKeyEvent가
     * 이 함수를 호출한다. */
    private fun goToEditScreen() {
        startActivity(Intent(this, StockEditActivity::class.java))
    }

    /** ISBN칸/수량칸에서 위 방향키: 위치/단/열을 건너뛰고 먼저 재고수정 버튼으로 포커스를 옮긴다. */
    private fun moveFocusUpFromInputRow(): Boolean {
        val cur = currentFocus
        if (cur == etIsbn || cur == etQty) {
            findViewById<View>(R.id.btnGoEdit).requestFocus()
            return true
        }
        return false
    }

    /** 수동/자동/재고수정에서 아래 방향키: 위치/단/열을 건너뛰고 바로 ISBN칸으로 */
    private fun moveFocusDownFromModeRow(): Boolean {
        val cur = currentFocus
        val btnGoEdit = findViewById<View>(R.id.btnGoEdit)
        if (cur?.id == R.id.rbManual || cur?.id == R.id.rbAuto || cur == btnGoEdit) {
            etIsbn.requestFocus()
            return true
        }
        return false
    }

    /** 아래 방향키: 마지막 입력칸(ISBN/수량)에서 누르면 목록 진입, 목록 안이면 다음 줄로 */
    private fun handleDpadDown(): Boolean {
        if (rowViews.isEmpty()) return false
        val cur = currentFocus
        return if (selectedRowIndex == -1) {
            if (cur == etIsbn || cur == etQty) {
                selectRow(0)
                true
            } else {
                false
            }
        } else if (selectedRowIndex < rowViews.size - 1) {
            selectRow(selectedRowIndex + 1)
            true
        } else {
            true // 마지막 줄에서 더 못 내려가지만, 다른 곳으로 포커스가 새지 않게 소비만 한다
        }
    }

    /** 위 방향키: 목록 첫 줄이면 다시 입력칸으로, 아니면 이전 줄로 */
    private fun handleDpadUp(): Boolean {
        if (selectedRowIndex == -1) return false
        return if (selectedRowIndex == 0) {
            deselectRows()
            etIsbn.requestFocus()
            true
        } else {
            selectRow(selectedRowIndex - 1)
            true
        }
    }

    private fun buildRowBackground(index: Int, selected: Boolean): Drawable {
        val altBg = if (index % 2 == 1) ContextCompat.getColor(this, R.color.bg_surface) else Color.TRANSPARENT
        if (!selected) return ColorDrawable(altBg)
        val border = GradientDrawable()
        border.setColor(Color.TRANSPARENT)
        border.setStroke((3 * resources.displayMetrics.density).toInt(), ContextCompat.getColor(this, R.color.focus_green))
        return LayerDrawable(arrayOf(ColorDrawable(altBg), border))
    }

    private fun selectRow(index: Int) {
        selectedRowIndex = index
        for ((i, v) in rowViews.withIndex()) {
            v.background = buildRowBackground(i, i == index)
        }
        val target = rowViews.getOrNull(index) ?: return
        scrollList.post {
            // [2026-10-02] 스크롤하기 전에 목록이 다시 그려져 이 줄이 이미 빠졌으면 건너뛴다
            // (빠진 줄로 위치를 계산하면 앱이 강제 종료됨).
            if (!target.isAttachedToWindow || target.parent == null) return@post
            try {
                val rect = Rect()
                target.getDrawingRect(rect)
                scrollList.offsetDescendantRectToMyCoords(target, rect)
                scrollList.smoothScrollTo(0, maxOf(rect.top - 10, 0))
            } catch (_: IllegalArgumentException) {
            }
        }
    }

    private fun deselectRows() {
        selectedRowIndex = -1
        for ((i, v) in rowViews.withIndex()) {
            v.background = buildRowBackground(i, false)
        }
    }

    /**
     * 물리 #* 키로 단(段)을 누를 때마다 1씩 계속 올린다 (5에서 순환하지 않고
     * 6, 7, 8... 계속 증가). 단이 바뀌면 그 단의 첫 칸부터 스캔하는 게
     * 자연스러우므로 열은 1로 초기화한다.
     */
    private fun increaseDan() {
        val current = etDan.text.toString().toIntOrNull() ?: 1
        val next = current + 1
        etDan.setText(next.toString())
        etYeol.setText(
            db.getNextAvailableYeol(AppState.currentArea, AppState.currentSection, AppState.currentShelfNo, next.toString()).toString()
        )
        android.widget.Toast.makeText(this, "단 $next 로 변경되었습니다.", android.widget.Toast.LENGTH_SHORT).show()
    }

    /**
     * 위치입력화면의 [Max수량설정]에서 지정한 최대 수량을 초과했는지 확인한다.
     */
    private fun warnIfExceedsMaxQty(qty: Int): Boolean {
        val max = db.getSetting("max_qty", "").toIntOrNull() ?: return false
        if (qty <= max) return false
        Dialogs.info(
            this,
            "MAX수량 초과",
            "입력한 수량(${formatQty(qty)})이 최대 수량(${formatQty(max)})을 초과했습니다.\n다시 입력해주세요."
        )
        return true
    }

    private val scanReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val isbn = intent.getStringExtra("SCAN_BARCODE1")
            val state = intent.getStringExtra("SCAN_STATE")
            if (state == "ok" && !isbn.isNullOrEmpty()) {
                runOnUiThread {
                    scanDetector.suppressed = true
                    etIsbn.setText(isbn)
                    scanDetector.suppressed = false
                    scanDetector.cancel()
                    onIsbnConfirmed(isbn)
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_stock_input)
        db = DbHelper.getInstance(this)

        findViewById<TextView>(R.id.tvTitleBarText).text = if (AppState.isStationery) "KOINTBOOK [문구 재고입력]" else "KOINTBOOK [재고입력]"

        rgMode = findViewById(R.id.rgMode)
        tvLoc = findViewById(R.id.tvLoc)
        etDan = findViewById(R.id.etDan)
        etYeol = findViewById(R.id.etYeol)
        etIsbn = findViewById(R.id.etBarcode)
        etQty = findViewById(R.id.etQty)
        tvBookName = findViewById(R.id.tvProductName)
        llList = findViewById(R.id.llList)
        scrollList = findViewById(R.id.scrollList)
        tvItemCount = findViewById(R.id.tvItemCount)
        tvTotalQty = findViewById(R.id.tvTotalQty)

        tvLoc.text = AppState.currentLocationKey()
        // 단/열은 AppState에 남아있던 값을 그대로 믿지 않고, 이 위치에
        // 실제로 저장된 마지막 데이터를 기준으로 "다음 위치"를 다시 계산한다.
        val (nextDan, nextYeol) = db.getNextPosition(AppState.currentArea, AppState.currentSection, AppState.currentShelfNo)
        AppState.currentDan = nextDan
        AppState.currentYeol = nextYeol
        etDan.setText(AppState.currentDan)
        etYeol.setText(AppState.currentYeol)
        rgMode.check(if (AppState.autoMode) R.id.rbAuto else R.id.rbManual)
        applyQtyFieldMode()

        // [2026-10-02] "단, 열은 자동 배정이니 터치나 물리 방향키로 이동 안 되게, 위치 칸처럼 수정 안 되게" -
        // 값은 프로그램이 넣고(다음 열 자동 계산, #/* 키로 단 올리기 등) 사람이 커서를 옮기거나 고칠 수 없게 한다.
        for (f in listOf(etDan, etYeol)) {
            f.isFocusable = false
            f.isFocusableInTouchMode = false
            f.isCursorVisible = false
            f.isLongClickable = false
            f.keyListener = null
        }

        rgMode.setOnCheckedChangeListener { _, checkedId ->
            AppState.autoMode = (checkedId == R.id.rbAuto)
            AppState.persistAutoMode(this)
            applyQtyFieldMode()
            etQty.setText("")
        }

        // 입력칸에 포커스가 다시 오면(터치든 뭐든) 목록 선택 상태는 해제한다.
        etIsbn.setOnFocusChangeListener { _, hasFocus -> if (hasFocus) deselectRows() }
        etQty.setOnFocusChangeListener { _, hasFocus -> if (hasFocus) deselectRows() }

        // ISBN칸: 엔터를 떼는 순간(ACTION_UP) 한 번만 처리한다.
        // [2026-10-01] "자동스캔시 수량 1로 자동 추가 안 되고 포커스가 수량칸으로 넘어가 멈춤" -
        // 스캐너가 바코드 뒤에 엔터 대신 탭(TAB)을 붙여 보내는 설정이면, 탭 때문에 확정 없이
        // 포커스만 수량칸으로 넘어가 버렸다. 탭도 엔터와 똑같이 "확정"으로 처리하고 소비한다.
        etIsbn.setOnKeyListener { _, keyCode, event ->
            if (keyCode == KeyEvent.KEYCODE_ENTER || keyCode == KeyEvent.KEYCODE_NUMPAD_ENTER ||
                keyCode == KeyEvent.KEYCODE_TAB) {
                if (event.action == KeyEvent.ACTION_UP) {
                    scanDetector.cancel()
                    val code = etIsbn.text.toString().trim()
                    if (code.isNotEmpty()) onIsbnConfirmed(code)
                }
                true
            } else {
                false
            }
        }

        // 수량칸: 마찬가지로 엔터를 떼는 순간 확정한다.
        etQty.setOnKeyListener { _, keyCode, event ->
            if (keyCode == KeyEvent.KEYCODE_ENTER || keyCode == KeyEvent.KEYCODE_NUMPAD_ENTER) {
                if (event.action == KeyEvent.ACTION_UP) {
                    val code = etIsbn.text.toString().trim()
                    val qty = etQty.text.toString().toIntOrNull() ?: 1
                    if (code.isNotEmpty()) {
                        if (warnIfExceedsMaxQty(qty)) {
                            etQty.selectAll()
                        } else {
                            commitRow(code, qty)
                            etIsbn.setText("")
                            etIsbn.requestFocus()
                        }
                    }
                }
                true
            } else {
                false
            }
        }

        etIsbn.addTextChangedListener(object : android.text.TextWatcher {
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                if (count > before) scanDetector.noteInput(count - before)
            }
            override fun afterTextChanged(s: android.text.Editable?) {
                val code = s.toString().trim()
                if (code.isEmpty()) { tvBookName.text = ""; return }
                val info = db.findBook(AppState.storeCode, code)
                tvBookName.text = if (info == null) "(미등록 도서 - 그대로 등록 가능)" else {
                    val cat = if (info.category.isNotEmpty()) "  [${info.category}]" else ""
                    "${info.bookName}$cat"
                }
            }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
        })

        // [2026-09-30] "재고수정 버튼 터치로 불가하고 방향키로 선택,
        // 초록색테두리 포커스, 엔터버튼만 작동하게" - 터치 클릭 리스너를
        // 없앴다(XML에서 clickable="false"로 터치 자체도 막아뒀다). 이제
        // 이 버튼은 방향키로 포커스만 옮겨갈 수 있고(포커스 시 초록 테두리는
        // button_secondary 배경이 그대로 그려줌), 실행은 dispatchKeyEvent의
        // 물리 엔터 키(ENTER/NUMPAD_ENTER) 처리에서만 한다(goToEditScreen 참고).

        refreshList()

        // 화면에 들어오면 ISBN 입력칸에 커서(포커스)만 가 있게 한다.
        etIsbn.isFocusableInTouchMode = true
        etIsbn.requestFocus()
    }

    /** 완료 버튼이 없으므로, 뒤로가기(back)로 나갈 때 단/열 값을 저장해둔다. */
    override fun onBackPressed() {
        AppState.currentDan = etDan.text.toString().ifEmpty { "1" }
        AppState.currentYeol = etYeol.text.toString().ifEmpty { "1" }
        super.onBackPressed()
    }

    override fun onResume() {
        super.onResume()
        registerScanReceiverCompat(scanReceiver, IntentFilter(SCAN_ACTION))
    }

    override fun onPause() {
        super.onPause()
        scanDetector.cancel()
        try { unregisterReceiver(scanReceiver) } catch (_: Exception) {}
    }

    /** ISBN이 스캔/입력으로 확정되었을 때 공통 처리 */
    private fun onIsbnConfirmed(isbn: String) {
        // 상품(도서)마스터가 수신되어 있는데 이 ISBN이 그 안에 없으면(미등록 도서)
        // 그대로 등록할지 먼저 확인한다. 도서마스터 자체가 없으면(전체 ISBN
        // 허용 모드) 이 확인 없이 바로 진행한다.
        val hasMaster = db.hasAnyBooks(AppState.storeCode)
        val info = db.findBook(AppState.storeCode, isbn)
        // [2026-10-08] PC 상품마스터 화면의 [미등록상품] 설정(allow/warn/block)을 따른다.
        // 미등록일 때만 설정을 읽는다(등록된 바코드 스캔에는 추가 DB 조회 없음)
        val unregPolicy = if (hasMaster && info == null) db.getSetting("unreg_policy", "warn") else "warn"
        if (hasMaster && info == null && unregPolicy == "allow") {
            proceedIsbn(isbn)
        } else if (hasMaster && info == null && unregPolicy == "block") {
            SoundUtil.warningBeep(this)
            Dialogs.info(this, "미등록 도서", "도서마스터에 없는 도서는 입력할 수 없습니다.\n(PC 설정: 차단)")
            etIsbn.setText("")
            etIsbn.requestFocus()
        } else if (hasMaster && info == null) {
            SoundUtil.warningBeep(this)
            Dialogs.confirm(
                activity = this,
                title = "확인",
                message = "도서마스터에 없는 미등록도서 입니다.\n입력하시겠습니까?",
                positiveText = "예",
                negativeText = "아니오",
                focusPositive = false, // 기본값 '아니오'
                onPositive = { markDialogClosed(); proceedIsbn(isbn) },
                onNegative = {
                    markDialogClosed()
                    etIsbn.setText("")
                    etIsbn.requestFocus()
                }
            )
        } else {
            proceedIsbn(isbn)
        }
    }

    /** [2026-10-01] 자동 모드에선 수량칸이 포커스를 아예 받지 못하게 한다(눌러도, 탭/방향키로도
     * 못 감) - 자동 모드인데 수량칸에 포커스가 가서 멈춰 버리는 일을 막는다. */
    private fun applyQtyFieldMode() {
        val manual = !AppState.autoMode
        etQty.isEnabled = manual
        etQty.isFocusable = manual
        etQty.isFocusableInTouchMode = manual
    }

    private fun proceedIsbn(isbn: String) {
        // [2026-10-01] 화면에 보이는 수동/자동 선택을 기준으로 판단한다(메모리 값과 어긋나 있던
        // 경우에도 사용자가 보는 그대로 동작하도록 맞춘다).
        val autoSelected = rgMode.checkedRadioButtonId == R.id.rbAuto
        if (AppState.autoMode != autoSelected) {
            AppState.autoMode = autoSelected
            AppState.persistAutoMode(this)
            applyQtyFieldMode()
        }
        if (AppState.autoMode) {
            if (warnIfExceedsMaxQty(1)) {
                etIsbn.setText("")
                etIsbn.requestFocus()
                return
            }
            commitRow(isbn, 1)
            etIsbn.setText("")
            etIsbn.requestFocus()
        } else {
            // 수동 모드: 수량 입력칸을 비우고 곧바로 포커스를 옮긴다.
            etQty.setText("")
            etQty.requestFocus()
        }
    }

    /** 실제 DB에 한 줄 저장 + 위치(열) 1 증가 */
    private fun commitRow(isbn: String, qty: Int) {
        val area = AppState.currentArea
        val section = AppState.currentSection
        val shelfNo = AppState.currentShelfNo
        val dan = etDan.text.toString().ifEmpty { "1" }
        val yeol = etYeol.text.toString().ifEmpty { "1" }
        val info = db.findBook(AppState.storeCode, isbn)
        val now = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())

        // [2026-09-29] "영문 대소문자 구분없이 상품마스터에 맞는쪽으로 자동변경" -
        // findBook()이 대소문자 구분 없이 찾아준 뒤에는, 저장할 때도 사용자가
        // 입력한 원래 표기가 아니라 상품마스터에 실제 저장된 표기(info.isbn)로
        // 맞춰서 저장한다(미등록 도서라 info가 없으면 입력한 그대로 저장).
        val matchedIsbn = info?.isbn ?: isbn

        AppState.pinSurveyDate(this)  // [2026-10-08] 자정을 넘어도 같은 조사일자로 저장/조회
        val newId = db.insertStockCount(
            storeCode = AppState.storeCode,
            storeName = AppState.storeName,
            surveyDate = AppState.surveyDate(),
            area = area,
            section = section,
            shelfNo = shelfNo,
            dan = dan,
            yeol = yeol,
            isbn = matchedIsbn,
            bookName = info?.bookName ?: "",
            qty = qty,
            workerCode = AppState.workerCode,
            workerName = AppState.workerName,
            scannedAt = now
        )

        // 위치(열)는 단순히 +1 하지 않고, 삭제 등으로 비어있는 열 번호가
        // 있으면 그 자리부터 채운다 (없으면 자연스럽게 다음 번호가 된다).
        etYeol.setText(db.getNextAvailableYeol(area, section, shelfNo, dan).toString())

        etQty.setText("")
        tvBookName.text = ""
        // [2026-10-10] 연속 스캔(0.5초 간격) 병목 개선 - 예전에는 스캔마다 이 서가의 목록 전체를
        // DB에서 다시 읽고 모든 줄을 지웠다가 다시 만들어서, 건수가 쌓일수록 한 건 처리 시간이
        // 늘어났다. 이제는 방금 저장한 줄 1개만 맨 위에 끼워 넣고 ITEM/총수량만 갱신한다.
        // 저장이 실패했거나(id<=0) 하면 화면이 DB와 어긋나지 않게 예전처럼 전체를 다시 그린다.
        // (삭제/수정/화면 재진입은 계속 전체 다시 그리기)
        if (newId > 0) {
            addRowToTop(
                StockRow(
                    id = newId, area = area, section = section, shelfNo = shelfNo,
                    dan = dan, yeol = yeol, isbn = matchedIsbn,
                    bookName = info?.bookName ?: "", qty = qty
                )
            )
        } else {
            refreshList()
        }
    }

    /** 새로 저장한 줄 1개만 목록 맨 위에 추가한다(최신 스캔이 맨 위). 나머지 줄은 다시 만들지 않는다. */
    private fun addRowToTop(row: StockRow) {
        val line = createRowView(row)
        llList.addView(line, 0)
        rowViews.add(0, line)
        rowData.add(0, row)
        selectedRowIndex = -1
        // 맨 위에 한 줄이 끼면 줄무늬(홀짝) 순서가 한 칸씩 밀리므로 배경만 다시 칠한다(뷰 재생성 없음).
        for ((i, v) in rowViews.withIndex()) {
            v.background = buildRowBackground(i, false)
        }
        listTotalQty += row.qty
        updateListSummary()
    }

    private fun updateListSummary() {
        tvItemCount.text = "ITEM: ${formatQty(rowData.size)}"
        // [2026-09-30] "item, 총수량 입력값 3자리 콤마" - 천단위 구분 콤마.
        tvTotalQty.text = "총수량: ${formatQty(listTotalQty)}"
    }

    private fun refreshList() {
        val rows = db.listByLocation(AppState.currentArea, AppState.currentSection, AppState.currentShelfNo)
        llList.removeAllViews()
        rowViews.clear()
        rowData.clear()
        selectedRowIndex = -1
        val orderedRows = rows.asReversed() // 최신 스캔이 맨 위

        for ((index, row) in orderedRows.withIndex()) {
            val line = createRowView(row)
            line.background = buildRowBackground(index, false)
            llList.addView(line)
            rowViews.add(line)
            rowData.add(row)
        }

        listTotalQty = rows.sumOf { it.qty }
        updateListSummary()
    }

    /** 목록의 한 줄(뷰)을 만든다. 전체 다시 그리기(refreshList)와 새 줄 1개 추가(addRowToTop)가 같이 쓴다.
     *  줄 위치(몇 번째 줄인지)는 맨 위에 줄이 끼면 바뀌므로, 만들 때 고정하지 않고 누를 때 rowViews에서 찾는다. */
    private fun createRowView(row: StockRow): LinearLayout {
        val density = resources.displayMetrics.density
        val padH = (4 * density).toInt()
        val padV = (8 * density).toInt()

        val line = LinearLayout(this)
        line.orientation = LinearLayout.HORIZONTAL
        line.setPadding(padH, padV, padH, padV)

        fun cell(text: String, weight: Float): TextView {
            val tv = TextView(this)
            tv.text = text
            tv.textSize = 14f
            tv.setTextColor(Color.parseColor("#000000"))
            tv.setTypeface(tv.typeface, android.graphics.Typeface.BOLD)
            tv.gravity = Gravity.CENTER
            tv.maxLines = 1
            tv.ellipsize = android.text.TextUtils.TruncateAt.END
            tv.setSingleLine(true)
            tv.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, weight)
            return tv
        }

        // [2026-09-29] activity_stock_input.xml 목록 헤더와 같은 비율(0.8 / 2.6 / 2 / 0.6)
        // - 바코드가 "..."으로 잘리지 않도록 위치/수량 너비를 조금씩 줄이고 바코드에 몰아줬다.
        line.addView(cell("${row.dan}-${row.yeol}", 0.8f))
        line.addView(cell(row.isbn, 2.6f))
        line.addView(cell(row.bookName, 2f))
        line.addView(cell(row.qty.toString(), 0.6f))

        // 터치로는 짧게 한 번 누르는 걸로는 안 열리고, 1초 이상 눌러야만
        // 열리게 한다 (정확한 1초를 재는 타이머를 직접 구현).
        val longPressHandler = android.os.Handler(android.os.Looper.getMainLooper())
        var downX = 0f
        var downY = 0f
        val touchSlop = android.view.ViewConfiguration.get(this).scaledTouchSlop
        val longPressRunnable = Runnable {
            val idx = rowViews.indexOf(line)
            if (idx >= 0) selectRow(idx)
            showRowEditDialog(row)
        }
        line.setOnTouchListener { v, event ->
            when (event.actionMasked) {
                android.view.MotionEvent.ACTION_DOWN -> {
                    if (System.currentTimeMillis() - dialogClosedAt < 400) {
                        return@setOnTouchListener true
                    }
                    downX = event.x
                    downY = event.y
                    longPressHandler.postDelayed(longPressRunnable, 1000)
                    v.parent?.requestDisallowInterceptTouchEvent(true)
                    true
                }
                android.view.MotionEvent.ACTION_MOVE -> {
                    if (kotlin.math.abs(event.x - downX) > touchSlop ||
                        kotlin.math.abs(event.y - downY) > touchSlop
                    ) {
                        longPressHandler.removeCallbacks(longPressRunnable)
                        v.parent?.requestDisallowInterceptTouchEvent(false)
                    }
                    true
                }
                android.view.MotionEvent.ACTION_UP, android.view.MotionEvent.ACTION_CANCEL -> {
                    longPressHandler.removeCallbacks(longPressRunnable)
                    v.parent?.requestDisallowInterceptTouchEvent(false)
                    true
                }
                else -> false
            }
        }
        return line
    }

    private fun formatQty(n: Int): String = NumberFormat.getNumberInstance(Locale.US).format(n)

    /** 목록의 한 줄을 방향키+엔터 또는 길게 터치로 선택했을 때: 수량 수정 또는 삭제 팝업 */
    private fun showRowEditDialog(row: StockRow) {
        Dialogs.editOrDeleteRow(
            activity = this,
            title = "재고 수정/삭제",
            message = "위치: ${row.dan}-${row.yeol}   바코드: ${row.isbn}",
            initialQty = row.qty.toString(),
            onSave = { newQtyText ->
                val newQty = newQtyText.toIntOrNull()
                if (newQty == null || newQty <= 0) {
                    android.widget.Toast.makeText(this, "올바른 수량을 입력하세요.", android.widget.Toast.LENGTH_SHORT).show()
                } else if (!warnIfExceedsMaxQty(newQty)) {
                    db.updateStockCountQty(row.id, newQty)
                    refreshList()
                }
            },
            onDelete = {
                Dialogs.confirm(
                    activity = this,
                    title = "확인",
                    message = "이 항목을 삭제할까요?\n${row.isbn} (${formatQty(row.qty)}개)",
                    positiveText = "예",
                    negativeText = "아니요",
                    focusPositive = false,
                    onPositive = {
                        db.deleteStockCount(row.id)
                        refreshList()
                        // 지금 화면에 표시된 단과 같은 줄을 지웠다면, 방금 생긴
                        // 빈 자리가 다음 스캔의 열 번호가 되도록 갱신한다.
                        if (row.dan == etDan.text.toString()) {
                            etYeol.setText(
                                db.getNextAvailableYeol(AppState.currentArea, AppState.currentSection, AppState.currentShelfNo, row.dan).toString()
                            )
                        }
                    }
                )
            }
        )
    }

    override fun onRestart() {
        super.onRestart()
        refreshList()
    }
}
