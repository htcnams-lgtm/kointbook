// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.os.Bundle
import android.view.Gravity
import android.widget.ArrayAdapter
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast

/**
 * Data 관리 > 2. DATA 조회
 *
 * 참고 화면 구성: LOCATION 드롭다운(전체/개별 로케이션) + 조회 버튼,
 * 그 아래 체크박스가 있는 로케이션 목록, 하단에 전체삭제/선택삭제.
 * 전송 여부와 관계없이 PDA에 실제로 입력되어 있는 로케이션을 모두 보여준다.
 */
class DataQueryActivity : BaseActivity() {

    private lateinit var db: DbHelper
    private lateinit var spLocation: Spinner
    private lateinit var llList: LinearLayout
    private val checked = mutableSetOf<String>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_data_query)
        db = DbHelper.getInstance(this)

        findViewById<TextView>(R.id.tvTitleBarText).text = "KOINTBOOK [DATA 조회]"

        spLocation = findViewById(R.id.spLocation)
        llList = findViewById(R.id.llList)

        findViewById<android.widget.Button>(R.id.btnQuery).setOnClickListener { refreshList() }
        findViewById<android.widget.Button>(R.id.btnDeleteAll).setOnClickListener { confirmDeleteAll() }
        findViewById<android.widget.Button>(R.id.btnDeleteSelected).setOnClickListener { deleteSelected() }

        // [2026-09-30] "DATA조회 화면 전환이 느려 최초 딜레이 2초" - onCreate()에서
        // 한 번, 곧이어 실행되는 onResume()에서 또 한 번, 같은 조회(loadLocationSpinner
        // + refreshList, 아래에서 sectionSummary를 여러 번 부름)를 화면에 들어올
        // 때마다 두 배로 실행하고 있었다. onCreate 직후에는 항상 onResume이 바로
        // 이어서 호출되므로, 여기서는 부르지 않고 onResume 한 곳에서만 처리한다.
    }

    override fun onResume() {
        super.onResume()
        loadLocationSpinner()
        refreshList()
    }

    private fun loadLocationSpinner() {
        val locations = mutableListOf("전체")
        locations.addAll(db.sectionSummary(null, AppState.storeCode, AppState.surveyDate()).map { it.first })
        val adapter = ArrayAdapter(this, R.layout.spinner_item, locations)
        adapter.setDropDownViewResource(R.layout.spinner_dropdown_item)
        spLocation.adapter = adapter
    }

    private fun refreshList() {
        checked.clear()
        val selected = spLocation.selectedItem?.toString()
        val allLocations = db.sectionSummary(null, AppState.storeCode, AppState.surveyDate()).map { it.first }
        val locations = if (selected.isNullOrEmpty() || selected == "전체") {
            allLocations
        } else {
            allLocations.filter { it == selected }
        }

        llList.removeAllViews()
        for (loc in locations) {
            val density = resources.displayMetrics.density
            val line = LinearLayout(this)
            line.orientation = LinearLayout.HORIZONTAL
            line.gravity = Gravity.CENTER_VERTICAL
            // 테두리(3dp)가 체크박스/글씨를 가리지 않도록 여백을 조금 둔다.
            // [2026-09-29] "로케이션 항목 목록 세로 사이간격을 70%로 줄여서
            // 목록이 한화면에 많이 보이도록" - 줄 사이 위아래 여백(세로 간격)만
            // 원래(4dp)의 70%로 줄인다(좌우 여백은 그대로 둔다).
            val padVVertical = (4 * 0.7f * density).toInt()
            line.setPadding((8 * density).toInt(), padVVertical, (8 * density).toInt(), padVVertical)

            val cb = CheckBox(this)
            cb.layoutParams = LinearLayout.LayoutParams(40, LinearLayout.LayoutParams.WRAP_CONTENT)
            cb.setOnCheckedChangeListener { _, isChecked ->
                if (isChecked) checked.add(loc) else checked.remove(loc)
            }
            // 방향키로 이 로케이션 줄에 포커스가 오면 초록 테두리를 보여준다.
            cb.setOnFocusChangeListener { _, hasFocus ->
                line.background = if (hasFocus) {
                    androidx.core.content.ContextCompat.getDrawable(this, R.drawable.row_focus_border)
                } else {
                    null
                }
            }
            line.addView(cb)

            // [2026-09-30] "DATA 조회 목록 글씨크기 2사이즈 크고 굵게" - 15sp -> 17sp, 굵게.
            val tv = TextView(this)
            tv.text = loc
            tv.textSize = 17f
            tv.setTypeface(tv.typeface, android.graphics.Typeface.BOLD)
            tv.setTextColor(android.graphics.Color.parseColor("#000000"))
            tv.gravity = Gravity.CENTER
            tv.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            line.addView(tv)

            llList.addView(line)
        }
    }

    private fun confirmDeleteAll() {
        Dialogs.confirm(
            activity = this,
            title = "확인",
            message = "조회된 위치 데이터를 전체 삭제할까요?",
            positiveText = "예",
            negativeText = "아니요",
            focusPositive = false,
            onPositive = {
                val selected = spLocation.selectedItem?.toString()
                if (selected.isNullOrEmpty() || selected == "전체") {
                    db.deleteAll()
                } else {
                    db.deleteLocation(selected)
                }
                Toast.makeText(this, "삭제되었습니다.", Toast.LENGTH_SHORT).show()
                loadLocationSpinner()
                refreshList()
            }
        )
    }

    private fun deleteSelected() {
        if (checked.isEmpty()) {
            Toast.makeText(this, "삭제할 위치를 선택하세요.", Toast.LENGTH_SHORT).show()
            return
        }
        Dialogs.confirm(
            activity = this,
            title = "확인",
            message = "선택한 ${checked.size}개 위치의 데이터를 삭제할까요?",
            positiveText = "예",
            negativeText = "아니요",
            focusPositive = false,
            onPositive = {
                for (loc in checked) db.deleteLocation(loc)
                Toast.makeText(this, "삭제되었습니다.", Toast.LENGTH_SHORT).show()
                loadLocationSpinner()
                refreshList()
            }
        )
    }
}
