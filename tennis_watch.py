"""都立公園テニスコートの空き監視。土日祝の空きが新しく出たら LINE にプッシュする。

都立公園スポーツレクリエーション予約システム（ログイン不要の空き状況API）を参照する。
標準ライブラリだけで動く（PC のタスクスケジューラでも GitHub Actions でも可）。

  py tennis_watch.py            # 確認して、新しい空きがあれば通知
  py tennis_watch.py --dry-run  # 現在の土日祝の空きを表示するだけ（通知・状態保存なし）

LINE の認証情報: 環境変数 LINE_TOKEN / LINE_USER_ID、無ければ ../kids_admin/common/line_secret.json
状態ファイル: 環境変数 TENNIS_STATE（既定は同じフォルダの state.json）
"""
import datetime
import http.cookiejar
import json
import os
import sys
import time
import traceback
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://kouen.sports.metro.tokyo.lg.jp/web/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) tennis_watch"
JST = datetime.timezone(datetime.timedelta(hours=9))
WD = "月火水木金土日"

# 監視対象（bld=公園コード, inst=施設コード）。コードは予約サイトの空き状況検索から取得
TARGETS = [
    {"park": "日比谷公園", "bld": "1000", "inst": "10000010", "court": "人工芝"},
    {"park": "浮間公園", "bld": "1100", "inst": "11000020", "court": "人工芝"},
    {"park": "城北中央公園", "bld": "1110", "inst": "11100030", "court": "人工芝・照明有"},
    {"park": "城北中央公園", "bld": "1110", "inst": "11100130", "court": "人工芝・照明無"},
    {"park": "善福寺川緑地", "bld": "1180", "inst": "11800030", "court": "人工芝"},
    {"park": "光が丘公園", "bld": "1190", "inst": "11900050", "court": "人工芝"},
    {"park": "石神井公園", "bld": "1205", "inst": "12050030", "court": "人工芝"},
    {"park": "井の頭恩賜公園", "bld": "1220", "inst": "12200020", "court": "人工芝"},
    {"park": "武蔵野中央公園", "bld": "1230", "inst": "12300010", "court": "人工芝"},
    {"park": "小金井公園", "bld": "1240", "inst": "12400020", "court": "人工芝"},
]
MAX_WEEKS = 7  # 受付期間外の週に当たったら打ち切り
ST_VACANT = 0  # timeResult.status: 0=空き, 210=予約あり, 1=保守日, 700=受付期間外
ST_OUT_OF_PERIOD = 700
HOLIDAY_FLGS = (2, 3, 4)  # weekDay.holidayFlg: 1=平日, 2=土曜, 3=日曜, 4=祝日
MONTHLY_PUSH_LIMIT = 120  # LINE 無料枠（月200通）を他の通知と分け合うための上限
ERROR_ALERT_STREAK = 3  # 連続でこの回数失敗したら1回だけ通知
REQUEST_INTERVAL = 0.3  # 秒。サイトに負荷をかけないよう間隔をあける
PARALLEL = 4  # 同時に確認する施設数（サイトの応答が1件2〜10秒と遅いため）


class Kouen:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.requests = 0

    def req(self, path, form=None, ajax=False):
        self.requests += 1
        time.sleep(REQUEST_INTERVAL)
        headers = {"User-Agent": UA}
        if ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"
        data = urllib.parse.urlencode(form).encode() if form else None
        with self.opener.open(urllib.request.Request(SITE + path, data=data, headers=headers), timeout=30) as r:
            return r.read().decode("cp932", "replace")

    def open(self, bld):
        """空き状況APIはセッションに検索条件が入っている必要があるため、最初に一度検索画面を通す。"""
        today = datetime.datetime.now(JST).date().isoformat()
        self.req("")
        self.req("rsvWOpeInstSrchVacantAction.do", {
            "daystarthome": today, "daystart": today, "selectPpsClPpscd": "1000_1030",
            "dayofweekClearFlg": "1", "timezoneClearFlg": "1", "selectAreaBcd": bld, "selectIcd": "0",
            "selectPpsClsCd": "1000", "selectPpsCd": "1030", "selectBldCd": "",
            "displayNo": "pawab2000", "displayNoFrm": "pawab2000",
        })

    def week(self, target, day):
        text = self.req("rsvWOpeInstSrchVacantAjaxAction.do", {
            "displayNo": "prwrc2000", "useDay": day.strftime("%Y%m%d"), "bldCd": target["bld"],
            "instCd": target["inst"], "transVacantMode": "11", "clearFlag": "0",
        }, ajax=True)
        try:
            j = json.loads(text)
        except ValueError:
            raise RuntimeError(f"空き状況APIの応答が不正: {text[:100]}")
        if j.get("ErrManager") or not isinstance(j.get("result"), list):
            raise RuntimeError(f"空き状況APIがエラーを返しました: {j.get('ErrManager')}")
        return j


def scan_target(kouen, target):
    """1施設ぶんの土日祝の空き枠を返す {"inst:yyyymmdd:hhmm": {...}}"""
    slots = {}
    day = datetime.datetime.now(JST).date()
    for _ in range(MAX_WEEKS):
        j = kouen.week(target, day)
        holiday = {w["useDay"] for w in j["weekDay"] if w["holidayFlg"] in HOLIDAY_FLGS}
        cells = [c for r in j["result"] for c in r["timeResult"]]
        for c in cells:
            if c["status"] == ST_VACANT and c["useDay"] in holiday:
                slots[f'{target["inst"]}:{c["useDay"]}:{c["startTime"]}'] = {
                    "park": target["park"], "court": target["court"], "day": c["useDay"],
                    "start": c["startTime"], "end": c["endTime"], "num": c["rsvNum"],
                }
        if not cells or all(c["status"] == ST_OUT_OF_PERIOD for c in cells):
            break
        day += datetime.timedelta(days=7)
    return slots


