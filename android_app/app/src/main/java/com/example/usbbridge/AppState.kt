// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

/**
 * 화면 간에 공유되는 현재 작업 세션 정보 (앱이 켜져 있는 동안만 유지).
 * 실제 값들은 DbHelper(settings 테이블)에도 저장되어 앱 재시작 시 복원된다.
 *
 * ZZOINT의 currentLocation(1개 필드) 대신, KOINTBOOK은 AREA/SECTION/서가번호 3개를
 * 따로 들고 있다 - PC(KOINTBOOK_pc.py) 쪽 stock_counts 스키마가 이 3단을 각각의
 * 컬럼으로 쓰기 때문이다.
 */
object AppState {
    const val KIND_BOOK = "서적"
    const val KIND_STATIONERY = "문구"
    // 문구는 서가번호가 없어 고정값 X로 저장한다.
    const val STATIONERY_SHELF_NO = "X"

    /** [2026-10-15] AREA 번호로 서적/문구 구분(PC scope.py와 같은 기준):
     * 서적 10~19, 90~99 / 문구 20~29, 80~89. 그 밖의 AREA는 null(사용 불가). */
    const val AREA_RULE_TEXT = "서적 10~19, 90~99\n문구 20~29, 80~89"
    fun kindOfArea(area: String?): String? {
        val a = area?.trim()?.toIntOrNull() ?: return null
        return when (a) {
            in 10..19, in 90..99 -> KIND_BOOK
            in 20..29, in 80..89 -> KIND_STATIONERY
            else -> null
        }
    }

    val isStationery: Boolean get() = kindOfArea(currentArea) == KIND_STATIONERY

    var storeCode: String = "KYOBO01"
    var storeName: String = "교보문고 광화문점"
    var workerCode: String = ""
    var workerName: String = ""
    var ip: String = "10.10.10.10"

    var currentArea: String = ""
    var currentSection: String = ""
    var currentShelfNo: String = ""
    var currentDan: String = ""
    var currentYeol: String = ""
    var autoMode: Boolean = true   // true=자동(스캔 시 수량 1 자동입력), false=수동(스캔 후 수량 직접입력)

    // [2026-09-30] "PC,PDA 둘다 프로그램을 접속했다가 나갔다가 다시 접속하거나
    // 화면을 껐다 키면 점포코드, 날짜가 최초로 바뀌거나 다른거로 바뀌어서
    // 전송에 문제가 된다" - PDA쪽 원인: AppState는 앱 프로세스가 살아있는
    // 동안만 유지되는 순수 메모리 객체(object)였다. 화면을 꺼둔 사이
    // 안드로이드가 메모리 확보를 위해 백그라운드 프로세스를 죽였다가, 화면을
    // 다시 켤 때 "스플래시 화면부터"가 아니라 "마지막으로 보고 있던 화면"을
    // 바로 재생성하는 경우가 흔한데, 그러면 storeCode 등이 SplashActivity의
    // findFirstStore() 복원 코드를 거치지 않고 그냥 코드에 박힌 기본값
    // ("KYOBO01"/빈 위치값)으로 되돌아가 있었다 - 작업자 번호, 지금 작업
    // 중이던 AREA/SECTION/서가번호까지 전부 사라져서, 그 상태로 스캔을
    // 계속하면 엉뚱한(빈) 위치로 데이터가 저장될 위험까지 있었다.
    //
    // 이제 값이 "확정"되는 자리(위치입력 완료 -> persistLocation, 작업준비에서
    // 작업자 확정 -> persistWorker, 수동/자동 모드 전환 -> persistAutoMode)
    // 마다 DB의 app_settings 테이블에도 같이 저장해두고, 앱이 어느 화면으로든
    // 처음 뜰 때(BaseActivity.onCreate에서 호출하는 ensureRestored() 참고)
    // 그 값부터 복원한다. 프로세스당 한 번만 동작하므로, 정상적으로 스플래시를
    // 거쳐 들어왔을 때 값을 또 덮어쓰는 일은 없다.
    //
    // (조사일자(surveyDate)는 PDA에는 별도 선택 UI가 없이 "오늘 날짜"를
    // 그때그때 계산해서 쓰는 구조라 저장/복원 대상이 아니다 - 현장에서 실사는
    // 보통 당일 안에 끝나는 것을 전제로 한 의도된 동작이다.)
    private var restored = false

