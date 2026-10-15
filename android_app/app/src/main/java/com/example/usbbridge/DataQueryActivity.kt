// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.os.Bundle
import android.view.Gravity
import android.view.KeyEvent
import android.view.inputmethod.EditorInfo
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

/**
 * Data 관리 > 3. DATA 삭제 (2026-10-15 전에는 "2. DATA 조회"였던 화면)
 *
 * 화면 구성: AREA / SECTION 입력칸(1줄), 서가번호 입력칸 + 조회 버튼(2줄),
 * 그 아래 체크박스가 있는 위치(AREA-SECTION-서가번호) 목록, 하단에 전체삭제/선택삭제.
 * 전송 여부와 관계없이 PDA에 실제로 입력되어 있는 위치를 보여준다.
 *
 * [2026-10-15] "검색조건을 선택스크롤로 하지 말고" - 위치 드롭다운 대신 입력칸으로 조회한다.
 *   - 엔터: AREA -> SECTION -> 서가번호 -> [조회] 버튼(초록 테두리) -> 엔터로 조회.
 *     칸이 비어 있어도 엔터로 다음 칸으로 넘어간다(AREA만 넣고 조회할 수 있게).
 *   - 조회 조건은 값을 넣은 칸만: AREA만 = 그 AREA 전체, AREA+SECTION = 둘 다 맞는 위치,
 *     AREA+SECTION+서가번호 = 셋 다 맞는 위치. 세 칸이 다 비면 전체(DbHelper.locationKeysByFilter).
 */
class DataQueryActivity : BaseActivity() {

    private lateinit var db: DbHelper
    private lateinit var etArea: EditText
    private lateinit var etSection: EditText
    private lateinit var etShelfNo: EditText
    private lateinit var fields: List<EditText>
    private var btnQuery: android.view.View? = null
    private lateinit var llList: LinearLayout
    private val checked = mutableSetOf<String>()

    // 마지막으로 조회해서 목록에 보여준 위치들과, 그때 조건(입력칸 값)이 하나라도 있었는지.
    // [전체삭제]는 입력칸을 고친 뒤 조회를 안 눌렀더라도 "지금 목록에 보이는 것"만 지운다.
    private var shownLocations: List<String> = emptyList()
    private var shownFiltered = false