def scan_one(target):
    """施設ごとに別セッションで確認する。セッション直後の初回呼び出しがまれに失敗するので1回だけやり直す。"""
    requests = 0
    for attempt in range(2):
        kouen = Kouen()
        try:
            kouen.open(target["bld"])
            return scan_target(kouen, target), requests + kouen.requests
        except Exception:
            requests += kouen.requests
            if attempt:
                raise
            time.sleep(3)


def scan_all():
    results, errors, requests = {}, [], 0
    with ThreadPoolExecutor(PARALLEL) as ex:
        futures = {ex.submit(scan_one, t): t for t in TARGETS}
        for f, t in futures.items():
            try:
                results[t["inst"]], n = f.result()
                requests += n
            except Exception as e:  # 1施設の失敗で全体を止めない
                errors.append(f'{t["park"]}({t["court"]}): {e}')
    return results, errors, requests


def day_label(use_day):
    d = datetime.datetime.strptime(str(use_day), "%Y%m%d").date()
    return f"{d.month}/{d.day}({WD[d.weekday()]})"


def hhmm(t):
    return f"{t // 100}:{t % 100:02d}"


def format_slots(slots):
    by_day = {}
    for s in slots:
        by_day.setdefault(s["day"], []).append(s)
    out = []
    for day in sorted(by_day):
        out.append(f"■{day_label(day)}")
        for s in sorted(by_day[day], key=lambda s: (s["park"], s["court"], s["start"])):
            out.append(f'・{s["park"]}（{s["court"]}）{hhmm(s["start"])}-{hhmm(s["end"])} {s["num"]}面')
    return "\n".join(out)


# ---------- LINE ----------
def line_secret():
    if os.environ.get("LINE_TOKEN"):
        return os.environ["LINE_TOKEN"], os.environ["LINE_USER_ID"]
    with open(os.path.join(HERE, "..", "kids_admin", "common", "line_secret.json"), encoding="utf-8") as f:
        s = json.load(f)
    return s["channel_access_token"], s["user_id"]


def push_line(text):
    token, user_id = line_secret()
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=json.dumps({"to": user_id, "messages": [{"type": "text", "text": text[:4900]}]}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def push_limited(state, text):
    """月ごとの送信数を数え、上限に達したら止める（上限到達時に1通だけ知らせる）。"""
    month = datetime.datetime.now(JST).strftime("%Y%m")
    if state.get("push_month") != month:
        state["push_month"], state["push_count"] = month, 0
    n = state["push_count"]
    if n > MONTHLY_PUSH_LIMIT:
        return
    if n == MONTHLY_PUSH_LIMIT:
        text = f"⚠️【テニス空き】今月の通知上限（{MONTHLY_PUSH_LIMIT}通）に達したため、月末まで通知を止めます。\n{SITE}"
    push_line(text)
    state["push_count"] = n + 1


# ---------- 状態 ----------
def state_path():
    return os.environ.get("TENNIS_STATE") or os.path.join(HERE, "state.json")


def load_state():
    try:
        with open(state_path(), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state):
    tmp = state_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, state_path())


def main():
    dry = "--dry-run" in sys.argv
    try:
        results, errors, requests = scan_all()
    except Exception as e:
        results, errors, requests = {}, [f"全体: {e}"], 0

    if dry:
        slots = [s for r in results.values() for s in r.values()]
        print(format_slots(slots) or "（土日祝の空きなし）")
        print(f"\nrequests={requests} errors={errors}")
        return

    state = load_state()
    today = int(datetime.datetime.now(JST).strftime("%Y%m%d"))
    prev_slots = state.get("slots", {})
    fresh = []
    for inst, slots in results.items():
        prev = prev_slots.get(inst, {})
        fresh += [s for k, s in slots.items() if s["day"] >= today and k not in prev]
        prev_slots[inst] = slots  # 取得に失敗した施設は前回の状態を残す
    state["slots"] = prev_slots

    if fresh:
        push_limited(state, f"🎾【テニス空き】土日祝の空きが出ました\n{format_slots(fresh)}\n\n予約: {SITE}")

    streak = state.get("error_streak", 0) + 1 if errors else 0
    if streak == ERROR_ALERT_STREAK:
        push_limited(state, "⚠️【テニス空き】監視が続けて失敗しています\n" + "\n".join(errors))
    state["error_streak"] = streak
    state["last_run"] = datetime.datetime.now(JST).isoformat(timespec="seconds")
    save_state(state)
    log(f"{state['last_run']} requests={requests} fresh={len(fresh)} errors={errors}")


def log(line):
    """pythonw（タスクスケジューラ）では標準出力が無いので log/YYYYMM.log にも書く。"""
    if sys.stdout:
        print(line)
    os.makedirs(os.path.join(HERE, "log"), exist_ok=True)
    with open(os.path.join(HERE, "log", datetime.datetime.now(JST).strftime("%Y%m") + ".log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log(traceback.format_exc())
        raise
