// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.app.Activity
import android.app.AlertDialog
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import androidx.core.content.ContextCompat

/**
 * 앱 전체에서 쓰는 확인/안내 팝업을 만드는 공용 헬퍼.
 *
 * AlertDialog의 setPositiveButton/setNegativeButton은 기종/테마에 따라
 * 버튼이 화면에 아예 안 보이거나 글자색이 배경과 겹쳐 안 보이는 문제가
 * 있었다. 그래서 버튼을 MaterialButton 기본 스타일에 맡기지 않고, 앱의
 * 다른 화면과 완전히 똑같은 button_classic/button_secondary 드로어블로
 * 직접 그려서 넣는다 - 색상과 포커스(초록 테두리) 표시가 항상 보장된다.
 */
object Dialogs {

    private fun Activity.dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    /**
     * 진행률 팝업의 조종기. 어느 스레드에서 update()/dismiss()를 불러도 된다
     * (내부에서 화면 스레드로 넘겨준다).
     */
    class ProgressHandle internal constructor(
        private val activity: Activity,
        private val dialog: AlertDialog,
        private val tvMessage: TextView,
        private val bar: ProgressBar,
        private val tvDetail: TextView
    ) {
        @Volatile private var lastPostNanos = 0L
        private val startMs = System.currentTimeMillis()

        private fun fmt(n: Int): String = java.text.NumberFormat.getIntegerInstance().format(n)

        /**
         * message: 위쪽 안내 문구 (null이면 그대로).
         * total <= 0 이면 전체를 모르는 상태라 빙글빙글 표시한다.
         * unit: 숫자 뒤에 붙일 단위 (기본 "건", 없애려면 "").
         * 너무 자주 부르면 화면이 버벅이므로, 문구가 바뀌거나 100%가 아니면
         * 0.08초 안에 다시 온 호출은 무시한다.
         */
        fun update(message: String? = null, done: Int = 0, total: Int = 0, unit: String = "건") {
            val now = System.nanoTime()
            val isLast = total > 0 && done >= total
            if (message == null && !isLast && now - lastPostNanos < 80_000_000L) return
            lastPostNanos = now
            activity.runOnUiThread {
                if (message != null) tvMessage.text = message
                val elapsedSec = (System.currentTimeMillis() - startMs) / 1000
                val elapsedText = if (elapsedSec >= 60) "${elapsedSec / 60}분 ${elapsedSec % 60}초" else "${elapsedSec}초"
                if (total > 0) {
                    bar.isIndeterminate = false
                    bar.max = 1000
                    bar.progress = (done.toLong() * 1000 / total).toInt().coerceIn(0, 1000)
                    val pct = done.toLong() * 100 / total
                    tvDetail.text = "${fmt(done)} / ${fmt(total)}$unit ($pct%)\n경과 $elapsedText"
                } else {
                    bar.isIndeterminate = true
                    tvDetail.text = if (done > 0) "${fmt(done)}$unit\n경과 $elapsedText" else "경과 $elapsedText"
                }
            }
        }

        fun dismiss() {
            activity.runOnUiThread {
                try {
                    if (dialog.isShowing) dialog.dismiss()
                } catch (_: Exception) {
                    // 화면이 이미 닫힌 경우 등 - 무시
                }
            }
        }
    }

