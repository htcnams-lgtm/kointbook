// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

/**
 * [2026-10-16] "서적 AREA에 문구 상품, 문구 AREA에 서적 상품을 스캔/입력하지 못하게" -
 * 스캔한(또는 손으로 친) 바코드가 서적인지 문구인지 판정한다.
 *
 * 판정 순서
 *  1) 상품마스터에 있으면 마스터의 구분(kind)을 그대로 쓴다(PC가 BOOK.db에 서적/문구 구분을 같이 보낸다).
 *  2) 마스터에 없거나(미등록), 옛 PC가 보낸 마스터라 구분이 비어 있으면 바코드 모양으로 판단한다:
 *     978/979(도서) 또는 977(잡지)로 시작하는 13자리, 또는 검사숫자가 맞는 ISBN-10이면 서적, 나머지는 문구.
 *     (한계: 마스터에 없는 문구 바코드가 우연히 978로 시작하면 서적으로 오판한다.)
 *
 * AppState.kindOfArea(AREA)와 같은 값("서적"/"문구")을 돌려주므로 서로 그냥 비교하면 된다.
 */
object BarcodeKind {

    /** kind = "서적" | "문구", fromMaster = 상품마스터 구분을 근거로 했는지(false면 바코드 모양 근거) */
    class Verdict(val kind: String, val fromMaster: Boolean)

    fun judge(info: DbHelper.BookInfo?, code: String): Verdict {
        val k = info?.kind ?: ""
        if (k == AppState.KIND_BOOK || k == AppState.KIND_STATIONERY) return Verdict(k, true)
        return Verdict(if (looksLikeBook(code)) AppState.KIND_BOOK else AppState.KIND_STATIONERY, false)
    }

    /** 바코드 모양만으로 서적(도서/잡지)인지. */
    fun looksLikeBook(raw: String): Boolean {
        val s = raw.trim().replace("-", "").replace(" ", "")
        if (s.length == 13 && s.all { it in '0'..'9' }) {
            return s.startsWith("978") || s.startsWith("979") || s.startsWith("977")
        }
        return s.length == 10 && isValidIsbn10(s)
    }

    private fun isValidIsbn10(s: String): Boolean {
        var sum = 0
        for (i in 0 until 10) {
            val ch = s[i]
            val v = when {
                ch in '0'..'9' -> ch - '0'
                i == 9 && (ch == 'X' || ch == 'x') -> 10
                else -> return false
            }
            sum += v * (10 - i)
        }
        return sum % 11 == 0
    }

    /** 막을 때 화면에 보여줄 문구. headline은 큰 빨간 글씨, detail은 그 아래 설명. */
    class Block(val headline: String, val detail: String)

    fun blockText(area: String, areaKind: String, code: String, name: String, v: Verdict): Block {
        val headline = "${v.kind} 상품입니다"
        val basis = if (v.fromMaster) {
            "판정 근거: 상품마스터(${v.kind})"
        } else if (v.kind == AppState.KIND_BOOK) {
            "판정 근거: 마스터에 없는 바코드 - 도서/잡지 바코드(978·979·977 또는 ISBN-10)라서 서적으로 판단"
        } else {
            "판정 근거: 마스터에 없는 바코드 - 도서/잡지 바코드(978·979·977)가 아니라서 문구로 판단"
        }
        val sb = StringBuilder()
        sb.append("${areaKind} AREA($area)에는 ${v.kind} 상품을 입력할 수 없습니다.\n")
        sb.append("저장하지 않았습니다.\n\n")
        sb.append("바코드: $code\n")
        if (name.isNotEmpty()) sb.append("상품명: $name\n")
        sb.append(basis)
        return Block(headline, sb.toString())
    }
}
