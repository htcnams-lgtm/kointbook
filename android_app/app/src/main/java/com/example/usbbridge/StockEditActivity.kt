// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Color
import android.graphics.Rect
import android.graphics.Typeface
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.LayerDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.KeyEvent
import android.view.TouchDelegate
import android.view.View
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import java.text.NumberFormat
import java.util.Locale

/** 재고수정화면: 이미 입력된 스캔 데이터를 조회/수정/삭제.
 *
 * 위치칸(etLoc)은 위치입력화면과 마찬가지로 "AREA-SECTION-서가번호"를
 * 하이픈으로 이어붙인 문자열 하나로 입력받는다.
 *
 * [2026-09-30] 대대적으로 다시 손봤다:
 *  - [수정] 버튼을 없애고, 목록 줄에서 엔터 -> 수량칸 이동 -> 엔터로 바로
 *    수정이 반영되는 흐름으로 바꿨다(commitQtyEdit 참고).
 *  - 물리스캔으로 바코드가 들어오면 직접 입력 후 엔터와 똑같이 조회한다
 *    (LOC칸이 비면 그 바코드가 찍힌 모든 LOC의 그 바코드만, LOC값이 있으면 LOC+바코드 일치만.
 *    [2026-10-10] 예전의 "LOC 자동 맞춤 + 그 LOC 전체 바코드 표시"는 없앴다).
 *
 * [2026-09-30 추가] "선택체크박스항목을 없애는대신" - 목록 줄마다 있던
 * 체크박스(L 칸)를 완전히 없애고, 그 대신 다음 방식으로 바꿨다:
 *  - 선택(삭제 대상 표시)은 그 줄의 "위치" 칸을 터치하거나(다른 칸을 터치하면
 *    선택되지 않고 그 줄 내용을 위 입력칸들에 불러오기만 한다) 위치 칸에
 *    포커스가 있을 때 엔터를 치면 토글된다 - 선택되면 위치 칸 내용(단-열) 위에
 *    초록색 "✓" 표시가 겹쳐서 보인다(FrameLayout으로 텍스트와 체크표시를
 *    같은 자리에 겹쳐 그림).
 *  - 목록 각 줄에서 방향키의 기본 포커스 대상은 "바코드" 칸이다(체크박스가
 *    있던 자리를 대신함) - 위/아래 방향키로 줄과 줄 사이를 옮겨다니면 그
 *    바코드 칸에 포커스가 있는 줄 전체가 (StockInputActivity와 같은 방식의)
 *    초록 테두리로 강조된다.
 *  - 바코드 칸에 포커스가 있을 때 방향키 왼쪽을 누르면 같은 줄의 "위치" 칸으로
 *    포커스가 넘어가고, 이때는 줄 전체 강조 대신 위치 칸 "그 자체에만" 작은
 *    초록 테두리가 그려진다. 위치 칸에 포커스가 있는 동안 위/아래 방향키는
 *    다른 줄의 바코드 칸으로 가지 않고 다른 줄의 "위치" 칸끼리만 오간다(컬럼
 *    고정 이동). 방향키 오른쪽을 누르면 다시 같은 줄의 바코드 칸으로 돌아간다.
 */
class StockEditActivity : BaseActivity() {

    companion object {
        const val SCAN_ACTION = "nlscan.action.SCANNER_RESULT"
    }

    private lateinit var db: DbHelper
    private var btnComplete: android.view.View? = null

    override fun primaryButton(): android.view.View? = btnComplete
    private lateinit var etLoc: EditText
    private lateinit var etIsbn: EditText
    private lateinit var etEditQty: EditText
    private lateinit var tvBookName: TextView
    private lateinit var llList: LinearLayout
    private lateinit var scrollList: ScrollView
    private lateinit var tvItemCount: TextView
    private lateinit var tvDan: TextView
    private lateinit var tvYeol: TextView
    private lateinit var tvTotalQty: TextView

    private var selectedRowId: Long? = null

    // [2026-10-06] 조회 조건. 화면 처음 진입 시에는 둘 다 비어 있어 목록이 비어 있다
    // ("최초 화면은 목록이 비어있게"). 목록은 항상 이 조건으로만 다시 그린다 - 입력칸
    // (etIsbn)은 줄을 선택할 때 그 줄 바코드로 채워지는데, 그 값이 조건으로 새어
    // 들어가 목록이 갑자기 좁혀지지 않도록 입력칸과 조건을 분리했다.
    //   LOC만      -> 그 LOC의 모든 바코드
    //   바코드만   -> 그 바코드가 있는 모든 LOC에서 그 바코드만
    //   LOC+바코드 -> 두 조건을 모두 만족하는 것만
    //   물리스캔   -> 직접 입력 후 엔터와 똑같이: LOC칸이 비어 있으면 그 바코드가 찍힌 모든 LOC의 그 바코드만,
    //                 LOC칸에 값이 있으면 LOC+바코드 둘 다 맞는 것만 (2026-10-10: LOC칸을 자동으로 채우거나
    //                 그 LOC의 모든 바코드를 보여주던 예전 동작을 없앴다)
    private var searchLoc = ""
    private var searchCode = ""

