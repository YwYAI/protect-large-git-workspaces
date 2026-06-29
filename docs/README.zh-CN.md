# Protect Large Git Workspaces

语言：[English](../README.md) | 中文

一个用于 Codex 的安全型 skill，用来防止代理在包含虚拟机、磁盘镜像、ISO、备份包、大型媒体或其他大文件的工作区里，意外执行高风险 Git 操作，导致 `.git/objects` 在短时间内膨胀到几十 GB 甚至几百 GB。

这个 skill 的目标不是让 Git 更会管理大文件，而是让 Codex 在危险操作前停下来、看清楚、说清楚、等确认。

## 快速上手

### 1. 安装 skill

克隆仓库，并把 skill 文件夹复制到 Codex skills 目录：

```bash
git clone https://github.com/YwYAI/protect-large-git-workspaces.git
cd protect-large-git-workspaces
mkdir -p ~/.codex/skills
cp -R skills/protect-large-git-workspaces ~/.codex/skills/
```

Windows PowerShell：

```powershell
git clone https://github.com/YwYAI/protect-large-git-workspaces.git
cd protect-large-git-workspaces
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\skills" | Out-Null
Copy-Item -Recurse -Force ".\skills\protect-large-git-workspaces" "$env:USERPROFILE\.codex\skills\"
```

安装后，新开一个 Codex 会话。

### 2. 让 Codex 检查工作区

可以显式调用：

```text
使用 $protect-large-git-workspaces 检查这个目录是否适合作为 Git 工作区。
```

也可以自然语言提问：

```text
这个目录能不能 git add .
为什么 .git/objects 这么大？
这个目录里有虚拟机文件，Codex 能不能安全操作？
帮我清理 Git 临时对象，但不要误删历史。
```

### 3. 运行只读主动扫描

安装后，可以让 Codex 运行 skill 自带的扫描脚本，判断问题是否已经发生，并列出可疑文件和文件夹：

```bash
python ~/.codex/skills/protect-large-git-workspaces/scripts/scan_large_git_workspace.py /path/to/workspace
```

Windows PowerShell：

```powershell
python "$env:USERPROFILE\.codex\skills\protect-large-git-workspaces\scripts\scan_large_git_workspace.py" "C:\path\to\workspace"
```

这个扫描器只读，不会删除、移动、暂存或修改文件。它会报告大文件、危险扩展名、可疑目录、大量小文件聚合风险、`.git/objects` 大小和 `tmp_obj_*` 垃圾。检测到风险时退出码为 `2`，没有发现明显风险时退出码为 `0`，方便以后接入自动化预警。

### 4. 阅读风险报告

Codex 应该说明：

- 风险等级，以及命中的评估标准
- 大文件和危险扩展名
- 候选文件数量和总大小
- 生成目录、依赖目录、缓存目录
- 相关的 `.git/objects` 大小和 `tmp_obj_*` 垃圾
- 它准备执行的具体命令
- 对任何清理建议使用了哪些证据
- 更安全的替代方案，例如写 `.gitignore` 或把代码移到干净工作区

### 5. 只有接受风险时才确认

如果 Codex 需要执行高风险 Git 写入或清理操作，它会要求你明确确认。只有在你理解并接受风险时，才回复以下任意一个确认令牌：

```text
CONFIRM-GIT-RISK
确认承担Git大文件风险
```

如果不想继续高风险操作，可以让 Codex 改用更安全的方案，例如先添加 `.gitignore` 规则，或者把代码文件移到单独仓库。

## 适用场景

当 Codex 工作区里包含以下内容时，这个 skill 应该介入：

