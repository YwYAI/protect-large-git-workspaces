# Protect Large Git Workspaces

Languages: English | [中文](docs/README.zh-CN.md)

A Codex skill that prevents accidental Git object-store blowups when an agent works inside directories containing virtual machines, disk images, ISO files, backups, generated outputs, media assets, or many small files.

The goal is not to make Git a better large-file storage system. The goal is to make Codex stop before risky Git operations, scan the workspace, explain the consequences, offer safer alternatives, and require explicit human confirmation.

## Quick Start

### 1. Install The Skill

Clone this repository and copy the skill folder into your Codex skills directory:

```bash
git clone https://github.com/YwYAI/protect-large-git-workspaces.git
cd protect-large-git-workspaces
mkdir -p ~/.codex/skills
cp -R skills/protect-large-git-workspaces ~/.codex/skills/
```

Windows PowerShell:

```powershell
git clone https://github.com/YwYAI/protect-large-git-workspaces.git
cd protect-large-git-workspaces
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\skills" | Out-Null
Copy-Item -Recurse -Force ".\skills\protect-large-git-workspaces" "$env:USERPROFILE\.codex\skills\"
```

Open a new Codex session after installing.

### 2. Ask Codex To Check A Workspace

Use the skill explicitly:

```text
Use $protect-large-git-workspaces to check whether this directory is safe as a Git workspace.
```

Or ask naturally:

```text
Can I run git add . in this folder?
Why is .git/objects so large?
This folder contains VM files. Can Codex work here safely?
Clean Git temporary objects without deleting history.
```

### 3. Run The Read-Only Active Scanner

After installing the skill, Codex can run the bundled scanner to show whether the problem already exists and list suspicious files and folders:

```bash
python ~/.codex/skills/protect-large-git-workspaces/scripts/scan_large_git_workspace.py /path/to/workspace
```

Windows PowerShell:

```powershell
python "$env:USERPROFILE\.codex\skills\protect-large-git-workspaces\scripts\scan_large_git_workspace.py" "C:\path\to\workspace"
```

The scanner is read-only. It reports large files, risky extensions, suspicious directories, aggregate many-small-file risk, `.git/objects` size, and `tmp_obj_*` garbage. It exits with code `2` when risk is detected and `0` when no obvious risk is found.

### 4. Read The Risk Report

Codex should report:

- risk level and the assessment standards that matched
- large files and risky extensions
- candidate file count and aggregate size
- generated/dependency/cache directories
- `.git/objects` size and `tmp_obj_*` garbage when relevant
- the exact command it wants to run
- evidence used for any cleanup recommendation
- safer alternatives such as `.gitignore` or moving code to a clean workspace

### 5. Confirm Only If You Accept The Risk

If Codex needs to run a risky Git write or cleanup operation, it will ask for explicit confirmation. Use one of these tokens only when you understand and accept the risk:

```text
CONFIRM-GIT-RISK
确认承担Git大文件风险
```

If you do not want to continue, ask Codex to apply a safer alternative instead, such as adding `.gitignore` rules or moving the code files into a separate repository.

## When To Use This

Use this skill when a Codex workspace may contain:

- VirtualBox files such as `.vdi`, `.sav`, `.vbox-prev`.
- VMware files such as `.vmdk`, `.vmem`, `.vmss`, `.vmwarevm/`.
- Hyper-V disks such as `.vhd`, `.vhdx`.
- QEMU / UTM images such as `.qcow2`, `.qed`, `.utm/`.
- Parallels virtual machines such as `.pvm/`, `.hdd`.
- Android emulator images, WSL exports, system install ISOs, OVA/OVF exports.
- Large archives, backups, media files, database dumps, or any file over 100 MB.
- Many small generated files whose aggregate size is large.
- Repositories where `.git/objects` is already unexpectedly large or contains many `tmp_obj_*` files.

Typical user requests that should trigger this skill:

```text
Commit this whole directory.
Run git add .
Clean up .git/objects.
Why is this repository's .git directory huge?
Can Codex work inside this VM directory?
Run git gc.
Delete tmp_obj_* files.
```

## Problem Statement

