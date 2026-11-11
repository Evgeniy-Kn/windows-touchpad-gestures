# Добавляет «Жесты тачпада» в автозагрузку (ярлык в shell:startup) и сразу запускает.
# Удалить из автозагрузки: удалить ярлык «Жесты тачпада.lnk» из папки shell:startup.
$script = Join-Path $PSScriptRoot 'touchpad_gestures.pyw'
$pythonw = (Get-Command pyw -ErrorAction Stop).Source
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Жесты тачпада.lnk'

$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = $pythonw
$s.Arguments = "`"$script`""
$s.WorkingDirectory = $PSScriptRoot
$s.Save()

Start-Process $pythonw "`"$script`""
"Готово: $lnk"
