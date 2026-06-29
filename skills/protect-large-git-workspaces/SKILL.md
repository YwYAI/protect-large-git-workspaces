---
name: protect-large-git-workspaces
description: Protect Git/Codex workspaces from accidental storage blowups. Use whenever Codex may run Git commands, create workspace snapshots/checkpoints, inspect or modify .git/objects, operate in directories containing any virtual machine, disk image, ISO file, exported appliance, emulator image, WSL export, backup, media archive, many generated files, large binaries, aggregate workspace candidate content over 500 MB, over 1000 candidate files, over 100 candidate files larger than 10 MB, any file over 100 MB, or propose cleanup of Git objects. Requires risk scanning, consequence disclosure, and explicit user confirmation before risky Git writes or deletions.
---

# Protect Large Git Workspaces

## Mandatory Rule

Do not run risky Git write operations until the user explicitly confirms after seeing the risk report.

Risky operations include:
- `git add`, `git add -A`, `git add .`, `git update-index`, `git hash-object`, `git commit` when new large files may be included.
- Codex workspace snapshot/checkpoint actions or commands that write under `.git/objects`.
- `git gc`, `git prune`, deletion of `.git`, deletion of `.git/objects`, or deletion of `tmp_obj_*`.
- Any recursive file move/delete in a workspace containing virtual machine or disk-image files.

Allowed without confirmation:
- Read-only inspection such as `git status --short --ignored`, `git rev-parse`, `git ls-files`, `git count-objects -vH`, `Get-ChildItem`, `rg`, and process/log inspection.
- Running the bundled read-only scanner `scripts/scan_large_git_workspace.py`.
- Adding or updating `.gitignore` to exclude clearly unsafe large generated artifacts, if the edit itself is small and scoped.

## Active Scan

When the user asks to scan, check, audit, diagnose, or look for existing large Git workspace risk, run the bundled read-only scanner from this skill:

```bash
python scripts/scan_large_git_workspace.py /path/to/workspace
```

Use the available Python executable for the environment. The scanner reports whether risk already exists, including `.git/objects` bloat, `tmp_obj_*` garbage, large files, risky extensions, suspicious directories, aggregate candidate size, and many-small-file risk. It does not modify files.

## Risk Scan

Before any risky operation, inspect the workspace for:
- Files larger than 100 MB.
- Aggregate workspace candidate content larger than 500 MB.
- More than 1000 workspace candidate files.
- More than 100 candidate files larger than 10 MB.
- VM and disk-image extensions: `.vdi`, `.vmdk`, `.vhd`, `.vhdx`, `.qcow2`, `.qed`, `.hdd`, `.img`, `.raw`, `.sav`, `.vmem`, `.vmss`, `.vmsn`, `.nvram`, `.iso`, `.viso`, `.ova`, `.ovf`.
- VM platform and bundle directories: VirtualBox, VMware, Hyper-V, QEMU/UTM, Parallels, emulator, WSL export, `Snapshots/`, `*.pvm/`, `*.utm/`, `*.vmwarevm/`.
- Backup/archive/media extensions likely to be large: `.zip`, `.7z`, `.rar`, `.tar`, `.gz`, `.mp4`, `.mov`, `.mkv`.
- Generated or dependency directories likely to contain many files: `node_modules/`, `.venv/`, `venv/`, `dist/`, `build/`, `target/`, `.cache/`, `vendor/`, `coverage/`, `.next/`, `.nuxt/`.
- Existing Git object bloat: `.git/objects`, `.git/objects/pack`, `.git/objects/*/tmp_obj_*`.

On Windows, prefer commands like:

```powershell
git status --short --ignored
git count-objects -vH
Get-ChildItem -LiteralPath . -Recurse -Force -File |
  Where-Object { $_.FullName -notmatch '\\.git\\' -and $_.Length -gt 100MB } |
  Sort-Object Length -Descending |
  Select-Object -First 30 FullName,Length,LastWriteTime
$candidateFiles = Get-ChildItem -LiteralPath . -Recurse -Force -File |
  Where-Object { $_.FullName -notmatch '\\.git\\' }
$candidateFiles |
  Measure-Object Length -Sum |
  Select-Object Count,Sum
```

On macOS/Linux, use equivalent read-only commands:

```bash
git status --short --ignored
git count-objects -vH
find . -path ./.git -prune -o -type f -size +100M -print
find . -path ./.git -prune -o -type f -print | wc -l
du -sh . 2>/dev/null
```

These scans are conservative workspace estimates. If the exact Git candidate set matters, cross-check with `git status --short --ignored` before deciding what would actually be added.

Treat aggregate size as risky even when every individual file is below 100 MB. For example, 2000 files of 5 MB each can still write about 10 GB of object data.

## Confirmation Format

If risk exists, stop and ask for confirmation in the user's current language. If the user uses Chinese, ask in Chinese. Include:
- The exact command or operation you want to run.
- The large paths involved and their approximate sizes.
- The candidate file count and aggregate candidate size when many smaller files create the risk.
- The likely consequence, such as writing tens or hundreds of GB into `.git/objects`, leaving `tmp_obj_*`, increasing disk usage, or deleting Git history.
- A safer alternative, usually adding `.gitignore`, moving the work to a non-VM directory, or deleting only confirmed Git temporary garbage.

Require an explicit affirmative response. Accept only unambiguous approval, such as the exact ASCII phrase `CONFIRM-GIT-RISK` or clear confirmation in the user's current language. For Chinese users, an equivalent phrase meaning "I accept the Git large-file risk" is acceptable. Do not treat silence, ambiguous wording, or general approval as permission.

Use this confirmation wording pattern:

```text
I detected large or VM-related files in this workspace. Running the requested Git/Codex operation may write very large objects into .git/objects, leave tmp_obj_* garbage if interrupted, or delete Git history if cleanup commands are involved.

If the risk comes from many smaller files, report the total candidate file count and aggregate size before continuing.

Safer alternatives: add ignore rules first, move work to a non-VM workspace, or delete only confirmed Git temporary garbage.

If you still want me to run the risky operation, reply with CONFIRM-GIT-RISK or the equivalent confirmation phrase in your language.
```

When speaking to the user, translate the warning naturally into the user's current language.

## Default Safe Behavior

When the workspace contains VM or large binary files:
- Prefer not to use that directory as a Git/Codex coding workspace.
- Add ignore rules before any Git write:

```gitignore
*.vdi
*.vmdk
*.vhd
*.vhdx
*.qcow2
*.qed
*.hdd
*.img
*.raw
*.sav
*.vmem
*.vmss
*.vmsn
*.vmsd
*.iso
*.viso
*.ova
*.ovf
*.nvram
*.vbox-prev
*.pvm/
*.utm/
*.vmwarevm/
Snapshots/
*/Snapshots/
node_modules/
.venv/
venv/
dist/
build/
target/
.cache/
coverage/
.next/
.nuxt/
```

- If cleanup is requested, first list what would be removed. Do not delete `.git`, `.git/objects`, or `tmp_obj_*` until the user confirms the exact scope.

## Evidence Handling

When diagnosing an existing blowup:
- Preserve evidence before cleanup: process command lines, `.git/objects` size summaries, `git count-objects -vH`, relevant Codex session log paths, and hourly object write distribution.
- Clearly distinguish model-initiated commands, Codex Desktop background behavior, user commands, and third-party application writes.
