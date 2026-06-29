# 大文件与 Git / Codex 工作区安全规则说明

这份说明是给中文阅读能力较强的人看的中文说明，用来解释为什么以后在包含任何虚拟机、大型二进制文件、磁盘镜像、系统镜像、模拟器镜像、WSL 导出包或备份归档的目录里，Codex 不能直接执行某些 Git 操作，必须先提示风险并等待人工确认。

## 背景

Git 不适合直接管理虚拟机磁盘、系统镜像、快照文件、内存状态文件、大型压缩包、大型媒体文件，以及数量很多的生成文件、依赖文件或缓存文件。

这不只适用于某一个具体虚拟机名称，也适用于其他虚拟机或镜像目录，例如 VirtualBox、VMware、Hyper-V、QEMU、UTM、Parallels、Android 模拟器、WSL 导出包、系统安装 ISO、OVA/OVF 虚拟机导出包等。

例如 VirtualBox 的 `.vdi`、VMware 的 `.vmdk`、Hyper-V 的 `.vhdx`、QEMU/UTM 的 `.qcow2`、Parallels 的 `.hdd`、虚拟机内存状态 `.vmem` 或快照 `.sav` 都可能很大。如果 Codex 或 Git 执行了类似下面的命令：

```powershell
git add .
git add -- SomeVirtualMachine.vdi
git hash-object --no-filters -- SomeDiskImage.qcow2
```

Git 会尝试把这些大文件写入 `.git\objects`。这可能导致：

- `.git\objects` 一次性增加几十 GB。
- 操作中断后留下大量 `tmp_obj_*` 临时垃圾。
- 后台重试时持续增长到几百 GB。
- 磁盘空间被迅速耗尽。
- 清理时如果误删 `.git` 或对象库，可能丢失 Git 历史或 Codex 快照记录。

即使没有单个文件超过 100 MB，也不能认为安全。几千个 5 MB 到 50 MB 的文件，合计同样可能让 `.git\objects` 增长数 GB 到数十 GB。

## 必须拦截的操作

以后在可能包含大文件的目录里，下面这些操作都必须先做风险扫描，不能直接执行：

- `git add`
- `git add .`
- `git add -A`
- `git update-index`
- `git hash-object`
- 可能包含新增大文件的 `git commit`
- Codex 工作区快照、checkpoint、turn diff 等可能写入 `.git\objects` 的动作
- `git gc`
- `git prune`
- 删除 `.git`
- 删除 `.git\objects`
- 删除 `.git\objects` 下的 `tmp_obj_*`
- 对包含虚拟机或磁盘镜像的目录做递归移动、删除、清理

## 需要重点识别的危险文件和目录

只要工作区里出现下面这些文件类型，就要高度警惕：

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
*.zip
*.7z
*.rar
*.tar
*.gz
*.mp4
*.mov
*.mkv
```

另外，任何超过 100 MB 的文件，都应该先人工确认是否允许进入 Git。即使单个文件都小于 100 MB，只要候选文件总量很大，也要预警。

## Codex 应该先做什么

在执行危险 Git 操作之前，Codex 应该先只读检查：

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

这些命令只是查看状态，不会写入或删除文件。

如果已经安装 `protect-large-git-workspaces` skill，也可以直接运行自带的只读主动扫描器：

```powershell
python "$env:USERPROFILE\.codex\skills\protect-large-git-workspaces\scripts\scan_large_git_workspace.py" "C:\path\to\workspace"
```

这个扫描器用于回答两个问题：

- 是否已经出现 `.git\objects` 异常膨胀或 `tmp_obj_*` 临时垃圾。
- 哪些文件夹和文件最可疑，例如虚拟机磁盘、快照、ISO、依赖目录、缓存目录、构建输出或大量小文件。

扫描器不会删除、移动、暂存或修改任何文件。检测到风险时退出码为 `2`，没有发现明显风险时退出码为 `0`，可以作为后续自动化预警的基础。

## 风险评估标准

风险提示不能只写“有风险”，必须说明按什么标准评估。建议使用以下等级：

- **Critical / 严重**：准备删除 `.git`、`.git\objects`、Git 历史，或在虚拟机/磁盘镜像工作区递归清理；`.git\objects` 超过 5 GiB；`tmp_obj_*` 超过 1 GiB 或 100 个；任意高风险虚拟机、磁盘、快照、镜像、归档或媒体文件超过 1 GiB；候选文件总量超过 10 GiB。
- **High / 高**：任意文件超过 100 MiB；候选文件总量超过 500 MiB；候选文件超过 1000 个；超过 100 个文件大于 10 MiB；存在虚拟机、磁盘镜像、归档、媒体扩展名；存在生成、缓存、依赖目录；`.git\objects` 超过 500 MiB 或存在任何 `tmp_obj_*`。
- **Medium / 中**：存在生成、缓存、依赖目录或高风险扩展名，但未达到 High 阈值；候选文件总量为 100-500 MiB；`.git\objects` 有异常近期写入，需要继续调查。
- **Low / 低**：没有高风险扩展名，没有可疑目录，没有大文件，候选文件总量低于 100 MiB，且 `.git\objects` 没有明显膨胀。

风险报告应至少包含：

- 风险等级。
- 命中的阈值和判断条件。
- 使用的证据，例如扫描器输出、命令输出、文件大小、时间戳、进程命令行、日志或 Git 状态。
- 仍然未知、无法证明的部分。

## 如果发现风险，必须这样提示

Codex 必须用中文说明：

- 准备执行的具体命令是什么。
- 风险等级是什么，命中了哪些评估标准。
- 哪些大文件会受到影响，大小大概是多少。
- 如果风险来自大量小文件，要说明候选文件数量和总大小。
- 可能造成什么后果，例如 `.git\objects` 增加几十到几百 GB、留下 `tmp_obj_*`、删除 Git 历史等。
- 有没有更安全的替代方案，例如先写 `.gitignore`、换到不包含虚拟机的工作区、只删除确认过的 Git 临时垃圾。

示例提示：

```text
我检测到当前目录包含大型虚拟机或磁盘镜像文件，例如 SomeVirtualMachine.vdi / SomeDiskImage.qcow2 / SomeVM.vhdx，约几十 GB。

