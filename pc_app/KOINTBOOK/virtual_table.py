# -*- coding: utf-8 -*-
# Copyright (c) 2026 namsman. All rights reserved.
# KOINTBOOK 재고실사 관리 시스템 - 무단 복제 및 배포를 금합니다.
"""가상 스크롤 표 (KOINTBOOK 실적관리 목록 / 조회 팝업 공용).

수만~수십만 건이어도 표(ttk.Treeview)에는 화면에 보이는 만큼(약 30줄)만
두고, 스크롤할 때는 줄을 지우고 다시 만들지 않고 그 줄들의 글자만 바꾼다.
스크롤바는 전체 건수 길이로 따로 둔다.

- 화면에 들어올 때 id 목록만 백그라운드에서 읽는다(30만 건 약 0.15초).
  총 건수/수량 합계는 SQL로 따로 계산한다.
- 보이는 줄(과 앞뒤 한 화면)만 DB에서 읽고, 읽은 줄은 잠시 기억해 둔다.
- 체크/선택/수정/삭제는 모두 레코드 id 기준으로 동작한다.
- DB 연결은 읽을 때마다 짧게 열고 닫는다(백업 복원 때 DB 파일 교체를 막지 않도록).
"""

import bisect
import threading
import tkinter as tk
from collections import OrderedDict
from tkinter import ttk

from . import db as dbmod
from .ui_common import setup_treeview

CACHE_MAX = 4000      # 기억해 둘 줄 수 (넘으면 오래된 것부터 버림)
FETCH_CHUNK = 500     # IN (...) 한 번에 넘기는 id 수
WHEEL_ROWS = 3        # 마우스 휠 한 칸당 움직이는 줄 수


