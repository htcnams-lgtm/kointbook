// Copyright (c) 2026 namsman. All rights reserved.
// KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.

package com.example.usbbridge

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/**
 * KOINTBOOK PDA 앱의 로컬 데이터베이스.
 *
 * ZZOINT(일반 매장용)의 DbHelper를 기반으로, 서점(도서) 재고실사에 맞게 스키마를
 * 다시 짰다. 가장 큰 차이는 위치 체계다 - ZZOINT는 "로케이션(1칸) + 단 + 열"
 * 3단이었지만, KOINTBOOK은 KYOBO/RBSKOREA 실사 화면 캡처에 나온 대로
 * "AREA + SECTION + 서가번호 + 단 + 열" 5단을 쓴다. 이 앱에서는 AREA/SECTION/
 * 서가번호 3개를 하나의 "위치입력" 화면에서 "1-5-12" 같은 하이픈 구분 문자열로
 * 한 번에 입력받는다(자세한 이유는 LocationInputActivity 주석 참고).
 *
 * - settings   : IP, 비밀번호, Max수량 등 환경설정 값 (key-value)
 * - stores     : 점포마스터 (PC에서 받거나 임시로 등록)
 * - workers    : 작업자마스터
 * - books      : 상품(도서)마스터 - ISBN 기준. 비어 있으면 "모든 ISBN을 그대로
 *   등록 허용"하는 것으로 취급한다(전체 바코드 스캔 허용과 동일한 개념).
 * - stock_counts : 실제 스캔되어 쌓인 재고실사 데이터 (자동 저장됨)
 *
 * PC로의 "전송"은 실시간 통신이 아니라, stock_counts 내용을 그대로
 * STOCK.db 라는 별도의 SQLite 파일(테이블명 stock_data)로 내보내서(export)
 * 외부 저장소에 두고, PC가 USB(adb pull)로 그 파일을 가져가는 방식이다.
 * ZZOINT에 있던 Firebase(무선) 동기화 관련 컬럼/기능(firestore_synced 등)은
 * KOINTBOOK에는 없다(USB adb 전용으로 단순화).
 */
class DbHelper private constructor(context: Context) : SQLiteOpenHelper(context.applicationContext, DB_NAME, null, DB_VERSION) {

