# Runs every inspection/*.query.json against the smFinance connector and saves the results
# to inspection/out (ignored by Git: query results are data and never committed).
$ErrorActionPreference = "Continue"
New-Item -ItemType Directory -Force -Path inspection/out | Out-Null
Get-ChildItem inspection -Filter *.query.json | Sort-Object Name | ForEach-Object {
    $name = $_.BaseName -replace '\.query$',''
    Write-Host "== $name"
    npx rayfin connector invoke smFinance executeQuery --file "inspection/$($_.Name)" --output-file "inspection/out/$name.json" --json *> "inspection/out/$name.log"
    if ($LASTEXITCODE -ne 0) { Write-Host "   failed (see inspection/out/$name.log)" -ForegroundColor Red } else { Write-Host "   ok" }
}
