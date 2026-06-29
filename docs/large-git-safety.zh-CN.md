# 大文件与 Git / Codex 工作区安全规则说明

这份说明是给中文读者看的中文版，用来解释为什么以后在包含任何虚拟机、大型二进制文件、磁盘镜像、系统镜像、模拟器镜像、WSL 导出包或备份归档的目录里，Codex 不能直接执行某些 Git 操作，必须先提示风险并等待人工确认。

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

## 如果发现风险，必须这样提示

Codex 必须用中文说明：

- 准备执行的具体命令是什么。
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
