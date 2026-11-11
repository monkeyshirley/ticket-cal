#!/usr/bin/env python3
"""Generate cal.ics from events.json.

Event types:
  sale   - a known on-sale time (start: "YYYY-MM-DDTHH:MM", Asia/Shanghai).
           Gets three alarms: 1 day, 1 hour and 10 minutes before.
  window - an estimated on-sale window (start_date..end_date, all-day), no alarm.
  show   - the performance itself (all-day), no alarm.
"""
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TZ = "Asia/Shanghai"


def esc(text):
    return (str(text).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def alarm(trigger, text):
    return ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(text)}",
            (f"TRIGGER{trigger}" if trigger.startswith(";") else f"TRIGGER:{trigger}"), "END:VALARM"]


def build(data):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ticket-cal//CN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc(data.get('calendar_name', '演出开票提醒'))}",
        f"X-WR-TIMEZONE:{TZ}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H",
        "BEGIN:VTIMEZONE", f"TZID:{TZ}", "BEGIN:STANDARD",
        "DTSTART:19700101T000000", "TZOFFSETFROM:+0800", "TZOFFSETTO:+0800",
        "TZNAME:CST", "END:STANDARD", "END:VTIMEZONE",
    ]
    for ev in data.get("events", []):
        lines += ["BEGIN:VEVENT", f"UID:{ev['id']}@ticket-cal", f"DTSTAMP:{stamp}",
                  f"SUMMARY:{esc(ev['title'])}"]
        kind = ev.get("type", "sale")
        if kind == "sale":
            start = datetime.strptime(ev["start"], "%Y-%m-%dT%H:%M")
            end = start + timedelta(minutes=ev.get("duration_min", 30))
            lines += [f"DTSTART;TZID={TZ}:{start:%Y%m%dT%H%M%S}",
                      f"DTEND;TZID={TZ}:{end:%Y%m%dT%H%M%S}"]
        else:
            s = date.fromisoformat(ev["start_date"])
            e = date.fromisoformat(ev.get("end_date", ev["start_date"])) + timedelta(days=1)
            lines += [f"DTSTART;VALUE=DATE:{s:%Y%m%d}", f"DTEND;VALUE=DATE:{e:%Y%m%d}",
                      "TRANSP:TRANSPARENT"]
        if ev.get("location"):
            lines.append(f"LOCATION:{esc(ev['location'])}")
        desc = ev.get("description", "")
        if ev.get("url"):
            desc = (desc + "\n" if desc else "") + ev["url"]
            lines.append(f"URL:{ev['url']}")
        if desc:
            lines.append(f"DESCRIPTION:{esc(desc)}")
        if kind == "sale":
            t = ev["title"]
            # "discovery" alerts: absolute times (Asia/Shanghai) shortly after the on-sale time was written
            for at in ev.get("notify_at", []):
                utc = datetime.strptime(at, "%Y-%m-%dT%H:%M") - timedelta(hours=8)
                lines += alarm(f";VALUE=DATE-TIME:{utc:%Y%m%dT%H%M%SZ}", f"新开票时间已确定：{t}")
            lines += alarm("-P1D", f"明天开票：{t}")
            lines += alarm("-PT1H", f"1小时后开票：{t}")
            lines += alarm("-PT10M", f"10分钟后开抢：{t}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"


if __name__ == "__main__":
    data = json.loads((HERE / "events.json").read_text(encoding="utf-8"))
    (HERE / "cal.ics").write_text(build(data), encoding="utf-8", newline="")
    print(f"wrote cal.ics with {len(data.get('events', []))} events", file=sys.stderr)
