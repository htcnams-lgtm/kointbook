# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""집계표관리 > 재고조사 보고서 화면.

AREA별로 건수/수량/미등록상품(상품마스터에 없는 바코드이 스캔된 건수)을
집계해서 보여준다.

[2026-09-23 정정] "시작시간/종료시각"(예전 이름 "개시시각/종료시각")
입력칸은 [조회] 목록을 걸러내는 필터가 아니다 - [조회]는 항상 그 점포/
조사일자의 전체 데이터를 보여준다. 이 두 입력칸은 [보고서생성]으로 만드는
엑셀 보고서 맨 위에 "시작시각/종료시각 : HH:MM ~ HH:MM"으로 그대로 찍히는
값일 뿐이다(실제 재고조사를 시작/종료한 시각을 사람이 적어 넣는 용도)."""

from . import scope
from .scope_ui import ScopeBar
import tkinter as tk
from tkinter import filedialog, messagebox
from . import db as dbmod
from .base_dir import get_base_dir, find_resource
from .ui_common import setup_treeview, export_rows_to_excel, print_rows_to_excel, print_excel_file, file_date, \
    normalize_area, CL_BG, CL_NAVY, CL_TEXT_DIM, win_button


class StockReportScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CL_BG)
        self.app = app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top = tk.Frame(self, bg=CL_BG)
        top.pack(fill=tk.X, padx=12, pady=(10, 6))
        LBL_VALUE_OPT = dict(bg=CL_BG, fg=CL_NAVY, font=("", 12, "bold"))
        tk.Label(top, text="점포코드", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=0, column=0, padx=(0, 6))
        self.lbl_store_code = tk.Label(top, text=self.app.state.store_code, **LBL_VALUE_OPT)
        self.lbl_store_code.grid(row=0, column=1, padx=(0, 28))
        tk.Label(top, text="점포명", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=0, column=2, padx=(0, 6))
        self.lbl_store_name = tk.Label(top, text=self.app.state.store_name, **LBL_VALUE_OPT)
        self.lbl_store_name.grid(row=0, column=3, padx=(0, 28))
        tk.Label(top, text="조사일자", bg=CL_BG, fg=CL_TEXT_DIM).grid(row=0, column=4, padx=(0, 6))
        self.lbl_date = tk.Label(top, text=self.app.state.survey_date, **LBL_VALUE_OPT)
        self.lbl_date.grid(row=0, column=5, padx=(0, 20))

        win_button(top, text="조회", command=self.refresh, kind="normal").grid(row=0, column=6, padx=4)
        win_button(top, text="발행", command=self.print_report, kind="normal").grid(row=0, column=7, padx=4)
        win_button(top, text="보고서생성", command=self.generate_report, kind="accent").grid(row=0, column=8, padx=4)

        # [2026-10-13] 도서/문구 구분(AREA·SECTION 범위) - 조회·발행·보고서생성에 모두 적용된다.
        scope_row = tk.Frame(self, bg=CL_BG)
        scope_row.pack(fill=tk.X, padx=12, pady=(0, 4))
        self.bar = ScopeBar(scope_row, on_change=self.refresh)
        self.bar.pack(side=tk.LEFT)

        opt_row = tk.Frame(self, bg=CL_BG)
        opt_row.pack(fill=tk.X, padx=12, pady=(0, 6))
        self.merge_mode = tk.StringVar(value="합산전")
        tk.Radiobutton(opt_row, text="AREA 합산전", variable=self.merge_mode, value="합산전", bg=CL_BG,
                       command=self.refresh).pack(side=tk.LEFT)
        tk.Radiobutton(opt_row, text="AREA 합산후", variable=self.merge_mode, value="합산후", bg=CL_BG,
                       command=self.refresh).pack(side=tk.LEFT)
        # [2026-09-23 정정] "개시시각" -> "시작시간"으로 이름을 바꿨고, 이 두
        # 칸은 더 이상 조회 필터가 아니라 보고서에 찍힐 시각을 적는 칸이라는
        # 뜻을 옆에 바로 알려준다.
        tk.Label(opt_row, text="시작시간/종료시각 :", bg=CL_BG).pack(side=tk.LEFT, padx=(24, 6))
        self.e_from = tk.Entry(opt_row, width=10)
        self.e_from.pack(side=tk.LEFT)
        tk.Label(opt_row, text="~", bg=CL_BG).pack(side=tk.LEFT, padx=4)
        self.e_to = tk.Entry(opt_row, width=10)
        self.e_to.pack(side=tk.LEFT)
        tk.Label(opt_row, text="(HH:MM, [보고서생성]에 찍힐 시각)", bg=CL_BG, fg=CL_TEXT_DIM).pack(side=tk.LEFT, padx=6)

        columns = ("area", "count", "qty", "unregistered")
        headings = ("AREA", "건수", "수량", "미등록상품")
        widths = (120, 100, 100, 100)
        container, self.tree = setup_treeview(self, columns, headings, widths, height=20)
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def refresh(self):
        if not self.bar.ready():
            return
        self.lbl_store_code.config(text=self.app.state.store_code)
        self.lbl_store_name.config(text=self.app.state.store_name)
        self.lbl_date.config(text=self.app.state.survey_date)

        store_code = self.app.state.store_code
        date = self.app.state.survey_date
        merged = self.merge_mode.get() == "합산후"

        # [2026-09-23 정정] "시작시간/종료시각"(예전 "개시시각/종료시각") 칸은
        # [조회] 목록을 걸러내는 필터가 아니다 - [조회]는 항상 그 점포/조사
        # 일자의 전체 데이터를 그대로 보여준다. 그 두 칸의 값은
        # generate_report()에서 보고서에 찍는 용도로만 쓴다.
        conn = dbmod.get_conn()
        sql = "SELECT area, isbn, qty, received_at FROM stock_counts WHERE store_code=? AND survey_date=?"
        params = [store_code, date]
        cond, cparams = self.bar.sql()
        sql += cond
        params += cparams
        rows = conn.execute(sql, params).fetchall()
        registered = {r["isbn"] for r in conn.execute("SELECT isbn FROM books WHERE store_code=?", (store_code,))}
        conn.close()

        totals = {}
        for r in rows:
            area = normalize_area(r["area"], merged=merged) or "(미지정)"
            t = totals.setdefault(area, {"count": 0, "qty": 0, "unregistered": 0})
            t["count"] += 1
            t["qty"] += r["qty"] or 0
            if r["isbn"] not in registered:
                t["unregistered"] += 1

        self.tree.delete(*self.tree.get_children())
        self._rows = []
        for i, (area, t) in enumerate(sorted(totals.items())):
            row = (area, t["count"], t["qty"], t["unregistered"])
            self._rows.append(row)
            self.tree.insert("", tk.END, values=row, tags=("odd",) if i % 2 == 1 else ())

    def _export_dir_path(self):
        headers = ("AREA", "건수", "수량", "미등록상품")
        return headers

    def _tag(self):
        t = self.bar.tag()
        return f"_{t}" if t else ""

    def print_report(self):
        """[발행] 버튼: [2026-09-28] "발행버튼을 누르면 왜 엑셀저장이 뜨냐" -
        저장 위치를 묻는 export_rows_to_excel() 대신 조용히 임시 파일을
        만드는 print_rows_to_excel()을 쓴다(양식이 있는 [보고서생성]은
        저장 위치를 직접 고르는 게 맞아 그대로 둔다). [2026-09-28 재수정]
        "인쇄전 설정창같은게 하나 뜨잖아? 그렇게 해줘" - 저장 위치
        대화상자는 계속 안 띄우되, 프린터/매수를 고를 수 있는 진짜 인쇄
        대화상자는 뜨도록 print_excel_file()로 바꿨다."""
        if not getattr(self, "_rows", None):
            messagebox.showinfo("알림", "인쇄할 데이터가 없습니다.")
            return
        headers = ("AREA", "건수", "수량", "미등록상품")
        path = print_rows_to_excel(self._rows, headers, default_name=f"재고조사보고서{self._tag()}_{file_date(self.app)}.xlsx")
        if not path:
            return
        print_excel_file(path)

    def generate_report(self):
        """[보고서생성] - 실제 운영 중인 양식(로고/제목/기업정보/표/서명란)과
        똑같은 형식의 엑셀 파일로 저장한다.

        [2026-09-23 정정] "시작시간/종료시각"(예전 "개시시각/종료시각") 칸의
        값은 여기서만 쓴다 - 조회 목록과는 무관하고, 보고서 맨 위 "시작시각/
        종료시각" 줄에 사람이 적어 넣은 그대로 찍힌다(비워두면 그 줄도
        비워둔다).

        표의 "금액" 열은 지금 KOINTBOOK에 도서 가격(판매가/정가) 데이터가
        없어서(ZZOINT에는 있었지만 KOINTBOOK으로 옮길 때 빠짐) 일단 0으로
        비워 둔다 - 나중에 상품마스터에 가격 컬럼이 생기면 채울 수 있다.
        "기업명"도 아직 점포마스터에 따로 없어서, 지금의 "점포명" 값을
        기업명/점포명 두 줄에 똑같이 쓴다."""
        if not getattr(self, "_rows", None):
            messagebox.showinfo("알림", "생성할 데이터가 없습니다.")
            return

        default_name = f"재고조사보고서{self._tag()}_{file_date(self.app)}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 파일", "*.xlsx")],
            initialfile=default_name,
        )
        if not path:
            return

        t_from = self.e_from.get().strip()
        t_to = self.e_to.get().strip()
        time_range = f"{t_from} ~ {t_to}" if (t_from or t_to) else ""

        date_disp = self.app.state.survey_date
        if len(date_disp) == 8 and date_disp.isdigit():
            date_disp = f"{date_disp[:4]}/{date_disp[4:6]}/{date_disp[6:]}"

        try:
            self._write_report_excel(path, time_range, date_disp)
        except ImportError:
            # openpyxl이 없으면 양식 없이 표만이라도 CSV로 저장한다(다른
            # 화면들의 openpyxl 미설치 대비 방식과 동일).
            import csv
            headers = ("AREA", "금액", "건수", "수량", "미등록상품")
            total_count = sum(r[1] for r in self._rows)
            total_qty = sum(r[2] for r in self._rows)
            total_unreg = sum(r[3] for r in self._rows)
            rows_with_total = [(r[0], 0, r[1], r[2], r[3]) for r in self._rows]
            rows_with_total.append(("TOTAL", 0, total_count, total_qty, total_unreg))
            csv_path = path.rsplit(".", 1)[0] + ".csv"
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(headers)
                for row in rows_with_total:
                    w.writerow(row)
            messagebox.showinfo(
                "알림",
                f"openpyxl이 설치되어 있지 않아 양식 없이 CSV로 저장했습니다:\n{csv_path}\n\n"
                "pip install openpyxl 설치 후 다시 시도하면 양식이 있는 .xlsx로 저장됩니다."
            )
            return
        msg = f"보고서가 생성되었습니다:\n{path}"
        if getattr(self, "_last_logo_warning", None):
            msg += f"\n\n[알림] {self._last_logo_warning}"
        messagebox.showinfo("완료", msg)

    def _write_report_excel(self, path, time_range, date_disp):
        import openpyxl
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
        from openpyxl.drawing.xdr import XDRPositiveSize2D
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
        from openpyxl.utils.units import pixels_to_EMU

        store_code = self.app.state.store_code
        store_name = self.app.state.store_name

        total_count = sum(r[1] for r in self._rows)
        total_qty = sum(r[2] for r in self._rows)
        total_unreg = sum(r[3] for r in self._rows)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "재고조사보고서"

        # [2026-09-28 재수정] A4 "세로"(portrait) 규격으로 맞춰달라는 요청 -
        # 예전에는 가로(landscape)였다. 표 폭(A~E열 다 합쳐도 약 7.1인치)이
        # A4 세로의 인쇄 가능 폭(8.27 - 좌우여백 0.8 = 약 7.47인치)에 이미
        # 넉넉히 들어가서, 세로로 바꿔도 한 페이지 폭 맞춤(fitToWidth) 그대로
        # 잘리지 않는다.
        # [2026-09-28 3차 수정] "페이지나누기로 보면 레이어가 잘린다"는 지적 -
        # 서명란 그림이 표 아래 빈 줄 계산으로 "거의" 한 페이지에 맞게
        # 배치되긴 했지만, fitToHeight=0(높이는 제한 없이 필요한 만큼 여러
        # 페이지)로 두면 엑셀이 우리 계산과 조금이라도 어긋나는 순간(엑셀
        # 자체의 기본 행높이 렌더링이 우리 근사식과 완전히 같지 않을 수 있어)
        # 바로 그 경계에서 페이지가 갈리고, 페이지 경계에 걸친 떠있는
        # 그림(서명란)은 실제로 반이 잘려서 인쇄/미리보기된다. fitToHeight를
        # 1로 주면 "세로도 반드시 1페이지에 맞춘다"는 뜻이 되어 엑셀이 내용
        # 전체(표+서명란 이미지 포함, 이미지도 인쇄배율을 같이 따라간다)를
        # 자동으로 축소해서 항상 한 페이지 안에 넣어준다 - 우리 수작업
        # 계산에 약간의 오차가 있어도 페이지가 갈리는 일 자체가 생기지
        # 않는 가장 확실한 방법.
        ws.page_setup.orientation = "portrait"
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 1
        ws.page_margins.left = 0.4
        ws.page_margins.right = 0.4
        ws.page_margins.top = 0.5
        ws.page_margins.bottom = 0.5

        LAST_COL = 5  # A~E (AREA/금액/건수/수량/미등록상품)
        ROW_H = 15  # 기본 줄 높이(포인트) - A4 한 페이지 기준으로 서명란을 맨 아래로 내릴 때 계산에 쓴다.
        thin = Side(style="thin", color="B0B0B0")
        border_all = Border(left=thin, right=thin, top=thin, bottom=thin)
        header_fill = PatternFill("solid", fgColor="595959")
        total_fill = PatternFill("solid", fgColor="D9D9D9")
        center = Alignment(horizontal="center", vertical="center")
        left = Alignment(horizontal="left", vertical="center")

        for i in range(1, LAST_COL + 1):
            ws.column_dimensions[get_column_letter(i)].width = 16
        ws.column_dimensions["E"].width = 30

        # ---- 로고 + 제목 ----
        # [2026-09-28] 로고 이미지(pc_app/assets/report_logo.png)를 끼워 넣다가
        # 문제가 생기면(파일이 없거나, Pillow가 설치되어 있지 않거나 등)
        # 예전에는 조용히 넘어가서(except: pass) 왜 로고가 안 찍혔는지 전혀 알
        # 수 없었다 - 이제는 실패 이유를 self._last_logo_warning에 남겨서
        # generate_report()가 완료 메시지에 같이 보여주고, 그림을 못 넣더라도
        # 최소한 "KOINT" 글자만이라도 자리에 남도록 글자로 대체한다.
        self._last_logo_warning = None
        # [2026-09-28 버그수정] 아래 로고 세로 정렬 계산(row_block_h_px)이
        # row_dimensions[1]/[2].height 값을 쓰는데, 예전에는 그 높이를 로고
        # 블록보다 "뒤"에서 지정해서 계산 시점엔 두 값이 전부 None이었다.
        # None + None 연산이 터지면서 "로고를 불러오지 못했다"는 엉뚱한
        # 오류로 보였던 것 - 높이 지정을 로고 삽입보다 먼저로 옮겨서 고쳤다.
        ws.row_dimensions[1].height = 30
        ws.row_dimensions[2].height = 22
        # [2026-09-28] "exe파일하나로 다되게 만들어줘" - assets 폴더가 exe
        # 옆에 따로 없어도(=onefile 안에만 있어도) 로고를 찾도록
        # find_resource()로 바꿨다(adb_utils와 같은 방식).
        logo_path = find_resource("assets", "report_logo.png")
        logo_drawn = False
        if logo_path.exists():
            try:
                img = XLImage(str(logo_path))
                target_w = 126  # [2026-09-28] 로고 크기를 기존(180)의 70%로 축소(요청)
                ratio = img.height / img.width if img.width else 1
                img.width = target_w
                img.height = round(target_w * ratio)
                # [2026-09-28] "로고는 재고조사보고서와 같은 선상이 되게 정렬"
                # 요청 - 그냥 "A1"에 걸면 로고가 1~2행 블록의 맨 위에 붙어서,
                # 그 블록 세로 가운데에 오는 제목 글씨보다 위쪽에 떠 보였다.
                # 로고 이미지는 "KOINT" 글자 부분이 위쪽 약 2/3, 그 아래
                # "SUPPORTING LOW COST OPERATION" 작은 글자가 나머지 1/3을
                # 차지해서, 이미지 전체(bbox) 기준으로 가운데를 맞추면 실제
                # 눈에 보이는 "KOINT" 글자 자체는 제목보다 아래로 처져 보인다.
                # 그래서 이미지 전체 높이가 아니라 "KOINT" 글자 부분의
                # 대략적인 세로 중심(전체 높이의 약 36% 지점)이 제목 글씨의
                # 세로 중앙선과 같아지도록 위쪽 여백을 계산한다.
                LOGO_VISUAL_CENTER_FRAC = 0.36
                row_block_h_px = (ws.row_dimensions[1].height + ws.row_dimensions[2].height) * 4 / 3
                top_off_px = max(0, row_block_h_px / 2 - img.height * LOGO_VISUAL_CENTER_FRAC)
                marker = AnchorMarker(col=0, colOff=pixels_to_EMU(6), row=0, rowOff=pixels_to_EMU(top_off_px))
                img.anchor = OneCellAnchor(_from=marker, ext=XDRPositiveSize2D(pixels_to_EMU(img.width), pixels_to_EMU(img.height)))
                ws.add_image(img)
                logo_drawn = True
            except Exception as e:
                self._last_logo_warning = (
                    f"로고 이미지를 불러오지 못해 글자로 대신했습니다 ({e}).\n"
                    "보통 Pillow가 설치되어 있지 않을 때 생깁니다 - pip install Pillow 후 다시 생성해보세요."
                )
        else:
            self._last_logo_warning = (
                f"로고 파일을 찾을 수 없어 글자로 대신했습니다.\n(찾은 경로: {logo_path})"
            )
        if not logo_drawn:
            logo_cell = ws.cell(row=1, column=1, value="KOINT")
            logo_cell.font = Font(bold=True, size=18, color="216ED6")
        # [2026-09-28 3차 수정] "상단 A셀이랑 BCDE셀이 합쳐져서 재고조사보고서
        # 글씨가 중앙으로 오게 해줘, 로고는 그대로있고" - 예전에는 로고가
        # 있는 A열을 제목 병합 범위에서 빼고 B~LAST_COL만 가운데 정렬했는데,
        # 이번엔 A열까지 포함해서 A~LAST_COL 전체 폭 기준으로 제목이
        # 가운데 오도록 바꾼다. 로고는 셀 병합과 무관하게 떠 있는
        # 이미지(OneCellAnchor)라서 이 병합 범위 변경과 상관없이 원래 위치
        # 그대로 남는다.
        ws.merge_cells(f"A1:{get_column_letter(LAST_COL)}2")
        title_cell = ws["A1"]
        title_cell.value = "재 고 조 사 보 고 서"
        title_cell.font = Font(bold=True, size=29)  # [2026-09-28] 기존(22)보다 30% 키움(요청)
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[3].height = ROW_H
        for col in range(1, LAST_COL + 1):
            ws.cell(row=3, column=col).border = Border(bottom=Side(style="medium", color="222222"))

        # [2026-09-28] 제목 밑줄(3행)과 "기업명" 줄 사이에 빈 줄을 한 칸
        # 띄워달라는 요청 - 4행을 비워두고 기업명 블록을 5행부터 시작한다.
        ws.row_dimensions[4].height = ROW_H

        # ---- 기업명/점포명/점포코드/재고조사일/시작시각~종료시각 ----
        # [2026-09-28] "기업명"은 점포마다 달라지는 값이 아니라 항상
        # "(주)교보문고"로 고정한다(요청) - 점포명은 그대로 점포별 값을 쓴다.
        info_lines = [
            "기업명 : (주)교보문고",
            f"점포명 : {store_name}",
            f"점포코드 : {store_code}",
            f"재고조사일 : {date_disp}",
            f"시작시각/종료시각 : {time_range}",
        ]
        r = 5
        for line in info_lines:
            ws.merge_cells(f"A{r}:C{r}")
            cell = ws.cell(row=r, column=1, value=line)
            cell.font = Font(size=11)
            cell.alignment = left
            ws.row_dimensions[r].height = ROW_H
            r += 1

        # ---- 표(AREA/금액/건수/수량/미등록상품) ----
        # [2026-09-28 3차 수정] 아래 서명란 세로 위치 계산(used_height_pt)이
        # "행 높이를 직접 지정하지 않은 행은 ROW_H(15pt)일 것"이라고
        # 가정하고 있었는데, 실제로는 이 아래 표 관련 행들(빈 줄/헤더/
        # 데이터/합계) 모두 높이를 지정한 적이 없어 엑셀의 "기본 행높이"에
        # 맡겨진 상태였다 - 우리 계산의 가정(15pt)과 엑셀이 실제로 쓰는
        # 기본값이 완전히 같다는 보장이 없어서(그 작은 오차가 쌓이면 서명란
        # 위치 계산이 틀어진다), 이제부터 여기서 만드는 모든 행에 ROW_H를
        # 명시적으로 지정해서 "계산에 쓴 값 = 실제 행높이"가 항상 일치하게
        # 만든다.
        ws.row_dimensions[r].height = ROW_H  # 표 위 빈 줄(기업정보와 표 사이 간격)
        r += 1
        ws.row_dimensions[r].height = ROW_H
        headers = ("AREA", "금액", "건수", "수량", "미등록상품")
        for col, h in enumerate(headers, start=1):
            cell = ws.cell(row=r, column=col, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill
            cell.alignment = center
            cell.border = border_all
        r += 1

        # [2026-09-28] "금액"은 아직 가격 데이터가 없어 항상 0인데, 표에
        # "0"으로 찍히면 마치 실제로 금액이 0원인 것처럼 보일 수 있어서(요청)
        # 값이 없을 때는 "0" 대신 "-"로 표시한다(합계 줄도 동일).
        for area, count, qty, unreg in self._rows:
            ws.row_dimensions[r].height = ROW_H
            amount = 0  # [2026-09-23] 도서 가격 데이터가 없어 일단 0으로 둔다.
            amount_disp = f"{amount:,}" if amount else "-"
            values = (area, amount_disp, count, qty, f"(미등록 상품(포함) : {unreg})")
            for col, v in enumerate(values, start=1):
                cell = ws.cell(row=r, column=col, value=v)
                cell.border = border_all
                cell.alignment = center
                if col in (3, 4):
                    cell.number_format = "#,##0"
            r += 1

        ws.row_dimensions[r].height = ROW_H
        total_amount = 0  # 금액 합계도 가격 데이터가 없어 항상 0
        total_amount_disp = f"{total_amount:,}" if total_amount else "-"
        total_values = ("TOTAL", total_amount_disp, total_count, total_qty, f"(미등록 상품(포함) : {total_unreg})")
        for col, v in enumerate(total_values, start=1):
            cell = ws.cell(row=r, column=col, value=v)
            cell.font = Font(bold=True)
            cell.fill = total_fill
            cell.border = border_all
            cell.alignment = center
            if col in (3, 4):
                cell.number_format = "#,##0"
        r += 1

        # ---- 서명란(구분/점포 책임자/코인트써비스) ----
        # [2026-09-28 4차 수정] "레이어를 없애고 BCD열에 넣어줘" - 그동안
        # 서명란을 떠 있는 그림(sign_block.png) 레이어로 넣다 보니, 실제
        # 엑셀과 LibreOffice가 그 그림의 세로 위치/페이지 나눔 계산을 서로
        # 다르게 해석해서 "레이어가 이상한곳에 가있다", "페이지나누기로
        # 보면 레이어가 잘린다"는 문제가 계속 반복됐다. 이제는 그림 대신
        # 표와 똑같은 방식의 "진짜 셀"(B~D열)로 만든다 - 셀은 일반 행/열
        # 흐름에 포함되기 때문에, 위에서 이미 fitToHeight=1로 강제해 둔
        # "항상 한 페이지에 맞춤" 설정이 표에 하던 것과 똑같이 서명란에도
        # 그대로 적용되어 더 이상 이런 종류의 어긋남이 생길 수 없다.
        # 헤더(구분/점포 책임자/코인트써비스)는 1행, 그 아래 실제 서명/도장
        # 칸은 2행을 병합해서 헤더보다 큼직하게(요청: "헤더는 1행, 서명칸은
        # 2행 쓰면 크기가 비슷하겠네") 잡는다.
        SIGN_COLS = (2, 3, 4)  # B, C, D열
        SIGN_HEADERS = ("구분", "점포 책임자", "코인트써비스")

        # 표 바로 아래에 딱 붙지 않고, 페이지 맨 아래에서도 살짝 띄우도록
        # ("제일 아래보다는 간격을 좀 두고") 그 사이를 보통 줄 높이(ROW_H)인
        # 빈 행 여러 개로 채운다 - fitToHeight=1이 페이지 넘침 자체는
        # 막아주므로, 여기서는 "보기 좋은 위치"만 계산하면 된다.
        PAGE_HEIGHT_IN = 11.69  # A4 세로(portrait)의 긴 변 - 페이지 세로 길이
        BOTTOM_SAFETY_PT = 40  # 페이지 맨 아래에서 서명란을 살짝 띄우는 여백
        USABLE_HEIGHT_PT = (PAGE_HEIGHT_IN - ws.page_margins.top - ws.page_margins.bottom) * 72
        used_height_pt = sum((ws.row_dimensions[i].height or ROW_H) for i in range(1, r))
        sign_block_h_pt = ROW_H * 3  # 헤더 1행 + 서명칸 2행
        gap_needed_pt = max(
            ROW_H,  # 표 바로 아래 최소 한 줄은 띄운다
            USABLE_HEIGHT_PT - BOTTOM_SAFETY_PT - sign_block_h_pt - used_height_pt,
        )
        spacer_rows = max(1, int(gap_needed_pt / ROW_H))
        for _ in range(spacer_rows):
            ws.row_dimensions[r].height = ROW_H
            r += 1

        header_row = r
        ws.row_dimensions[header_row].height = ROW_H
        for col, h in zip(SIGN_COLS, SIGN_HEADERS):
            cell = ws.cell(row=header_row, column=col, value=h)
            cell.font = Font(bold=True)
            cell.fill = total_fill
            cell.alignment = center
            cell.border = border_all
        r += 1

        sign_row_start = r
        sign_row_end = r + 1
        ws.row_dimensions[sign_row_start].height = ROW_H
        ws.row_dimensions[sign_row_end].height = ROW_H
        sign_values = {2: ("서명", center), 3: ("[인]", Alignment(horizontal="right", vertical="center")),
                       4: ("[인]", Alignment(horizontal="right", vertical="center"))}
        for col in SIGN_COLS:
            ws.merge_cells(start_row=sign_row_start, start_column=col, end_row=sign_row_end, end_column=col)
            value, align = sign_values[col]
            cell = ws.cell(row=sign_row_start, column=col, value=value)
            cell.alignment = align
            cell.font = Font(size=11)
            # 병합된 셀은 openpyxl에서 테두리가 자동으로 안 퍼지므로, 병합
            # 범위 안의 각 칸에 개별적으로 테두리를 지정해야 사방이 막힌
            # 모양으로 보인다.
            for rr in (sign_row_start, sign_row_end):
                ws.cell(row=rr, column=col).border = border_all
        r = sign_row_end + 1

        ws.print_area = f"A1:{get_column_letter(LAST_COL)}{sign_row_end}"

        wb.save(path)
