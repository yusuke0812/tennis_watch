"""suginami_bookmarklet.js から、ブックマーク登録用の install.html を作る。

  py make_bookmarklet.py
"""
import os
import re
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "suginami_bookmarklet.js"), encoding="utf-8") as f:
    src = f.read()
# 行頭コメントを落とし、行を詰める（文字列中の // は行頭ではないので影響しない）
lines = [ln.strip() for ln in src.splitlines() if ln.strip() and not ln.strip().startswith("//")]
code = "\n".join(lines)
code = re.sub(r"\s*\n\s*", "\n", code)
href = "javascript:" + urllib.parse.quote(code, safe="")  # 全部エンコードして HTML 属性に安全に入れる

page = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>杉並テニス空きボタン</title>
<style>
body{{font:16px/1.7 sans-serif;max-width:640px;margin:24px auto;padding:0 16px;color:#222;background:#fff}}
a.bm{{display:inline-block;padding:10px 18px;background:#2a7;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold}}
ol li{{margin-bottom:6px}} small{{color:#666}}
</style></head><body>
<h1>杉並テニス空きボタン</h1>
<p>杉並区さざんかねっとの「施設別空き状況」画面で押すと、土日祝の「空き」「一部空き」を一覧にします。
前回押したときになかった空きには <b style="color:#d33">NEW</b> が付きます。</p>
<p><a class="bm" href="{href}">🎾 杉並テニス空き</a></p>
<h2>登録のしかた（Chrome / Edge）</h2>
<ol>
<li>ブックマークバーを表示します（Ctrl + Shift + B）。</li>
<li>上の緑のボタン「🎾 杉並テニス空き」を、ブックマークバーへドラッグして離します。</li>
</ol>
<h2>使いかた</h2>
<ol>
<li>さざんかねっとで「利用目的から探す → スポーツ施設 → その他屋外スポーツ → テニス（硬式）→ 検索 → 4施設にチェック → 次へ進む」と進みます。</li>
<li>表示期間を「1ヶ月」にして表示すると、先までまとめて確認できます。</li>
<li>表が出たら、ブックマークバーの「🎾 杉並テニス空き」を押します。</li>
</ol>
<p><small>このボタンは画面に表示済みの内容を読むだけで、サイトへの通信や操作はしません。前回の結果はこのブラウザの中にだけ保存されます。</small></p>
</body></html>
"""
with open(os.path.join(HERE, "install.html"), "w", encoding="utf-8") as f:
    f.write(page)
print(f"install.html を作成しました（ボタンの長さ {len(href)} 文字）")
