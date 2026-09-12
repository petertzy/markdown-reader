param(
    [ValueFromRemainingArguments()]$RemainingArgs
)

$bashPath = "C:\Program Files\Git\bin\bash.exe"
$scriptPath = Join-Path $PSScriptRoot "dev-tauri.sh"

if (-not (Test-Path $bashPath)) {
    Write-Error "Git Bash not found at $bashPath. Please install Git for Windows."
    exit 1
}

# Если переданы аргументы (путь к файлу), пробрасываем их
if ($RemainingArgs.Count -gt 0) {
    & $bashPath $scriptPath $RemainingArgs
} else {
    & $bashPath $scriptPath
}