    // 바코드칸의 값이 사용자가 직접 입력한 값인지(false), 줄 선택/스캔으로 자동으로
    // 채워진 값인지(true). 자동으로 채워진 값은 LOC만 바꿔 엔터를 칠 때 조건으로
    // 쓰지 않는다.
    private var isbnAuto = false
    private var settingIsbn = false
    private val checkedIds = mutableSetOf<Long>()

    // [2026-09-30] 목록 각 줄의 "위치" 칸(선택 토글용, 초록 V 표시)과 "바코드"
    // 칸(방향키 기본 포커스 대상)을 방향키로 옮겨다닐 수 있도록 순서대로
    // 기억해둔다(둘 다 refreshList()가 부를 때마다 새로 만들어지는 뷰라서,
    // 고정된 R.id 대신 이 목록으로 이전/다음 줄을 찾는다). checkMarks는
    // locationCells와 같은 순서로, 그 위치 칸의 초록 V 표시(TextView)를
    // 담아둔다. rowIds/rowLines도 같은 순서로 같이 관리한다(각각 그 줄의
    // stock_counts id, 그 줄의 LinearLayout).
    private val locationCells = mutableListOf<FrameLayout>()
    private val barcodeCells = mutableListOf<TextView>()
    private val checkMarks = mutableListOf<TextView>()
    private val rowIds = mutableListOf<Long>()
    // [2026-09-30] "LOC입력값넣고 엔터시 그 값으로 바로 조회 바코드값까지
    // 있을시 그 로케이션에 바코드로 조회" - rowIds/barcodeCells와 같은 순서로
    // 그 줄의 원본 StockRow를 같이 들고 있는다(재조회 없이 필드를 바로 채우기
    // 위함).
    private val rowDataCache = mutableListOf<StockRow>()
    private val rowLines = mutableListOf<LinearLayout>()
    private lateinit var btnDeleteSelected: View

    // [2026-09-30] "물리방향키로 위아래 어디든 이동가능하고 초록색 테두리
    // 포커스" - 지금 초록 테두리로 표시 중인 줄의 인덱스(-1 = 없음, 바코드
    // 칸이 포커스를 받았을 때만 줄 전체를 강조한다). 실제 안드로이드 포커스와는
    // 별개로 둬서, 스캔으로 찾은 줄을(포커스는 바코드칸에 그대로 둔 채) 강조
    // 표시만 할 수 있게 한다. 위치 칸으로 포커스가 넘어가면 이 줄 전체 강조는
    // 끄고 위치 칸 자체에만 작은 테두리를 그린다(clearRowHighlight 참고).
    private var highlightedRowIndex = -1