    /** 이 프로세스에서 처음으로 어떤 화면이든 열릴 때 한 번, DB에 저장해둔
     * 마지막 상태로 복원한다 (BaseActivity.onCreate에서 호출). */
    fun ensureRestored(context: android.content.Context) {
        if (restored) return
        restored = true
        val db = DbHelper.getInstance(context)
        // 점포코드/점포명은 별도 설정값을 새로 두지 않고, SplashActivity와
        // 동일하게 stores 테이블(점포마스터 - PDA 전송으로 받은 뒤 DB에 남아
        // 있음)에서 다시 찾는다(단일 출처 유지).
        db.findFirstStore()?.let { (code, name) ->
            storeCode = code
            storeName = name
        }
        workerCode = db.getSetting("app_worker_code", workerCode)
        workerName = db.getSetting("app_worker_name", workerName)
        currentArea = db.getSetting("app_current_area", currentArea)
        currentSection = db.getSetting("app_current_section", currentSection)
        currentShelfNo = db.getSetting("app_current_shelf_no", currentShelfNo)
        currentDan = db.getSetting("app_current_dan", currentDan)
        currentYeol = db.getSetting("app_current_yeol", currentYeol)
        autoMode = db.getSetting("app_auto_mode", if (autoMode) "1" else "0") == "1"
        // [2026-10-08] 조사일자 고정값 복원(아래 surveyDate() 설명 참고).
        pinnedSurveyDate = db.getSetting("app_survey_date", "")
    }

    /** 작업자 번호/이름이 확정되는 자리(WorkPrepActivity)에서 호출. */
    fun persistWorker(context: android.content.Context) {
        val db = DbHelper.getInstance(context)
        db.setSetting("app_worker_code", workerCode)
        db.setSetting("app_worker_name", workerName)
    }

    /** AREA/SECTION/서가번호/단/열이 확정/변경되는 자리(LocationInputActivity,
     * StockInputActivity)에서 호출. */
    fun persistLocation(context: android.content.Context) {
        val db = DbHelper.getInstance(context)
        db.setSetting("app_current_area", currentArea)
        db.setSetting("app_current_section", currentSection)
        db.setSetting("app_current_shelf_no", currentShelfNo)
        db.setSetting("app_current_dan", currentDan)
        db.setSetting("app_current_yeol", currentYeol)
    }

    /** 수동/자동 모드가 바뀌는 자리(StockInputActivity)에서 호출. */
    fun persistAutoMode(context: android.content.Context) {
        DbHelper.getInstance(context).setSetting("app_auto_mode", if (autoMode) "1" else "0")
    }

    /** 위치입력 화면에 보여줄 "AREA-SECTION-서가번호" 형태의 문자열. */
    fun currentLocationKey(): String = DbHelper.locationKey(currentArea, currentSection, currentShelfNo)

    /**
     * [2026-10-08] "10월 7일로 세팅하고 실사를 시작했는데 날짜가 8일로 넘어가니 앞선 데이터/
     * 로케이션/총수량이 조회가 안 된다" 수정. 예전엔 조사일자를 항상 "오늘"로 계산해서
     * 자정이 지나면 어제 스캔한 자료가 모든 조회 화면(DATA조회/위치 조회/재고수정)에서 사라졌다.
     * 이제 조사일자는 고정값(pinnedSurveyDate)이다:
     *  - PC에서 상품마스터를 PDA로 전송하면 PC의 조사일자가 같이 와서 그 값으로 고정된다.
     *  - 그 값이 없으면(옛 PC) 첫 스캔을 저장할 때의 날짜로 고정한다(pinSurveyDate).
     *  - PDA 자료를 전체삭제하면 고정이 풀린다.
     */
    var pinnedSurveyDate: String = ""

    fun surveyDate(): String {
        if (pinnedSurveyDate.isNotEmpty()) return pinnedSurveyDate
        val f = java.text.SimpleDateFormat("yyyyMMdd", java.util.Locale.getDefault())
        return f.format(java.util.Date())
    }

    /** 고정된 조사일자가 아직 없으면 지금(오늘) 날짜로 고정한다. 스캔 저장 직전에 부른다. */
    fun pinSurveyDate(context: android.content.Context) {
        if (pinnedSurveyDate.isNotEmpty()) return
        pinnedSurveyDate = surveyDate()
        DbHelper.getInstance(context).setSetting("app_survey_date", pinnedSurveyDate)
    }
}
