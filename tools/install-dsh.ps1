#!/usr/bin/env pwsh
# Install novel-ledger into a DSH skills root as a directory link (Windows junction,
# POSIX symlink), so `git pull` in this repo updates the installed skill in place.
#
#   pwsh tools/install-dsh.ps1                 # install into the user root
#   pwsh tools/install-dsh.ps1 -Remove         # uninstall
#   pwsh tools/install-dsh.ps1 -Root D:\other  # install into another skills root
#
# DSH discovers skills from several roots, in priority order:
#   <projectRoot>/.dsh/skills (100), <projectRoot>/.agents/skills (200),
#   customSkillDirs (300), $DSH_HOME/skills (400), $DSH_AGENTS_HOME/skills (500)
# The default here is the user root (400), which covers every workspace you open.
param(
    [string]$Root = '',
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$name = Split-Path -Leaf $repo

if (-not (Test-Path (Join-Path $repo 'SKILL.md'))) {
    throw "SKILL.md not found in $repo - run this script from the novel-ledger repository."
}
if (-not $Root) {
    $home_dsh = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $HOME '.dsh' }
    $Root = Join-Path $home_dsh 'skills'
}
$target = Join-Path $Root $name
Write-Host "repo   : $repo"
Write-Host "target : $target"

if ($Remove) {
    if (-not (Test-Path $target)) { Write-Host 'nothing installed at that path'; exit 0 }
    $item = Get-Item $target -Force
    if ($item.LinkType -or $item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        # Remove the link only; never recurse into the repository it points at.
        [IO.Directory]::Delete($target, $false)
        Write-Host 'removed link'
    } else {
        throw "$target is a real directory, not a link - refusing to delete it. Remove it by hand if that is intended."
    }
    exit 0
}

New-Item -ItemType Directory -Path $Root -Force | Out-Null
if (Test-Path $target) {
    $item = Get-Item $target -Force
    if ($item.LinkType -or $item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        $current = @($item.Target)[0]
        if ($current -and ($current -eq $repo -or $current -eq "\\?\$repo")) {
            Write-Host 'already linked to this repository'
        } else {
            throw "$target is a link to $current - remove it first (-Remove) if that mapping should change."
        }
    } else {
        throw "$target is a real directory - move it aside first so the link does not shadow it."
    }
} else {
    if ($IsWindows -or $env:OS -eq 'Windows_NT') {
        # Junctions need no elevation and survive without Developer Mode.
        $out = cmd /c mklink /J "`"$target`"" "`"$repo`"" 2>&1
        if ($LASTEXITCODE -ne 0) { throw "mklink failed: $out" }
    } else {
        New-Item -ItemType SymbolicLink -Path $target -Target $repo | Out-Null
    }
    Write-Host 'linked'
}

# Verify the way the harness sees it: frontmatter discovery plus a real command run.
$skill = Join-Path $target 'SKILL.md'
if (-not (Test-Path $skill)) { throw "verification failed: $skill is not readable through the link" }
$head = Get-Content $skill -TotalCount 5 -Encoding UTF8
Write-Host '--- SKILL.md head ---'
$head | ForEach-Object { Write-Host $_ }
$python = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' }
          elseif (Get-Command python3 -ErrorAction SilentlyContinue) { 'python3' }
          else { $null }
if ($python) {
    $entry = Join-Path (Join-Path $target 'scripts') 'novel.py'
    $version = & $python $entry --version
    Write-Host "cli    : novel.py --version -> $version"
} else {
    Write-Host 'cli    : python not found; skipped the CLI check'
}
Write-Host 'done - the skill is discovered from this root on the next catalog refresh.'
