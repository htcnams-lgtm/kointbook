// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

/**
 * [2026-10-16] "서적 AREA에 문구 상품, 문구 AREA에 서적 상품을 스캔/입력하지 못하게" -
 * 스캔한(또는 손으로 친) 바코드가 서적인지 문구인지 상품마스터의 구분으로 판정한다.
 *
 * PC에서 상품마스터를 [서적 불러오기]/[문구 불러오기]로 따로 불러오면 상품마다 서적/문구 구분(kind)이
 * 붙고, PDA 전송 때 BOOK.db에 그 구분이 같이 실려 온다. 여기서는 그 구분만 본다.
 *  - 마스터에 없는 바코드(미등록)는 서적/문구를 알 수 없으므로 여기서 막지 않는다
 *    (기존 [미등록상품] 설정 허용/경고/차단이 그대로 처리한다).
 *  - 옛 PC가 보낸 마스터라 구분이 비어 있으면 마찬가지로 막지 않는다(마스터를 다시 전송하면 적용).
 *
 * AppState.kindOfArea(AREA)와 같은 값("서적"/"문구")을 돌려주므로 서로 그냥 비교하면 된다.
 */
object BarcodeKind {

    /** 마스터에 적힌 이 상품의 구분("서적" | "문구"). 마스터에 없거나 구분이 비어 있으면 null. */
    fun kindOf(info: DbHelper.BookInfo?): String? {
        val k = info?.kind ?: ""
        return if (k == AppState.KIND_BOOK || k == AppState.KIND_STATIONERY) k else null
    }

    /** 막을 때 화면에 보여줄 문구. headline은 큰 빨간 글씨, detail은 그 아래 설명. */
    class Block(val headline: String, val detail: String)

    fun blockText(area: String, areaKind: String, code: String, name: String, itemKind: String): Block {
        val sb = StringBuilder()
        sb.append("${areaKind} AREA($area)에는 ${itemKind} 상품을 입력할 수 없습니다.\n")
        sb.append("저장하지 않았습니다.\n\n")
        sb.append("바코드: $code\n")
        if (name.isNotEmpty()) sb.append("상품명: $name\n")
        sb.append("판정 근거: 상품마스터(${itemKind})")
        return Block("${itemKind} 상품입니다", sb.toString())
    }
}