Git writes added file content into `.git/objects`. For source code, that is expected. For VM disks, memory snapshots, ISO images, exported appliances, dependency folders, build outputs, or thousands of generated files, it can be disastrous.

For example, if a 40 GB virtual disk is processed by `git add .` or `git hash-object`, Git may try to write it into `.git/objects`. Even when no single file is larger than 100 MB, a few thousand 5-50 MB files can still write many GB of object data in a short time.

Common symptoms:

- `.git/objects` grows by tens or hundreds of GB.
- Hundreds of `tmp_obj_*` files appear under `.git/objects`.
- Git commands become slow, hang, or time out.
- Disk space disappears unexpectedly.
- The user mistakes the cause for VM software, sync tools, or system updates.
- Cleanup becomes risky because deleting `.git` or object files can destroy history or evidence.

This skill addresses the missing risk check before an agent performs Git writes or cleanup.

## Design Goals

The skill is designed like a safety control in an industrial workflow: identify the environment, isolate dangerous actions, present consequences, and require explicit confirmation before proceeding.

### Visible Risk

Codex must scan before risky operations and explain risk in the user's current language. The user should not need to understand Git internals to know why an operation is dangerous.

### Safe Defaults

Do not write large or numerous files into `.git/objects` by default. Prefer read-only diagnosis, `.gitignore`, or moving code work into a non-VM workspace.

### Explicit Confirmation

Ambiguous replies are not authorization. The default confirmation tokens are:

```text
CONFIRM-GIT-RISK
确认承担Git大文件风险
```

The English token is language-neutral and easy to copy. The Chinese token is included for Chinese readers.

### Recoverability

Before cleanup commands such as deleting `tmp_obj_*`, pruning, garbage collection, or deleting `.git`, Codex must list the scope and explain what may be lost.

### Portability

The rule is not tied to one VM name or platform. VirtualBox, VMware, Hyper-V, QEMU, UTM, Parallels, WSL exports, Android emulators, and similar disk-image workflows all follow the same risk model.

## Protection Model

The skill separates operations into read-only inspection and high-risk writes/deletions.

### Read-Only Operations

These are usually safe to run without confirmation:

```bash
git status --short --ignored
git rev-parse --show-toplevel
git ls-files
git count-objects -vH
```

Windows PowerShell checks:

