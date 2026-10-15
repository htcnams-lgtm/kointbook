// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Bundle
import android.text.InputFilter
import android.view.KeyEvent
import android.view.inputmethod.EditorInfo
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast

/**
 * 위치입력화면: AREA / SECTION / 서가번호 입력 -> 재고입력화면으로 이동.
 *
 * [2026-09-23 정정] 예전에는 "1-5-12"처럼 하이픈으로 이어붙인 문자열 하나를
 * 한 칸에 입력받아 DbHelper.splitLocationKey()로 쪼갰는데, 실제 작업
 * 흐름과 맞지 않아 캡처처럼 세로로 3칸(1.AREA 2.SECTION 3.서가번호)으로
 * 나눴다. 칸마다 독립적으로 값을 받는다:
 *   - 물리 스캔버튼: 지금 포커스가 있는 칸(activeFieldIndex)에 스캔값이
 *     그대로 들어가고, 그 칸이 확정되어 자동으로 다음 칸으로 넘어간다.
 *   - 키보드/엔터: 값을 입력하고 엔터(또는 IME의 "다음")를 누르면 같은
 *     방식으로 다음 칸으로 넘어간다.
 * 마지막 칸(서가번호)에서 확정하면 재고입력화면으로 넘어간다.
 */
class LocationInputActivity : BaseActivity() {

    companion object {
        private const val SCAN_ACTION = "nlscan.action.SCANNER_RESULT"
        private val FIELD_NAMES = arrayOf("AREA", "SECTION", "서가번호")
        // [2026-09-23 재정정] AREA 2자리 / SECTION 3자리 / 서가번호 11자리
        // 자릿수 제한(서가번호는 PC/PDA 모두 11자리). activity_location_input.xml의
        // android:maxLength도 같은 값으로 맞춰서 키보드 입력을 막고, 여기서는
        // 물리 스캔값처럼 maxLength를 안 타는 경로까지 한 번 더 잘라서 확실히
        // 지킨다.
        private val MAX_LENGTHS = intArrayOf(2, 3, 11)
        // [2026-09-23 재재정정] AREA는 정확히 2자리, SECTION은 정확히 3자리가
        // 아니면 다음 칸으로 못 넘어가게 막는다(1자리나 3자리처럼 자릿수가
        // 안 맞으면 확정 자체가 안 됨). 서가번호는 정해진 자릿수가 없어 위
        // MAX_LENGTHS(11자리)만 지키면 되므로 -1(자릿수 검사 없음)로 둔다.
        private val EXACT_LENGTHS = intArrayOf(2, 3, -1)

        // 경고 팝업 문구용 조사 ("AREA가 / SECTION이", "AREA를 / SECTION을")
        private val NAME_SUBJECT = arrayOf("AREA가", "SECTION이", "서가번호가")
        private val NAME_OBJECT = arrayOf("AREA를", "SECTION을", "서가번호를")
    }

    // AREA/SECTION/서가번호 칸마다, 자릿수 제한 때문에 잘려 나간 글자 수와 그 글자들
    // (스캔된 전체 값을 팝업에 보여주고, 상품바코드 의심 여부를 판단하는 데 쓴다)
    private val overflowCount = IntArray(3)
    private val overflowText = Array(3) { StringBuilder() }

    // [2026-10-02] 칸마다 "스캐너가 키보드처럼 쳐 넣은 입력"을 알아내는 감지기(ScanInputDetector.kt).
    // 물리 스캔버튼 값이 엔터 없이 들어와도 스캔으로 처리하고, 사람이 손으로 누른 입력과 구분한다.
    private val detectors = Array(3) { i -> ScanInputDetector(onScanned = { onKeyboardScan(i) }, minChars = 2) }

    private fun clearOverflow(index: Int) {
        overflowCount[index] = 0
        overflowText[index].setLength(0)
    }

    /** 프로그램이 칸에 값을 넣을 때 - 스캔 감지/잘림 계산에 섞이지 않게 한다. */
    private fun setFieldText(index: Int, text: String) {
        detectors[index].suppressed = true
        fields[index].setText(text)
        detectors[index].suppressed = false
        detectors[index].cancel()
        clearOverflow(index)
    }

    private lateinit var db: DbHelper
    private lateinit var etArea: EditText
    private lateinit var etSection: EditText
    private lateinit var etShelfNo: EditText
    private lateinit var fields: List<EditText>