    companion object {
        const val DB_NAME = "KOINTBOOK.db"
        const val DB_VERSION = 1

        @Volatile
        private var instance: DbHelper? = null

        /**
         * 화면마다 DbHelper(this)를 새로 만들면, 같은 DB 파일에 여러 연결이
         * 동시에 열리면서 "database is locked" 충돌이 생겨 앱을 배경으로
         * 보냈다가 돌아올 때 멈추거나 응답 없음이 뜨는 원인이 될 수 있다.
         * 앱 전체에서 이 하나의 인스턴스만 공유해서 그 문제를 없앤다.
         */
        fun getInstance(context: Context): DbHelper {
            return instance ?: synchronized(this) {
                instance ?: run {
                    migrateOldDbFileIfNeeded(context)
                    DbHelper(context).also { instance = it }
                }
            }
        }

        /** [2026-09-23 정정] 앱 이름이 KYOINT -> KOINT-BOOK -> KOINTBOOK
         * 순서로 바뀌면서 로컬 DB 파일명도 같이 바뀌었다. 새 파일(KOINTBOOK.db)
         * 이 아직 없고 예전 이름(KYOINT.db 또는 KOINT-BOOK.db)의 파일이
         * 있으면(기존 개발/테스트 자료), 그 파일을 그대로 새 이름으로 옮겨서
         * 기존 자료(점포/작업자/상품마스터, 실사 데이터)가 사라지지 않게 한다. */
        private fun migrateOldDbFileIfNeeded(context: Context) {
            try {
                val newDb = context.getDatabasePath(DB_NAME)
                if (newDb.exists()) return
                for (oldName in listOf("KYOINT.db", "KOINT-BOOK.db")) {
                    val oldDb = context.getDatabasePath(oldName)
                    if (oldDb.exists()) {
                        oldDb.renameTo(newDb)
                        return
                    }
                }
            } catch (_: Exception) {
                // 마이그레이션 실패해도 앱은 새 DB로 정상 시작해야 한다.
            }
        }

        /** AREA/SECTION/서가번호 3개를 화면·DB 양쪽에서 똑같은 규칙으로 합친다. */
        fun locationKey(area: String, section: String, shelfNo: String): String =
            "$area-$section-$shelfNo"

        /**
         * locationKey()의 역함수. "1-5-12" -> ("1","5","12"). 값 자체에 "-"가
         *들어가는 경우는 지원하지 않는다(AREA/SECTION/서가번호 이름 규칙상 보통
         * 숫자나 짧은 코드라 문제없다고 가정했다 - 실제로 "-"가 들어간 값을
         * 쓴다면 이 부분을 다른 구분자로 바꿔야 한다).
         */
        fun splitLocationKey(key: String): Triple<String, String, String> {
            val parts = key.split("-", limit = 3)
            return Triple(
                parts.getOrElse(0) { "" },
                parts.getOrElse(1) { "" },
                parts.getOrElse(2) { "" }
            )
        }
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """.trimIndent()
        )
        db.execSQL(
            """
            CREATE TABLE stores (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """.trimIndent()
        )
        db.execSQL(
            """
            CREATE TABLE workers (
                code TEXT PRIMARY KEY,
                name TEXT
            )
            """.trimIndent()
        )
        db.execSQL(
            """
            CREATE TABLE books (
                store_code TEXT,
                isbn TEXT,
                book_name TEXT,
                category TEXT,
                publisher TEXT,
                PRIMARY KEY (store_code, isbn)
            )
            """.trimIndent()
        )
        db.execSQL(
            """
            CREATE TABLE stock_counts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_code TEXT,
                store_name TEXT,
                survey_date TEXT,
                area TEXT,
                section TEXT,
                shelf_no TEXT,
                dan TEXT,
                yeol TEXT,
                isbn TEXT,
                book_name TEXT,
                qty INTEGER,
                worker_code TEXT,
                worker_name TEXT,
                scanned_at TEXT
            )
            """.trimIndent()
        )

        // 데모용 샘플 작업자 (실제 운영에서는 PC 작업자마스터에서 받아오는 형태로 확장 가능)
        db.execSQL("INSERT INTO workers(code, name) VALUES ('1', '이정현')")
        db.execSQL("INSERT INTO workers(code, name) VALUES ('2', '박고을')")
        db.execSQL("INSERT INTO workers(code, name) VALUES ('3', '오성택')")
    }

    /**
     * DB를 열 때마다 확인해서 필요한 색인/통계를 보장한다.
     * - idx_books_store: 재고입력 화면에서 ISBN을 스캔/타이핑할 때마다 이 점포의
     *   도서 전체(수만~수십만 건)를 훑지 않도록 하기 위한 색인.
     * - idx_stock_store_date: [2026-09-30] "재고수정 화면으로 넘어가는데 4초가
     *   걸려" - listForCurrentSurvey(store_code, survey_date)가 이 색인을 타고
     *   빠르게 조회되도록 추가했다.
     */
    override fun onOpen(db: SQLiteDatabase) {
        super.onOpen(db)
        if (db.isReadOnly) return
        try {
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_books_store ON books(store_code, isbn)")
            // [2026-10-08] findBook()은 isbn을 COLLATE NOCASE(대소문자 무시)로 찾는데, 위 색인은
            // 대소문자 구분 방식이라 못 쓰고 전체를 훑었다. 같은 규칙(NOCASE)의 색인을 추가해
            // 스캔 때마다 걸리던 전체 훑기를 없앤다(검색 결과/동작은 그대로, 속도만 빨라짐).
            db.execSQL(
                "CREATE INDEX IF NOT EXISTS idx_books_store_nocase ON books(store_code, isbn COLLATE NOCASE)"
            )
            db.execSQL(
                "CREATE INDEX IF NOT EXISTS idx_stock_location ON stock_counts(area, section, shelf_no)"
            )
            db.execSQL(
                "CREATE INDEX IF NOT EXISTS idx_stock_store_date ON stock_counts(store_code, survey_date)"
            )
            refreshBookStats(db)
        } catch (_: Exception) {
            // 색인 정리는 속도를 위한 것일 뿐이라, 실패해도 앱 동작에는 지장이 없다.
        }
    }

    /**
     * SQLite는 통계(ANALYZE 결과)가 없으면 색인이 있어도 안 쓰고 기본키로 전체를
     * 훑어버릴 수 있다(ZZOINT의 products 색인에서 실측된 문제, 도서마스터도
     * 건수가 많을 수 있어 동일하게 대비한다). 상품마스터를 새로 받은 직후에도
     * 다시 불러서, 앱을 껐다 켜지 않아도 바로 빨라지게 한다.
     */
    fun refreshBookStats(db: SQLiteDatabase = writableDatabase) {
        try {
            db.execSQL("ANALYZE books")
        } catch (_: Exception) {
        }
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        db.execSQL("DROP TABLE IF EXISTS settings")
        db.execSQL("DROP TABLE IF EXISTS stores")
        db.execSQL("DROP TABLE IF EXISTS workers")
        db.execSQL("DROP TABLE IF EXISTS books")
        db.execSQL("DROP TABLE IF EXISTS stock_counts")
        onCreate(db)
    }

    // ---------- settings ----------
    fun setSetting(key: String, value: String) {
        val db = writableDatabase
        val cv = ContentValues()
        cv.put("key", key)
        cv.put("value", value)
        db.insertWithOnConflict("settings", null, cv, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun getSetting(key: String, default: String = ""): String {
        val db = readableDatabase
        db.rawQuery("SELECT value FROM settings WHERE key = ?", arrayOf(key)).use { c ->
            return if (c.moveToFirst()) c.getString(0) else default
        }
    }

    // ---------- workers ----------
    fun findWorkerName(code: String): String? {
        val db = readableDatabase
        db.rawQuery("SELECT name FROM workers WHERE code = ?", arrayOf(code)).use { c ->
            return if (c.moveToFirst()) c.getString(0) else null
        }
    }

    fun upsertWorker(code: String, name: String) {
        val db = writableDatabase
        val cv = ContentValues()
        cv.put("code", code)
        cv.put("name", name)
        db.insertWithOnConflict("workers", null, cv, SQLiteDatabase.CONFLICT_REPLACE)
    }

    // ---------- stores ----------
    fun upsertStore(code: String, name: String) {
        val db = writableDatabase
        val cv = ContentValues()
        cv.put("code", code)
        cv.put("name", name)
        db.insertWithOnConflict("stores", null, cv, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun findFirstStore(): Pair<String, String>? {
        val db = readableDatabase
        db.rawQuery("SELECT code, name FROM stores ORDER BY code LIMIT 1", null).use { c ->
            return if (c.moveToFirst()) Pair(c.getString(0), c.getString(1)) else null
        }
    }

    fun findStoreName(code: String): String? {
        val db = readableDatabase
        db.rawQuery("SELECT name FROM stores WHERE code = ?", arrayOf(code)).use { c ->
            return if (c.moveToFirst()) c.getString(0) else null
        }
    }

    /** 방금 받은 상품(도서)마스터가 실제로 어느 점포코드로 들어왔는지 확인한다. */
    fun findAnyBookStoreCode(): String? {
        val db = readableDatabase
        db.rawQuery("SELECT DISTINCT store_code FROM books LIMIT 1", null).use { c ->
            return if (c.moveToFirst()) c.getString(0) else null
        }
    }

    fun upsertBook(storeCode: String, isbn: String, bookName: String, category: String, publisher: String) {
        val db = writableDatabase
        val cv = ContentValues()
        cv.put("store_code", storeCode)
        cv.put("isbn", isbn)
        cv.put("book_name", bookName)
        cv.put("category", category)
        cv.put("publisher", publisher)
        db.insertWithOnConflict("books", null, cv, SQLiteDatabase.CONFLICT_REPLACE)
        invalidateBookCount()
    }

    /** 여러 건을 한 트랜잭션으로 묶어서 처리한다 (건마다 디스크에 쓰지 않아 훨씬 빠르다). */
    fun runInTransaction(block: () -> Unit) {
        val d = writableDatabase
        d.beginTransaction()
        try {
            block()
            d.setTransactionSuccessful()
        } finally {
            d.endTransaction()
        }
    }

    private fun android.database.sqlite.SQLiteStatement.bindText(index: Int, value: String?) {
        if (value == null) bindNull(index) else bindString(index, value)
    }

    private fun bookInsertStatement(localDb: SQLiteDatabase) = localDb.compileStatement(
        "INSERT OR REPLACE INTO books (store_code, isbn, book_name, category, publisher) VALUES (?,?,?,?,?)"
    )

    /**
     * PC가 adb push로 보낸 마스터 파일(STORE.db / WORKER.db / BOOK.db)을
     * 외부 저장소에서 찾아 로컬 테이블로 가져온다. 가져온 뒤에는 원본 파일을
     * 삭제해서, 다음에 PC가 다시 전송하기 전까지는 "마스터 수신" 버튼이
     * 비활성 상태로 유지되도록 한다.
     *
     * BOOK.db는 KOINTBOOK PC의 pda_transfer.push_books()가 만드는 파일로,
     * 테이블명은 book_data (store_code, isbn, book_name, category, publisher)다
     * (ZZOINT의 PRODUCT.db/product_data에 대응).
     *
     * @param onProgress (안내문구, 처리한 건수, 전체 건수)
     * @return Triple(가져온 점포 수, 작업자 수, 도서 수)
     */
    fun importMasterFilesIfPresent(
        externalFilesDir: java.io.File?,
        onProgress: ((label: String, done: Int, total: Int) -> Unit)? = null
    ): Triple<Int, Int, Int> {
        if (externalFilesDir == null) return Triple(0, 0, 0)
        var storeCount = 0
        var workerCount = 0
        var bookCount = 0
        val localDb = writableDatabase

        val storeFile = java.io.File(externalFilesDir, "STORE.db")
        if (storeFile.exists()) {
            try {
                onProgress?.invoke("점포마스터 저장 중...", 0, 0)
                val ext = SQLiteDatabase.openDatabase(storeFile.path, null, SQLiteDatabase.OPEN_READONLY)
                localDb.beginTransaction()
                try {
                    ext.rawQuery("SELECT store_code, store_name FROM store_data", null).use { c ->
                        while (c.moveToNext()) {
                            upsertStore(c.getString(0), c.getString(1))
                            storeCount++
                        }
                    }
                    localDb.setTransactionSuccessful()
                } finally {
                    localDb.endTransaction()
                }
                ext.close()
                storeFile.delete()
            } catch (_: Exception) { }
        }

        val workerFile = java.io.File(externalFilesDir, "WORKER.db")
        if (workerFile.exists()) {
            try {
                onProgress?.invoke("작업자마스터 저장 중...", 0, 0)
                val ext = SQLiteDatabase.openDatabase(workerFile.path, null, SQLiteDatabase.OPEN_READONLY)
                localDb.beginTransaction()
                try {
                    ext.rawQuery("SELECT worker_code, worker_name FROM worker_data", null).use { c ->
                        while (c.moveToNext()) {
                            upsertWorker(c.getString(0), c.getString(1))
                            workerCount++
                        }
                    }
                    localDb.setTransactionSuccessful()
                } finally {
                    localDb.endTransaction()
                }
                ext.close()
                workerFile.delete()
            } catch (_: Exception) { }
        }

        val bookFile = java.io.File(externalFilesDir, "BOOK.db")
        if (bookFile.exists()) {
            try {
                val ext = SQLiteDatabase.openDatabase(bookFile.path, null, SQLiteDatabase.OPEN_READONLY)
                var total = 0
                ext.rawQuery("SELECT COUNT(*) FROM book_data", null).use { c ->
                    if (c.moveToFirst()) total = c.getInt(0)
                }
                onProgress?.invoke("상품마스터(도서) 저장 중...", 0, total)
                localDb.beginTransaction()
                try {
                    // 무선 수신과 동일하게, 파일에 들어있는 점포들의 기존 도서를
                    // 먼저 지우고 새로 채운다(완전 교체) - 안 그러면 단종된
                    // 도서가 예전 데이터로 계속 남는다.
                    val storeCodesInFile = mutableSetOf<String>()
                    ext.rawQuery("SELECT DISTINCT store_code FROM book_data", null).use { c ->
                        while (c.moveToNext()) storeCodesInFile.add(c.getString(0))
                    }
                    for (sc in storeCodesInFile) {
                        localDb.delete("books", "store_code = ?", arrayOf(sc))
                    }
                    // [2026-09-29] "점포코드는 바뀌나 점포명이 바뀌지 않음" 수정 -
                    // 도서마스터만 따로 보냈을 때도(점포마스터를 같이 안 보내도)
                    // 이 파일 안에 같이 들어있는 book_store_meta로 점포명을 미리
                    // 반영해둔다. 옛날 버전 PC가 보낸 파일에는 이 표가 없을 수
                    // 있으니 없으면 조용히 건너뛴다.
                    try {
                        ext.rawQuery("SELECT store_code, store_name FROM book_store_meta", null).use { c ->
                            while (c.moveToNext()) {
                                val metaName = c.getString(1)
                                if (!metaName.isNullOrBlank()) {
                                    upsertStore(c.getString(0), metaName)
                                }
                            }
                        }
                    } catch (_: Exception) { }
                    // [2026-10-08] PC가 정한 조사일자로 PDA 조사일자를 고정한다(옛 PC 파일엔 없을 수 있음).
                    try {
                        ext.rawQuery("SELECT survey_date FROM book_store_meta LIMIT 1", null).use { c ->
                            if (c.moveToFirst()) {
                                val d = c.getString(0)
                                if (!d.isNullOrBlank()) {
                                    setSetting("app_survey_date", d)
                                    AppState.pinnedSurveyDate = d
                                }
                            }
                        }
                    } catch (_: Exception) { }
                    // [2026-10-08] 미등록 상품 입력 정책(allow/warn/block) - 옛 PC 파일엔 없을 수 있음.
                    try {
                        ext.rawQuery("SELECT unreg_policy FROM book_store_meta LIMIT 1", null).use { c ->
                            if (c.moveToFirst()) {
                                val u = c.getString(0)
                                if (!u.isNullOrBlank()) setSetting("unreg_policy", u)
                            }
                        }
                    } catch (_: Exception) { }
                    val stmt = bookInsertStatement(localDb)
                    ext.rawQuery(
                        "SELECT store_code, isbn, book_name, category, publisher FROM book_data", null
                    ).use { c ->
                        while (c.moveToNext()) {
                            stmt.clearBindings()
                            stmt.bindText(1, c.getString(0))
                            stmt.bindText(2, c.getString(1))
                            stmt.bindText(3, c.getString(2) ?: "")
                            stmt.bindText(4, c.getString(3) ?: "")
                            stmt.bindText(5, c.getString(4) ?: "")
                            stmt.executeInsert()
                            bookCount++
                            if (bookCount % 2000 == 0) onProgress?.invoke("상품마스터(도서) 저장 중...", bookCount, total)
                        }
                    }
                    stmt.close()
                    localDb.setTransactionSuccessful()
                } finally {
                    localDb.endTransaction()
                }
                ext.close()
                bookFile.delete()
                onProgress?.invoke("상품마스터(도서) 저장 중...", bookCount, total)
            } catch (_: Exception) {
                // 트랜잭션이 취소되었으므로 실제로는 하나도 저장되지 않은 상태다.
                bookCount = 0
            } finally {
                invalidateBookCount()
                if (bookCount > 0) refreshBookStats(localDb)
            }
        }

        return Triple(storeCount, workerCount, bookCount)
    }

    /** [마스터 초기화] 버튼용: 받은 점포/작업자/도서 마스터를 모두 지워서 처음 상태로 되돌린다. */
    fun resetMasterData() {
        val localDb = writableDatabase
        localDb.beginTransaction()
        try {
            localDb.delete("books", null, null)
            invalidateBookCount()
            localDb.delete("stores", null, null)
            localDb.delete("workers", null, null)
            localDb.setTransactionSuccessful()
        } finally {
            localDb.endTransaction()
        }
        // 데모용 샘플 작업자는 다시 넣어둔다 (완전히 텅 빈 상태 방지)
        upsertWorker("1", "이정현")
        upsertWorker("2", "박고을")
        upsertWorker("3", "오성택")
    }

    /** [2026-10-02] 기기에 도착해 있는(아직 가져오지 않은) 마스터 이름 목록 - 화면 안내용.
     * 예: ["점포", "작업자", "상품"] */
    fun pendingMasterNames(externalFilesDir: java.io.File?): List<String> {
        if (externalFilesDir == null) return emptyList()
        val names = mutableListOf<String>()
        if (java.io.File(externalFilesDir, "STORE.db").exists()) names.add("점포")
        if (java.io.File(externalFilesDir, "WORKER.db").exists()) names.add("작업자")
        if (java.io.File(externalFilesDir, "BOOK.db").exists()) names.add("상품")
        return names
    }

    /** 아직 가져오지 않은 마스터 파일이 기기에 도착해 있는지(=버튼 활성화 여부) 확인 */
    fun hasPendingMasterFiles(externalFilesDir: java.io.File?): Boolean {
        if (externalFilesDir == null) return false
        return java.io.File(externalFilesDir, "STORE.db").exists() ||
               java.io.File(externalFilesDir, "WORKER.db").exists() ||
               java.io.File(externalFilesDir, "BOOK.db").exists()
    }

    // 도서가 수십만 건이면 COUNT(*)가 매번 전부 세어야 해서 느리다. 화면에 들어올 때마다
    // 물어보는 값이라 한 번 센 결과를 기억해두고, 도서가 바뀔 때만 다시 센다.
    @Volatile private var bookCountCache: Pair<String, Int>? = null

    private fun invalidateBookCount() {
        bookCountCache = null
    }

    fun bookCountForStore(storeCode: String): Int {
        bookCountCache?.let { if (it.first == storeCode) return it.second }
        val db = readableDatabase
        db.rawQuery("SELECT COUNT(*) FROM books WHERE store_code = ?", arrayOf(storeCode)).use { c ->
            c.moveToFirst()
            val n = c.getInt(0)
            bookCountCache = Pair(storeCode, n)
            return n
        }
    }

    // ---------- books ----------
    data class BookInfo(val isbn: String, val bookName: String, val category: String, val publisher: String)

    /** ISBN으로 도서마스터에서 찾는다. store_code+isbn이 기본키라 결과는 0건 또는 1건뿐이다
     * (ZZOINT의 findMatchingProducts처럼 "같은 바코드에 자사코드가 여러 개"인 경우가
     * 도서에는 없어서, 사용자가 여러 건 중 고르는 단계 자체가 필요 없다).
     *
     * [2026-09-29] "영문 소문자,대문자 구분하지 않고 상품마스터에 맞는쪽으로
     * 자동변경하여 매칭되도록" - ISBN 끝자리 체크문자가 X/x인 경우 등, 스캐너나
     * 수동입력이 상품마스터와 대소문자만 다르게 들어오면 원래는 매칭이 안 됐다.
     * COLLATE NOCASE로 대소문자를 구분하지 않고 찾되, 반환하는 isbn은 항상
     * 이 조회 결과(상품마스터에 실제 저장된 그대로의 대소문자)를 쓴다 - 그래야
     * 호출하는 쪽(commitRow 등)이 그 값을 그대로 저장해서 마스터와 완전히
     * 같은 표기로 맞춰진다. */
    fun findBook(storeCode: String, isbn: String): BookInfo? {
        val db = readableDatabase
        db.rawQuery(
            "SELECT isbn, book_name, category, publisher FROM books " +
                "WHERE store_code = ? AND isbn = ? COLLATE NOCASE",
            arrayOf(storeCode, isbn)
        ).use { c ->
            return if (c.moveToFirst()) {
                BookInfo(c.getString(0) ?: "", c.getString(1) ?: "", c.getString(2) ?: "", c.getString(3) ?: "")
            } else null
        }
    }

    /** 이 점포의 도서가 하나라도 있는지. 개수를 세지 않고 한 건만 찾아보므로 도서가 30만 건이어도 즉시 끝난다. */
    fun hasAnyBooks(storeCode: String): Boolean {
        val db = readableDatabase
        db.rawQuery("SELECT 1 FROM books WHERE store_code = ? LIMIT 1", arrayOf(storeCode)).use { c ->
            return c.moveToFirst()
        }
    }

    // ---------- stock_counts ----------
    fun insertStockCount(
        storeCode: String, storeName: String, surveyDate: String,
        area: String, section: String, shelfNo: String, dan: String, yeol: String,
        isbn: String, bookName: String, qty: Int,
        workerCode: String, workerName: String, scannedAt: String
    ): Long {
        val db = writableDatabase
        val cv = ContentValues()
        cv.put("store_code", storeCode)
        cv.put("store_name", storeName)
        cv.put("survey_date", surveyDate)
        cv.put("area", area)
        cv.put("section", section)
        cv.put("shelf_no", shelfNo)
        cv.put("dan", dan)
        cv.put("yeol", yeol)
        cv.put("isbn", isbn)
        cv.put("book_name", bookName)
        cv.put("qty", qty)
        cv.put("worker_code", workerCode)
        cv.put("worker_name", workerName)
        cv.put("scanned_at", scannedAt)
        return db.insert("stock_counts", null, cv)
    }

    fun deleteStockCount(id: Long) {
        writableDatabase.delete("stock_counts", "id = ?", arrayOf(id.toString()))
    }

    fun updateStockCountQty(id: Long, qty: Int) {
        val db = writableDatabase
        val cv = ContentValues()
        cv.put("qty", qty)
        db.update("stock_counts", cv, "id = ?", arrayOf(id.toString()))
    }

    fun countAllStock(): Pair<Int, Int> {
        readableDatabase.rawQuery("SELECT COUNT(*), IFNULL(SUM(qty),0) FROM stock_counts", null).use { c ->
            c.moveToFirst()
            return Pair(c.getInt(0), c.getInt(1))
        }
    }

    /**
     * "PC 미전송데이터": Data 전송으로 STOCK.db에 내보내졌지만
     * PC가 아직 adb pull로 가져가지 않은 데이터 건수.
     * PC가 파일을 가져가면 그 자리에서 STOCK.db를 삭제하므로, 이 파일이
     * 더 이상 없으면(=0을 반환) "PC로 전송 완료"라는 뜻이다.
     */
    fun countPendingStockDbRows(externalFilesDir: java.io.File?): Int {
        if (externalFilesDir == null) return 0
        val f = java.io.File(externalFilesDir, "STOCK.db")
        if (!f.exists()) return 0
        return try {
            val extDb = SQLiteDatabase.openDatabase(f.path, null, SQLiteDatabase.OPEN_READONLY)
            var count = 0
            extDb.rawQuery("SELECT COUNT(*) FROM stock_data", null).use { c ->
                if (c.moveToFirst()) count = c.getInt(0)
            }
            extDb.close()
            count
        } catch (_: Exception) {
            0
        }
    }

    /**
     * 위치별(AREA-SECTION-서가번호) 건수/수량 집계. locationKey가 null/"전체"면 전체.
     * 화면에는 DbHelper.locationKey()로 만든 "1-5-12" 형태의 문자열로 보여준다.
     *
     * [2026-09-30] "3.DATA조회 화면 전환이 느려 최초 딜레이 2초" - listForCurrentSurvey()와
     * 똑같은 원인이었다: locationKey가 비어있을(=전체) 때 WHERE 조건이 전혀
     * 없어서 이 기기에 쌓인 모든 점포/모든 날짜의 stock_counts 전체를 매번
     * GROUP BY로 다시 훑었다(DATA조회/위치별 건수·수량 조회 화면 모두 이
     * 함수를 쓴다). "위치와 무관한 전체집계"가 실제로 의미 있는 범위도 결국
     * "지금 이 점포, 이 조사일자" 뿐이므로, storeCode/surveyDate를 받아 항상
     * 그 범위로 좁히도록 바꿨다(idx_stock_store_date 색인을 그대로 탄다).
     * 옛 호출부와의 호환을 위해 두 값은 기본값 null(=조건 없음)로 둔다.
     */
    fun sectionSummary(locationKey: String?, storeCode: String? = null, surveyDate: String? = null): List<Triple<String, Int, Int>> {
        val db = readableDatabase
        val result = mutableListOf<Triple<String, Int, Int>>()
        val groupExpr = "area || '-' || section || '-' || shelf_no"
        val conditions = mutableListOf<String>()
        val args = mutableListOf<String>()
        if (!storeCode.isNullOrEmpty()) {
            conditions.add("store_code = ?")
            args.add(storeCode)
        }
        if (!surveyDate.isNullOrEmpty()) {
            conditions.add("survey_date = ?")
            args.add(surveyDate)
        }
        if (!locationKey.isNullOrEmpty() && locationKey != "전체") {
            val (area, section, shelfNo) = splitLocationKey(locationKey)
            conditions.add("area = ?")
            conditions.add("section = ?")
            conditions.add("shelf_no = ?")
            args.add(area)
            args.add(section)
            args.add(shelfNo)
        }
        val whereClause = if (conditions.isEmpty()) "" else "WHERE " + conditions.joinToString(" AND ")
        val sql = "SELECT $groupExpr, COUNT(*), IFNULL(SUM(qty),0) FROM stock_counts $whereClause GROUP BY $groupExpr ORDER BY $groupExpr"
        db.rawQuery(sql, args.toTypedArray()).use { c ->
            while (c.moveToNext()) {
                result.add(Triple(c.getString(0) ?: "", c.getInt(1), c.getInt(2)))
            }
        }
        return result
    }

    fun deleteLocation(locationKey: String) {
        val (area, section, shelfNo) = splitLocationKey(locationKey)
        writableDatabase.delete(
            "stock_counts", "area = ? AND section = ? AND shelf_no = ?", arrayOf(area, section, shelfNo)
        )
    }

    fun deleteAll() {
        writableDatabase.delete("stock_counts", null, null)
        // [2026-10-08] 자료를 전부 지우면 조사일자 고정도 푼다(새 조사는 새 날짜로 시작).
        setSetting("app_survey_date", "")
        AppState.pinnedSurveyDate = ""
    }

    /**
     * [2026-10-08] "위치 건수/수량 조회는 서가번호를 제외한 AREA+SECTION 기준" - 서가번호를
     * 빼고 "AREA-SECTION" 단위로 건수/수량을 집계한다. areaSection이 null/"전체"면 전체.
     */
    fun areaSectionSummary(areaSection: String?, storeCode: String? = null, surveyDate: String? = null): List<Triple<String, Int, Int>> {
        val db = readableDatabase
        val result = mutableListOf<Triple<String, Int, Int>>()
        val groupExpr = "area || '-' || section"
        val conditions = mutableListOf<String>()
        val args = mutableListOf<String>()
        if (!storeCode.isNullOrEmpty()) { conditions.add("store_code = ?"); args.add(storeCode) }
        if (!surveyDate.isNullOrEmpty()) { conditions.add("survey_date = ?"); args.add(surveyDate) }
        if (!areaSection.isNullOrEmpty() && areaSection != "전체") {
            conditions.add("$groupExpr = ?")
            args.add(areaSection)
        }
        val whereClause = if (conditions.isEmpty()) "" else "WHERE " + conditions.joinToString(" AND ")
        val sql = "SELECT $groupExpr, COUNT(*), IFNULL(SUM(qty),0) FROM stock_counts $whereClause GROUP BY $groupExpr ORDER BY $groupExpr"
        db.rawQuery(sql, args.toTypedArray()).use { c ->
            while (c.moveToNext()) {
                result.add(Triple(c.getString(0) ?: "", c.getInt(1), c.getInt(2)))
            }
        }
        return result
    }

    /**
     * 해당 위치(AREA/SECTION/서가번호) 안에서, 아직 안 쓰인 가장 작은 열 번호를 찾는다.
     * (예: 1,2,3까지 있다가 2번을 삭제했으면 2를 돌려준다 - 빈 자리부터
     * 채워지게 하기 위함. 빈 자리가 없으면 마지막 다음 번호를 돌려준다)
     */
    fun getNextAvailableYeol(area: String, section: String, shelfNo: String, dan: String): Int {
        val db = readableDatabase
        val used = mutableSetOf<Int>()
        db.rawQuery(
            "SELECT yeol FROM stock_counts WHERE area = ? AND section = ? AND shelf_no = ? AND dan = ?",
            arrayOf(area, section, shelfNo, dan)
        ).use { c ->
            while (c.moveToNext()) {
                c.getString(0)?.toIntOrNull()?.let { used.add(it) }
            }
        }
        var candidate = 1
        while (used.contains(candidate)) candidate++
        return candidate
    }

    fun getNextPosition(area: String, section: String, shelfNo: String): Pair<String, String> {
        val db = readableDatabase
        db.rawQuery(
            "SELECT dan, yeol FROM stock_counts WHERE area = ? AND section = ? AND shelf_no = ? ORDER BY id DESC LIMIT 1",
            arrayOf(area, section, shelfNo)
        ).use { c ->
            if (c.moveToFirst()) {
                val dan = c.getString(0) ?: "1"
                return Pair(dan, getNextAvailableYeol(area, section, shelfNo, dan).toString())
            }
        }
        return Pair("1", "1")
    }

    /** 재고입력/재고수정 화면에서 쓰는, 특정 위치(AREA/SECTION/서가번호)의 스캔 목록 조회 */
    fun listByLocation(area: String, section: String, shelfNo: String): List<StockRow> {
        val db = readableDatabase
        val result = mutableListOf<StockRow>()
        db.rawQuery(
            """
            SELECT id, area, section, shelf_no, dan, yeol, isbn, book_name, qty
            FROM stock_counts WHERE area = ? AND section = ? AND shelf_no = ? ORDER BY id
            """.trimIndent(),
            arrayOf(area, section, shelfNo)
        ).use { c ->
            while (c.moveToNext()) {
                result.add(
                    StockRow(
                        id = c.getLong(0),
                        area = c.getString(1) ?: "",
                        section = c.getString(2) ?: "",
                        shelfNo = c.getString(3) ?: "",
                        dan = c.getString(4) ?: "",
                        yeol = c.getString(5) ?: "",
                        isbn = c.getString(6) ?: "",
                        bookName = c.getString(7) ?: "",
                        qty = c.getInt(8)
                    )
                )
            }
        }
        return result
    }

    /** [2026-09-29] "로케이션 기본 입력값은 비워두고 전체조건을 검색되게" -
     * 재고수정 화면에서 위치칸을 비워두면 특정 위치로 좁히지 않고 이 기기에
     * 입력되어 있는 모든 실사 데이터를 대상으로 조회한다.
     *
     * [2026-09-30 정정] "재고수정 화면으로 넘어가는데 4초가 걸려 심각하게
     * 개선이 필요할듯" - 이 함수가 WHERE 조건이 전혀 없어서, 이 기기에 여러
     * 점포/여러 날짜에 걸쳐 실사 데이터가 쌓일수록(수천~수만 건) stock_counts
     * 테이블 전체를 통째로 읽어와 화면을 열 때마다 그만큼 느려지는 원인이었다.
     * "위치와 무관하게 전체 검색"이 실제로 의미 있는 범위는 어차피 "지금 이
     * 점포, 이 조사일자" 뿐이므로(다른 점포/날짜 데이터까지 뒤섞어 보여줄
     * 이유가 없다), storeCode/surveyDate로 좁혀서 조회하도록 이름과 시그니처를
     * 바꿨다 - idx_stock_store_date 색인과 함께 훨씬 빠르게 조회된다. */
    fun listForCurrentSurvey(storeCode: String, surveyDate: String): List<StockRow> {
        val db = readableDatabase
        val result = mutableListOf<StockRow>()
        db.rawQuery(
            """
            SELECT id, area, section, shelf_no, dan, yeol, isbn, book_name, qty
            FROM stock_counts WHERE store_code = ? AND survey_date = ? ORDER BY id
            """.trimIndent(),
            arrayOf(storeCode, surveyDate)
        ).use { c ->
            while (c.moveToNext()) {
                result.add(
                    StockRow(
                        id = c.getLong(0),
                        area = c.getString(1) ?: "",
                        section = c.getString(2) ?: "",
                        shelfNo = c.getString(3) ?: "",
                        dan = c.getString(4) ?: "",
                        yeol = c.getString(5) ?: "",
                        isbn = c.getString(6) ?: "",
                        bookName = c.getString(7) ?: "",
                        qty = c.getInt(8)
                    )
                )
            }
        }
        return result
    }
}

data class StockRow(
    val id: Long,
    val area: String,
    val section: String,
    val shelfNo: String,
    val dan: String,
    val yeol: String,
    val isbn: String,
    val bookName: String,
    val qty: Int
)
