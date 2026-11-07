<#
check_render.ps1: open a resume in Microsoft Word (on a copy, read-only) and report what the page
really looks like: page count, paragraphs that wrap to a second line, every hyperlink and where it
points. It also saves a PDF, and a picture of page 1 (preview.png in <data folder>\resume\) when pdftoppm is installed.

Usage (Windows PowerShell 5.1 or PowerShell 7):
  powershell -ExecutionPolicy Bypass -File tools\check_render.ps1 -Docx <data folder>\resume\live\Resume.docx
  powershell -ExecutionPolicy Bypass -File tools\check_render.ps1 -Docx Resume.docx -OutPdf C:\temp\Resume.pdf
  Add -MaxPages 2 if the resume is allowed two pages (default 1).

Exit codes: 0 = done (read the report), 1 = file problem, 2 = Word is not installed (use check_render.sh
with LibreOffice instead).

What the report means:
  WRAPS     a paragraph whose first and last characters are on different lines. For a bullet that
            should fit on one line, that means it is too long. Shorten it.
  PAGES     more pages than -MaxPages means something has to go.
  LINKS     check every target. A link that points to the wrong place is easy to miss.
The original file is never changed. Word is always closed at the end, even after an error.
#>
param(
    [Parameter(Mandatory = $true)][string]$Docx,
    [string]$OutPdf,
    [int]$MaxPages = 1
)

$src = Resolve-Path -LiteralPath $Docx -ErrorAction SilentlyContinue
if (-not $src) { Write-Output "File not found: $Docx"; exit 1 }
$src = $src.Path
if (-not $OutPdf) { $OutPdf = [IO.Path]::ChangeExtension($src, '.pdf') }
$OutPdf = [IO.Path]::GetFullPath($OutPdf)

# Work on a temporary copy so the real file can't be touched or locked.
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("render-check-" + [guid]::NewGuid().ToString('N') + '.docx')
Copy-Item -LiteralPath $src -Destination $tmp

$word = $null
$doc = $null
try {
    try { $word = New-Object -ComObject Word.Application }
    catch {
        Write-Output "Microsoft Word is not installed (or can't start), so this check can't run."
        Write-Output "Fallback: install LibreOffice and run tools/check_render.sh, or open the file in Word"
        Write-Output "or Google Docs yourself and look for bullets that wrap to a second line."
        exit 2
    }
    $word.Visible = $false
    $word.DisplayAlerts = 0
    # Open(FileName, ConfirmConversions, ReadOnly, AddToRecentFiles)
    $doc = $word.Documents.Open($tmp, $false, $true, $false)
    $doc.Repaginate()

    $pages = $doc.ComputeStatistics(2)   # 2 = pages
    Write-Output "Resume: $([IO.Path]::GetFileName($src))"
    if ($pages -gt $MaxPages) {
        Write-Output "PAGES: $pages (limit $MaxPages). Too long: cut or shorten something."
    } else {
        Write-Output "PAGES: $pages (limit $MaxPages). OK."
    }

    Write-Output ""
    Write-Output "WRAPS (paragraphs that run onto a second line):"
    $wraps = 0
    foreach ($p in $doc.Paragraphs) {
        $text = $p.Range.Text.Trim()
        if ($text.Length -eq 0) { continue }
        # Information(10) = the line number of that character on its page.
        $first = $p.Range.Characters.First.Information(10)
        $last = $p.Range.Characters.Last.Information(10)
        $firstPage = $p.Range.Characters.First.Information(3)   # 3 = page number
        $lastPage = $p.Range.Characters.Last.Information(3)
        if ($first -ne $last -or $firstPage -ne $lastPage) {
            $wraps++
            $short = if ($text.Length -gt 80) { $text.Substring(0, 80) + '...' } else { $text }
            Write-Output ("  {0,4} chars, lines {1} to {2}: {3}" -f $text.Length, $first, $last, $short)
        }
    }
    if ($wraps -eq 0) { Write-Output "  none. Every paragraph fits on one line." }
    else { Write-Output "  $wraps paragraph(s) wrap. A bullet that wraps is too long. A summary paragraph may wrap on purpose." }

    Write-Output ""
    Write-Output "LINKS:"
    if ($doc.Hyperlinks.Count -eq 0) { Write-Output "  none found." }
    foreach ($h in $doc.Hyperlinks) {
        $shown = $h.TextToDisplay
        $target = $h.Address
        if ($h.SubAddress) { $target = "$target#$($h.SubAddress)" }
        Write-Output "  '$shown' -> $target"
    }
    Write-Output "  Check that each target matches its text."

    # 17 = PDF
    $doc.ExportAsFixedFormat($OutPdf, 17)
    Write-Output ""
    Write-Output "PDF saved: $OutPdf"

    # Picture of page 1: <data folder>\resume\preview.png (JOBHUNT_DATA_DIR or the saved choice), else next to the resume.
    $pdftoppm = Get-Command pdftoppm -ErrorAction SilentlyContinue
    if ($pdftoppm) {
        $data = $env:JOBHUNT_DATA_DIR
        if (-not $data) {
            $saved = Join-Path $env:APPDATA 'job-search-assistant\config.json'
            if (Test-Path $saved) { try { $data = (Get-Content $saved -Raw -Encoding utf8 | ConvertFrom-Json).data_dir } catch { $data = $null } }
        }
        $previewDir = if ($data) { Join-Path $data 'resume' } else { Split-Path $src -Parent }
        New-Item -ItemType Directory -Force $previewDir | Out-Null
        & $pdftoppm.Source -png -r 150 -f 1 -l 1 -singlefile $OutPdf (Join-Path $previewDir 'preview')
        if ($LASTEXITCODE -eq 0) { Write-Output "Picture of page 1: $(Join-Path $previewDir 'preview.png') (open it and look before sending anything)." }
    }
    exit 0
}
catch {
    Write-Output "check_render.ps1 stopped with an error: $($_.Exception.Message)"
    exit 1
}
finally {
    if ($doc) { $doc.Close(0) | Out-Null }   # 0 = don't save
    if ($word) { $word.Quit() | Out-Null; [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
    Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
}