    private val scanReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val isbn = intent.getStringExtra("SCAN_BARCODE1")
            val state = intent.getStringExtra("SCAN_STATE")
            // [2026-09-29] "물리스캔 버튼으로 스캔시에도 입력하고 엔터친 효과로" -
            // 스캔으로 들어온 바코드도 사용자가 입력칸에 타이핑하고 엔터를 친
            // 것과 완전히 똑같이 처리한다(같은 함수 confirmIsbn 하나로 통일).
            //
            // [2026-09-30] "LOC도 물리 스캔버튼으로 입력할수있게" - 지금 포커스가
            // LOC칸에 있을 때 스캔하면, 그 값을 바코드칸이 아니라 LOC칸에 채우고
            // LOC 엔터 확정(confirmLoc)과 같은 효과를 낸다.
            if (state == "ok" && !isbn.isNullOrEmpty()) {
                runOnUiThread {
                    if (currentFocus == etLoc) {
                        // LOC를 물리 스캔: 바코드칸 값과 상관없이 그 LOC의 모든 바코드를 보여준다.
                        etLoc.setText(isbn)
                        etLoc.setSelection(etLoc.text.length)
                        confirmLoc(ignoreCode = true)
                    } else {
                        confirmIsbn(isbn)
                    }
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_stock_edit)
        db = DbHelper.getInstance(this)

        findViewById<TextView>(R.id.tvTitleBarText).text = "KOINTBOOK [재고수정]"

        etLoc = findViewById(R.id.etLoc)
        etIsbn = findViewById(R.id.etBarcode)
        etEditQty = findViewById(R.id.etEditQty)
        tvBookName = findViewById(R.id.tvProductName)
        llList = findViewById(R.id.llList)
        scrollList = findViewById(R.id.scrollList)
        tvItemCount = findViewById(R.id.tvItemCount)
        tvDan = findViewById(R.id.etDan)
        tvYeol = findViewById(R.id.etYeol)
        tvTotalQty = findViewById(R.id.tvTotalQty)

        // [2026-09-29] "로케이션 기본 입력값은 비워두고 전체조건을 검색되게" -
        // 예전엔 여기서 AppState.currentLocationKey()로 미리 채워서 항상 특정
        // 위치로만 좁혀 조회했다. 이제 기본값을 비워두고, 비어있으면
        // rowsForCurrentLocation()이 전체 데이터를 대상으로 조회한다.
        btnDeleteSelected = findViewById<android.widget.Button>(R.id.btnDeleteSelected).also {
            it.setOnClickListener { deleteSelected() }
        }
        findViewById<android.widget.Button>(R.id.btnComplete).also { btnComplete = it }.setOnClickListener { finish() }

        // [2026-10-02] "재고수정에서 바코드 입력 후 엔터 -> 목록이 조회되면 앱이 계속 중단됨" 수정.
        // 물리 엔터 한 번에 이 리스너가 누를 때(DOWN)와 뗄 때(UP) 두 번 불려서 목록을 두 번 연달아
        // 다시 그렸고, 첫 번째로 그린 줄로 스크롤하려던 예약 작업이 이미 지워진 그 줄을 찾다가 앱이
        // 강제 종료됐다. 이제 뗄 때(UP)는 무시해서 한 번만 처리한다(highlightRow도 안전하게 보완).
        etLoc.setOnEditorActionListener { _, _, event ->
            if (event != null && event.action == KeyEvent.ACTION_UP) return@setOnEditorActionListener true
            confirmLoc()
            true
        }
        etIsbn.setOnEditorActionListener { _, _, event ->
            if (event != null && event.action == KeyEvent.ACTION_UP) return@setOnEditorActionListener true
            val code = etIsbn.text.toString().trim()
            if (code.isNotEmpty()) {
                // 직접 입력(엔터) -> LOC칸 값이 있으면 LOC+바코드, 없으면 바코드만으로 조회.
                searchTyped(code)
            } else {
                // 바코드칸이 빈 채로 엔터 -> LOC 칸 값 기준으로만 조회(LOC도 비면 빈 목록)
                confirmLoc()
            }
            true
        }
        etIsbn.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, st: Int, c: Int, a: Int) {}
            override fun onTextChanged(s: CharSequence?, st: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: android.text.Editable?) {
                if (!settingIsbn) isbnAuto = false
            }
        })
        // [2026-09-30] "목록 엔터 누르면 수량칸으로 이동하여 또 엔터 누르면
        // 수정되고" - 수량칸에서 엔터(또는 IME의 '완료')를 누르면 [수정] 버튼
        // 없이 바로 반영한다.
        etEditQty.setOnEditorActionListener { _, _, event ->
            if (event != null && event.action == KeyEvent.ACTION_UP) return@setOnEditorActionListener true
            commitQtyEdit()
            true
        }

        refreshList()

        // [2026-09-29] "기본포커스는 바코드 입력칸" - 화면에 들어오면 바로
        // 스캔/타이핑할 수 있도록 바코드 입력칸에 포커스를 준다.
        etIsbn.isFocusableInTouchMode = true
        etIsbn.requestFocus()
    }

    /**
     * 물리 방향키(D-pad)/엔터로 다음칸·아랫칸으로 포커스를 옮긴다
     * (StockInputActivity의 dispatchKeyEvent 방식과 같은 원리).
     *
     * [2026-09-30 정정] "재고수정 화면에서 바코드 포커스 상태에서 방향키
     * 위아래로 LOC 입력칸, 아래 목록으로 이동할수 있게" - 예전엔 바코드칸
     * 아래 방향키가 수량칸으로 갔었는데, 그러면 목록으로 가려면 아래를
     * 두 번 눌러야 해서 헷갈렸다. 이제 바코드칸에서 위/아래는 LOC(위)/
     * 목록(아래)으로 바로 이동하고, 수량칸은 바코드칸에서 오른쪽 방향키로
     * (수량칸에서는 왼쪽 방향키로 되돌아오게) 옮겨다닌다 - 같은 줄 안에서
     * 좌우로 나란히 있는 두 칸이라는 화면 배치와도 자연스럽게 맞는다.
     *
     * [2026-09-30] "물리방향키 왼쪽키를 누르면 위치항목만 초록색테두리로
     * 포커스돼서 상하 이동도 위치로만 이동 엔터로도 선택표시" - 목록 줄의
     * 바코드 칸에 포커스가 있을 때 왼쪽 방향키를 누르면 같은 줄의 "위치"
     * 칸으로 포커스가 넘어가고, 위치 칸에 있는 동안 위/아래는 다른 줄의
     * "위치" 칸끼리만 오간다(컬럼 고정). 오른쪽 방향키나 엔터로 다시 바코드
     * 칸으로 돌아가거나(오른쪽), 그 자리에서 선택 표시를 토글한다(엔터).
     */
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action == KeyEvent.ACTION_DOWN) {
            val cur = currentFocus
            when (event.keyCode) {
                KeyEvent.KEYCODE_DPAD_DOWN -> {
                    when {
                        cur == etLoc -> { etIsbn.requestFocus(); return true }
                        cur == etIsbn || cur == etEditQty -> {
                            // 방금 스캔으로 강조해둔 줄이 있으면 그 줄부터 이어서
                            // 내려가고, 없으면 첫 줄부터 시작한다.
                            val startIdx = if (highlightedRowIndex in barcodeCells.indices) highlightedRowIndex else 0
                            if (barcodeCells.isNotEmpty()) barcodeCells[startIdx].requestFocus() else btnDeleteSelected.requestFocus()
                            return true
                        }
                        cur is TextView && cur in barcodeCells -> {
                            val idx = barcodeCells.indexOf(cur)
                            if (idx < barcodeCells.size - 1) barcodeCells[idx + 1].requestFocus()
                            else btnDeleteSelected.requestFocus()
                            return true
                        }
                        cur is FrameLayout && cur in locationCells -> {
                            // 위치 칸에 있을 때 상하 이동은 다른 줄의 위치 칸끼리만
                            // (컬럼 고정 - 바코드 칸으로는 넘어가지 않는다).
                            val idx = locationCells.indexOf(cur)
                            if (idx < locationCells.size - 1) locationCells[idx + 1].requestFocus()
                            else btnDeleteSelected.requestFocus()
                            return true
                        }
                    }
                }
                KeyEvent.KEYCODE_DPAD_UP -> {
                    when {
                        cur == etIsbn -> { etLoc.requestFocus(); return true }
                        cur == etEditQty -> { etIsbn.requestFocus(); return true }
                        cur is TextView && cur in barcodeCells -> {
                            val idx = barcodeCells.indexOf(cur)
                            if (idx > 0) barcodeCells[idx - 1].requestFocus() else etIsbn.requestFocus()
                            return true
                        }
                        cur is FrameLayout && cur in locationCells -> {
                            val idx = locationCells.indexOf(cur)
                            if (idx > 0) locationCells[idx - 1].requestFocus() else etIsbn.requestFocus()
                            return true
                        }
                        cur == btnDeleteSelected || cur?.id == R.id.btnComplete -> {
                            if (barcodeCells.isNotEmpty()) barcodeCells[barcodeCells.size - 1].requestFocus() else etIsbn.requestFocus()
                            return true
                        }
                    }
                }
                KeyEvent.KEYCODE_DPAD_LEFT -> {
                    // 바코드 칸 -> 같은 줄의 위치 칸으로.
                    if (cur is TextView && cur in barcodeCells) {
                        val idx = barcodeCells.indexOf(cur)
                        locationCells[idx].requestFocus()
                        return true
                    }
                    // 수량칸 -> 바코드칸으로 되돌아간다(좌우로 나란한 배치).
                    if (cur == etEditQty) { etIsbn.requestFocus(); return true }
                }
                KeyEvent.KEYCODE_DPAD_RIGHT -> {
                    // 위치 칸 -> 같은 줄의 바코드 칸으로 되돌아간다.
                    if (cur is FrameLayout && cur in locationCells) {
                        val idx = locationCells.indexOf(cur)
                        barcodeCells[idx].requestFocus()
                        return true
                    }
                    // 바코드칸 -> 수량칸으로(좌우로 나란한 배치).
                    if (cur == etIsbn) { etEditQty.requestFocus(); etEditQty.selectAll(); return true }
                }
                KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_NUMPAD_ENTER -> {
                    if (cur == etLoc) { confirmLoc(); return true }
                    // [2026-09-30] "엔터로도 선택표시" - 위치 칸에 포커스가 있을
                    // 때 엔터를 치면 터치했을 때와 똑같이 선택(초록 V) 표시가
                    // 토글된다.
                    if (cur is FrameLayout && cur in locationCells) {
                        val idx = locationCells.indexOf(cur)
                        toggleSelection(rowIds[idx], checkMarks[idx])
                        return true
                    }
                    // "목록 엔터 누르면 수량칸으로 이동하여 또 엔터 누르면
                    // 수정되고" - 바코드 칸(목록 줄의 기본 포커스)에 포커스가 있는
                    // 상태에서 엔터를 누르면 수량칸으로 이동한다.
                    if (cur is TextView && cur in barcodeCells) {
                        etEditQty.requestFocus()
                        etEditQty.selectAll()
                        return true
                    }
                    if (cur == etEditQty) { commitQtyEdit(); return true }
                    // etIsbn의 엔터는 etIsbn.setOnEditorActionListener에서 confirmIsbn()으로 처리한다.
                }
            }
        }
        return super.dispatchKeyEvent(event)
    }

    override fun onResume() {
        super.onResume()
        registerScanReceiverCompat(scanReceiver, IntentFilter(SCAN_ACTION))
    }

    override fun onPause() {
        super.onPause()
        try { unregisterReceiver(scanReceiver) } catch (_: Exception) {}
    }

    /** [2026-09-29] "로케이션 기본 입력값은 비워두고 전체조건을 검색되게" -
     * LOC칸이 비어있으면 특정 위치로 좁히지 않고(단, 지금 점포/조사일자
     * 안에서는) 전체를 대상으로 조회한다. 값이 있으면 예전처럼 그 위치로
     * 좁힌다.
     *
     * [2026-09-30 정정] "재고수정 화면으로 넘어가는데 4초가 걸려" - 예전엔
     * db.listAll()이 이 기기에 쌓인 모든 점포/모든 날짜의 실사 데이터를
     * 조건 없이 통째로 읽어와서 데이터가 쌓일수록 느려졌다 - 지금 점포/조사
     * 일자로 좁힌 db.listForCurrentSurvey()로 바꿨다(그 안에서는 위치 조건
     * 없이 전체 검색이라는 원래 취지 그대로다). */
    private fun rowsForCurrentLocation(): List<StockRow> {
        val loc = searchLoc.trim()
        val code = searchCode.trim()
        if (loc.isEmpty() && code.isEmpty()) return emptyList()
        // 항상 지금 점포/조사일자 안에서만 조회한다(색인 사용, 다른 날짜 데이터와 섞이지 않음).
        var rows: List<StockRow> = db.listForCurrentSurvey(AppState.storeCode, AppState.surveyDate())
        if (loc.isNotEmpty()) {
            val (area, section, shelfNo) = DbHelper.splitLocationKey(loc)
            rows = rows.filter { it.area == area && it.section == section && it.shelfNo == shelfNo }
        }
        if (code.isNotEmpty()) rows = rows.filter { it.isbn.equals(code, ignoreCase = true) }
        return rows
    }

    /** 바코드칸 값을 "자동으로 채운 값"으로 표시하며 넣는다(조건으로 쓰이지 않음). */
    private fun setIsbnText(text: String) {
        settingIsbn = true
        etIsbn.setText(text)
        etIsbn.setSelection(etIsbn.text.length)
        settingIsbn = false
        isbnAuto = true
    }

    /** 선택/조회된 줄의 내용을 위 입력칸들에 채운다. */
    private fun fillFields(row: StockRow) {
        selectedRowId = row.id
        setIsbnText(row.isbn)
        etEditQty.setText(row.qty.toString())
        tvBookName.text = row.bookName
        tvDan.text = row.dan
        tvYeol.text = row.yeol
    }

    /**
     * [2026-09-30] "LOC입력값넣고 엔터시 그 값으로 바로 조회 바코드값까지
     * 있을시 그 로케이션에 바코드로 조회" - LOC칸이 엔터(또는 물리 스캔)로
     * 확정되었을 때 공통으로 처리한다. 그 값으로 목록을 다시 좁혀 보여주고,
     * 이미 바코드칸에 값이 남아있으면(예: 다른 위치에서 바코드를 찾다가
     * LOC를 직접 바꾼 경우) 그 값으로 새로 좁혀진 목록 안에서 바로 이어서
     * 찾아준다. 바코드칸이 비어있으면 그냥 그 위치 목록만 보여주고 바코드
     * 칸으로 포커스를 돌려준다(예전 동작과 동일).
     */
    private fun confirmLoc(ignoreCode: Boolean = false) {
        // 바코드칸에 사용자가 직접 입력한 값이 있으면 LOC+바코드 조건, 없으면 LOC만.
        // (LOC를 물리 스캔한 경우에는 항상 LOC만)
        val code = if (ignoreCode || isbnAuto) "" else etIsbn.text.toString().trim()
        if (ignoreCode) setIsbnText("")
        searchLoc = etLoc.text.toString().trim()
        searchCode = code
        refreshList()
        if (searchLoc.isEmpty() && code.isEmpty()) {
            Toast.makeText(this, "LOC 또는 바코드를 입력하세요.", Toast.LENGTH_SHORT).show()
        } else if (rowIds.isEmpty()) {
            Toast.makeText(this, "조건에 맞는 항목이 없습니다.", Toast.LENGTH_SHORT).show()
        } else if (code.isNotEmpty()) {
            fillFields(rowDataCache[0])
            highlightRow(0, scrollTo = true)
        }
        etIsbn.requestFocus()
        etIsbn.selectAll()
    }

    /**
     * 바코드를 직접 입력하고 엔터를 쳤을 때: LOC칸이 비어 있으면 그 바코드가 있는 모든
     * LOC에서 그 바코드만, LOC칸에 값이 있으면 그 LOC 안의 그 바코드만 보여준다.
     */
    private fun searchTyped(code: String) {
        searchLoc = etLoc.text.toString().trim()
        searchCode = code
        refreshList()
        if (rowIds.isEmpty()) {
            Toast.makeText(this, "조건에 맞는 항목이 없습니다.", Toast.LENGTH_SHORT).show()
        } else {
            fillFields(rowDataCache[0])
            highlightRow(0, scrollTo = true)
        }
        etIsbn.requestFocus()
        etIsbn.selectAll()
    }

    /**
     * 물리 스캔으로 바코드가 들어왔을 때. [2026-10-10] "그 바코드가 찍힌 곳만 나오고, 그 위치의 모든
     * 바코드가 나오면 안 된다 / LOC+바코드면 둘 다 일치하는 값만" - 예전에는 바코드가 한 LOC에만 있으면
     * LOC칸을 그 LOC로 채우고 그 LOC의 모든 바코드를 보여줬다(여러 LOC에 있을 때만 그 바코드 줄만 보여서
     * 경우마다 달랐다). 이제는 바코드를 직접 입력하고 엔터를 친 것(searchTyped)과 똑같이 처리한다:
     *   - LOC칸이 비어 있으면: 그 바코드가 찍힌 모든 LOC의 그 바코드 줄만
     *   - LOC칸에 값이 있으면: 그 LOC 안의 그 바코드 줄만(LOC+바코드 둘 다 일치)
     * LOC칸 값은 스캔이 바꾸지 않는다.
     */
    private fun confirmIsbn(isbn: String) {
        setIsbnText(isbn)
        searchTyped(isbn)
    }

    /**
     * [2026-09-30] "목록 엔터 누르면 수량칸으로 이동하여 또 엔터 누르면
     * 수정되고 수정되었습니다 메세지 잠깐 띄워주고 수정하고 다시 포커스는
     * 방금전 수정했던 목록 그 줄로 포커스" - 예전 [수정] 버튼(applyQtyEdit)을
     * 대신한다. 버튼이 없어졌으므로 이 함수가 유일한 "수정 반영" 경로다.
     *
     * "수량 0으로 수정할수있게 변경" - qty<=0을 전부 막던 것을 0은 허용하고
     * 음수/숫자아님만 막도록 바꿨다.
     */
    private fun commitQtyEdit() {
        val id = selectedRowId
        if (id == null) {
            Toast.makeText(this, "먼저 목록에서 항목을 선택하거나 바코드를 스캔하세요.", Toast.LENGTH_SHORT).show()
            return
        }
        val qty = etEditQty.text.toString().toIntOrNull()
        if (qty == null || qty < 0) {
            Toast.makeText(this, "올바른 수량을 입력하세요.", Toast.LENGTH_SHORT).show()
            etEditQty.selectAll()
            return
        }
        db.updateStockCountQty(id, qty)
        Toast.makeText(this, "수정되었습니다.", Toast.LENGTH_SHORT).show()
        refreshList()
        // 수정한 그 줄로 다시 포커스를 돌려준다(그 줄의 바코드 칸 - 목록의
        // 기본 포커스 대상).
        val idx = rowIds.indexOf(id)
        if (idx in barcodeCells.indices) barcodeCells[idx].requestFocus()
    }

    private fun deleteSelected() {
        if (checkedIds.isEmpty()) {
            Toast.makeText(this, "삭제할 항목을 선택하세요.", Toast.LENGTH_SHORT).show()
            return
        }
        for (id in checkedIds) db.deleteStockCount(id)
        checkedIds.clear()
        selectedRowId = null
        Toast.makeText(this, "삭제되었습니다.", Toast.LENGTH_SHORT).show()
        refreshList()
    }

    /** [2026-09-30] 선택(삭제 대상) 표시를 토글한다 - 위치 칸을 터치하거나
     * (그 칸에 포커스가 있을 때) 엔터를 치면 호출된다. 선택되면 위치 칸
     * 내용(단-열) 위에 겹쳐진 초록색 "✓" 표시를 보이게 하고, checkedIds에
     * 담아 [선택삭제]의 대상이 되게 한다. */
    private fun toggleSelection(rowId: Long, mark: TextView) {
        if (checkedIds.contains(rowId)) {
            checkedIds.remove(rowId)
            mark.visibility = View.GONE
        } else {
            checkedIds.add(rowId)
            mark.visibility = View.VISIBLE
        }
    }

    /** [2026-09-30] StockInputActivity와 동일한 방식: 짝수/홀수 줄 배경색 +
     * 강조된 줄만 초록 테두리(GradientDrawable stroke)를 얹는다. 목록 줄의
     * 바코드 칸에 포커스가 있을 때(방향키로 줄과 줄을 오갈 때) 이 방식으로
     * 줄 전체를 강조한다. */
    private fun buildRowBackground(index: Int, highlighted: Boolean): Drawable {
        val altBg = if (index % 2 == 1) ContextCompat.getColor(this, R.color.bg_surface) else Color.TRANSPARENT
        if (!highlighted) return ColorDrawable(altBg)
        val border = GradientDrawable()
        border.setColor(Color.TRANSPARENT)
        border.setStroke((3 * resources.displayMetrics.density).toInt(), ContextCompat.getColor(this, R.color.focus_green))
        return LayerDrawable(arrayOf(ColorDrawable(altBg), border))
    }

    /** idx번 줄만 초록 테두리로 강조하고 나머지는 원래 배경으로 되돌린다.
     * scrollTo=true면 그 줄이 보이도록 스크롤도 옮긴다. */
    private fun highlightRow(idx: Int, scrollTo: Boolean = false) {
        highlightedRowIndex = idx
        for ((i, line) in rowLines.withIndex()) {
            line.background = buildRowBackground(i, i == idx)
        }
        if (scrollTo) {
            val target = rowLines.getOrNull(idx) ?: return
            scrollList.post {
                // [2026-10-02] 그 사이 목록이 다시 그려져 이 줄이 빠졌으면 건너뛴다(빠진 줄로 위치를
                // 계산하면 IllegalArgumentException으로 앱이 강제 종료되던 원인).
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
    }

    /** [2026-09-30] "위치항목만 초록색테두리로 포커스돼서" - 바코드 칸에서
     * 왼쪽 방향키로 위치 칸에 포커스가 넘어가면, 줄 전체 강조(초록 테두리)는
     * 끄고 위치 칸 "그 자체에만" 작은 테두리를 그린다(buildLocationCellBorder
     * 참고) - 이 함수는 그 전환 시점에 줄 전체 강조를 지운다. */
    private fun clearRowHighlight() {
        if (highlightedRowIndex == -1) return
        highlightedRowIndex = -1
        for ((i, line) in rowLines.withIndex()) {
            line.background = buildRowBackground(i, false)
        }
    }

    /** 위치 칸 자체에 두르는 작은 초록 테두리(포커스 표시). 줄 전체
     * 배경(buildRowBackground)과는 별개로 위치 칸의 background에만 씌운다. */
    private fun buildLocationCellBorder(focused: Boolean): Drawable {
        if (!focused) return ColorDrawable(Color.TRANSPARENT)
        val border = GradientDrawable()
        border.setColor(Color.TRANSPARENT)
        border.setStroke((2 * resources.displayMetrics.density).toInt(), ContextCompat.getColor(this, R.color.focus_green))
        return border
    }

    private fun refreshList() {
        val rows = rowsForCurrentLocation()
        llList.removeAllViews()
        checkedIds.clear()
        locationCells.clear()
        barcodeCells.clear()
        checkMarks.clear()
        rowIds.clear()
        rowDataCache.clear()
        rowLines.clear()
        highlightedRowIndex = -1

        for ((index, row) in rows.asReversed().withIndex()) {
            val line = LinearLayout(this)
            line.orientation = LinearLayout.HORIZONTAL
            line.setPadding(4, 4, 4, 4)
            line.background = buildRowBackground(index, false)
            val selectRowFields = { fillFields(row) }
            // 위치 칸을 뺀 나머지(바코드/도서명/수량) 영역을 탭하면 이 줄
            // 내용을 위 입력칸들로 불러온다(선택 표시와는 무관 - 위치 칸을
            // 터치했을 때만 선택 표시가 토글된다. 위치 칸은 자신만의
            // OnClickListener를 갖고 있어 이 리스너로 이벤트가 전달되지
            // 않는다).
            line.setOnClickListener { selectRowFields() }
            rowIds.add(row.id)
            rowDataCache.add(row)
            rowLines.add(line)

            // [2026-09-30] "선택방식은 항목중 위치 쪽만 터치해야 선택되고
            // 선택표시는 위치내용 위에 초록색 V표시" - 위치 칸을 FrameLayout으로
            // 만들어, 단-열 텍스트 위에 초록색 "✓" 표시(기본은 숨김)를 겹쳐
            // 그린다. 터치하거나(포커스 상태에서) 엔터를 치면 toggleSelection()
            // 으로 이 표시를 켜고 끈다.
            // [2026-09-30] "위치 터치 체크 범위를 개선해야될거같은데 잘
            // 안눌려서 선택이 잘안됨" - 칸 너비 자체도 0.8 -> 1.1로 조금
            // 넓혔다(그만큼 도서명 칸을 줄여 전체 비율은 맞춘다 - 아래
            // 도서명 cell(row.bookName, ...) 참고). 진짜 히트 영역 확대는
            // 아래 TouchDelegate로 한다.
            val locFrame = FrameLayout(this)
            locFrame.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 0.8f)
            locFrame.isFocusable = true
            locFrame.isFocusableInTouchMode = true
            locFrame.isClickable = true

            val locText = TextView(this)
            locText.text = "${row.dan}-${row.yeol}"
            locText.textSize = 14f
            locText.setTypeface(Typeface.DEFAULT_BOLD)
            locText.setTextColor(Color.parseColor("#000000"))
            locText.gravity = Gravity.CENTER
            locText.maxLines = 1
            locText.ellipsize = android.text.TextUtils.TruncateAt.END
            locText.setSingleLine(true)
            locText.layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT
            )
            locFrame.addView(locText)

            val mark = TextView(this)
            mark.text = "✓"
            mark.textSize = 16f
            mark.setTypeface(Typeface.DEFAULT_BOLD)
            mark.setTextColor(ContextCompat.getColor(this, R.color.focus_green))
            mark.gravity = Gravity.CENTER
            mark.visibility = View.GONE
            mark.layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT
            )
            locFrame.addView(mark)

            locFrame.setOnClickListener { toggleSelection(row.id, mark) }
            // 위치 칸이 포커스를 받으면(방향키 왼쪽으로 들어왔을 때) 그
            // 칸에만 작은 초록 테두리를 두르고, 줄 전체 강조는 끈다. 포커스를
            // 잃으면(방향키 오른쪽 등) 테두리를 없앤다.
            //
            // [2026-09-30] "재고수정화면 목록 선택시 V표시만, 초록색 배경은
            // 안되게" - 위치 칸은 isClickable/isFocusable이라 터치로 눌러
            // 선택(V표시)할 때도 동시에 포커스를 받아 이 초록 테두리가 함께
            // 나타나 "선택하면 초록 배경도 생긴다"처럼 보였다. 방향키(D-pad)
            // 탐색 중일 때만(터치 모드가 아닐 때만) 테두리를 그리도록 해서,
            // 터치로 선택할 때는 ✓ 표시만 나타나고, 물리 방향키로 이동할
            // 때는 기존처럼 초록 테두리 포커스 표시가 그대로 남게 했다.
            locFrame.setOnFocusChangeListener { _, hasFocus ->
                locFrame.background = buildLocationCellBorder(hasFocus && !locFrame.isInTouchMode)
                if (hasFocus) clearRowHighlight()
            }
            locationCells.add(locFrame)
            checkMarks.add(mark)
            line.addView(locFrame)

            // [2026-10-06] 재고입력 화면 목록과 같은 글자(14sp 굵게)와 너비 비율(0.8/2.6/2/0.6).
            fun cell(text: String, weight: Float): TextView {
                val tv = TextView(this)
                tv.text = text
                tv.textSize = 14f
                tv.setTypeface(Typeface.DEFAULT_BOLD)
                tv.setTextColor(Color.parseColor("#000000"))
                tv.gravity = Gravity.CENTER
                tv.maxLines = 1
                tv.ellipsize = android.text.TextUtils.TruncateAt.END
                tv.setSingleLine(true)
                tv.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, weight)
                return tv
            }

            // [2026-09-30] "목록에서 바코드가 처음포커스" - 바코드 칸이 이제
            // 목록 줄의 기본 방향키 포커스 대상이다(예전 체크박스 역할을
            // 대신함). 포커스를 받으면 그 줄 내용을 위 입력칸에 채우고, 줄
            // 전체를 초록 테두리로 강조한다(StockInputActivity와 동일한 느낌).
            val barcodeTv = cell(row.isbn, 2.6f)
            barcodeTv.isFocusable = true
            barcodeTv.isFocusableInTouchMode = true
            barcodeTv.isClickable = true
            barcodeTv.setOnClickListener { selectRowFields() }
            barcodeTv.setOnFocusChangeListener { _, hasFocus ->
                if (hasFocus) {
                    selectRowFields()
                    highlightRow(index)
                }
            }
            barcodeCells.add(barcodeTv)
            line.addView(barcodeTv)

            // [2026-09-30] "목록을 재고입력 목록이랑 동일하게 구성"이 원래
            // 비율이었으나(0.8 / 2.6 / 2 / 0.6), 위치 칸 터치 문제로 위치
            // 칸만 1.1로 넓힌 만큼 도서명 칸을 2 -> 1.7로 줄여 전체 비율을
            // 맞췄다(activity_stock_edit.xml 헤더도 같은 비율로 맞춰뒀다).
            line.addView(cell(row.bookName, 2f))
            line.addView(cell(row.qty.toString(), 0.6f))
            llList.addView(line)

            // [2026-09-30] "위치 터치 체크 범위를 개선해야될거같은데 잘
            // 안눌려서 선택이 잘안됨" - 위치 칸의 실제 터치 판정 영역을
            // TouchDelegate로 사방 12dp씩 넓혀서, 칸 경계에 살짝 벗어나게
            // 눌러도 선택이 인식되게 한다(레이아웃 자체는 그대로 두고 터치
            // 판정 영역만 넓히는 표준 안드로이드 방식). 실제 좌표는 레이아웃이
            // 끝난 뒤에만 알 수 있으므로 post{}로 한 프레임 뒤에 계산한다.
            line.post {
                val rect = Rect()
                locFrame.getHitRect(rect)
                val expand = (12 * resources.displayMetrics.density).toInt()
                rect.left -= expand
                rect.top -= expand
                rect.right += expand
                rect.bottom += expand
                line.touchDelegate = TouchDelegate(rect, locFrame)
            }
        }

        tvItemCount.text = "ITEM: ${formatQty(rows.size)}"
        // [2026-09-30] "총수량 숫자 세자리 이상시 3자리 콤마" - 천단위 구분 콤마.
        tvTotalQty.text = "총수량: ${formatQty(rows.sumOf { it.qty })}"
    }

    private fun formatQty(n: Int): String = NumberFormat.getNumberInstance(Locale.US).format(n)
}
