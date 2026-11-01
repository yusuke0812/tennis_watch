// 杉並区さざんかねっと「施設別空き状況」画面で押すブックマークボタンの元コード。
// 画面に表示中の表から、土日祝の「空き」「一部空き」を一覧にし、前回押したときから増えたものに NEW を付ける。
// サイトへの通信はしない（表示済みの内容を読むだけ）。前回の結果はこのブラウザの localStorage に保存。
// make_bookmarklet.py で javascript: 形式に変換して install.html に埋め込む。
(() => {
  const KEY = "tennisWatchSuginamiPrev";
  const VACANT = ["空き", "一部空き"];
  const tables = [...document.querySelectorAll("table.table-schedule")];
  if (!location.pathname.includes("AvailabilityCheckApplySelectDays") || !tables.length) {
    alert("杉並区さざんかねっとの「施設別空き状況」の表が表示された画面で押してください。");
    return;
  }

  // 表の左上「2026/11/1(日)～」から開始年月を取り、12月→1月の年またぎに対応する
  const start = (document.querySelector("th.startdate")?.textContent || "").match(/(\d{4})\/(\d{1,2})\//);
  const startYear = start ? +start[1] : new Date().getFullYear();
  const startMonth = start ? +start[2] : new Date().getMonth() + 1;
  const toKeyDate = (md) => {
    const [m, d] = md.split("/").map(Number);
    const y = m < startMonth ? startYear + 1 : startYear;
    return `${y}${String(m).padStart(2, "0")}${String(d).padStart(2, "0")}`;
  };

  const found = [];
  for (const t of tables) {
    // 施設名は表の外側の見出しにある
    let name = "";
    for (let el = t.parentElement; el && !name; el = el.parentElement) {
      const h = el.querySelector("h2,h3,h4,.card-header,[class*=title]");
      if (h && !t.contains(h)) name = h.textContent.replace(/\s+/g, " ").trim();
    }
    const days = [...t.querySelectorAll("thead th.month")].map((th) => {
      const md = th.textContent.replace(/\s+/g, "").match(/(\d{1,2})\/(\d{1,2})/);
      const dow = th.querySelector(".week")?.textContent.trim() || "";
      const holiday = /\bsun\b/.test(th.className) && dow !== "日"; // sun クラスは日曜と祝日
      return { md: md ? `${md[1]}/${md[2]}` : "", dow, weekend: /\b(sun|sat)\b/.test(th.className), holiday };
    });
    for (const tr of t.querySelectorAll("tbody tr")) {
      const room = tr.querySelector("td")?.textContent.replace(/\s+/g, " ").trim() || "";
      [...tr.querySelectorAll("td.btn-group-toggle")].forEach((td, i) => {
        const status = td.querySelector(".sr-only")?.textContent.trim() || "";
        const day = days[i];
        if (!day || !day.weekend || !VACANT.includes(status)) return;
        // 空き枠の先着申込は「利用日の1カ月前の朝7時」から。それより前は○でも選べない
        const kd = toKeyDate(day.md);
        const open = new Date(+kd.slice(0, 4), +kd.slice(4, 6) - 2, +kd.slice(6, 8), 7, 0);
        const notYet = open > new Date();
        found.push({
          openLabel: notYet ? `${open.getMonth() + 1}/${open.getDate()} 7:00から受付` : "",
          key: `${name}|${room}|${toKeyDate(day.md)}`,
          sort: toKeyDate(day.md),
          label: `${day.md}(${day.dow}${day.holiday ? "・祝" : ""})`,
          name,
          room,
          status,
        });
      });
    }
  }

  let prev = [];
  try {
    prev = JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch (e) {}
  const prevSet = new Set(prev);
  try {
    localStorage.setItem(KEY, JSON.stringify(found.map((f) => f.key)));
  } catch (e) {}
  found.sort((a, b) => a.sort.localeCompare(b.sort) || a.name.localeCompare(b.name));
  const newCount = found.filter((f) => !prevSet.has(f.key)).length;

  const range = [...document.querySelectorAll("table.table-schedule thead th.month")].map((th) => th.textContent.replace(/\s+/g, "").match(/\d{1,2}\/\d{1,2}/)?.[0]).filter(Boolean);
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const rows = found.length
    ? found
        .map(
          (f) =>
            `<tr><td>${prevSet.has(f.key) ? "" : '<b style="color:#d33">NEW</b>'}</td><td>${esc(f.label)}</td><td>${esc(f.name)}<br><small>${esc(f.room)}</small></td><td>${esc(f.status)}${f.openLabel ? `<br><small style="color:#b60">${esc(f.openLabel)}</small>` : ""}</td></tr>`,
        )
        .join("")
    : '<tr><td colspan="4">土日祝の空きはありません</td></tr>';

  document.getElementById("tw-suginami-panel")?.remove();
  const panel = document.createElement("div");
  panel.id = "tw-suginami-panel";
  panel.style.cssText =
    "position:fixed;top:12px;right:12px;z-index:2147483647;width:min(440px,calc(100vw - 24px));max-height:80vh;overflow:auto;background:#fff;color:#222;border:2px solid #2a7;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.25);font:14px/1.5 sans-serif;padding:12px";
  panel.innerHTML =
    `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px"><b>🎾 土日祝の空き（${found.length}件・新着${newCount}件）</b><button id="tw-suginami-close" style="border:0;background:#eee;border-radius:6px;padding:2px 10px;cursor:pointer">閉じる</button></div>` +
    `<div style="color:#666;font-size:12px;margin-bottom:6px">表示中の期間: ${esc(range[0] || "")}〜${esc(range[range.length - 1] || "")}　（期間を広げるには画面の「1ヶ月」で表示し直してから押してください）</div>` +
    `<table style="width:100%;border-collapse:collapse">${rows}</table>` +
    `<div style="color:#666;font-size:12px;margin-top:6px">時間帯は表のマスを選んで「次へ進む」で確認できます。NEW は前回このボタンを押したときになかった空きです。空き枠の先着申込は利用日の1カ月前の朝7時からです（「○/○ 7:00から受付」と出ているものはまだ申し込めません）。</div>`;
  panel.querySelectorAll("td").forEach((td) => (td.style.cssText = "border-top:1px solid #eee;padding:4px 6px;vertical-align:top"));
  document.body.appendChild(panel);
  document.getElementById("tw-suginami-close").onclick = () => panel.remove();
})();