如果执行 git add . 或 Codex 工作区快照，Git 可能会把这些虚拟机磁盘、快照、内存状态或系统镜像写入 .git\objects，导致额外占用几十 GB 到几百 GB。操作中断时还可能留下 tmp_obj_* 垃圾文件。

更安全的做法是先把虚拟机磁盘、快照、ISO、OVA/OVF、模拟器镜像和虚拟机目录加入 .gitignore，或者换到不包含这些大文件的工作区。

如果你仍然确认要执行这个高风险操作，请明确回复：

CONFIRM-GIT-RISK
确认承担Git大文件风险
```

如果风险来自大量小文件，提示应类似：

```text
我检测到当前目录虽然没有超过 100 MB 的单个文件，但有 3200 个候选文件，总大小约 8.6 GB。

如果执行 git add . 或 Codex 工作区快照，Git 仍可能把这些文件写入 .git\objects，导致对象库增加数 GB 到数十 GB。大量文件也会让 Git 状态检查、差异计算和垃圾回收变慢。

更安全的做法是先确认这些文件是否是依赖目录、构建产物、缓存目录、日志批量输出或截图序列。如果是，应先加入 .gitignore。

如果你仍然确认要执行这个高风险操作，请明确回复：

CONFIRM-GIT-RISK
确认承担Git大文件风险
```

## 人工确认规则

只有用户明确回复以下内容之一，Codex 才能继续执行高风险操作：

```text
CONFIRM-GIT-RISK
确认承担Git大文件风险
确认执行
同意执行
```

下面这些都不算有效确认：

- “可以吧”
- “你看着办”
- “继续”
- “随便”
- 用户没有回复
- 用户只是问风险但没有明确授权

## 默认安全做法

如果目录里有虚拟机或大文件，默认应该先加入 `.gitignore`：

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

对于虚拟机目录，通常还应该忽略整类目录，而不是只忽略某一个具体名字：

```gitignore
VirtualBox VMs/
VMs/
*.pvm/
*.utm/
*.vmwarevm/
Snapshots/
ISO/
ISOs/
```

更推荐的做法是：不要把虚拟机目录当作 Codex 或 Git 工作区。把代码、脚本、说明文档放在单独的小目录里，把虚拟机磁盘和 ISO 放在普通数据目录里。

## 可删除证据标准

清理提示必须区分“可疑”“清理候选”和“可安全删除”。没有证据时，只能说“清理候选”或“疑似临时/生成文件”，不能说“可安全删除”。

要证明某个文件或目录可删除，应尽量提供：

- 精确路径、大小、数量和最后写入时间。
- 生成这些文件的日志或命令记录，例如 Git/Codex 会话日志、shell history、构建日志、包管理器日志、虚拟机或应用日志。
- 时间戳证据，例如文件创建/修改时间与某次中断的 `git hash-object`、`git add`、构建、安装或快照操作一致。
- 进程证据，例如当前没有相关 Git、虚拟机、构建工具或同步工具进程仍在使用这些文件。
- 对 `.git\objects\tmp_obj_*`，要证明它们是 Git 写入中断留下的临时对象，而不是正常 loose object 或仍可能被引用的对象。
- 对 `node_modules`、`.venv`、`dist`、`build`、`.cache`、批量日志、截图序列、帧序列等目录，要提供 manifest、构建命令、安装日志或可重新生成命令。

虚拟机磁盘、快照、ISO、OVA/OVF 导出包、备份和媒体文件默认都是用户数据。除非用户明确说明它们可丢弃，或平台/日志能证明它们是临时输出，否则不能建议删除。

## 示例事故场景

一个典型问题是：代理工具在包含虚拟机磁盘的目录里触发 Git 对象写入。Git 尝试处理虚拟机磁盘、快照文件、镜像文件或大量生成文件，导致 `.git\objects` 快速膨胀。

需要举一反三：以后不管虚拟机叫什么名字，也不管是 VirtualBox、VMware、Hyper-V、QEMU、UTM、Parallels、Android 模拟器还是 WSL 导出包，只要目录里存在大型镜像、快照、内存状态或虚拟机包，都按同一套高风险规则处理。

以后遇到类似目录，正确流程是：

1. 先扫描大文件。
2. 再统计候选文件总数和总大小。
3. 先写 `.gitignore`。
4. 不自动执行 `git add`、`hash-object`、快照或清理。
5. 先用中文提示风险和后果。
6. 等用户明确确认后再执行。
