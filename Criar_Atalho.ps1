$WshShell = New-Object -ComObject WScript.Shell
$ShortcutPath = "$([Environment]::GetFolderPath('Desktop'))\Amicando.lnk"
$TargetFile = "$PSScriptRoot\Abrir_Amicando.bat"
$IconFile = "$PSScriptRoot\logo.ico"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "cmd.exe"
$Shortcut.Arguments = "/c `"$TargetFile`""
$Shortcut.WorkingDirectory = "$PSScriptRoot"
$Shortcut.IconLocation = "$IconFile"
$Shortcut.Description = "Sistema de Gestão Amicando"
$Shortcut.Save()

Write-Host "Atalho criado na sua Área de Trabalho!" -ForegroundColor Green