- VirtualBox 虚拟机目录，例如 `.vdi`、`.sav`、`.vbox-prev`。
- VMware 虚拟机目录，例如 `.vmdk`、`.vmem`、`.vmss`、`.vmwarevm/`。
- Hyper-V 磁盘，例如 `.vhd`、`.vhdx`。
- QEMU / UTM 镜像，例如 `.qcow2`、`.qed`、`.utm/`。
- Parallels 虚拟机，例如 `.pvm/`、`.hdd`。
- Android 模拟器、WSL 导出包、系统安装 ISO、OVA/OVF 虚拟机导出包。
- 大型压缩包、备份包、媒体文件、数据库 dump、超过 100 MB 的任意文件。
- 单个文件都不大，但数量很多或总体积很大的生成文件、依赖目录、缓存目录。
- 已经出现 `.git/objects` 膨胀、`tmp_obj_*` 垃圾对象、Git 垃圾回收失败或磁盘空间异常消耗的仓库。

典型触发请求包括：

```text
帮我提交当前目录
帮我 git add .
帮我清理 .git/objects
为什么 .git 变得很大
帮我把这个虚拟机目录交给 Codex 继续操作
帮我运行 git gc
帮我删除 tmp_obj_*
```

## 解决的问题

Git 默认会把 `git add` 涉及的文件写入对象库。对于代码文件，这是正常行为；对于虚拟机磁盘和镜像文件，这可能造成严重后果。

例如一个 40 GB 的虚拟机磁盘被 `git add .` 或 `git hash-object` 处理时，Git 会尝试把它写入 `.git/objects`。类似地，即使没有单个文件超过 100 MB，几千个 5 MB 到 50 MB 的文件也可能在短时间内写入数 GB 到数十 GB 的 Git 对象。如果操作被中断、后台重试、或 Codex 自动快照反复触发，就可能出现：

- `.git/objects` 短时间内增加几十 GB。
- 上百个 `tmp_obj_*` 临时对象残留。
- Git 命令变慢、卡住或超时。
- 磁盘空间被耗尽。
- 用户误以为是虚拟机、同步软件或系统更新造成的问题。
- 清理时误删 `.git`、对象库或历史记录。

这个 skill 针对的是“操作前缺少风险感知”的问题。它把高风险 Git 操作改造成一个受控流程。

## 风险评估标准

风险报告必须可解释、可复核。Codex 应说明风险等级、命中的阈值、使用的证据，以及哪些信息仍然未知。

- **Critical / 严重**：准备删除 `.git`、`.git/objects`、Git 历史，或在虚拟机/磁盘镜像工作区做递归清理；`.git/objects` 超过 5 GiB；`tmp_obj_*` 超过 1 GiB 或 100 个；任意高风险虚拟机、磁盘、快照、镜像、归档或媒体文件超过 1 GiB；候选文件总量超过 10 GiB。
- **High / 高**：任意文件超过 100 MiB；候选文件总量超过 500 MiB；候选文件超过 1000 个；超过 100 个文件大于 10 MiB；存在虚拟机、磁盘镜像、归档、媒体扩展名；存在生成、缓存、依赖目录；`.git/objects` 超过 500 MiB 或存在任何 `tmp_obj_*`。
- **Medium / 中**：存在生成、缓存、依赖目录或高风险扩展名，但未达到 High 阈值；候选文件总量为 100-500 MiB；`.git/objects` 有异常近期写入，需要继续调查。
- **Low / 低**：没有高风险扩展名，没有可疑目录，没有大文件，候选文件总量低于 100 MiB，且 `.git/objects` 没有明显膨胀。

自带扫描器会把这套评估标准和扫描结果一起输出，方便用户理解为什么当前工作区被评为 Critical、High、Medium 或 Low。

## 设计目标

这个 skill 按照安全产品和工业设计的思路设计：先识别使用场景，再限制危险动作，最后给用户一个清楚、可恢复、可确认的决策点。

### 1. 可感知

Codex 在执行危险操作前，必须先扫描工作区，并把风险用用户能理解的语言说出来。用户不应该需要知道 Git 对象库的内部机制，才能理解为什么这个操作危险。

### 2. 可预防

默认不执行高风险 Git 写入，不把大文件送进 `.git/objects`。优先建议 `.gitignore`、换工作区、只读诊断等低风险方案。

