# タスクスケジューラに登録する（毎日 6:00〜24:00 の20分ごと）
#   このフォルダで .\register_task.ps1
# 止めるとき: Unregister-ScheduledTask -TaskName テニス空き監視 -Confirm:$false
$ErrorActionPreference = "Stop"
$py = (Get-Command pythonw.exe).Source
$script = Join-Path $PSScriptRoot "tennis_watch.py"

$action = New-ScheduledTaskAction -Execute $py -Argument "`"$script`"" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At 6:00
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At 6:00 -RepetitionInterval (New-TimeSpan -Minutes 20) -RepetitionDuration (New-TimeSpan -Hours 18)).Repetition
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "テニス空き監視" -Action $action -Trigger $trigger -Settings $settings -Description "都立公園テニスコートの土日祝の空きを LINE 通知（tennis_watch.py）" -Force | Out-Null
Write-Host "登録しました: テニス空き監視（6:00〜24:00 の20分ごと）"
