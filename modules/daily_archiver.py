# modules/daily_archiver.py
import os
import json
import atexit
import tempfile
import shutil
import datetime
import hashlib
from typing import Optional, Callable, List, Dict, Any
from PyQt5.QtCore import QTimer, QObject, pyqtSlot
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem

from modules.pdf_exporter import export_qtablewidget_to_pdf

# Base folder for daily archives
ARCHIVE_BASE = os.path.join(os.getcwd(), "archives")

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _date_str(dt: Optional[datetime.date] = None) -> str:
    if dt is None:
        dt = datetime.date.today()
    return dt.strftime("%Y-%m-%d")

def _atomic_write(src_path: str, final_path: str):
    _ensure_dir(os.path.dirname(final_path))
    try:
        os.replace(src_path, final_path)
    except Exception:
        shutil.copyfile(src_path, final_path)
        try:
            os.remove(src_path)
        except Exception:
            pass

def _snapshot_hash(snapshot: Dict[str, Any]) -> str:
    try:
        payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
    except Exception:
        return ""

class DailyArchiver(QObject):
    """
    Autosave / daily archiver helper.

    Usage:
      arch = DailyArchiver(namespace, table_widget, title="Registro", autosave_interval_ms=..., check_interval_ms=..., rows_provider=callable)
      arch.start()

    Parameters:
      - namespace: subfolder name under ./archives (e.g. 'productos', 'entradas', 'salidas')
      - table: QTableWidget instance used to capture snapshots (can be None initially; must be set before start())
      - title: printed title in PDF
      - autosave_interval_ms: interval between autosaves (default 4 hours)
      - check_interval_ms: how often to check for day rollover (default 1 minute)
      - rows_provider: optional callable(date_str) -> {"headers": [...], "rows": [[...], ...]}
                       if provided, it will be used to create archives for a specific date (useful to export DB-filtered rows for a past day)
    Behavior:
      - Saves one PDF per day named YYYY-MM-DD.pdf under ./archives/{namespace}/
      - Uses an internal hash to skip writes when snapshot didn't change.
      - On start(), if .last_archive.json records a last_date != today and the corresponding file is missing,
        it will attempt to write an archive for that date (using rows_provider if given, otherwise using current table snapshot).
      - Saves on periodic autosave, on day rollover, on shutdown/close and at exit.
    """
    def __init__(
        self,
        namespace: str,
        table: Optional[QTableWidget] = None,
        title: Optional[str] = None,
        autosave_interval_ms: int = 4 * 3600 * 1000,   # default 4 hours
        check_interval_ms: int = 60 * 1000,            # 1 minute
        rows_provider: Optional[Callable[[str], Dict[str, Any]]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.namespace = (namespace or "general").lower()
        self.table = table
        self.title = title or f"{self.namespace.capitalize()} - Export"
        self.autosave_interval_ms = int(autosave_interval_ms)
        self.check_interval_ms = int(check_interval_ms)
        self.rows_provider = rows_provider

        # snapshot and tracking
        self._snapshot = {"headers": [], "rows": []}
        self._last_saved_hash = None
        self._last_saved_date = self._read_last_date() or _date_str()

        # timers
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(self.autosave_interval_ms)
        self._autosave_timer.timeout.connect(self._on_autosave_tick)

        self._date_check_timer = QTimer(self)
        self._date_check_timer.setInterval(self.check_interval_ms)
        self._date_check_timer.timeout.connect(self._on_date_check_tick)

        # register atexit final save
        atexit.register(self._atexit_save)

    # file helpers
    def _get_folder(self) -> str:
        folder = os.path.join(ARCHIVE_BASE, self.namespace)
        _ensure_dir(folder)
        return folder

    def _get_pdf_path_for_date(self, date_str: str) -> str:
        return os.path.join(self._get_folder(), f"{date_str}.pdf")

    def _get_state_path(self) -> str:
        return os.path.join(self._get_folder(), ".last_archive.json")

    def _read_last_date(self) -> Optional[str]:
        path = self._get_state_path()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    j = json.load(fh)
                    return j.get("last_date")
        except Exception:
            pass
        return None

    def _write_last_date(self, date_str: str):
        path = self._get_state_path()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"last_date": date_str}, fh)
        except Exception:
            pass

    # snapshot helpers
    def _capture_snapshot_from_table(self):
        """Capture snapshot from self.table into self._snapshot"""
        try:
            if not self.table:
                self._snapshot = {"headers": [], "rows": []}
                return
            headers = []
            for c in range(self.table.columnCount()):
                hi = self.table.horizontalHeaderItem(c)
                headers.append(hi.text() if hi else f"Col{c}")
            rows = []
            for r in range(self.table.rowCount()):
                row = []
                for c in range(self.table.columnCount()):
                    it = self.table.item(r, c)
                    if it:
                        row.append(it.text())
                    else:
                        w = self.table.cellWidget(r, c)
                        if w is not None:
                            try:
                                text = getattr(w, "text", lambda: "")()
                                row.append(str(text))
                            except Exception:
                                try:
                                    row.append(str(w.text()))
                                except Exception:
                                    row.append("")
                        else:
                            row.append("")
                rows.append(row)
            self._snapshot = {"headers": headers, "rows": rows}
        except Exception:
            self._snapshot = {"headers": [], "rows": []}

    def _capture_snapshot(self):
        """Public snapshot capture wrapper (can be called externally)."""
        # prefer provider only when saving for past date; here we capture current UI
        self._capture_snapshot_from_table()

    def _snapshot_has_data(self, snapshot: Optional[Dict[str, Any]] = None) -> bool:
        s = snapshot if snapshot is not None else self._snapshot
        try:
            return bool(s.get("rows"))
        except Exception:
            return False

    # Start / stop
    def start(self):
        """
        Start timers and perform initial checks:
         - capture snapshot from table
         - if last_saved_date != today and an archive for last_saved_date is missing, attempt to save it
           (use rows_provider(date) if provided; otherwise use current table snapshot)
        IMPORTANT: call start() after the window has loaded and table is populated.
        """
        try:
            # capture current UI snapshot
            self._capture_snapshot_from_table()

            today = _date_str()
            last = self._last_saved_date

            # if we have a last saved date different from today, and its pdf is missing, attempt to save it
            if last and last != today:
                target_path = self._get_pdf_path_for_date(last)
                if not os.path.exists(target_path):
                    # attempt to get rows for that date via provider
                    snapshot_for_save = None
                    try:
                        if self.rows_provider:
                            snapshot_for_save = self.rows_provider(last)
                            # ensure structure
                            if not isinstance(snapshot_for_save, dict) or "headers" not in snapshot_for_save:
                                snapshot_for_save = None
                        # fallback: use the current captured snapshot (caller should have populated the table reflecting DB)
                        if snapshot_for_save is None:
                            snapshot_for_save = self._snapshot
                    except Exception:
                        snapshot_for_save = self._snapshot

                    # only save if there is data
                    if self._snapshot_has_data(snapshot_for_save):
                        try:
                            self._save_snapshot(snapshot_for_save, date=last)
                        except Exception:
                            pass

            # update last_saved_date to today (we won't clear table here)
            self._last_saved_date = today
            self._write_last_date(today)

            # start timers
            self._autosave_timer.start()
            self._date_check_timer.start()
        except Exception:
            # ensure timers are running to not block future saves
            try:
                self._autosave_timer.start()
                self._date_check_timer.start()
            except Exception:
                pass

    def stop(self):
        try:
            self._autosave_timer.stop()
            self._date_check_timer.stop()
        except Exception:
            pass

    # save helpers
    def _save_snapshot(self, snapshot: Dict[str, Any], date: Optional[str] = None) -> Dict[str, str]:
        """
        Internal: export the given snapshot (headers+rows) to pdf for date (YYYY-MM-DD).
        Uses temp file + atomic move. Returns exporter response or {} on failure.
        """
        try:
            target_date = date or _date_str()
            target_path = self._get_pdf_path_for_date(target_date)

            # change detection: if today's file and hash matches last saved, skip
            curr_hash = _snapshot_hash(snapshot)
            if target_date == _date_str() and self._last_saved_hash and curr_hash == self._last_saved_hash:
                return {"type": "skipped", "path": target_path}

            # build temporary QTableWidget from snapshot
            tmp_table = QTableWidget()
            headers = snapshot.get("headers", [])
            rows = snapshot.get("rows", [])
            tmp_table.setColumnCount(len(headers))
            tmp_table.setHorizontalHeaderLabels(headers)
            tmp_table.setRowCount(0)
            for r in rows:
                rowidx = tmp_table.rowCount()
                tmp_table.insertRow(rowidx)
                for c, val in enumerate(r):
                    item = QTableWidgetItem(str(val))
                    tmp_table.setItem(rowidx, c, item)

            fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            try:
                res = export_qtablewidget_to_pdf(tmp_table, tmp_path, title=f"{self.title} ({target_date})", company_info={"name": "Minimarket ChiChi N-K, C.A", "tax_id": "J-5099900-7"}, orientation="landscape")
                _atomic_write(tmp_path, target_path)
                # update metadata
                if target_date == _date_str():
                    self._last_saved_hash = curr_hash
                    self._last_saved_date = target_date
                    self._write_last_date(target_date)
                return {"type": res.get("type", "pdf"), "path": target_path}
            except Exception:
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
                return {}
        except Exception:
            return {}

    def save_now(self) -> Dict[str, str]:
        """
        Public: capture current snapshot from table and save it for today (if changed).
        """
        try:
            self._capture_snapshot_from_table()
            if not self._snapshot_has_data():
                return {"type": "skipped", "path": self._get_pdf_path_for_date(_date_str())}
            return self._save_snapshot(self._snapshot, date=_date_str())
        except Exception:
            return {}

    @pyqtSlot()
    def _on_autosave_tick(self):
        """
        Periodic autosave tick: save current snapshot if changed.
        """
        try:
            self._capture_snapshot_from_table()
            if not self._snapshot_has_data():
                return
            self._save_snapshot(self._snapshot, date=_date_str())
        except Exception:
            pass

    @pyqtSlot()
    def _on_date_check_tick(self):
        """
        Check for day rollover. When day changes:
         - attempt to save an archive for the previous day if necessary (using rows_provider if available)
         - clear UI table rows (so the user sees an empty table for the new day) -- note: this does not delete DB data
         - reset last_saved_hash so first save of new day persists
        """
        try:
            today = _date_str()
            if today != self._last_saved_date:
                yesterday = self._last_saved_date
                # try to ensure yesterday archive exists
                if yesterday:
                    y_path = self._get_pdf_path_for_date(yesterday)
                    if not os.path.exists(y_path):
                        # prefer rows_provider when available
                        snapshot_for_yesterday = None
                        try:
                            if self.rows_provider:
                                snapshot_for_yesterday = self.rows_provider(yesterday)
                                if not isinstance(snapshot_for_yesterday, dict) or "headers" not in snapshot_for_yesterday:
                                    snapshot_for_yesterday = None
                        except Exception:
                            snapshot_for_yesterday = None

                        if snapshot_for_yesterday is None:
                            # fallback to last captured snapshot (which hopefully corresponds to yesterday if called right after midnight)
                            snapshot_for_yesterday = self._snapshot

                        if self._snapshot_has_data(snapshot_for_yesterday):
                            try:
                                self._save_snapshot(snapshot_for_yesterday, date=yesterday)
                            except Exception:
                                pass

                # clear table view so UI starts visually blank (do not delete DB)
                try:
                    if self.table:
                        self.table.setRowCount(0)
                except Exception:
                    pass

                # reset tracking for new day
                self._last_saved_hash = None
                self._last_saved_date = today
                self._write_last_date(today)
                # capture (now-empty) snapshot
                try:
                    self._capture_snapshot_from_table()
                except Exception:
                    pass
        except Exception:
            pass

    def update_snapshot(self):
        """Public: refresh internal snapshot from table (call after reloading the table)."""
        try:
            self._capture_snapshot_from_table()
        except Exception:
            pass

    def shutdown(self):
        """Stop timers and perform a final save (if data present)."""
        try:
            self.stop()
            self._capture_snapshot_from_table()
            if self._snapshot_has_data():
                self._save_snapshot(self._snapshot, date=_date_str())
        except Exception:
            pass

    def _atexit_save(self):
        try:
            self._capture_snapshot_from_table()
            if self._snapshot_has_data():
                self._save_snapshot(self._snapshot, date=_date_str())
        except Exception:
            pass