    // 물리 스캔버튼은 "지금 어느 칸을 채워야 하는지"를 모르고 그냥 한
    // 건만 쏴주므로, 마지막으로 포커스를 받은 칸의 인덱스를 기억해뒀다가
    // 그 칸에 스캔값을 채운다.
    private var activeFieldIndex = 0

    // [2026-09-23] 재고입력화면에서 뒤로가기로 이 화면에 다시 돌아온 경우를
    // 구분하기 위한 플래그 - onCreate() 직후의 첫 onResume()에서는 기본
    // 포커스(첫 칸)를 그대로 두고, 그 이후(재고입력화면 등에서 돌아왔을 때)의
    // onResume()에서만 서가번호를 전체 선택해서 바로 고쳐 쓸 수 있게 한다.
    private var enteredOnce = false

    private val scanReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val scanned = intent.getStringExtra("SCAN_BARCODE1")
            val state = intent.getStringExtra("SCAN_STATE")
            if (state == "ok" && !scanned.isNullOrEmpty()) {
                runOnUiThread {
                    val limit = MAX_LENGTHS[activeFieldIndex]
                    // [2026-10-01] AREA(2자리)/SECTION(3자리) 칸에 그보다 긴 값이 스캔되면 앞자리만
                    // 잘라 넣지 않고(예: 상품바코드 978...을 찍으면 "97"이 AREA로 들어가 버림),
                    // 상품바코드로 의심된다는 팝업 + ZZOINT 미등록 스캔과 같은 소리/진동으로 알린다.
                    val exact = EXACT_LENGTHS[activeFieldIndex]
                    if (exact > 0 && scanned.trim().length > exact) {
                        warnSuspectBarcode(activeFieldIndex, scanned.trim(), keepValue = true)
                        return@runOnUiThread
                    }
                    val trimmed = if (scanned.length > limit) scanned.substring(0, limit) else scanned
                    setFieldText(activeFieldIndex, trimmed)
                    confirmField(activeFieldIndex, fromScan = true)
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_location_input)
        db = DbHelper.getInstance(this)

        findViewById<TextView>(R.id.tvTitleBarText).text = "KOINTBOOK [위치입력]"

        etArea = findViewById(R.id.etArea)
        etSection = findViewById(R.id.etSection)
        etShelfNo = findViewById(R.id.etShelfNo)
        fields = listOf(etArea, etSection, etShelfNo)

        for ((index, field) in fields.withIndex()) {
            // 자릿수 제한은 XML(maxLength) 대신 여기서 건다 - 잘라낸 글자 수를 세어 두었다가
            // 상품바코드로 의심되는 입력(키보드 방식 스캔)을 알아내기 위해서다. 입력 결과는 예전과 같다.
            val max = MAX_LENGTHS[index]
            field.filters = arrayOf(InputFilter { source, start, end, dest, dstart, dend ->
                val keep = max - (dest.length - (dend - dstart))
                val incoming = end - start
                if (!detectors[index].suppressed) detectors[index].noteInput(incoming)
                if (incoming <= keep) {
                    null
                } else {
                    val kept = maxOf(keep, 0)
                    overflowCount[index] += incoming - kept
                    if (!detectors[index].suppressed) overflowText[index].append(source.subSequence(start + kept, end))
                    if (keep <= 0) "" else source.subSequence(start, start + keep)
                }
            })
            field.setOnFocusChangeListener { _, hasFocus ->
                if (hasFocus) {
                    activeFieldIndex = index
                    clearOverflow(index)
                }
            }
            field.setOnEditorActionListener { _, actionId, event ->
                if (actionId == EditorInfo.IME_ACTION_NEXT || actionId == EditorInfo.IME_ACTION_DONE ||
                    (event != null && event.keyCode == KeyEvent.KEYCODE_ENTER && event.action == KeyEvent.ACTION_DOWN)
                ) {
                    confirmField(index)
                    true
                } else false
            }
            // [2026-09-23 4차 정정] android:nextFocusUp/Down만으로는 일부
            // 기기(터치모드에서 방향키 포커스 이동이 꺼져 있는 PDA 등)에서
            // 위/아래 방향키로 칸 이동이 안 되는 경우가 있어, 여기서 직접
            // 키 이벤트를 받아 확실하게 다음/이전 칸으로 옮긴다(이동한 칸의
            // 값은 바로 고쳐 쓸 수 있게 전체 선택까지 해준다).
            field.setOnKeyListener { _, keyCode, keyEvent ->
                if (keyEvent.action != KeyEvent.ACTION_DOWN) return@setOnKeyListener false
                when (keyCode) {
                    KeyEvent.KEYCODE_DPAD_DOWN -> {
                        if (index < fields.size - 1) {
                            fields[index + 1].requestFocus()
                            fields[index + 1].selectAll()
                        }
                        true
                    }
                    KeyEvent.KEYCODE_DPAD_UP -> {
                        if (index > 0) {
                            fields[index - 1].requestFocus()
                            fields[index - 1].selectAll()
                        }
                        true
                    }
                    else -> false
                }
            }
        }

        setFieldText(0, AppState.currentArea)
        setFieldText(1, AppState.currentSection)
        setFieldText(2, AppState.currentShelfNo)

        findViewById<android.widget.Button>(R.id.btnMaxQty).setOnClickListener {
            showMaxQtyDialog()
        }
    }

