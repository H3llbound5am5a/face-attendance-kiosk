import csv
import os
import datetime
from config import ATTENDANCE_DIR

class AttendanceLog:
    """One CSV per day in ATTENDANCE_DIR (e.g. attendance/2026-07-17.csv).
    Each person is logged once per day, at first sighting."""

    def __init__(self):
        os.makedirs(ATTENDANCE_DIR, exist_ok=True)
        self._today = None
        self._marked = {}  # name -> time string of first mark today
        self._recent = []  # (time_str, name) in check-in order
        self._load_today()

    def _today_path(self):
        return os.path.join(ATTENDANCE_DIR, f"{self._today.isoformat()}.csv")

    def _load_today(self):
        self._today = datetime.date.today()
        self._marked = {}
        self._recent = []
        path = self._today_path()
        if os.path.exists(path):
            try:
                with open(path, newline='') as f:
                    for row in csv.DictReader(f):
                        if row.get('Name'):
                            self._marked[row['Name']] = row.get('Time', '')
                            self._recent.append((row.get('Time', ''), row['Name']))
                print(f"[ATTENDANCE] Resumed today's log: {len(self._marked)} already marked.")
            except Exception as e:
                print(f"[ATTENDANCE] Could not read {path}: {e}")

    def mark(self, name, category=""):
        """Returns (marked_now, time_str). marked_now is False if the person
        was already marked earlier today (time_str = their first check-in)."""
        if datetime.date.today() != self._today:
            self._load_today()  # midnight rollover

        if name in self._marked:
            return False, self._marked[name]

        time_str = datetime.datetime.now().strftime("%I:%M %p")
        path = self._today_path()
        is_new_file = not os.path.exists(path)
        with open(path, 'a', newline='') as f:
            writer = csv.writer(f)
            if is_new_file:
                writer.writerow(["Name", "Category", "Time"])
            writer.writerow([name, category, time_str])

        self._marked[name] = time_str
        self._recent.append((time_str, name))
        print(f"[ATTENDANCE] Marked: {name} ({category}) at {time_str}")
        return True, time_str

    def count_today(self):
        return len(self._marked)

    def recent(self, n=3):
        """Last n check-ins, newest first, as (time_str, name)."""
        return list(reversed(self._recent[-n:]))
