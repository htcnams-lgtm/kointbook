# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
"""빠른 엑셀(.xlsx) 저장기.

openpyxl 없이 표준 라이브러리(zipfile)만으로 엑셀 파일을 직접 쓴다. 셀 객체를 만들지 않고
XML 글자를 바로 흘려 쓰기 때문에 openpyxl보다 약 7배 빠르고(30만 줄 x 11칸: 약 29초 -> 약 4초),
줄을 메모리에 쌓지 않으므로 몇 십만 줄이어도 메모리를 거의 쓰지 않는다.

- 제목줄은 굵게, 열 너비는 기본 16(엑셀 기존 저장과 같음)
- amount_cols(수량/금액 칸)는 숫자 + #,##0(3자리 콤마) 서식. "1,234" 같은 글자도 숫자로 바꿔 저장
- 그 밖의 글자는 글자 그대로 저장(바코드 앞자리 0 보존, "="로 시작해도 수식이 되지 않음)
- 엑셀이 허용하지 않는 제어문자는 빼고 저장(그대로 두면 엑셀이 파일 손상으로 판단함)
"""
import os
import re
import zipfile
from xml.sax.saxutils import escape

_BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _col_letter(i):
    s = ""
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _sheet_xml_chunks(headers, rows, amount_cols, widths, freeze_header=False, bold_header=True):
    ncol = len(headers)
    letters = [_col_letter(i) for i in range(1, ncol + 1)]
    yield ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">')
    if freeze_header:
        yield ('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
               'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
    if widths:
        yield "<cols>" + "".join(
            f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths, start=1)) + "</cols>"
    yield "<sheetData>"
    hs = ' s="1"' if bold_header else ""
    head = "".join(f'<c r="{letters[i]}1" t="inlineStr"{hs}><is><t xml:space="preserve">{escape(_BAD.sub("", str(h)))}</t></is></c>'
                   for i, h in enumerate(headers))
    yield f'<row r="1">{head}</row>'
    amount = set(amount_cols)
    buf = []
    rn = 1
    for row in rows:
        rn += 1
        parts = [f'<row r="{rn}">']
        for i in range(ncol):
            v = row[i] if i < len(row) else None
            if v is None or v == "":
                continue
            ref = f"{letters[i]}{rn}"
            if i in amount:
                num = None
                if isinstance(v, bool):
                    num = None
                elif isinstance(v, (int, float)):
                    num = v
                elif isinstance(v, str):
                    t = v.strip().replace(",", "")
                    body = t[1:] if t.startswith("-") else t
                    if body.isdigit():
                        num = int(t)
                if num is not None:
                    parts.append(f'<c r="{ref}" s="2"><v>{num}</v></c>')
                    continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                parts.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(_BAD.sub("", str(v)))}</t></is></c>')
        parts.append("</row>")
        buf.append("".join(parts))
        if len(buf) >= 2000:
            yield "".join(buf)
            buf = []
    if buf:
        yield "".join(buf)
    yield "</sheetData></worksheet>"


_STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           '<fonts count="2"><font><sz val="11"/><name val="맑은 고딕"/><family val="2"/></font>'
           '<font><b/><sz val="11"/><name val="맑은 고딕"/><family val="2"/></font></fonts>'
           '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
           '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
           '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
           '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
           '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
           '<xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
           '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
           '</styleSheet>')


def amount_cols_for(headers, is_amount_header):
    """제목 목록에서 수량/금액 칸 번호(0부터)를 돌려준다."""
    return [i for i, h in enumerate(headers) if is_amount_header(h)]


def write_xlsx(path, headers, rows, amount_cols=(), widths=None, sheet_name="Sheet", freeze_header=False,
               bold_header=True):
    """headers: 제목 목록, rows: 줄(리스트/튜플)들을 차례로 내주는 반복자(제너레이터 가능 - 메모리에 다 올리지 않아도 됨).
    amount_cols: 숫자 + 3자리 콤마(#,##0)로 저장할 칸 번호(0부터).
    widths: None이면 모든 칸 16, 빈 목록()이면 엑셀 기본 너비. bold_header: 제목줄 굵게."""
    if widths is None:
        widths = [16] * len(headers)
    sheet_name = escape(_BAD.sub("", str(sheet_name)).replace("/", " ").replace("\\", " ")
                        .replace("?", " ").replace("*", " ").replace("[", "(").replace("]", ")")
                        .replace(":", " "))[:31] or "Sheet1"
    try:
        _write(path, headers, rows, amount_cols, widths, sheet_name, freeze_header, bold_header)
    except BaseException:
        try:
            os.remove(path)
        except OSError:
            pass
        raise


def _write(path, headers, rows, amount_cols, widths, sheet_name, freeze_header, bold_header):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   f'<sheets><sheet name="{sheet_name}" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                   '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                   '</Relationships>')
        z.writestr("xl/styles.xml", _STYLES)
        with z.open("xl/worksheets/sheet1.xml", "w", force_zip64=True) as f:
            for chunk in _sheet_xml_chunks(headers, rows, amount_cols, widths, freeze_header, bold_header):
                f.write(chunk.encode("utf-8"))