class VirtualTable:
    """사용법:
        vt = VirtualTable(parent, columns, headings, widths, cell_values, style_name=...)
        vt.container.pack(...)
        vt.load(where="location LIKE ?", params=("%A%",))   # 백그라운드 조회
    cell_values(row) : DB 한 줄(sqlite3.Row) -> "선택","NO"를 뺀 나머지 칸 값 튜플
    """

    def __init__(self, parent, columns, headings, widths, cell_values, height=20,
                 style_name="BigCheck.Treeview", table="stock_counts",
                 on_loaded=None, on_double=None, select_all_column="check"):
        self.table = table
        self.cell_values = cell_values
        self.on_loaded = on_loaded          # on_loaded(total, qty_sum_or_None) - 목록/합계가 바뀔 때마다
        self.on_double = on_double          # on_double(record_id)
        self.columns = columns

        self.container, self.tree = setup_treeview(parent, columns, headings, widths, height=height,
                                                   style_name=style_name)
        self.tree.configure(selectmode="browse")
        # 기본 세로 스크롤바를 우리 것으로 갈아 끼운다(전체 길이 기준).
        self.vsb = None
        for w in self.container.winfo_children():
            if isinstance(w, ttk.Scrollbar) and str(w.cget("orient")) == "vertical":
                self.vsb = w
        self.vsb.configure(command=self._on_scrollbar)
        self.tree.configure(yscrollcommand=lambda *a: None)

        self.where = ""
        self.params = ()
        self.order_by = "id"
        self._pos_map = None                # id -> 위치 (정렬이 id순이 아니어도 찾을 수 있게)
        self.ids = []                       # 조회된 레코드 id (오름차순)
        self.total = 0
        self.qty_sum = None
        self.top = 0                        # 맨 윗줄이 ids의 몇 번째인지
        self.checked = set()                # 체크된 레코드 id (int)
        self.sel_id = None                  # 선택된 레코드 id
        self.loading = False
        self.version_seen = None            # 마지막으로 읽었을 때의 stock_version

        self._cache = OrderedDict()         # id -> 칸 값 튜플
        self._slots = []                    # 표에 만들어 둔 줄(iid)
        self._slot_ids = []                 # 각 줄이 지금 보여 주는 레코드 id
        self._rendering = False
        self._render_job = None
        self._load_token = 0
        self._stat_token = 0
        self._dead = False
        self._pending = None                # (token, box) 백그라운드 결과 대기
        self._keep_on_load = None

        tree = self.tree
        tree.bind("<Configure>", lambda e: self._schedule_render(), add="+")
        tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        tree.bind("<MouseWheel>", self._on_wheel)
        tree.bind("<Button-4>", lambda e: self._scroll_rows(-WHEEL_ROWS))
        tree.bind("<Button-5>", lambda e: self._scroll_rows(WHEEL_ROWS))
        tree.bind("<Button-1>", self._on_click, add="+")
        tree.bind("<Double-Button-1>", self._on_double_click)
        tree.bind("<space>", self._on_space)
        tree.bind("<Up>", lambda e: self._move_sel(-1))
        tree.bind("<Down>", lambda e: self._move_sel(1))
        tree.bind("<Prior>", lambda e: self._move_sel(-max(1, self._full_rows() - 1)))
        tree.bind("<Next>", lambda e: self._move_sel(max(1, self._full_rows() - 1)))
        tree.bind("<Home>", lambda e: self._move_sel_to(0))
        tree.bind("<End>", lambda e: self._move_sel_to(self.total - 1))
        tree.heading(select_all_column, command=self.toggle_select_all)
        # 칸 복사(Ctrl+C): 스크롤하면 같은 자리에 다른 줄이 오므로, 클릭한 순간의 글자를 기억해 둔다.
        self._copy_text = None
        tree.bind("<ButtonRelease-1>", self._remember_cell, add="+")
        tree.bind("<Control-c>", self._copy_cell)
        tree.bind("<Control-C>", self._copy_cell)
        self.container.bind("<Destroy>", self._on_destroy, add="+")

    # ------------------------------------------------------------------
    # 조회 (백그라운드)
    # ------------------------------------------------------------------
    def load(self, where="", params=(), keep_position=False, order_by="id"):
        """조건에 맞는 id 목록과 건수/수량 합계를 백그라운드에서 읽는다. 화면은 바로 뜬다.
        keep_position=True면 보던 위치/선택/체크를 최대한 유지한다."""
        self.where, self.params = where, tuple(params)
        self.order_by = order_by or "id"
        self._load_token += 1
        token = self._load_token
        self.loading = True
        self.version_seen = dbmod.stock_version()
        if keep_position:
            self._keep_on_load = (self.top, self.sel_id, set(self.checked))
        else:
            self._keep_on_load = None
            self.checked = set()
            self.sel_id = None
            self.top = 0
            self.ids = []
            self._pos_map = None
            self.total = 0
            self.qty_sum = None
            self._cache.clear()
            self._sync_pool()
            self._update_scrollbar()
            self._notify()

        box = {}
        w = f" WHERE {where}" if where else ""
        table, prm = self.table, self.params
        order = self.order_by if self.order_by == "id" else f"{self.order_by}, id"

        def work():
            try:
                conn = dbmod.get_conn()
                try:
                    ids = [r[0] for r in conn.execute(f"SELECT id FROM {table}{w} ORDER BY {order}", prm)]
                    cnt, qty = conn.execute(
                        f"SELECT COUNT(*), COALESCE(SUM(qty),0) FROM {table}{w}", prm).fetchone()
                finally:
                    conn.close()
                box["ids"], box["qty"] = ids, qty
            except Exception as e:  # noqa: BLE001
                box["error"] = e

        threading.Thread(target=work, daemon=True).start()
        self._poll(token, box)

    def _poll(self, token, box):
        if self._dead or token != self._load_token:
            return
        if not box:
            try:
                self.container.after(30, lambda: self._poll(token, box))
            except tk.TclError:
                pass
            return
        self.loading = False
        if "error" in box:
            self.ids, self.total, self.qty_sum = [], 0, 0
        else:
            self.ids = box["ids"]
            self._pos_map = None
            self.total = len(self.ids)
            self.qty_sum = box["qty"]
        keep, self._keep_on_load = self._keep_on_load, None
        self._pos_map = None
        if keep:
            top, sel, checked = keep
            self.top = top
            self.sel_id = sel if (sel is not None and self._has_id(sel)) else None
            idset = set(self.ids) if checked else set()
            self.checked = {i for i in checked if i in idset}
            self._cache.clear()
        self.top = self._clamp_top(self.top)
        self._sync_pool()
        self._render()
        self._notify()

    def is_stale(self):
        """마지막으로 읽은 뒤 실사 데이터가 바뀌었는지."""
        return self.version_seen != dbmod.stock_version()

    def mark_fresh(self):
        self.version_seen = dbmod.stock_version()

    # ------------------------------------------------------------------
    # 바뀐 줄만 반영 (전체 재조회 없음)
    # ------------------------------------------------------------------
    def apply_changes(self, changed_ids=(), deleted_ids=(), added_ids=(), append_added=True):
        """수정/삭제/등록된 줄만 반영한다(전체 재조회 없음). 등록은 정렬 순서 안에서의 위치를
        다시 잡아야 해서, 목록(id 순서)만 백그라운드로 다시 읽는다(보던 위치/선택/체크는 유지)."""
        for i in changed_ids:
            self._cache.pop(int(i), None)
        if deleted_ids:
            dset = {int(i) for i in deleted_ids}
            self.ids = [i for i in self.ids if i not in dset]   # 새 리스트로 교체(백그라운드 계산과 충돌 방지)
            self._pos_map = None
            self.checked -= dset
            if self.sel_id in dset:
                self.sel_id = None
            for i in dset:
                self._cache.pop(i, None)
        if added_ids and append_added:
            if self.order_by == "id":
                ids = list(self.ids)
                present = set(ids)
                for i in sorted(int(x) for x in added_ids):
                    if i not in present:
                        bisect.insort(ids, i)
                self.ids = ids
                self._pos_map = None
            else:
                self.total = len(self.ids)
                self._sync_pool()
                self._render()
                self._notify()
                self.load(self.where, self.params, keep_position=True, order_by=self.order_by)
                return
        self.total = len(self.ids)
        self.top = self._clamp_top(self.top)
        self._sync_pool()
        self._render()
        self._notify()
        self.mark_fresh()
        self._recompute_qty()

    def _recompute_qty(self):
        """수정/삭제 뒤 수량 합계를 백그라운드에서 다시 계산한다(지금 목록의 id 기준)."""
        self._stat_token += 1
        token = self._stat_token
        ids = self.ids
        table = self.table
        box = {}

        def work():
            try:
                conn = dbmod.get_conn()
                try:
                    s = 0
                    for k in range(0, len(ids), 900):
                        chunk = ids[k:k + 900]
                        s += conn.execute(
                            f"SELECT COALESCE(SUM(qty),0) FROM {table} WHERE id IN ({','.join('?' * len(chunk))})",
                            chunk).fetchone()[0]
                        if token != self._stat_token:
                            return
                finally:
                    conn.close()
                box["qty"] = s
            except Exception as e:  # noqa: BLE001
                box["error"] = e

        threading.Thread(target=work, daemon=True).start()

        def poll():
            if self._dead or token != self._stat_token:
                return
            if not box:
                try:
                    self.container.after(60, poll)
                except tk.TclError:
                    pass
                return
            if "qty" in box:
                self.qty_sum = box["qty"]
                self._notify()

        try:
            self.container.after(60, poll)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # 화면 그리기
    # ------------------------------------------------------------------
    def _page_rows(self):
        """지금 화면에 (일부라도) 보이는 줄 수."""
        try:
            h = self.tree.winfo_height()
        except tk.TclError:
            return 20
        if h <= 1:
            return 20
        try:
            style = ttk.Style()
            rh = int(style.lookup(self.tree.cget("style"), "rowheight") or 20)
        except Exception:
            rh = 20
        header = 26
        return max(1, (h - header + rh - 1) // rh)

    def _full_rows(self):
        """지금 화면에 온전히 보이는 줄 수 (반쯤 잘린 아래 줄은 뺀다)."""
        try:
            h = self.tree.winfo_height()
        except tk.TclError:
            return 20
        if h <= 1:
            return 20
        try:
            rh = int(ttk.Style().lookup(self.tree.cget("style"), "rowheight") or 20)
        except Exception:
            rh = 20
        return max(1, (h - 26) // rh)

    def _clamp_top(self, top):
        return max(0, min(top, max(0, self.total - self._full_rows())))

    def _sync_pool(self):
        """표에 만들어 둘 줄 수를 (화면에 보이는 줄 수 + 1, 총 건수) 중 작은 값으로 맞춘다."""
        want = min(self.total, self._page_rows() + 1)
        cur = len(self._slots)
        if want > cur:
            for k in range(cur, want):
                iid = f"s{k}"
                self.tree.insert("", tk.END, iid=iid, values=("",) * len(self.columns))
                self._slots.append(iid)
                self._slot_ids.append(None)
        elif want < cur:
            for iid in self._slots[want:]:
                self.tree.delete(iid)
            del self._slots[want:]
            del self._slot_ids[want:]

    def _schedule_render(self):
        if self._render_job is not None or self._dead:
            return
        try:
            self._render_job = self.tree.after_idle(self._render_job_run)
        except tk.TclError:
            self._render_job = None

    def _render_job_run(self):
        self._render_job = None
        if self._dead:
            return
        self._sync_pool()
        self._render()

    def _ensure_cached(self, lo, hi):
        """ids[lo:hi] 중 기억해 두지 않은 줄을 DB에서 한 번에 읽는다."""
        want = [i for i in self.ids[lo:hi] if i not in self._cache]
        if not want:
            return
        conn = dbmod.get_conn()
        try:
            for k in range(0, len(want), FETCH_CHUNK):
                chunk = want[k:k + FETCH_CHUNK]
                for r in conn.execute(
                        f"SELECT * FROM {self.table} WHERE id IN ({','.join('?' * len(chunk))})", chunk):
                    self._cache[r["id"]] = self.cell_values(r)
        finally:
            conn.close()
        while len(self._cache) > CACHE_MAX:
            self._cache.popitem(last=False)

    def _render(self):
        n = len(self._slots)
        if n == 0:
            self._update_scrollbar()
            return
        top = self.top
        lo, hi = top, min(self.total, top + n)
        vis = self.ids[lo:hi]
        # 화면에 없는 줄이 있으면, 앞뒤 한 화면씩 미리 같이 읽어 둔다(스크롤이 매끄럽도록).
        if any(i not in self._cache for i in vis):
            self._ensure_cached(max(0, lo - n), min(self.total, hi + n))
        blank = ("",) * (len(self.columns) - 2)
        self._rendering = True
        try:
            sel_slot = None
            for k, iid in enumerate(self._slots):
                if k < len(vis):
                    rid = vis[k]
                    cells = self._cache.get(rid, blank)
                    mark = "☑" if rid in self.checked else "☐"
                    num = top + k + 1
                    self._slot_ids[k] = rid
                    self.tree.item(iid, values=(mark, num) + tuple(cells),
                                   tags=("odd",) if num % 2 == 0 else ())
                    if rid == self.sel_id:
                        sel_slot = iid
                else:
                    self._slot_ids[k] = None
                    self.tree.item(iid, values=("",) * len(self.columns), tags=())
            cur = self.tree.selection()
            if sel_slot is None:
                if cur:
                    self.tree.selection_remove(*cur)
            elif tuple(cur) != (sel_slot,):
                self.tree.selection_set(sel_slot)
                self.tree.focus(sel_slot)
        finally:
            self._rendering = False
        self._update_scrollbar()

    def _update_scrollbar(self):
        if self.vsb is None:
            return
        if self.total <= 0:
            self.vsb.set(0.0, 1.0)
            return
        n = self._full_rows()
        first = self.top / self.total
        last = min(1.0, (self.top + n) / self.total)
        self.vsb.set(first, last)

    def refresh_visible(self):
        """체크 표시 등만 다시 그린다."""
        self._render()

    # ------------------------------------------------------------------
    # 스크롤 / 키보드 / 마우스
    # ------------------------------------------------------------------
    def _set_top(self, top):
        top = self._clamp_top(int(top))
        if top != self.top:
            self.top = top
            self._schedule_render_now()

    def _schedule_render_now(self):
        # 드래그/휠 연타 시 밀리지 않게: 이미 예약돼 있으면 한 번만 그린다.
        self._schedule_render()

    def _scroll_rows(self, delta):
        self._set_top(self.top + delta)
        return "break"

    def _on_wheel(self, event):
        step = -1 if event.delta > 0 else 1
        n = max(1, abs(int(event.delta / 120))) if event.delta else 1
        self._scroll_rows(step * WHEEL_ROWS * n)
        return "break"

    def _on_scrollbar(self, *args):
        if not args:
            return
        if args[0] == "moveto":
            self._set_top(round(float(args[1]) * self.total))
        elif args[0] == "scroll":
            amount = int(args[1])
            if args[2].startswith("page"):
                self._set_top(self.top + amount * max(1, self._full_rows() - 1))
            else:
                self._set_top(self.top + amount * WHEEL_ROWS)

    def _pos_of(self, rid):
        """id의 위치(정렬 순서 기준). 위치표를 한 번 만들어 두고 쓴다. 없으면 -1."""
        if rid is None:
            return -1
        if self._pos_map is None:
            self._pos_map = {i: p for p, i in enumerate(self.ids)}
        return self._pos_map.get(rid, -1)

    def _has_id(self, rid):
        return self._pos_of(rid) >= 0

    def _ensure_visible(self, pos):
        rows = self._full_rows()
        if pos < self.top:
            self.top = self._clamp_top(pos)
        elif pos >= self.top + rows:
            self.top = self._clamp_top(pos - rows + 1)

    def _move_sel(self, delta):
        if self.total <= 0:
            return "break"
        cur = self._pos_of(self.sel_id)
        pos = 0 if cur < 0 else cur + delta
        return self._move_sel_to(pos)

    def _move_sel_to(self, pos):
        if self.total <= 0:
            return "break"
        pos = max(0, min(self.total - 1, pos))
        self.sel_id = self.ids[pos]
        self._ensure_visible(pos)
        self._render()
        return "break"

    def _on_tree_select(self, _e):
        if self._rendering:
            return
        sel = self.tree.selection()
        if not sel:
            return
        try:
            k = self._slots.index(sel[0])
        except ValueError:
            return
        rid = self._slot_ids[k] if k < len(self._slot_ids) else None
        if rid is not None:
            self.sel_id = rid

    def _row_id_at(self, y):
        iid = self.tree.identify_row(y)
        if not iid:
            return None, None
        try:
            k = self._slots.index(iid)
        except ValueError:
            return None, None
        rid = self._slot_ids[k] if k < len(self._slot_ids) else None
        return iid, rid

    def _on_click(self, event):
        self.tree.focus_set()
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        iid, rid = self._row_id_at(event.y)
        if rid is None:
            return
        if self.tree.identify_column(event.x) == "#1":     # 맨 앞 체크칸
            self.toggle_check(rid)

    def _on_double_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        iid, rid = self._row_id_at(event.y)
        if rid is None:
            return
        self.sel_id = rid
        if self.on_double is not None:
            self.on_double(rid)

    def _on_space(self, _e):
        if self.sel_id is not None:
            self.toggle_check(self.sel_id)
        return "break"

    # ------------------------------------------------------------------
    # 체크 / 선택
    # ------------------------------------------------------------------
    def toggle_check(self, rid):
        if rid in self.checked:
            self.checked.discard(rid)
        else:
            self.checked.add(rid)
        self._render()

    def toggle_select_all(self):
        """"선택" 헤더: 조회된 전체가 이미 다 체크돼 있으면 전체 해제, 아니면 전체 체크."""
        if not self.ids:
            return
        if self.checked.issuperset(self.ids):
            self.checked.clear()
        else:
            self.checked = set(self.ids)
        self._render()

    def checked_ids(self):
        return sorted(self.checked)

    def select_id(self, rid):
        """해당 레코드를 선택하고 화면에 보이게 스크롤한다."""
        pos = self._pos_of(rid)
        if pos < 0:
            return
        self.sel_id = rid
        self._ensure_visible(pos)
        self._render()

    # ------------------------------------------------------------------
    def _remember_cell(self, event):
        try:
            if self.tree.identify_region(event.x, event.y) != "cell":
                return
            row, col = self.tree.identify_row(event.y), self.tree.identify_column(event.x)
            if row and col:
                v = self.tree.set(row, col)
                self._copy_text = "" if v is None else str(v)
        except Exception:
            pass

    def _copy_cell(self, _e=None):
        if self._copy_text is not None:
            try:
                self.tree.clipboard_clear()
                self.tree.clipboard_append(self._copy_text)
            except Exception:
                pass
        return "break"

    def _notify(self):
        if self.on_loaded is not None:
            try:
                self.on_loaded(self.total, self.qty_sum)
            except tk.TclError:
                pass

    def _on_destroy(self, _e):
        self._dead = True
        self._load_token += 1
        self._stat_token += 1


# ======================================================================
# VirtualList: 체크박스 없는 "보기 전용" 목록용 가상 스크롤 표
# (자료생성 / 상품마스터 / 이상치 확인 / SECTION 품목현황)
# ======================================================================
class IdListModel:
    """정해진 순서의 rowid 목록을 들고 있다가, 보이는 줄만 DB에서 읽어 주는 모델.
    make_cells(no, row) -> 표에 보일 칸 값 전체 튜플(맨 앞 NO 포함)."""

    def __init__(self, ids, table, make_cells, extras=None):
        self.ids = ids
        self.table = table
        self.make_cells = make_cells
        self.extras = extras or {}      # 위치 -> (tag, cells)  (소계 줄처럼 DB에 없는 줄)
        self._extra_pos = sorted(self.extras)
        self._cache = OrderedDict()

    def count(self):
        return len(self.ids)

    def _no(self, pos):
        return pos + 1 - bisect.bisect_left(self._extra_pos, pos)

    def _fetch(self, lo, hi):
        want = [i for p, i in enumerate(self.ids[lo:hi], start=lo)
                if i is not None and i not in self._cache]
        if not want:
            return
        conn = dbmod.get_conn()
        try:
            for k in range(0, len(want), FETCH_CHUNK):
                chunk = want[k:k + FETCH_CHUNK]
                for r in conn.execute(
                        f"SELECT rowid AS _rid, * FROM {self.table} "
                        f"WHERE rowid IN ({','.join('?' * len(chunk))})", chunk):
                    self._cache[r["_rid"]] = r
        finally:
            conn.close()
        while len(self._cache) > CACHE_MAX:
            self._cache.popitem(last=False)

    def rows(self, lo, hi):
        """위치 lo..hi 사이 줄들의 [(칸 값 튜플, 태그 또는 None), ...]."""
        hi = min(hi, len(self.ids))
        if lo >= hi:
            return []
        self._fetch(lo, hi)
        out = []
        for pos in range(lo, hi):
            if pos in self.extras:
                tag, cells = self.extras[pos]
                out.append((cells, tag))
                continue
            r = self._cache.get(self.ids[pos])
            no = self._no(pos)
            if r is None:
                out.append((("",) * 1, None))
                continue
            out.append((self.make_cells(no, r), "odd" if no % 2 == 0 else None))
        return out

    def all_rows(self, chunk=1000):
        """엑셀/CSV 저장용: 전체 줄의 칸 값을 순서대로 (메모리 캐시를 키우지 않고) 읽어 준다."""
        for lo in range(0, len(self.ids), chunk):
            saved = self._cache
            self._cache = OrderedDict()
            try:
                for cells, _tag in self.rows(lo, lo + chunk):
                    yield cells
            finally:
                self._cache = saved


class ListModel:
    """이미 메모리에 만들어 둔 줄 목록(튜플들)을 그대로 보여 주는 모델 (NO 칸은 자동으로 붙인다).
    조회/필터 계산은 화면이 하던 대로 하고, 이 모델은 보여 주기만 한다."""

    def __init__(self, rows, tag_of=None):
        self.rows_data = rows
        self.tag_of = tag_of

    def count(self):
        return len(self.rows_data)

    def rows(self, lo, hi):
        hi = min(hi, len(self.rows_data))
        out = []
        for pos in range(lo, hi):
            no = pos + 1
            tag = self.tag_of(pos, self.rows_data[pos]) if self.tag_of else ("odd" if no % 2 == 0 else None)
            out.append(((no,) + tuple(self.rows_data[pos]), tag))
        return out

    def all_rows(self, chunk=1000):
        for lo in range(0, len(self.rows_data), chunk):
            for cells, _tag in self.rows(lo, lo + chunk):
                yield cells


class VirtualList:
    """보기 전용 가상 스크롤 표. 사용법:
        vl = VirtualList(parent, columns, headings, widths, height=18, tags={"dan_sub": "#..."})
        vl.container.pack(...)
        vl.load(build_model, on_ready=None)   # build_model()은 백그라운드 스레드에서 돌고 모델을 돌려준다
    화면 표시 규칙(줄무늬, 열 너비 드래그, 구분선, Ctrl+C 셀 복사)은 기존 표와 같다."""

    def __init__(self, parent, columns, headings, widths, height=18, tags=None,
                 style_name="Classic.Treeview", on_loaded=None):
        self.columns = columns
        self.on_loaded = on_loaded
        self.container, self.tree = setup_treeview(parent, columns, headings, widths, height=height,
                                                   style_name=style_name)
        self.tree.configure(selectmode="browse")
        for name, bg in (tags or {}).items():
            self.tree.tag_configure(name, background=bg)
        self.vsb = None
        for w in self.container.winfo_children():
            if isinstance(w, ttk.Scrollbar) and str(w.cget("orient")) == "vertical":
                self.vsb = w
        self.vsb.configure(command=self._on_scrollbar)
        self.tree.configure(yscrollcommand=lambda *a: None)

        self.model = None
        self.total = 0
        self.top = 0
        self.sel_pos = None
        self.loading = False
        self._slots = []
        self._rendering = False
        self._render_job = None
        self._token = 0
        self._dead = False
        self._copy_text = None

        t = self.tree
        t.bind("<Configure>", lambda e: self._schedule_render(), add="+")
        t.bind("<<TreeviewSelect>>", self._on_tree_select)
        t.bind("<MouseWheel>", self._on_wheel)
        t.bind("<Button-4>", lambda e: self._scroll_rows(-WHEEL_ROWS))
        t.bind("<Button-5>", lambda e: self._scroll_rows(WHEEL_ROWS))
        t.bind("<Button-1>", lambda e: t.focus_set(), add="+")
        t.bind("<Up>", lambda e: self._move_sel(-1))
        t.bind("<Down>", lambda e: self._move_sel(1))
        t.bind("<Prior>", lambda e: self._move_sel(-max(1, self._full_rows() - 1)))
        t.bind("<Next>", lambda e: self._move_sel(max(1, self._full_rows() - 1)))
        t.bind("<Home>", lambda e: self._move_sel_to(0))
        t.bind("<End>", lambda e: self._move_sel_to(self.total - 1))
        # 칸 복사(Ctrl+C): 스크롤하면 같은 자리에 다른 줄이 오므로, 클릭한 순간의 글자를 기억해 둔다.
        t.bind("<ButtonRelease-1>", self._remember_cell, add="+")
        t.bind("<Control-c>", self._copy_cell)
        t.bind("<Control-C>", self._copy_cell)
        self.container.bind("<Destroy>", self._on_destroy, add="+")

    # -- 조회 -----------------------------------------------------------
    def load(self, build_model, keep_position=False):
        """build_model()을 백그라운드에서 돌려 새 모델을 받는다. 그동안 예전 내용은 그대로 보인다.
        keep_position=False면 맨 위로 돌아간다(조회 조건이 바뀐 경우)."""
        self._token += 1
        token = self._token
        self.loading = True
        box = {}

        def work():
            try:
                box["model"] = build_model()
            except Exception as e:  # noqa: BLE001
                box["error"] = e

        threading.Thread(target=work, daemon=True).start()
        self._notify()
        self._poll(token, box, keep_position)

    def _poll(self, token, box, keep_position):
        if self._dead or token != self._token:
            return
        if not box:
            try:
                self.container.after(30, lambda: self._poll(token, box, keep_position))
            except tk.TclError:
                pass
            return
        self.loading = False
        self.model = box.get("model")
        self.total = self.model.count() if self.model else 0
        if not keep_position:
            self.top, self.sel_pos = 0, None
        self.top = self._clamp_top(self.top)
        if self.sel_pos is not None and self.sel_pos >= self.total:
            self.sel_pos = None
        self._sync_pool()
        self._render()
        self._notify()

    def set_model(self, model, keep_position=False):
        """이미 만들어진 모델을 바로(백그라운드 없이) 보여 준다. 메모리 목록용."""
        self._token += 1
        self.loading = False
        self.model = model
        self.total = model.count() if model else 0
        if not keep_position:
            self.top, self.sel_pos = 0, None
        self.top = self._clamp_top(self.top)
        if self.sel_pos is not None and self.sel_pos >= self.total:
            self.sel_pos = None
        self._sync_pool()
        self._render()
        self._notify()

    def all_rows(self):
        """지금 목록 전체를 (화면 순서대로) 칸 값 튜플로 돌려준다. 저장/인쇄용."""
        if self.model is None:
            return []
        return list(self.model.all_rows())

    # -- 그리기 ---------------------------------------------------------
    def _row_h(self):
        try:
            return int(ttk.Style().lookup(self.tree.cget("style"), "rowheight") or 20)
        except Exception:
            return 20

    def _page_rows(self):
        try:
            h = self.tree.winfo_height()
        except tk.TclError:
            return 20
        if h <= 1:
            return 20
        return max(1, (h - 26 + self._row_h() - 1) // self._row_h())

    def _full_rows(self):
        try:
            h = self.tree.winfo_height()
        except tk.TclError:
            return 20
        if h <= 1:
            return 20
        return max(1, (h - 26) // self._row_h())

    def _clamp_top(self, top):
        return max(0, min(top, max(0, self.total - self._full_rows())))

    def _sync_pool(self):
        want = min(self.total, self._page_rows() + 1)
        cur = len(self._slots)
        if want > cur:
            for k in range(cur, want):
                iid = f"v{k}"
                self.tree.insert("", tk.END, iid=iid, values=("",) * len(self.columns))
                self._slots.append(iid)
        elif want < cur:
            for iid in self._slots[want:]:
                self.tree.delete(iid)
            del self._slots[want:]

    def _schedule_render(self):
        if self._render_job is not None or self._dead:
            return
        try:
            self._render_job = self.tree.after_idle(self._render_job_run)
        except tk.TclError:
            self._render_job = None

    def _render_job_run(self):
        self._render_job = None
        if self._dead:
            return
        self._sync_pool()
        self._render()

    def _render(self):
        n = len(self._slots)
        if n == 0 or self.model is None:
            self._update_scrollbar()
            return
        rows = self.model.rows(self.top, self.top + n)
        blank = ("",) * len(self.columns)
        self._rendering = True
        try:
            sel_iid = None
            for k, iid in enumerate(self._slots):
                if k < len(rows):
                    cells, tag = rows[k]
                    if len(cells) < len(self.columns):
                        cells = tuple(cells) + ("",) * (len(self.columns) - len(cells))
                    self.tree.item(iid, values=cells, tags=(tag,) if tag else ())
                    if self.top + k == self.sel_pos:
                        sel_iid = iid
                else:
                    self.tree.item(iid, values=blank, tags=())
            cur = self.tree.selection()
            if sel_iid is None:
                if cur:
                    self.tree.selection_remove(*cur)
            elif tuple(cur) != (sel_iid,):
                self.tree.selection_set(sel_iid)
                self.tree.focus(sel_iid)
        finally:
            self._rendering = False
        self._update_scrollbar()

    def _update_scrollbar(self):
        if self.vsb is None:
            return
        if self.total <= 0:
            self.vsb.set(0.0, 1.0)
            return
        self.vsb.set(self.top / self.total, min(1.0, (self.top + self._full_rows()) / self.total))

    # -- 스크롤 / 키보드 --------------------------------------------------
    def _set_top(self, top):
        top = self._clamp_top(int(top))
        if top != self.top:
            self.top = top
            self._schedule_render()

    def _scroll_rows(self, delta):
        self._set_top(self.top + delta)
        return "break"

    def _on_wheel(self, event):
        step = -1 if event.delta > 0 else 1
        n = max(1, abs(int(event.delta / 120))) if event.delta else 1
        self._scroll_rows(step * WHEEL_ROWS * n)
        return "break"

    def _on_scrollbar(self, *args):
        if not args:
            return
        if args[0] == "moveto":
            self._set_top(round(float(args[1]) * self.total))
        elif args[0] == "scroll":
            amount = int(args[1])
            if args[2].startswith("page"):
                self._set_top(self.top + amount * max(1, self._full_rows() - 1))
            else:
                self._set_top(self.top + amount * WHEEL_ROWS)

    def _move_sel(self, delta):
        if self.total <= 0:
            return "break"
        return self._move_sel_to(0 if self.sel_pos is None else self.sel_pos + delta)

    def _move_sel_to(self, pos):
        if self.total <= 0:
            return "break"
        pos = max(0, min(self.total - 1, pos))
        self.sel_pos = pos
        rows = self._full_rows()
        if pos < self.top:
            self.top = self._clamp_top(pos)
        elif pos >= self.top + rows:
            self.top = self._clamp_top(pos - rows + 1)
        self._render()
        return "break"

    def _on_tree_select(self, _e):
        if self._rendering:
            return
        sel = self.tree.selection()
        if sel and sel[0] in self._slots:
            self.sel_pos = self.top + self._slots.index(sel[0])

    def _remember_cell(self, event):
        try:
            if self.tree.identify_region(event.x, event.y) != "cell":
                return
            row, col = self.tree.identify_row(event.y), self.tree.identify_column(event.x)
            if row and col:
                v = self.tree.set(row, col)
                self._copy_text = "" if v is None else str(v)
        except Exception:
            pass

    def _copy_cell(self, _e=None):
        if self._copy_text is not None:
            try:
                self.tree.clipboard_clear()
                self.tree.clipboard_append(self._copy_text)
            except Exception:
                pass
        return "break"

    def _notify(self):
        if self.on_loaded is not None:
            try:
                self.on_loaded(self.total, self.loading)
            except tk.TclError:
                pass

    def _on_destroy(self, _e):
        self._dead = True
        self._token += 1