    // 입력칸에 포커스가 없을 때 엔터를 누르면 [조회]가 눌린다(BaseActivity).
    override fun primaryButton(): android.view.View? = btnQuery

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_data_query)
        db = DbHelper.getInstance(this)

        findViewById<TextView>(R.id.tvTitleBarText).text = "KOINTBOOK [DATA 삭제]"

        etArea = findViewById(R.id.etArea)
        etSection = findViewById(R.id.etSection)
        etShelfNo = findViewById(R.id.etShelfNo)
        fields = listOf(etArea, etSection, etShelfNo)
        llList = findViewById(R.id.llList)

        findViewById<android.widget.Button>(R.id.btnQuery).also { btnQuery = it }.apply {
            setOnClickListener { refreshList(fromButton = true) }
            // moveToNext()에서 터치 모드 때문에 잠깐 켠 포커스 허용은 포커스가 빠지면 다시 끈다
            // (켠 채로 두면 손가락으로 [조회]를 누를 때 두 번 눌러야 한다).
            setOnFocusChangeListener { v, hasFocus -> if (!hasFocus) v.isFocusableInTouchMode = false }
        }
        findViewById<android.widget.Button>(R.id.btnDeleteAll).setOnClickListener { confirmDeleteAll() }
        findViewById<android.widget.Button>(R.id.btnDeleteSelected).setOnClickListener { deleteSelected() }

        // 엔터(물리 엔터 또는 키보드의 다음/완료): AREA -> SECTION -> 서가번호 -> [조회] 버튼.
        // 작업준비 화면(작업자번호 엔터 -> [다음] 버튼)과 같은 방식으로, 마지막 칸에서는 조회를
        // 바로 하지 않고 [조회] 버튼에 포커스(초록 테두리)만 옮긴다. 다시 엔터를 누르면 버튼이 눌린다.
        for ((index, field) in fields.withIndex()) {
            field.setOnEditorActionListener { _, actionId, event ->
                val isEnter = actionId == EditorInfo.IME_ACTION_NEXT || actionId == EditorInfo.IME_ACTION_DONE ||
                    (event != null && event.action == KeyEvent.ACTION_DOWN &&
                        (event.keyCode == KeyEvent.KEYCODE_ENTER || event.keyCode == KeyEvent.KEYCODE_NUMPAD_ENTER))
                if (isEnter) {
                    moveToNext(index)
                    true
                } else false
            }
        }

        etArea.requestFocus()

        // [2026-09-30] "DATA조회 화면 전환이 느려 최초 딜레이 2초" - onCreate()에서
        // 한 번, 곧이어 실행되는 onResume()에서 또 한 번, 같은 조회(loadLocationSpinner
        // + refreshList, 아래에서 sectionSummary를 여러 번 부름)를 화면에 들어올
        // 때마다 두 배로 실행하고 있었다. onCreate 직후에는 항상 onResume이 바로
        // 이어서 호출되므로, 여기서는 부르지 않고 onResume 한 곳에서만 처리한다.
    }

    override fun onResume() {
        super.onResume()
        refreshList()
    }

    /** index번 입력칸에서 엔터: 다음 입력칸(전체 선택해서 바로 덮어쓰기), 마지막 칸이면 [조회] 버튼. */
    private fun moveToNext(index: Int) {
        if (index < fields.size - 1) {
            val next = fields[index + 1]
            next.requestFocus()
            next.selectAll()
        } else {
            val btn = btnQuery ?: return
            // 물리 엔터는 터치 모드를 풀어서 버튼이 바로 포커스를 받는다. 화면을 터치한 뒤 화면 키보드의
            // 완료로 넘어온 경우(터치 모드)는 버튼이 포커스를 못 받으므로, 그때만 잠깐 받을 수 있게 켠다.
            if (!btn.requestFocus()) {
                btn.isFocusableInTouchMode = true
                btn.requestFocus()
            }
        }
    }

    /** 위/아래 방향키: 입력칸 사이 이동(AREA·SECTION 줄 <-> 서가번호 줄). 나머지는 기본 동작. */
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.action == KeyEvent.ACTION_DOWN) {
            val cur = currentFocus
            when (event.keyCode) {
                KeyEvent.KEYCODE_DPAD_DOWN -> {
                    if (cur == etArea || cur == etSection) {
                        etShelfNo.requestFocus(); etShelfNo.selectAll(); return true
                    }
                }
                KeyEvent.KEYCODE_DPAD_UP -> {
                    if (cur == etShelfNo || cur == btnQuery) {
                        etArea.requestFocus(); etArea.selectAll(); return true
                    }
                }
            }
        }
        return super.dispatchKeyEvent(event)
    }

    private fun refreshList(fromButton: Boolean = false) {
        checked.clear()
        val area = etArea.text.toString().trim()
        val section = etSection.text.toString().trim()
        val shelfNo = etShelfNo.text.toString().trim()
        val locations = db.locationKeysByFilter(area, section, shelfNo, AppState.storeCode, AppState.surveyDate())
        shownLocations = locations
        shownFiltered = area.isNotEmpty() || section.isNotEmpty() || shelfNo.isNotEmpty()
        if (fromButton && shownFiltered && locations.isEmpty()) {
            Toast.makeText(this, "조건에 맞는 위치가 없습니다.", Toast.LENGTH_SHORT).show()
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
        val filtered = shownFiltered
        val targets = shownLocations
        if (filtered && targets.isEmpty()) {
            Toast.makeText(this, "삭제할 위치가 없습니다.", Toast.LENGTH_SHORT).show()
            return
        }
        Dialogs.confirm(
            activity = this,
            title = "확인",
            message = if (filtered) "조회된 ${targets.size}개 위치의 데이터를 전체 삭제할까요?"
                else "조회된 위치 데이터를 전체 삭제할까요?",
            positiveText = "예",
            negativeText = "아니요",
            focusPositive = false,
            onPositive = {
                // 입력칸을 모두 비우고 조회한 상태 = 예전 드롭다운의 "전체"와 같이 PDA 자료 전체 삭제.
                // 조건을 넣고 조회한 상태 = 지금 목록에 보이는 위치만 삭제.
                if (!filtered) {
                    db.deleteAll()
                } else {
                    db.runInTransaction { for (loc in targets) db.deleteLocation(loc) }
                }
                Toast.makeText(this, "삭제되었습니다.", Toast.LENGTH_SHORT).show()
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
                refreshList()
            }
        )
    }
}