    override fun onResume() {
        super.onResume()
        registerScanReceiverCompat(scanReceiver, IntentFilter(SCAN_ACTION))
        if (enteredOnce) {
            // [2026-10-01] 재고입력화면 등에서 뒤로가기로 돌아온 경우 - 서가번호가 아니라
            // SECTION 칸에 포커스를 주고 값을 전체 선택해 둔다(바로 다음 SECTION을 스캔/입력).
            // 화면이 다시 그려진 뒤에 선택해야 전체 선택이 풀리지 않아서 post로 한 번 더 건다.
            etSection.requestFocus()
            etSection.selectAll()
            etSection.post {
                etSection.requestFocus()
                etSection.selectAll()
            }
        } else {
            // [2026-09-23 정정] 처음 이 화면에 들어왔을 때도 AREA 칸에 이전
            // 값이 그대로 남아있을 수 있는데, 그 값을 지우지 않고는 새로
            // 입력할 수 없었다 - AREA 칸에 포커스를 주고 값을 전체 선택해서
            // (값이 있어도) 바로 덮어쓸 수 있는 상태를 기본값으로 만든다.
            etArea.requestFocus()
            etArea.selectAll()
        }
        enteredOnce = true
    }

    override fun onPause() {
        super.onPause()
        detectors.forEach { it.cancel() }
        try { unregisterReceiver(scanReceiver) } catch (_: Exception) {}
    }

    /** index번 칸을 확정한다(스캔 또는 엔터) - 비어있으면 그 칸에 머물게
     * 안내하고, 값이 있으면 다음 칸으로 넘어가거나(마지막 칸이면) 위치입력을
     * 완료 처리한다. */
    private fun confirmField(index: Int, fromScan: Boolean = false) {
        // [2026-10-02] 스캐너가 키보드처럼 값을 쳐 넣고 엔터까지 붙인 경우: AREA/SECTION 자릿수보다
        // 긴 값이었으면(잘려 나간 글자가 있음) 잘린 값으로 넘어가지 않고 상품바코드 의심 팝업.
        // 사람이 손으로 한 자리 더 누른 경우(스캔이 아님)는 예전처럼 자릿수만큼 잘려 들어가기만 한다.
        val scannedBurst = detectors[index].isBurst
        detectors[index].cancel()
        // [2026-10-06] "서가번호 물리스캔후 바로 재고입력화면으로 넘어가지않고 물리 엔터키 눌러야
        // 재고입력화면으로" - 마지막 칸(서가번호)은 스캔으로 값만 채우고 멈춘다. 스캐너가 값 뒤에
        // 자동으로 붙이는 엔터(scannedBurst)도 무시하고, 사람이 직접 누른 물리 엔터만 이동시킨다.
        val isLast = index == fields.size - 1
        if (isLast && (fromScan || scannedBurst)) {
            clearOverflow(index)
            fields[index].requestFocus()
            fields[index].selectAll()
            return
        }
        if (EXACT_LENGTHS[index] > 0 && overflowCount[index] > 0 && scannedBurst) {
            val full = fields[index].text.toString() + overflowText[index].toString()
            warnSuspectBarcode(index, full.trim(), keepValue = false)
            return
        }
        clearOverflow(index)
        val text = fields[index].text.toString().trim()
        if (text.isEmpty()) {
            Toast.makeText(this, "${FIELD_NAMES[index]}를 입력하세요.", Toast.LENGTH_SHORT).show()
            return
        }
        val exact = EXACT_LENGTHS[index]
        if (exact > 0 && text.length != exact) {
            Toast.makeText(this, "${FIELD_NAMES[index]}는 ${exact}자리로 입력하세요.", Toast.LENGTH_SHORT).show()
            fields[index].selectAll()
            return
        }
        if (index < fields.size - 1) {
            val next = fields[index + 1]
            next.requestFocus()
            next.selectAll()
        } else {
            enterLocation()
        }
    }