### 3. 可确认

如果用户确实要继续执行，必须明确确认。模糊回复不算授权。默认提供中英两个等价确认令牌，方便中文读者理解，也方便跨语言环境复制粘贴：

```text
CONFIRM-GIT-RISK
确认承担Git大文件风险
```

### 4. 可恢复

在清理 `.git/objects`、删除 `tmp_obj_*`、运行 `git gc` 或删除 `.git` 前，必须先列出影响范围。这样用户可以先保存证据、备份目录，或选择更保守的清理方式。

### 5. 可迁移

规则不绑定某一个虚拟机名称，也不绑定某一个虚拟机平台。VirtualBox、VMware、Hyper-V、QEMU、UTM、Parallels、WSL、Android 模拟器和其他磁盘镜像目录都按同一套风险模型处理。

## 防护模型

这个 skill 把操作分成两类。

### 允许直接执行的只读操作

这些操作用于观察状态，通常不会改变文件或 Git 对象库：

```bash
git status --short --ignored
git rev-parse --show-toplevel
git ls-files
git count-objects -vH
```

Windows 下也可以只读扫描大文件和聚合风险：

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

macOS / Linux 下可以使用这些通用只读检查：

```bash
find . -path ./.git -prune -o -type f -size +100M -print
find . -path ./.git -prune -o -type f -print | wc -l
du -sh . 2>/dev/null
git status --short --ignored
git count-objects -vH
```

如果需要更精细的聚合统计，GNU/Linux 可以使用 `du --files0-from`；macOS 默认 `du` 不支持这个参数，应使用 `du -sh` 或安装 GNU coreutils 后再使用 GNU 版本命令。

### 必须人工确认的高风险操作

以下操作在存在大文件或虚拟机文件时必须停下来确认：

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

以及：

- 删除 `.git`。
- 删除 `.git/objects`。
- 删除 `.git/objects/*/tmp_obj_*`。
- 对虚拟机目录或磁盘镜像目录做递归删除、移动、清理。
- 任何可能写入 `.git/objects` 的 Codex 工作区快照、checkpoint 或 turn diff 操作。

## 工作流程

当 Codex 准备执行高风险 Git 操作时，skill 要求它按以下流程处理。

### Step 1: 只读扫描

先检查工作区里是否存在大文件、虚拟机磁盘、系统镜像、备份包、媒体文件和已有 Git 对象库膨胀。

不要只看“最大文件”。还要看候选文件总数和总大小。很多小于 100 MB 的文件在 Git 里仍然可能造成大规模对象写入。

重点识别：

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

### Step 2: 判断风险

如果扫描发现：

- 任意文件超过 100 MB。
- 候选文件总大小超过 500 MB。
- 候选文件数量超过 1000 个。
- 超过 100 个候选文件大于 10 MB。
- 工作区包含虚拟机、磁盘镜像或快照文件。
- 工作区包含明显的生成目录或依赖目录，例如 `node_modules/`、`.venv/`、`dist/`、`build/`、`target/`、`.cache/`、`.next/`。
- `.git/objects` 已经异常大。
- `.git/objects` 里存在大量 `tmp_obj_*`。

则必须把操作升级为需要人工确认的风险操作。

### Step 3: 给出风险说明

Codex 必须说明：

- 准备执行的具体命令。
- 哪些路径或文件会受影响。
- 最大文件大概多大。
- 候选文件总数和总大小是多少。
- 可能造成的后果。
- 更安全的替代方案。

示例：

```text
我检测到当前工作区包含大型虚拟机或磁盘镜像文件，可能达到几十 GB。

如果执行 `git add .` 或继续进行工作区快照，Git 可能把这些文件写入 `.git/objects`，导致额外占用几十 GB 到几百 GB。操作中断后还可能留下 `tmp_obj_*` 临时垃圾。

更安全的做法是先加入 `.gitignore`，或把代码工作区移动到不包含虚拟机文件的目录。

如果你仍然确认执行，请回复以下任意一个确认令牌：

CONFIRM-GIT-RISK
确认承担Git大文件风险
```

