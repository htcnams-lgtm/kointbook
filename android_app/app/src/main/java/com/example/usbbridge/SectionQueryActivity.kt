// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.os.Bundle
import android.view.Gravity
import android.view.KeyEvent
import android.widget.ArrayAdapter
import android.widget.LinearLayout
import android.widget.Spinner
import android.widget.TextView
import androidx.core.content.ContextCompat
import java.text.NumberFormat
import java.util.Locale

/** 위치 건수/수량 조회: 위치별 건수/수량 집계표
 * [2026-10-15] Data 관리 메뉴 이름 "2. DATA 조회"(예전 3. 위치별 건수/수량 조회). 화면 내용은 그대로. */
class SectionQueryActivity : BaseActivity() {

    private lateinit var db: DbHelper
    private var btnQuery: android.view.View? = null

    override fun primaryButton(): android.view.View? = btnQuery
    private lateinit var spLocation: Spinner
    private lateinit var llList: LinearLayout
    private lateinit var tvItemCount: TextView
    private lateinit var tvTotalQty: TextView

    // [2026-09-29] "물리방향키로 로케이션 선택칸, 조회칸, 목록으로 이동시
    // 초록색테두리 포커스 안생김" - 이 화면은 원래 목록 줄이 포커스를 아예
    // 받을 수 없는 평범한 TextView라서 방향키로는 목록까지 갈 수도 없었고,
    // Spinner는 방향키 아래를 누르면 포커스 이동 대신 자기 드롭다운을 여는
    // 기본 동작이 있어 다음 칸으로 넘어가지도 못했다. 그래서 목록 줄을
    // 포커스 가능하게 만들고, DPAD 상하 이동은 아래 dispatchKeyEvent에서
    // 직접 처리한다 (StockInputActivity 등과 같은 방식).
    private val rowViews = mutableListOf<LinearLayout>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_section_query)
        db = DbHelper.getInstance(this)

        findViewById<TextView>(R.id.tvTitleBarText).text = "KOINTBOOK [DATA 조회]"

        spLocation = findViewById(R.id.spLocation)
        llList = findViewById(R.id.llList)
        tvItemCount = findViewById(R.id.tvItemCount)
        tvTotalQty = findViewById(R.id.tvTotalQty)

        spLocation.isFocusableInTouchMode = true

        // [2026-09-30] DataQueryActivity와 같은 이유로 이 화면도 store_code/
        // survey_date로 좁혀서 조회한다(DbHelper.sectionSummary 참고).
        val locations = mutableListOf("전체")
        locations.addAll(db.areaSectionSummary(null, AppState.storeCode, AppState.surveyDate()).map { it.first })
        val adapter = ArrayAdapter(this, R.layout.spinner_item, locations)
        adapter.setDropDownViewResource(R.layout.spinner_dropdown_item)
        spLocation.adapter = adapter

        findViewById<android.widget.Button>(R.id.btnQuery).also { btnQuery = it }.setOnClickListener { runQuery() }
        runQuery()

        // 화면에 들어오면 위치 선택칸에 바로 포커스(초록 테두리)가 보이게 한다.
        spLocation.requestFocus()
    }

    /** 방향키로 다음칸·아랫칸 이동: 위치선택 -> 조회버튼 -> 목록 각 줄 순서로
     * 내려가고, 위 방향키는 반대로 올라간다. */
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action == KeyEvent.ACTION_DOWN) {
            val cur = currentFocus
            val btn = btnQuery
            when (event.keyCode) {
                KeyEvent.KEYCODE_DPAD_DOWN -> {
                    when {
                        cur == spLocation -> { btn?.requestFocus(); return true }
                        cur == btn -> {
                            if (rowViews.isNotEmpty()) rowViews[0].requestFocus()
                            return true
                        }
                        cur is LinearLayout && cur in rowViews -> {
                            val idx = rowViews.indexOf(cur)
                            if (idx < rowViews.size - 1) rowViews[idx + 1].requestFocus()
                            return true
                        }
                    }
                }
                KeyEvent.KEYCODE_DPAD_UP -> {
                    when {
                        cur == btn -> { spLocation.requestFocus(); return true }
                        cur is LinearLayout && cur in rowViews -> {
                            val idx = rowViews.indexOf(cur)
                            if (idx > 0) rowViews[idx - 1].requestFocus() else btn?.requestFocus()
                            return true
                        }
                    }
                }
            }
        }
        return super.dispatchKeyEvent(event)
    }

    private fun runQuery() {
        val selected = spLocation.selectedItem?.toString()
        val rows = db.areaSectionSummary(selected, AppState.storeCode, AppState.surveyDate())
        llList.removeAllViews()
        rowViews.clear()

        // 건수/수량 칸 너비: 목록 글씨(17sp 굵게)로 "99,999"와 실제 값들 중 가장 긴 것을 재서 + 여백.
        val numPaint = android.text.TextPaint().apply {
            textSize = android.util.TypedValue.applyDimension(
                android.util.TypedValue.COMPLEX_UNIT_SP, 17f, resources.displayMetrics
            )
            typeface = android.graphics.Typeface.DEFAULT_BOLD
        }
        val numTexts = listOf("99,999") + rows.flatMap { listOf(formatNum(it.second), formatNum(it.third)) }
        val numColWidth = kotlin.math.ceil(numTexts.maxOf { numPaint.measureText(it) }).toInt() +
            (12 * resources.displayMetrics.density).toInt()
        for (id in intArrayOf(R.id.tvHeadCount, R.id.tvHeadQty)) {
            findViewById<TextView>(id).layoutParams =
                LinearLayout.LayoutParams(numColWidth, LinearLayout.LayoutParams.WRAP_CONTENT)
        }

        for ((loc, count, qty) in rows) {
            val line = LinearLayout(this)
            line.orientation = LinearLayout.HORIZONTAL
            line.setPadding(6, 8, 6, 8)
            line.isFocusable = true
            line.isFocusableInTouchMode = true
            line.setOnFocusChangeListener { _, hasFocus ->
                line.background = if (hasFocus) {
                    ContextCompat.getDrawable(this, R.drawable.row_focus_border)
                } else {
                    null
                }
            }

            // [2026-09-30] "목록 내용 글씨크기 2사이즈 크고굵게" - 13sp -> 15sp,
            // 굵게(bold) 추가.
            // [2026-09-30 추가] "로케이션 건수/수량 조회 목록 내용 글자,숫자 크기
            // 2사이즈 크게" - 15sp -> 17sp (한 번 더).
            fun cell(text: String, widthPx: Int): TextView {
                val tv = TextView(this)
                tv.text = text
                tv.textSize = 17f
                tv.setTypeface(tv.typeface, android.graphics.Typeface.BOLD)
                tv.setTextColor(android.graphics.Color.parseColor("#000000"))  // DATA 조회 화면과 같은 진한 글씨
                tv.gravity = Gravity.CENTER
                tv.maxLines = 1
                tv.setSingleLine(true)
                tv.layoutParams = if (widthPx > 0) {
                    LinearLayout.LayoutParams(widthPx, LinearLayout.LayoutParams.WRAP_CONTENT)
                } else {
                    LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                }
                return tv
            }
            // [2026-10-02] "위치값이 길어서 줄바꿈 - 건수/수량을 5자리로 보고 위치 너비를 넓혀서 줄바꿈이
            // 안 되게, 단 건수/수량 값도 잘리면 안 됨" - 건수/수량 칸은 "99,999"(또는 실제로 더 긴 값)가
            // 다 들어가는 딱 그 너비만 쓰고, 나머지 너비를 전부 위치 칸에 준다. 위치 값이 그래도 길면
            // 줄을 바꾸지 않고 글씨를 조금씩 줄여 한 줄에 맞춘다(최소 11sp).
            val locCell = cell(loc, 0)
            androidx.core.widget.TextViewCompat.setAutoSizeTextTypeUniformWithConfiguration(
                locCell, 11, 17, 1, android.util.TypedValue.COMPLEX_UNIT_SP
            )
            line.addView(locCell)
            line.addView(cell(formatNum(count), numColWidth))
            line.addView(cell(formatNum(qty), numColWidth))
            llList.addView(line)
            rowViews.add(line)
        }

        // [2026-09-30] "ITEM, 총수량 값 3자리 이상 콤마" - 천단위 구분 콤마.
        tvItemCount.text = "ITEM: ${formatNum(rows.sumOf { it.second })}"
        tvTotalQty.text = "총수량: ${formatNum(rows.sumOf { it.third })}"
    }

    private fun formatNum(n: Int): String = NumberFormat.getNumberInstance(Locale.US).format(n)
}