    /** 스캐너가 키보드처럼(엔터 없이) 값을 다 넣고 멈췄을 때: 엔터를 친 것과 같이 처리한다. */
    private fun onKeyboardScan(index: Int) {
        if (EXACT_LENGTHS[index] > 0 && overflowCount[index] > 0) {
            val full = fields[index].text.toString() + overflowText[index].toString()
            warnSuspectBarcode(index, full.trim(), keepValue = false)
            return
        }
        clearOverflow(index)
        confirmField(index, fromScan = true)
    }

    /** [2026-10-02] AREA(2자리)/SECTION(3자리) 칸에 그보다 긴 값이 스캔됐을 때:
     * ZZOINT 미등록 상품 스캔과 같은 소리/진동 + 간단한 경고 팝업.
     * keepValue=true(물리 스캔 신호로 받은 경우): 칸에 아무것도 넣지 않았으므로 원래 값을 두고 전체 선택.
     * keepValue=false(키보드처럼 들어온 경우): 앞자리만 잘려 들어간 값이라 비우고 다시 입력받는다. */
    private fun warnSuspectBarcode(index: Int, scanned: String, keepValue: Boolean) {
        SoundUtil.zzointWarning(this)
        if (!keepValue) setFieldText(index, "") else clearOverflow(index)
        val field = fields[index]
        field.requestFocus()
        field.selectAll()
        Dialogs.info(
            activity = this,
            title = "경고",
            message = "${NAME_SUBJECT[index]} ${EXACT_LENGTHS[index]}자리보다 긴 값이 스캔됨.\n" +
                "상품바코드로 의심됨.\n" +
                "${NAME_OBJECT[index]} 다시 입력.\n" +
                "스캔값: $scanned"
        )
    }

    private fun enterLocation() {
        val area = etArea.text.toString().trim()
        val section = etSection.text.toString().trim()
        val shelfNo = etShelfNo.text.toString().trim()
        if (area.isEmpty() || section.isEmpty() || shelfNo.isEmpty()) {
            Toast.makeText(this, "AREA/SECTION/서가번호를 모두 입력하세요.", Toast.LENGTH_SHORT).show()
            when {
                area.isEmpty() -> etArea.requestFocus()
                section.isEmpty() -> etSection.requestFocus()
                else -> etShelfNo.requestFocus()
            }
            return
        }
        // confirmField()에서 이미 확인하지만, 위쪽 칸을 나중에 다시 고쳐서
        // 자릿수가 안 맞는 상태로 남아있을 수도 있어 한 번 더 확인한다.
        if (area.length != 2) {
            Toast.makeText(this, "AREA는 2자리로 입력하세요.", Toast.LENGTH_SHORT).show()
            etArea.requestFocus()
            etArea.selectAll()
            return
        }
        if (section.length != 3) {
            Toast.makeText(this, "SECTION은 3자리로 입력하세요.", Toast.LENGTH_SHORT).show()
            etSection.requestFocus()
            etSection.selectAll()
            return
        }
        AppState.currentArea = area
        AppState.currentSection = section
        AppState.currentShelfNo = shelfNo
        AppState.currentDan = "1"
        AppState.currentYeol = "1"
        // [2026-09-30] 화면이 꺼진 사이 프로세스가 죽었다 살아나도 지금 작업
        // 중이던 위치를 잃지 않도록 DB에도 같이 저장한다(AppState.kt 참고).
        AppState.persistLocation(this)
        startActivity(Intent(this, StockInputActivity::class.java))
        // 화면이 넘어갈 때의 기본 애니메이션(약 0.3초)을 없애서 재고입력 화면이 바로 뜨게 한다.
        @Suppress("DEPRECATION")
        overridePendingTransition(0, 0)
    }

    private fun showMaxQtyDialog() {
        val input = EditText(this)
        input.hint = "최대 수량 (예: 999)"
        input.setHintTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.text_secondary))
        input.setTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.text_primary))
        input.inputType = android.text.InputType.TYPE_CLASS_NUMBER
        input.setText(db.getSetting("max_qty", ""))

        Dialogs.prompt(
            activity = this,
            title = "Max수량설정",
            inputView = input,
            positiveText = "저장",
            negativeText = "취소",
            onPositive = {
                db.setSetting("max_qty", input.text.toString())
                Toast.makeText(this, "저장되었습니다.", Toast.LENGTH_SHORT).show()
            }
        )
    }
}
