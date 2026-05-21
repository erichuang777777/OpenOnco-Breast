# open_issues.ps1
#
# Opens 6 [Chunk] issues on romeo111/task_torrent for the chunk specs drafted
# in this folder.
#
# Prerequisite: each chunk spec .md file must FIRST be pushed to
# romeo111/task_torrent under chunks/openonco/<chunk-id>.md, OR the spec
# bodies must already be on the romeo111/task_torrent default branch. See
# README.md in this folder for the recommended push sequence.
#
# Run from this folder:
#   cd docs/plans/proposed-chunks-2026-05-20-1500
#   pwsh ./open_issues.ps1
#
# Each command targets romeo111/task_torrent and reads its body from the
# issue_bodies/ subfolder.

$ErrorActionPreference = 'Stop'

$repo = 'romeo111/task_torrent'
$bodyDir = Join-Path $PSScriptRoot 'issue_bodies'

# Canonical labels for every OpenOnco chunk-task issue (all already exist on task_torrent).
$baseLabels = 'chunk-task,openonco,status-active,pilot-active'

# Per-chunk: title, body file, additional labels.
$chunks = @(
    @{
        title = '[Chunk] OpenOnco algo-branch-wiring-ovarian-2l'
        body  = 'algo-branch-wiring-ovarian-2l.md'
        extra = 'mechanical+judgment,good first issue'
    },
    @{
        title = '[Chunk] OpenOnco algo-branch-wiring-breast-1l'
        body  = 'algo-branch-wiring-breast-1l.md'
        extra = 'mechanical+judgment,good first issue'
    },
    @{
        title = '[Chunk] OpenOnco algo-branch-wiring-esoph-metastatic-1l'
        body  = 'algo-branch-wiring-esoph-metastatic-1l.md'
        extra = 'mechanical+judgment,good first issue'
    },
    @{
        title = '[Chunk] OpenOnco prevention-regimen-authoring-wave1'
        body  = 'prevention-regimen-authoring-wave1.md'
        extra = ''
    },
    @{
        title = '[Chunk] OpenOnco workup-thyroid-papillary'
        body  = 'workup-thyroid-papillary.md'
        extra = 'good first issue'
    },
    @{
        title = '[Chunk] OpenOnco hereditary-brca-carrier-surveillance'
        body  = 'hereditary-brca-carrier-surveillance.md'
        extra = ''
    }
)

foreach ($chunk in $chunks) {
    $bodyPath = Join-Path $bodyDir $chunk.body
    if (-not (Test-Path $bodyPath)) {
        Write-Error "Body file not found: $bodyPath"
        continue
    }

    $labels = if ($chunk.extra) { "$baseLabels,$($chunk.extra)" } else { $baseLabels }

    Write-Host "==> Opening: $($chunk.title)" -ForegroundColor Cyan

    & gh issue create `
        --repo $repo `
        --title $chunk.title `
        --body-file $bodyPath `
        --label $labels

    if ($LASTEXITCODE -ne 0) {
        Write-Error "gh issue create failed for $($chunk.title) (exit $LASTEXITCODE)"
    }
}

Write-Host "" -ForegroundColor Green
Write-Host "Done. Verify at: https://github.com/$repo/issues?q=is%3Aissue+is%3Aopen+label%3Achunk-task+label%3Astatus-active" -ForegroundColor Green