如果风险来自大量小文件，提示应改成类似：

```text
我检测到当前工作区虽然没有超过 100 MB 的单个文件，但有 3200 个候选文件，总大小约 8.6 GB。

如果执行 `git add .` 或继续进行工作区快照，Git 仍可能把这些文件写入 `.git/objects`，造成数 GB 到数十 GB 的对象库增长。大量文件也会让 Git 状态检查、差异计算和垃圾回收变慢。

更安全的做法是先确认这些文件是否是构建产物、依赖目录或缓存目录；如果是，应先加入 `.gitignore`，例如 `node_modules/`、`dist/`、`build/`、`.cache/`。

如果你仍然确认执行，请回复以下任意一个确认令牌：

CONFIRM-GIT-RISK
确认承担Git大文件风险
```

### Step 4: 等待明确确认

只有明确确认才允许继续，例如：

```text
CONFIRM-GIT-RISK
确认承担Git大文件风险
确认执行
同意执行
```

以下回复不应视为确认：

```text
继续
可以吧
你看着办
随便
应该没事
```

### Step 5: 优先执行低风险替代方案

默认优先建议或执行小范围安全修改，例如添加 `.gitignore`：

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

## 安装

推荐仓库结构：

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
    large-git-safety.zh-CN.md
```

安装到本地 Codex：

```bash
mkdir -p ~/.codex/skills
cp -R skills/protect-large-git-workspaces ~/.codex/skills/
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\skills" | Out-Null
Copy-Item -Recurse -Force ".\skills\protect-large-git-workspaces" "$env:USERPROFILE\.codex\skills\"
```

安装后，新开的 Codex 会话会在相关任务中发现并使用这个 skill。

## 使用方式

你可以显式要求 Codex 使用：

```text
使用 $protect-large-git-workspaces 检查这个目录是否适合作为 Git 工作区。
```

也可以在涉及 Git、大文件或虚拟机目录的问题中自动触发，例如：

```text
为什么这个仓库的 .git/objects 这么大？
帮我检查这个目录能不能 git add .
帮我清理 Git 临时对象，但不要误删历史。
这个目录里有虚拟机文件，能不能交给 Codex 操作？
主动扫描这个工作区，并列出可疑文件和文件夹。
```

直接运行扫描器：

```bash
python ~/.codex/skills/protect-large-git-workspaces/scripts/scan_large_git_workspace.py /path/to/workspace
```

## 适合解决的问题

### 1. Git 对象库异常膨胀

症状：

- `.git/objects` 占用几十 GB 或几百 GB。
- `git count-objects -vH` 显示大量 loose objects 或 garbage。
- `.git/objects/xx/tmp_obj_*` 很多。

skill 行为：

- 先诊断对象库大小。
- 列出大对象、临时对象和最近写入时间。
- 区分可删除的 Git 临时垃圾和可能仍被引用的对象。
- 清理前要求明确确认。

### 2. 虚拟机目录被误当作 Git 工作区

症状：

- 工作区里有 `.vdi`、`.vmdk`、`.vhdx`、`.qcow2`、`.sav`、`.iso`。
- 用户或 Codex 准备运行 `git add .`。

skill 行为：

- 阻止直接 Git 写入。
- 提醒后果。
- 建议添加 `.gitignore` 或迁移代码目录。

### 3. 大量小文件造成聚合风险

症状：

- 没有单个文件超过 100 MB。
- 但未跟踪或待提交文件数量很多，例如几千到几万个。
- 总大小达到数百 MB、数 GB 或更高。
- 常见来源是 `node_modules/`、`.venv/`、`dist/`、`build/`、`target/`、`.cache/`、导出的日志、截图序列、帧序列、批量中间产物。

skill 行为：

- 不只检查最大文件，也统计候选文件数量和总大小。
- 当候选总大小超过 500 MB、候选文件数超过 1000 个、或大于 10 MB 的候选文件超过 100 个时触发确认。
- 优先建议将生成目录、依赖目录和缓存目录写入 `.gitignore`。
- 要求用户确认后才允许执行 Git 写入。

### 4. 代理后台快照带来的副作用

症状：

- 用户没有手动运行 `git add`，但 `.git/objects` 仍增长。
- Codex 或其他代理工具在工作区里执行了快照、diff、checkpoint。

skill 行为：

- 要求代理在写入 `.git/objects` 前做风险扫描。
- 明确说明只能约束代理发起或可见的操作。
- 对完全绕过模型的产品内部行为不做不实承诺。

### 5. 清理时避免二次事故

症状：

- 用户想删除 `.git`、`.git/objects` 或 `tmp_obj_*`。
- 磁盘空间紧张，希望快速释放。

skill 行为：

- 先列出清理对象。
- 说明会丢失什么。
- 区分临时垃圾、未引用对象和可能需要保留的 Git 历史。
- 先提供证据，再说某个对象是否可安全删除。
- 要求明确确认后再执行删除。

## 可删除证据标准

不能因为文件“很大”“看起来像临时文件”“像生成文件”，就直接说它可以删除。

在 Codex 声称某个文件或目录可安全删除之前，应先提供证据，例如：

- 精确路径、大小、数量和最后写入时间。
- 能证明文件来源的日志或命令记录。
- 与某次已知中断的 Git、构建、包管理器、虚拟机或 Codex 操作相匹配的时间戳。
- 没有相关进程仍在运行的证明。
- 对 `.git/objects/tmp_obj_*`，要证明它是 Git 写入中断后的临时对象，而不是正常 loose object。
- 对 `node_modules`、`.venv`、`dist`、`build`、`.cache`、帧输出或批量日志等生成目录，要提供 manifest、构建命令、安装日志或可重新生成命令。

虚拟机磁盘、快照、ISO、导出包、备份和媒体文件默认都应视为用户数据。不能因为它们很大就说可删除。如果证据不足，正确说法是“清理候选”或“疑似生成文件”，不是“可安全删除”。

## 不解决的问题

这个 skill 不是 Git LFS 替代品，也不是虚拟机备份工具。

它不能保证：

- Git 可以安全管理几十 GB 的虚拟机磁盘。
- Codex Desktop 的所有内部后台机制都一定会被拦截。
- 删除 `.git` 或对象库后还能恢复历史。
- 未备份的大文件清理一定可逆。

如果确实需要版本化大型二进制文件，应考虑：

- Git LFS。
- DVC。
- 专门的 artifact storage。
- 备份系统或对象存储。
- 虚拟机平台自带的快照和导出机制。

## 设计原则

### 人先于命令

用户真正关心的不是 Git 命令本身，而是磁盘空间、数据安全、可恢复性和操作后果。README 和 skill 都围绕这些用户目标组织。

### 默认安全

在信息不足时，不执行写入和删除。先扫描、先解释、先确认。

### 降低误操作成本

危险命令不直接执行，必须经过确认门槛。确认文本设计成明确、可复制、不会被普通寒暄误触发。

### 保持透明

Codex 需要说明它看到了什么、准备做什么、为什么危险、替代方案是什么。

### 不过度承诺

skill 能约束遵循指令的代理行为，但不能声明能控制所有软件内部后台行为。这个边界必须在文档里说清楚。

## 发布前检查清单

发布到 GitHub 前建议确认：

- `SKILL.md` 能通过 Codex skill 校验。
- `agents/openai.yaml` 存在且 `default_prompt` 包含 `$protect-large-git-workspaces`。
- 仓库不包含个人路径、用户名、真实事故日志或私有文件名。
- README 中的示例路径使用泛化名称。
- 文档包含 Windows、macOS、Linux 的扫描建议。
- 已明确说明确认流程和局限性。
- 已添加合适的开源许可证。

## 许可证

本项目使用 MIT License。详见 [LICENSE](LICENSE)。
