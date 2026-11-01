"""杉並区テニスの「空き枠先着受付」前夜リマインド。

杉並区の空き枠は「利用日の1カ月前の朝7時」から先着順で申し込める。
明日7:00に受付が始まる利用日が土日祝なら、前夜に LINE で知らせる。
杉並のサイトには一切アクセスしない（カレンダー計算と祝日データだけを使う）。

  py suginami_reminder.py            # 明日が受付開始の土日祝があれば通知
  py suginami_reminder.py --dry-run  # 通知せず、今後60日ぶんの通知予定を表示
"""
import calendar
import datetime
import json
import sys
import urllib.request

from tennis_watch import JST, push_line

# 内閣府の祝日CSVを元にした公開データ（内閣府のサイトは証明書チェーンが不完全で Python から取得できないため）
HOLIDAY_JSON = "https://holidays-jp.github.io/api/v1/date.json"
BOOK_URL = "https://www.shisetsuyoyaku.city.suginami.tokyo.jp/user/Home"
WD = "月火水木金土日"


def load_holidays():
    """祝日一覧 {date: 名前}。取れなければ土日だけで判定する。"""
    try:
        with urllib.request.urlopen(HOLIDAY_JSON, timeout=30) as r:
            data = json.load(r)
    except Exception:
        return {}, False
    return {datetime.date.fromisoformat(k): v for k, v in data.items()}, True


def use_days_opening_on(open_day):
    """open_day の7:00に受付が始まる利用日（＝1カ月後の同じ日）。
    月末で翌月の方が日数が多い場合（例 11/30 → 12/30・12/31）、余った日も含め、未確認の印を付ける。"""
    y, m = (open_day.year + 1, 1) if open_day.month == 12 else (open_day.year, open_day.month + 1)
    last = calendar.monthrange(y, m)[1]
    if open_day.day > last:
        return []  # 例 1/31 → 2/31 は存在しない（2/28 は 1/28 に開く）
    days = [(datetime.date(y, m, open_day.day), False)]
    if open_day.day == calendar.monthrange(open_day.year, open_day.month)[1]:
        days += [(datetime.date(y, m, d), True) for d in range(open_day.day + 1, last + 1)]
    return days


def label(d, holidays):
    name = holidays.get(d)
    return f"{d.month}/{d.day}({WD[d.weekday()]}{'・' + name if name else ''})"


def message_for(open_day, holidays):
    targets = [(d, unsure) for d, unsure in use_days_opening_on(open_day) if d.weekday() >= 5 or d in holidays]
    if not targets:
        return None
    lines = [f"・{label(d, holidays)}{'（月末の扱いは未確認）' if unsure else ''}" for d, unsure in targets]
    return (
        f"🎾【杉並テニス】明日 {open_day.month}/{open_day.day}({WD[open_day.weekday()]}) 7:00 から、次の日の空き枠の先着受付が始まります\n"
        + "\n".join(lines)
        + f"\n\n上井草SC・妙正寺体育館・松ノ木運動場・柏の宮公園庭球場\n{BOOK_URL}"
    )


def main():
    holidays, ok = load_holidays()
    today = datetime.datetime.now(JST).date()
    if "--dry-run" in sys.argv:
        print(f"祝日データ: {'取得OK' if ok else '取得失敗（土日のみで判定）'}")
        for i in range(1, 61):
            msg = message_for(today + datetime.timedelta(days=i), holidays)
            if msg:
                print(f"--- {today + datetime.timedelta(days=i - 1)} の夜に送信\n{msg}")
        return
    msg = message_for(today + datetime.timedelta(days=1), holidays)
    if msg:
        push_line(msg)
    print(f"{today} reminder={'sent' if msg else 'none'} holidays_csv={'ok' if ok else 'failed'}")


if __name__ == "__main__":
    main()