    /**
     * 진행률 팝업을 띄운다 (뒤로가기로 못 닫음). 전송/수신처럼 오래 걸리는 작업을
     * 시작할 때 부르고, 끝나면 반드시 handle.dismiss()를 부른다.
     * 전송 도중 화면이 꺼져 와이파이가 끊기지 않도록 화면 켜짐을 유지한다.
     */
    fun progress(activity: Activity, title: String, message: String = "준비 중..."): ProgressHandle {
        val root = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(activity.dp(20), activity.dp(20), activity.dp(20), activity.dp(16))
        }
        root.addView(TextView(activity).apply {
            text = title
            textSize = 19f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, 0, 0, activity.dp(10))
        })
        val tvMessage = TextView(activity).apply {
            text = message
            textSize = 16f
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, 0, 0, activity.dp(12))
        }
        root.addView(tvMessage)

        val bar = ProgressBar(activity, null, android.R.attr.progressBarStyleHorizontal).apply {
            isIndeterminate = true
            max = 1000
            val accent = ColorStateList.valueOf(ContextCompat.getColor(activity, R.color.accent))
            progressTintList = accent
            indeterminateTintList = accent
        }
        root.addView(bar, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, activity.dp(10)))

        val tvDetail = TextView(activity).apply {
            textSize = 15f
            gravity = android.view.Gravity.CENTER
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, activity.dp(10), 0, 0)
        }
        root.addView(tvDetail)

        val dialog = AlertDialog.Builder(activity, R.style.KointBookDialog)
            .setView(root)
            .setCancelable(false)
            .create()
        dialog.show()
        dialog.window?.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        return ProgressHandle(activity, dialog, tvMessage, bar, tvDetail)
    }

    /** 예/아니오 같은 확인 팝업 */
    fun confirm(
        activity: Activity,
        title: String,
        message: String,
        positiveText: String = "예",
        negativeText: String = "아니요",
        focusPositive: Boolean = true,
        onPositive: () -> Unit,
        onNegative: (() -> Unit)? = null
    ) {
        val root = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(activity.dp(20), activity.dp(20), activity.dp(20), activity.dp(16))
        }
        root.addView(TextView(activity).apply {
            text = title
            textSize = 19f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, 0, 0, activity.dp(10))
        })
        root.addView(TextView(activity).apply {
            text = message
            textSize = 16f
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, 0, 0, activity.dp(18))
        })

        val btnNegative = Button(activity).apply {
            text = negativeText
            textSize = 17f
            setTextColor(ContextCompat.getColor(activity, R.color.danger_red))
            background = ContextCompat.getDrawable(activity, R.drawable.button_secondary)
        }
        val btnPositive = Button(activity).apply {
            text = positiveText
            textSize = 17f
            setTextColor(Color.parseColor("#FFFFFF"))
            background = ContextCompat.getDrawable(activity, R.drawable.button_classic)
        }
        val btnRow = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL }
        btnRow.addView(btnNegative, LinearLayout.LayoutParams(0, activity.dp(46), 1f).apply {
            marginEnd = activity.dp(8)
        })
        btnRow.addView(btnPositive, LinearLayout.LayoutParams(0, activity.dp(46), 1f))
        root.addView(btnRow)

        val dialog = AlertDialog.Builder(activity, R.style.KointBookDialog)
            .setView(root)
            .setCancelable(true)
            .create()

        btnPositive.setOnClickListener { dialog.dismiss(); onPositive() }
        btnNegative.setOnClickListener { dialog.dismiss(); onNegative?.invoke() }
        // 물리 뒤로가기(back)나 ESC로 닫아도 '아니오'를 누른 것과 동일하게 취급한다.
        dialog.setOnCancelListener { onNegative?.invoke() }
        // [2026-10-02] "확인 팝업은 기본 포커스(예: 아니요)에 초록색 테두리" - 지금 엔터로 눌릴 버튼에
        // 초록 테두리를 두르고, 좌/우 방향키로 바꾸며, 엔터는 그 버튼을 누른다. 터치로 쓰다가 팝업이 떠서
        // 안드로이드 포커스가 버튼에 안 잡히는 경우(터치 모드)에도 기본 버튼과 테두리가 그대로 동작한다.
        val negBg = btnNegative.background
        val posBg = btnPositive.background
        var current: Button = if (focusPositive) btnPositive else btnNegative
        fun paint() {
            val stroke = (3 * activity.resources.displayMetrics.density).toInt()
            for ((b, bg) in listOf(btnNegative to negBg, btnPositive to posBg)) {
                b.background = if (b === current && bg != null) {
                    // [2026-10-08] 테두리 모서리를 버튼 배경과 같은 둥글기로(예: 6dp / 아니요 버튼 14dp).
                    // 예전엔 모서리 설정이 없어 초록 테두리만 직각으로 보였다.
                    val radiusDp = if (b === btnNegative) 14f else 6f
                    val border = android.graphics.drawable.GradientDrawable().apply {
                        setColor(Color.TRANSPARENT)
                        cornerRadius = radiusDp * activity.resources.displayMetrics.density
                        setStroke(stroke, ContextCompat.getColor(activity, R.color.focus_green))
                    }
                    android.graphics.drawable.LayerDrawable(arrayOf(bg, border))
                } else bg
            }
        }
        for (b in listOf(btnNegative, btnPositive)) {
            b.setOnFocusChangeListener { _, hasFocus -> if (hasFocus) { current = b; paint() } }
        }
        var enterDownSeen = false
        dialog.setOnKeyListener { _, keyCode, event ->
            when (keyCode) {
                android.view.KeyEvent.KEYCODE_DPAD_LEFT, android.view.KeyEvent.KEYCODE_DPAD_RIGHT -> {
                    if (event.action == android.view.KeyEvent.ACTION_DOWN) {
                        current = if (keyCode == android.view.KeyEvent.KEYCODE_DPAD_LEFT) btnNegative else btnPositive
                        current.requestFocus()
                        paint()
                    }
                    true
                }
                android.view.KeyEvent.KEYCODE_ENTER, android.view.KeyEvent.KEYCODE_NUMPAD_ENTER,
                android.view.KeyEvent.KEYCODE_DPAD_CENTER -> {
                    // 팝업이 뜬 뒤에 누른 엔터만 처리한다(팝업을 띄운 엔터가 떼어지는 것은 무시).
                    if (event.action == android.view.KeyEvent.ACTION_DOWN) {
                        enterDownSeen = true
                    } else if (event.action == android.view.KeyEvent.ACTION_UP && enterDownSeen) {
                        enterDownSeen = false
                        current.performClick()
                    }
                    true
                }
                else -> false
            }
        }
        dialog.setOnShowListener {
            current.requestFocus()
            paint()
        }
        dialog.show()
    }

    /** 확인 버튼 하나짜리 안내 팝업.
     * [2026-09-30] "미전송확인 팝업창 속 글자,숫자크기 지금에 2사이즈 크게" -
     * 이 팝업만 메시지 글씨 크기를 따로 키울 수 있도록 messageTextSize를
     * 추가했다(기본값 14f는 그대로라 다른 info() 호출부는 영향 없음). */
    fun info(activity: Activity, title: String, message: String, buttonText: String = "확인", messageTextSize: Float = 16f) {
        val root = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(activity.dp(20), activity.dp(20), activity.dp(20), activity.dp(16))
        }
        root.addView(TextView(activity).apply {
            text = title
            textSize = 19f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, 0, 0, activity.dp(10))
        })
        root.addView(TextView(activity).apply {
            text = message
            textSize = messageTextSize
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, 0, 0, activity.dp(18))
        })

        val btnOk = Button(activity).apply {
            text = buttonText
            textSize = 17f
            setTextColor(Color.parseColor("#FFFFFF"))
            background = ContextCompat.getDrawable(activity, R.drawable.button_classic)
        }
        root.addView(btnOk, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, activity.dp(46)))

        val dialog = AlertDialog.Builder(activity, R.style.KointBookDialog)
            .setView(root)
            .setCancelable(true)
            .create()
        btnOk.setOnClickListener { dialog.dismiss() }
        dialog.setOnShowListener { btnOk.requestFocus() }
        dialog.show()
    }

    /**
     * [2026-10-16] 도서 AREA에 문구 상품(또는 문구 AREA에 도서 상품)을 입력하려 할 때 띄우는
     * 큰 빨간 경고창. 확인 버튼(물리 엔터)을 눌러야만 닫히고, 닫히기 전에는 뒤로가기/바깥 터치로도
     * 닫히지 않는다. 막 뜬 직후(0.6초)에는 스캐너가 이어서 보낸 엔터/연속 스캔으로 바로 닫히지 않게
     * 확인을 무시한다. 닫히면 onClosed를 부른다.
     */
    fun kindBlock(activity: Activity, headline: String, detail: String, onClosed: () -> Unit) {
        val root = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(activity.dp(14), activity.dp(14), activity.dp(14), activity.dp(14))
        }
        val banner = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            gravity = android.view.Gravity.CENTER
            setPadding(activity.dp(8), activity.dp(16), activity.dp(8), activity.dp(16))
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(Color.parseColor("#C62828"))
                cornerRadius = activity.dp(8).toFloat()
            }
        }
        banner.addView(TextView(activity).apply {
            text = headline
            textSize = 28f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(Color.parseColor("#FFFFFF"))
            gravity = android.view.Gravity.CENTER
        })
        banner.addView(TextView(activity).apply {
            text = "입력 금지"
            textSize = 20f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(Color.parseColor("#FFFFFF"))
            gravity = android.view.Gravity.CENTER
        })
        root.addView(banner, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = activity.dp(12) })
        root.addView(TextView(activity).apply {
            text = detail
            textSize = 16f
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, 0, 0, activity.dp(14))
        })

        val btnOk = Button(activity).apply {
            text = "확인"
            textSize = 17f
            setTextColor(Color.parseColor("#FFFFFF"))
            background = ContextCompat.getDrawable(activity, R.drawable.button_classic)
        }
        root.addView(btnOk, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, activity.dp(46)))

        val dialog = AlertDialog.Builder(activity, R.style.KointBookDialog)
            .setView(root)
            .setCancelable(false)
            .create()
        var shownAt = 0L
        btnOk.setOnClickListener {
            if (android.os.SystemClock.uptimeMillis() - shownAt < 600) return@setOnClickListener
            dialog.dismiss()
            onClosed()
        }
        // 팝업이 뜬 뒤에 누른 엔터만 처리한다(팝업을 띄운 엔터가 떼어지는 것은 무시).
        var enterDownSeen = false
        dialog.setOnKeyListener { _, keyCode, event ->
            when (keyCode) {
                android.view.KeyEvent.KEYCODE_ENTER, android.view.KeyEvent.KEYCODE_NUMPAD_ENTER,
                android.view.KeyEvent.KEYCODE_DPAD_CENTER -> {
                    if (event.action == android.view.KeyEvent.ACTION_DOWN) {
                        enterDownSeen = true
                    } else if (event.action == android.view.KeyEvent.ACTION_UP && enterDownSeen) {
                        enterDownSeen = false
                        btnOk.performClick()
                    }
                    true
                }
                else -> false
            }
        }
        dialog.setOnShowListener {
            shownAt = android.os.SystemClock.uptimeMillis()
            btnOk.requestFocus()
        }
        dialog.show()
    }

    /** 입력창(비밀번호, 수량 등)이 있는 저장/취소 팝업 */
    fun prompt(
        activity: Activity,
        title: String,
        inputView: View,
        positiveText: String = "저장",
        negativeText: String = "취소",
        onPositive: () -> Unit
    ) {
        val root = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(activity.dp(20), activity.dp(20), activity.dp(20), activity.dp(16))
        }
        root.addView(TextView(activity).apply {
            text = title
            textSize = 19f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, 0, 0, activity.dp(14))
        })
        (inputView.parent as? LinearLayout)?.removeView(inputView)
        root.addView(inputView, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = activity.dp(18) })

        val btnNegative = Button(activity).apply {
            text = negativeText
            textSize = 17f
            setTextColor(ContextCompat.getColor(activity, R.color.danger_red))
            background = ContextCompat.getDrawable(activity, R.drawable.button_secondary)
        }
        val btnPositive = Button(activity).apply {
            text = positiveText
            textSize = 17f
            setTextColor(Color.parseColor("#FFFFFF"))
            background = ContextCompat.getDrawable(activity, R.drawable.button_classic)
        }
        val btnRow = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL }
        btnRow.addView(btnNegative, LinearLayout.LayoutParams(0, activity.dp(46), 1f).apply {
            marginEnd = activity.dp(8)
        })
        btnRow.addView(btnPositive, LinearLayout.LayoutParams(0, activity.dp(46), 1f))
        root.addView(btnRow)

        val dialog = AlertDialog.Builder(activity, R.style.KointBookDialog)
            .setView(root)
            .setCancelable(true)
            .create()

        btnPositive.setOnClickListener { dialog.dismiss(); onPositive() }
        btnNegative.setOnClickListener { dialog.dismiss() }
        dialog.setOnShowListener { inputView.requestFocus() }
        dialog.show()
    }

    /** 목록의 한 줄을 길게 누르거나 선택했을 때: 수량 수정 또는 삭제 */
    fun editOrDeleteRow(
        activity: Activity,
        title: String,
        message: String,
        initialQty: String,
        onSave: (String) -> Unit,
        onDelete: () -> Unit
    ) {
        val root = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(activity.dp(20), activity.dp(20), activity.dp(20), activity.dp(16))
        }
        root.addView(TextView(activity).apply {
            text = title
            textSize = 19f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, 0, 0, activity.dp(10))
        })
        root.addView(TextView(activity).apply {
            text = message
            textSize = 15f
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, 0, 0, activity.dp(12))
        })

        val qtyInput = android.widget.EditText(activity).apply {
            setText(initialQty)
            inputType = android.text.InputType.TYPE_CLASS_NUMBER
            textSize = 18f
            gravity = android.view.Gravity.CENTER
            setTextColor(Color.parseColor("#000000"))
            background = ContextCompat.getDrawable(activity, R.drawable.edit_classic)
            setPadding(activity.dp(8), activity.dp(8), activity.dp(8), activity.dp(8))
        }
        root.addView(qtyInput, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = activity.dp(16) })

        val btnDelete = Button(activity).apply {
            text = "삭제"
            textSize = 17f
            setTextColor(Color.parseColor("#FFFFFF"))
            background = ContextCompat.getDrawable(activity, R.drawable.button_danger)
        }
        val btnSave = Button(activity).apply {
            text = "저장"
            textSize = 17f
            setTextColor(Color.parseColor("#FFFFFF"))
            background = ContextCompat.getDrawable(activity, R.drawable.button_classic)
        }
        val btnRow = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL }
        btnRow.addView(btnDelete, LinearLayout.LayoutParams(0, activity.dp(46), 1f).apply {
            marginEnd = activity.dp(8)
        })
        btnRow.addView(btnSave, LinearLayout.LayoutParams(0, activity.dp(46), 1f))
        root.addView(btnRow)

        val dialog = AlertDialog.Builder(activity, R.style.KointBookDialog)
            .setView(root)
            .setCancelable(true)
            .create()

        btnSave.setOnClickListener {
            dialog.dismiss()
            onSave(qtyInput.text.toString())
        }
        btnDelete.setOnClickListener {
            dialog.dismiss()
            onDelete()
        }
        dialog.setOnShowListener {
            // requestFocus()를 다이얼로그가 뜨자마자 바로 부르면(레이아웃이
            // 아직 안 끝나 있어) 가끔 씹혀서 [삭제] 버튼에 포커스가 가거나,
            // 포커스는 가더라도 커서만 값 맨 앞에 놓이고 전체 선택은 안 되는
            // 문제가 있었다. post로 한 박자 늦춰서 레이아웃이 끝난 뒤에
            // 포커스를 주고, selectAll()로 기존 값을 전체 선택해둬서 -
            // 숫자를 바로 입력하면 그 값으로 통째로 바뀌게 한다(수정 팝업의
            // 일반적인 동작과 같다).
            qtyInput.post {
                qtyInput.requestFocus()
                qtyInput.selectAll()
            }
        }
        dialog.show()
    }

    /** 여러 선택지 중 하나를 목록에서 고르게 하는 범용 팝업.
     * (ZZOINT에서는 "같은 바코드에 자사코드가 여러 개"인 경우에 썼지만, 도서는
     * ISBN이 1:1이라 KOINTBOOK 화면에서는 현재 사용하지 않는다 - 다른 선택
     * 팝업이 필요할 때 재사용할 수 있게 남겨둔다.) */
    fun choose(
        activity: Activity,
        title: String,
        message: String,
        options: List<String>,
        onSelected: (Int) -> Unit,
        onCancel: (() -> Unit)? = null
    ) {
        val root = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(activity.dp(20), activity.dp(20), activity.dp(20), activity.dp(16))
        }
        root.addView(TextView(activity).apply {
            text = title
            textSize = 19f
            setTypeface(typeface, Typeface.BOLD)
            setTextColor(Color.parseColor("#000000"))
            setPadding(0, 0, 0, activity.dp(10))
        })
        if (message.isNotEmpty()) {
            root.addView(TextView(activity).apply {
                text = message
                textSize = 15f
                setTextColor(Color.parseColor("#000000"))
                setPadding(0, 0, 0, activity.dp(12))
            })
        }

        val scroll = android.widget.ScrollView(activity)
        val listContainer = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL }
        scroll.addView(listContainer)
        root.addView(
            scroll,
            LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, activity.dp(280)).apply {
                bottomMargin = activity.dp(14)
            }
        )

        val btnCancel = Button(activity).apply {
            text = "취소"
            textSize = 17f
            setTextColor(ContextCompat.getColor(activity, R.color.danger_red))
            background = ContextCompat.getDrawable(activity, R.drawable.button_secondary)
        }
        root.addView(btnCancel, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, activity.dp(46)))

        val dialog = AlertDialog.Builder(activity, R.style.KointBookDialog)
            .setView(root)
            .setCancelable(true)
            .create()

        for ((index, opt) in options.withIndex()) {
            val optBtn = Button(activity).apply {
                text = opt
                textSize = 17f
                isAllCaps = false
                setTextColor(Color.parseColor("#FFFFFF"))
                background = ContextCompat.getDrawable(activity, R.drawable.button_classic)
            }
            listContainer.addView(
                optBtn,
                LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, activity.dp(50)).apply {
                    bottomMargin = activity.dp(8)
                }
            )
            optBtn.setOnClickListener {
                dialog.dismiss()
                onSelected(index)
            }
        }

        btnCancel.setOnClickListener { dialog.dismiss(); onCancel?.invoke() }
        dialog.setOnCancelListener { onCancel?.invoke() }
        dialog.setOnShowListener { listContainer.getChildAt(0)?.requestFocus() }
        dialog.show()
    }
}