```powershell
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

macOS / Linux checks:

```bash
find . -path ./.git -prune -o -type f -size +100M -print
find . -path ./.git -prune -o -type f -print | wc -l
du -sh . 2>/dev/null
git status --short --ignored
git count-objects -vH
```

For more precise aggregate statistics on GNU/Linux, `du --files0-from` may be used. macOS ships BSD `du`, so use `du -sh` unless GNU coreutils is installed.

### High-Risk Operations

These require a risk scan and explicit confirmation when risky files or aggregate risk are present:

```bash
git add
git add .
git add -A
git update-index
git hash-object
git commit
git gc
git prune
```

Also risky:

- Deleting `.git`.
- Deleting `.git/objects`.
- Deleting `.git/objects/*/tmp_obj_*`.
- Recursive move/delete/cleanup inside VM or disk-image directories.
- Any Codex workspace snapshot, checkpoint, or turn diff operation that may write under `.git/objects`.

## Risk Thresholds

The skill treats a workspace as risky if any of these are true:

- Any file is over 100 MB.
- Candidate files have aggregate size over 500 MB.
- There are over 1000 candidate files.
- More than 100 candidate files are larger than 10 MB.
- The workspace contains VM disks, disk images, snapshots, or ISO-like files.
- The workspace contains generated/dependency/cache directories such as `node_modules/`, `.venv/`, `dist/`, `build/`, `target/`, `.cache/`, `.next/`.
- `.git/objects` is already unusually large.
- `.git/objects` contains many `tmp_obj_*` files.

The 100 MB threshold is intentionally conservative. It aligns with GitHub's single-file limit and serves as a warning threshold, not an absolute ban.

## Risk Assessment Standard

Risk reports should be explainable and auditable. Codex should state the risk level, the matched thresholds, the evidence used, and any unknowns.

- **Critical**: proposed deletion of `.git`, `.git/objects`, Git history, or recursive cleanup in a VM/disk-image workspace; `.git/objects` over 5 GiB; `tmp_obj_*` over 1 GiB or 100 files; any risky VM/disk/snapshot/image/archive/media file over 1 GiB; aggregate candidate content over 10 GiB.
- **High**: any file over 100 MiB; aggregate candidate content over 500 MiB; more than 1000 candidate files; more than 100 files over 10 MiB; VM/disk-image/archive/media extensions; suspicious generated/cache/dependency directories; `.git/objects` over 500 MiB or any `tmp_obj_*`.
- **Medium**: generated/cache/dependency directories or risky extensions exist but thresholds are below High; aggregate candidate content is 100-500 MiB; unusual recent writes to `.git/objects` need investigation.
- **Low**: no risky extensions, no suspicious directories, no large files, aggregate candidate content below 100 MiB, and `.git/objects` has no obvious bloat.

The bundled scanner prints this assessment standard with its findings, so a user can see why a workspace was classified as Critical, High, Medium, or Low.

## Workflow

### 1. Scan First

Codex checks large files, aggregate size, candidate file count, VM/image file extensions, generated directories, and existing Git object bloat.

Common risky patterns:

```text
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
```

### 2. Explain The Risk

Codex must state:

- The exact command or operation it wants to run.
- Which paths are involved.
- The largest relevant files.
- Candidate file count and aggregate size if many small files create the risk.
- Likely consequences, such as object-store growth, `tmp_obj_*` leftovers, slow Git operations, or history loss.
- A safer alternative.

Example for a large VM image:

```text
I detected VM or disk-image files in this workspace, possibly tens of GB.

Running `git add .` or continuing a workspace snapshot may write those files into `.git/objects`, consuming tens or hundreds of GB. If interrupted, Git may leave `tmp_obj_*` garbage.

Safer options: add ignore rules first, move code into a non-VM workspace, or only clean confirmed Git temporary garbage.

If you still want me to continue, reply with one of:

CONFIRM-GIT-RISK
确认承担Git大文件风险
```

Example for many smaller files:

```text
I did not find a single file over 100 MB, but I found 3200 candidate files with an aggregate size of about 8.6 GB.

Running `git add .` or continuing a workspace snapshot may still write many GB into `.git/objects`. It can also make Git status, diff, and garbage collection slow.

Safer options: check whether these are build artifacts, dependency folders, cache directories, logs, screenshot sequences, or frame outputs; if so, add them to `.gitignore`.

If you still want me to continue, reply with one of:

CONFIRM-GIT-RISK
确认承担Git大文件风险
```

### 3. Wait For Explicit Confirmation

Accept examples:

```text
CONFIRM-GIT-RISK
确认承担Git大文件风险
confirm execution
```

Do not accept:

```text
go ahead
maybe
you decide
continue
probably fine
```

### 4. Prefer Safer Alternatives

Default `.gitignore` suggestions:

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

## Installation

Repository layout:

```text
protect-large-git-workspaces/
  README.md
  LICENSE
  skills/
    protect-large-git-workspaces/
      SKILL.md
      agents/
        openai.yaml
      scripts/
        scan_large_git_workspace.py
  docs/
    README.zh-CN.md
    large-git-safety.zh-CN.md
```

Install to Codex on macOS/Linux:

```bash
mkdir -p ~/.codex/skills
cp -R skills/protect-large-git-workspaces ~/.codex/skills/
```

Install on Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\skills" | Out-Null
Copy-Item -Recurse -Force ".\skills\protect-large-git-workspaces" "$env:USERPROFILE\.codex\skills\"
```

Open a new Codex session after installation.

## Usage

Explicit use:

```text
Use $protect-large-git-workspaces to check whether this directory is safe as a Git workspace.
```

Natural-language requests that should trigger it:

```text
Why is .git/objects so large?
Can I run git add . here?
Clean Git temporary objects without deleting history.
This folder contains VM files. Can Codex work here safely?
Scan this workspace and list suspicious files and folders.
```

Run the scanner directly:

```bash
python ~/.codex/skills/protect-large-git-workspaces/scripts/scan_large_git_workspace.py /path/to/workspace
```

## What It Helps With

### Git Object Store Blowups

Symptoms:

- `.git/objects` uses tens or hundreds of GB.
- `git count-objects -vH` shows many loose objects or garbage.
- Many `.git/objects/xx/tmp_obj_*` files exist.

Behavior:

- Diagnose object-store size first.
- Identify large objects and temporary objects.
- Avoid deleting history or evidence without confirmation.

### VM Directories Used As Git Workspaces

Symptoms:

- Workspace contains `.vdi`, `.vmdk`, `.vhdx`, `.qcow2`, `.sav`, `.iso`.
- The user or agent is about to run `git add .`.

Behavior:

- Block direct Git writes.
- Explain consequences.
- Suggest `.gitignore` or a separate code workspace.

### Many Small Files Creating Aggregate Risk

Symptoms:

- No single file exceeds 100 MB.
- Thousands or tens of thousands of files are untracked or changed.
- Aggregate size reaches hundreds of MB or several GB.
- Common sources: `node_modules/`, `.venv/`, `dist/`, `build/`, `target/`, `.cache/`, logs, screenshot sequences, frame outputs.

Behavior:

- Count candidate files and estimate aggregate size.
- Trigger confirmation when aggregate thresholds are crossed.
- Prefer ignoring generated, dependency, and cache directories.

### Agent Snapshot Side Effects

Symptoms:

- The user did not manually run `git add`, but `.git/objects` still grows.
- Codex or another agent tool creates snapshots, diffs, or checkpoints.

Behavior:

- Require risk scanning before visible agent-initiated writes to `.git/objects`.
- Clearly state that the skill can guide compliant agent behavior, not guarantee interception of all product-internal background mechanisms.

### Safer Cleanup

Symptoms:

- User wants to delete `.git`, `.git/objects`, or `tmp_obj_*`.
- Disk space is low.

Behavior:

- List what would be removed.
- Explain what may be lost.
- Distinguish temporary garbage from possibly referenced history.
- Provide evidence before calling anything safe to delete.
- Require confirmation before deletion.

## Deletion Evidence Standard

Do not treat "large", "temporary-looking", or "generated-looking" as enough proof for deletion.

Before Codex says a file or folder is safe to delete, it should provide evidence such as:

- exact paths, sizes, counts, and last-write times
- logs or command records showing what generated the files
- timestamp correlation with a known interrupted Git, build, package-manager, VM, or Codex operation
- proof that no related process is still active
- for `.git/objects/tmp_obj_*`, evidence that the files are temporary Git write leftovers, not normal loose objects
- for generated folders such as `node_modules`, `.venv`, `dist`, `build`, `.cache`, frame outputs, or log batches, the manifest, build command, install log, or reproducible regeneration command

VM disks, snapshots, ISOs, exports, backups, and media are user data by default. Codex should not call them deletable merely because they are large. If evidence is incomplete, the correct wording is "cleanup candidate" or "suspected generated file", not "safe to delete".

## Non-Goals

This skill is not:

- A Git LFS replacement.
- A VM backup system.
- A guarantee that Git can safely manage large VM disks.
- A guarantee that all Codex Desktop internal background operations can be intercepted.
- A recovery tool after `.git` or object history has been deleted.

For real large-file versioning, consider:

- Git LFS.
- DVC.
- Artifact storage.
- Backup systems or object storage.
- VM platform snapshot/export tools.

## Design Principles

### People Before Commands

Users care about disk space, data safety, recoverability, and consequences more than command names.

### Safe By Default

When context is incomplete, do not write or delete. Scan, explain, then ask.

### Clear Confirmation

Confirmation text is explicit and copyable. Casual replies should not accidentally authorize dangerous work.

### Transparent Reasoning

Codex should state what it found, what it wants to do, why it is risky, and what safer alternatives exist.

### No Overclaiming

The skill guides agent behavior. It does not claim to control all software internals.

## Release Checklist

- `SKILL.md` passes Codex skill validation.
- `agents/openai.yaml` exists and `default_prompt` includes `$protect-large-git-workspaces`.
- The repository contains no personal paths, usernames, real incident logs, tokens, or private file names.
- Examples use generic paths and file names.
- Documentation includes Windows, macOS, and Linux scan suggestions.
- Confirmation flow and limitations are documented.
- MIT License is included.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
