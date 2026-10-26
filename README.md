# tennis_watch — 都立公園テニスコート空き通知

都立公園スポーツレクリエーション予約システムを見に行き、**土日祝の空きが新しく出たら LINE に通知**します。
対象は日比谷・浮間・城北中央（照明有/無）・善福寺川緑地・光が丘・石神井・井の頭・武蔵野中央・小金井の人工芝コート、計10施設です。

- 通知が届くのは、前回の確認時にはなかった空き枠が見つかったときだけです。いったん埋まった枠が再び空いた場合も通知します。
- 確認するのは当月の受付期間内だけです。翌月分は抽選期間中のため「受付期間外」と表示され、対象外になります。
- LINE の無料枠は月200通で、ほかの通知と共用する想定です。このため、この監視の通知は**月120通**で止まります。
- 確認が3回続けて失敗したときは、1回だけ警告が届きます。
- 杉並区（さざんかねっと）は Cloudflare Turnstile（ボット判定）があるため対象外です。
- Cloudflare Workers では動きません。都のサイトが古い暗号方式（CBC のみ）しか提供しておらず、Workers がそれに対応していないためです。

## PC で動かす（稼働中）

タスク名は「テニス空き監視」です。毎日 6:00〜24:00 に20分ごとに実行し、1回あたり約2分かかります。

```
py tennis_watch.py --dry-run     # いまの土日祝の空きを表示（通知しない）
.\register_task.ps1              # タスクを登録・再登録する
```

- ログ: `log/YYYYMM.log`
- 前回の状態: `state.json`
- LINE の認証情報: `../kids_admin/common/line_secret.json`

## GitHub Actions に移す

1. git を導入し、GitHub に**公開**リポジトリを作って、このフォルダを push します。
   1回の実行に約3分かかるため、非公開リポジトリでは無料枠（月2000分）を超えます。
   公開されるのはコードだけで、認証情報は Secrets に入るので公開されません。
2. Settings > Secrets and variables > Actions に `LINE_TOKEN` と `LINE_USER_ID` を登録します。
   値は `kids_admin/common/line_secret.json` の channel_access_token と user_id です。
3. Actions タブで `tennis_watch` を手動実行（Run workflow）し、正常に終わるか確認します。
4. **PC のタスクを止めます**（両方動かしたままだと通知が二重に届きます）。

   ```
   Unregister-ScheduledTask -TaskName テニス空き監視 -Confirm:$false
   ```

GitHub の制約:
- 実行時刻が数分〜数十分ずれることがあります。
- 60日間リポジトリに更新がないと、定期実行が自動で止まります。

## 監視対象を変える

`tennis_watch.py` の `TARGETS` を編集します。公園コード（bld）と施設コード（inst）は予約サイトの空き状況検索から取得したものです。
曜日の条件は `HOLIDAY_FLGS` で指定します（1=平日, 2=土, 3=日, 4=祝）。
