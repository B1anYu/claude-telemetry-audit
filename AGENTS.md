# Repository Guidelines

## Project Overview

- 分析工作区（非可构建软件项目）：对 **Claude Desktop 2.9939.2**（macOS/Electron，`app.asar` 解包）、**Claude Code CLI 2.1.283**（bun 单文件二进制，切分出明文模块）与 **Claude Android 1.260930.20**（`com.anthropic.claude`，Play base APK + R8 混淆后的 jadx 产物）做遥测/隐私/指纹审计。源码提取是一次性过程，**提取产物不入库**，复现规则见 `Reproduction Path` 一节。
- **平台范围**：`desktop/`（含 `native-unpacked/` 的 Mach-O）**只覆盖 macOS 构建**；Electron 单包内含各平台 JS 分支（`process.platform === "win32"` 等），所以代码里能看到 Windows 分支，但**各平台的实际路径、安装形态与卸载行为不在这棵树里，本仓库无法证实**。**Android 端单独立篇**（`telemetry/android.md`），素材为 Play 分发 base APK 的 jadx 产物，与 desktop/cli **不共享代码**；`android/` 素材树同样只存在于本地工作树（gitignore）。
- 产出：`README.md`（对外成稿；§8 的索引表已失效，待重写）、`telemetry/` 下三篇主题文档（`cli.md`、`desktop.md`、`linked.md`）、一份数据附录（`desktop-event-catalog.md`）与 Android 篇（`android.md`）。
- 仓库**只保留结论、复现规则与分析工具，不保留任何逆向产物**：解包树、切分出的模块、反编译源、原生转储一律不入库（规则见 `Reproduction Path`）。原始安装件同样不在仓库内，需自行从公开分发渠道获取。
- 报告结论可由「公开分发制品 + `Reproduction Path` 的规则」重建并逐条核对。

## Architecture & Data Flow

```
Claude Desktop dmg / Claude Code CLI 二进制            ← 原始安装件（不入库，需自行获取）
        │  7-Zip 抽 app.asar → 自写 Python 解 asar；bun 二进制按 banner 切分
        ▼
desktop/asar-tree/         asar 原样解包（.vite/build 原始 chunk、renderer、resources、vendored node_modules）
desktop/native-unpacked/   10 个 unpacked 原生模块（Mach-O，非 macOS 主机无法执行，只能静态读取）
cli/modules/               2153 个明文 JS 模块
        │  bunx prettier（仅主进程 chunk）
        ▼
desktop/main-process-readable/   250 个格式化 chunk + INDEX.md    ← 行号基准
        │  grep 定位 → read 区间 → 与原始 chunk / 原生转储交叉核对
        ▼
telemetry/{cli,desktop,linked}.md（主题文档，带 `文件:行` 与原文片段）+ desktop-event-catalog.md（数据附录） → README.md（对外成稿）

Claude Android base APK（claude.apk / .xapk，不入库）
        │  unzip 解包；jadx -d --no-res 出反编译源；dexdump -d 看 R8 合成方法
        ▼
android/apk-tree/ + android/jadx-sources/    ← android.md 的行号基准（jadx 产物）
        │  telemetry/tools/dex.py 做 字符串→类/方法 交叉引用
        ▼
telemetry/android.md
```

同一份代码的三种形态（引用时二选一并在文件头写明）：

| 形态 | 路径 | 特征 |
|---|---|---|
| prettier 产物 | `desktop/main-process-readable/*.js` | per-file 1-based 行号；报告行号均指向这里 |
| 原始 chunk | `desktop/asar-tree/.vite/build/*.js` | 未格式化；prettier 不改标识符名，用于导出别名/字面量交叉验证 |
| 原生转储 | `telemetry/native/*.txt` | info / imports / exports / strings 四类预生成文本 |

提取链路未落盘为脚本（原始会话用的是内联命令 + 临时 Python 片段）；关键参数：asar header 偏移与 pickle 结构、CLI 二进制的明文源码区 offset、模块间单字节 `\x00` 分隔与 `// @bun @bytecode` banner。

Android 篇另有一套三形态：原始 dex（`android/apk-tree/classes*.dex`）、jadx 产物（`android/jadx-sources/`，**本篇行号基准**）、`dexdump -d`（仅用于 jadx 无法反编译的 R8 合成方法）。详见 `android.md` §0.1。

## Reproduction Path

本仓库**不附带任何逆向产物**——解包树、切分出的模块、反编译源码都不入库。报告里的每条结论都由「公开分发的安装件 + 下面这套规则」重建得出，任何人都可以照做并逐条核对。

**一个前提**：报告的行号是**版本绑定**的，只在被审计的那一版上成立，换版本必须重新定位。被审计的三版是 **Desktop 2.9939.2**、**Claude Code CLI 2.1.283**、**Claude Android 1.260930.20**。

### 制品与校验

- **Desktop**：官方 macOS 安装镜像 `Claude.dmg`，`sha256 = db9d09eda0131576960e5d5a4569335dc700664b8ffde534ef541cc8635aa587`。
- **CLI**：随发行件一同分发的 `manifest.json` 是官方清单，含逐平台的版本、大小与校验和。审计用的是 **darwin-arm64** 那份，`sha256 = d8cb1e5c79684cc12a8bfc813e3a2073406921b6245744b3009be3ab5651d21e`（与清单一致）。**注意不是 x64 那份**，两者内容布局不同。
- **Android**：Play 分发的 base APK，`sha256 = d4335899898597378ef1ce86b96b948dee01bc31ec1bd7728b1976ff8e3080b3`（详见 `telemetry/android.md` §1）。单独安装 base 会缺 ABI/density split，复现安装需一并取用。

### Desktop

从镜像的 `Claude/Claude.app/Contents/Resources/` 下取出 `app.asar`，**同时取出同级的 `app.asar.unpacked/`**——asar 头里被标记为 unpacked 的条目其内容并不在 `app.asar` 内，缺了同级目录，解包器会在原生模块处直接报错中止。那 10 个原生件在报告里单列为 `native-unpacked/`，也对应这一节。

解包得到的树即 `asar-tree/`，但它比 asar 本身多一部分：`resources/bundled-skills/` 下的 `.skill` 是 zip 包，逐个解开后才是 `resources/skills-unpacked/`，报告引用的技能文本在那里。

那 10 个原生件是编译产物，报告对它们的引用指向的是 `telemetry/native/` 下的**转储文本**，不是二进制本身，而转储同样不入库。转储由仓库内的 `telemetry/tools/macho.py` 生成，每个二进制四类：`info`（头部、架构、UUID、build version、依赖库与 install name、节区表）、`imports`（未定义符号）、`exports`（export trie）、`strings`（默认最短 5 字符）。命名一律为 `<二进制名>.<类别>.txt`——info / imports / strings 各 10 份，exports 9 份。另有 5 个 0 字节的 `<名>.exports.err`，是生成时 stderr 重定向留下的空文件，**无内容、无意义**，不必复现也不必在意。Swift 符号另经 `telemetry/tools/swiftdemangle.py` 处理对应的 `exports.txt`，输出**按字典序排序后**才是 `swift_addon.demangled.txt` 与 `computer_use.demangled.txt`（脚本本身不排序，这一步别漏）。四类转储 39 份，加 5 个 `.exports.err` 与 2 份 demangled，合计 46 个文件。

报告里 Desktop 的行号（含 `desktop-event-catalog.md` 的 722 条）指向的是**重新缩进后的产物**，不是随包发行的原始 chunk。缩进用 prettier，**版本必须锁在 3.9.9，列宽必须为 100**——默认的 80 会让行数相差约一成（实测某 chunk 22518 行 vs 20554 行），届时全部行号错位。原始 chunk 与缩进产物**文件名相同、分处两棵树**，行号基准是后者，引用时不要弄混。

事件清单里的 722 个事件名本身是唯一字面量，用它定位比用行号稳，且不依赖 prettier 版本。

### CLI

取 **darwin-arm64** 那份二进制。它内部有一段明文源码区，由若干模块首尾相接构成，模块之间以单个 `0x00` 字节分隔，每个模块以 `// @bun @bytecode` 开注。

别拿这个注释行去数模块——它在运行时代码的字符串里还出现过两次，是假阳性（全二进制共 2155 次，真模块 2153 个）。可靠的起点是「**前一个字节为 `0x00` 的那个 `// @bun @bytecode`**」，从该处起按 `0x00` 切分，直到出现不以该注释开头的片段为止，所得即全部模块。

切分结果按顺序编号为 `mod-0000.js … mod-2152.js`。**这个编号是本仓库自己的约定，不是上游的名字**，跨版本对不上是正常的。

CLI 模块体量很大（最大约 4MB），报告里 CLI 的行号只作参考；锚点请用每条结论附带的 grep 定位串。另注意：本机 `grep` 对超大文件只扫前 4MB，尾段匹配会静默丢失，复验时限定到具体模块文件，不要对整目录盲跑。

### Android

解包得到 `classes*.dex` 与 `AndroidManifest.xml`。反编译用 **jadx，版本必须锁在 1.5.1**，`-j 8 --no-res --log-level warn`，输入整个 APK（不要先拆 dex 再跑）。报告的行号指向这个产物。

**jadx 自身有轻微非确定性**，需要预先知道：同版本、同参数重复跑，约十个文件（三万六千余中的）会出现差异，且每次跑受影响的文件集合不同。差异全部落在 jadx 自己的诊断文本与字面量渲染上——SSA 寄存器名（`r12v1` / `r13v1`）、异常消息的详尽程度与栈帧行数、`(byte) 4` 与 `4` 这类常量转换的写法——不涉及反编译逻辑。逐条核对过：**报告引用的全部行号都不落在这批文件里**。

R8 合成的协程状态机等方法 jadx 反编译不出来，要看字节码；把某条字符串字面量归属到类与方法，用仓库内的 `telemetry/tools/dex.py`（它解析 DEX 的 `const-string` 指令，不做反编译，因此 jadx 反编译失败的方法也能定位）。报告中反复使用的混淆名→真名对照表在 `telemetry/android.md` §0.2。

### 验收方式

把报告里每条引用在重建出的素材上打开，比对行号处的原文。三个平台都以此法验证过：Desktop 250 个 chunk 全部逐字节一致；CLI 2153 个模块全部逐字节一致；Android 的 79 条行号引用区间全部一致。

## Key Directories

| 目录 | 内容 | 入库 |
|---|---|---|
| `telemetry/` | 5 篇 `.md`（`cli.md`、`desktop.md`、`linked.md`、`desktop-event-catalog.md`、`android.md`）+ `tools/`（`macho.py`、`swiftdemangle.py`、`dex.py`） | **是** |
| `desktop/asar-tree/` | asar 原样解包：`.vite/build`（250 chunk + 7 个 worker 子目录）、`.vite/renderer`（6 个窗口）、`resources`（含解开 `.skill` 后的 `skills-unpacked`）、`compile-cache`、vendored `node_modules` | 否 |
| `desktop/main-process-readable/` | prettier 3.9.9 / 列宽 100 的产物 —— **Desktop 与事件清单的行号基准** | 否 |
| `desktop/native-unpacked/` | `app.asar.unpacked/` 里的 10 个原生件（`swift_addon.node` 24.6M、`claude-native-binding.node` 5.0M、`github-mcp-server` 39.8M、`libmsalruntime_arm64.dylib` 等） | 否 |
| `cli/modules/` | `mod-0000.js … mod-2152.js`（编号连续）+ `MODULES.txt`（逐行 模块名 字节数） | 否 |
| `telemetry/native/` | 46 个原生转储（info / imports / exports / strings 四类） | 否 |
| `android/` | Android 素材树：`apk-tree/`（APK 原样解包）、`jadx-sources/`（**Android 行号基准**）、`manifest-readable/`、`dex-strings.txt` | 否 |

「否」的目录只存在于本地工作树（gitignore），按 `Reproduction Path` 重建；`telemetry/native/` 用仓库内的 `telemetry/tools/macho.py` 对解包出的原生件生成。

报告正文使用的 chunk 别名：`DZ`=`index.chunk-DzZc-q0x.js`、`CB`=`index.chunk-Cb2x-E4A.js`、`9hg`=`index.chunk-9hgN2KD3.js`、`CT`=`index.chunk-CtwayTMM.js`、`PRE`=`index.pre.js`、`MV`=`mainView.js`。

## Development Commands

本仓库没有 build / lint / test 命令；以下为分析过程中实际使用的命令形态。

```bash
# 定位 → 定点读取（超大文件的常态用法）
rg -n 'ipcMain\.handle' desktop/main-process-readable/index.chunk-DzZc-q0x.js
read desktop/main-process-readable/index.chunk-DzZc-q0x.js:130300-130385

# 原生模块静态分析（纯 stdlib）
python3 telemetry/tools/macho.py info|imports|exports|symbols|section|strings <file> [minlen]
python3 telemetry/tools/swiftdemangle.py telemetry/native/swift_addon.exports.txt

# Android：解包 / 反编译 / 字符串→类交叉引用（纯 stdlib）
unzip -q -o claude.apk -d android/apk-tree
jadx -d android/jadx-sources -j 8 --no-res --log-level warn claude.apk      # jadx 1.5.1；行号基准
python3 telemetry/tools/dex.py xref claude.apk android_id
python3 telemetry/tools/dex.py code android/apk-tree/classes.dex 'Lxru;'
dexdump -d android/apk-tree/classes.dex | grep -n 'getNetworkInterfaces\|isLoopbackAddress'  # R8 合成方法

# 重新格式化某个 chunk（重写文件）
cd <js-dir> && bunx prettier@3.9.9 --write --print-width 100 --log-level warn ./*.js

# 重新抽 asar（7-Zip 静态二进制，免安装）；必须连同 app.asar.unpacked 一起取出
7zz x Claude.dmg 'Claude/Claude.app/Contents/Resources/app.asar' -oasar -y
7zz x Claude.dmg 'Claude/Claude.app/Contents/Resources/app.asar.unpacked/*' -oasar -y

# 取回已不在工作树中的文件
git show HEAD:telemetry/<file>.md | head
```

`macho.py` 各子命令：`info`（架构/uuid/build version/dylibs/weak dylibs/install name/节区表）、`exports`（export trie）、`symbols`（LC_SYMTAB，含 `UNDF` 标记）、`imports`（仅未定义符号）、`section <name>`（原始字节）、`strings [minlen]`；无参数时打印 docstring 并返回 1。

`dex.py` 各子命令：`xref <apk|dex> <字面量>`（`const-string` 交叉引用，**仅对字符串字面量有效**——API 调用/字段访问走 `method_id`/`field_id`，需 `dexdump -d` 定位）、`code <dex> <L类;>`（类方法表 + `code_off`）、`strings <apk> <子串>`；仅 stdlib。

## Code Conventions & Common Patterns

**编辑任何文档前先读这一条——无源码接手（硬约束）。**
本仓库**不携带素材树**，所以每篇文档都必须能被一个**手上没有素材树**的读者完整读懂并复验。这是本仓库成立的前提，不是风格偏好。编辑时守住四条：

1. **每条结论自带定位手段。** 给出可复跑的唯一字面量或 grep 定位串。行号只是辅助——它绑定被审计的版本，且指向读者手上根本没有的产物。**只给行号 = 这条结论不可复验**，等同于没写。
2. **不写依赖素材树的相互引用。** 「见上文那份 chunk」「同前」这类写法对读者无效。要引就引仓库相对路径 `telemetry/<file>.md`。
3. **不要把素材树提交回来。** `cli/`、`desktop/asar-tree/`、`desktop/main-process-readable/`、`desktop/native-unpacked/`、`telemetry/native/`、`android/` 都在 `.gitignore` 里，只应存在于本地工作树。需要引用其中内容时，引用方式见 `Reproduction Path`。
4. **不要新增提取脚本。** 提取链路的复现规则一律以散文陈述，不落盘为脚本（`telemetry/tools/` 下既有的三个分析工具是历史例外，不再扩充）。

以下为其余约定：

- **证据最小单位** `文件:行`（桌面端 `index.chunk-DzZc-q0x.js:130039`、CLI `mod-0365.js:544`、原生 `strings:13055`），并同时记录**原文片段**（grep 定位串）；行号仅对 `desktop/main-process-readable/` 有效，片段可跨格式化版本重定位。
- 确定性标注：全仓统一用 `[Observed]`（有原文/行号证据）/ `[Inference]`（推断，须写明所依赖的 `[Observed]` 前提）。
- 压缩成单行的文件（renderer `assets/*.js`、部分原始 chunk）不引行号，改给 ≤200 字符原文片段 + 可复现的 `grep -o` 形式。
- 正文中文；代码标识符、命令、日志、字段名保持英文原样。
- 单文件 >10,000 行或 >1MB 的目标（`DZ` 289,971 行、`cli/modules/mod-0365.js` ~4MB、`telemetry/native/*.strings.txt` 最大 ~6MB）一律先 grep 后小范围 read；`.js` 单行文件的深行号（例如 `DZ` 13 万行之后）用 `read <file>:<start>-<end>` 定点读取。
- 文档命名：主题文档按「平台或主题」命名（`cli.md`、`desktop.md`、`linked.md`），纯数据附录加 `-catalog` 后缀（`desktop-event-catalog.md`），Android 单独立篇（`android.md`，与 desktop/cli 不共享代码）。**文档不编号、不按轮次推进。**
- 每篇主题文档自含结论速览表（开头，每条带等级、锚点与一条可复跑 grep）与证据正文，**不另设索引或汇总篇**——权威源即每篇自身。
- 文档间引用一律用仓库相对路径 `telemetry/<file>.md`。`README.md` §8 的索引表已失效，待重写。
- `desktop/`、`cli/` 两棵素材树自解包以来未修改；darwin 二进制（`.node`/`.dylib`/Go 二进制）在非 macOS 主机上不可执行，相关结论均来自静态读取。`android/` 是第三棵（Android）素材树，同样 gitignore、不入库。

## Important Files

| 文件 | 内容 | 定位用途 |
|---|---|---|
| `README.md` | 对外成稿：速查结论、Desktop/CLI 通道、跨端关联场景、加固建议、§8 索引表（**已失效**，待重写） | 结论层入口 |
| `telemetry/cli.md` | Claude Code CLI 2.1.283：通道 A–I、标识符、上行字段、BYOK/第三方暴露面、开关矩阵、负面清单 | CLI 主题唯一入口 |
| `telemetry/desktop.md` | Claude Desktop 2.9939.2：四条通道、身份与 DeviceRegistry、Desktop↔CLI 耦合、指纹面、原生模块、开关 | Desktop 主题唯一入口 |
| `telemetry/linked.md` | 跨端关联：三种场景的判定、唯一机械 join（出口 IP + 时间窗）、已证伪机制清单、切断措施 | 跨端判定唯一入口 |
| `telemetry/desktop-event-catalog.md` | 722 个 Desktop 事件名的逐条清单（含首个调用点行号），纯数据附录 | 按事件名查取 |
| `telemetry/android.md` | Android 端（`com.anthropic.claude` 1.260930.20）：5 条通道、Sift 设备指纹、身份锚点、同意门控、披露面、攻击面 | Android 主题入口 |
| `desktop/main-process-readable/INDEX.md` | 250 chunk 的 文件｜行数｜大小｜21 个关键词命中数 表（按体积降序） | 定位某 API/关键词落在哪个 chunk |
| `desktop/asar-tree/package.json` | 上游 manifest：`name=@ant/desktop`、`version=2.9939.2`、`main=.vite/build/index.pre.js`、8 个运行时依赖 | 版本/入口/依赖 |
| `telemetry/tools/macho.py`、`swiftdemangle.py`、`dex.py` | Mach-O 检查器、Swift 符号粗 demangler、DEX 字符串→类交叉引用 | 原生模块 / Android 分析 |

### 文档地图（去哪找什么）

> 下表是当前工作树里的全部文档。

- **`cli.md`**（Claude Code CLI）：§1 provider 分类与闸门 · §2 通道 A–I · §3 标识符 · §4 上行字段（事件载荷 / GrowthBook 属性 / 请求头 / 模型请求面） · §5 第三方 provider 暴露面 · §6 开关矩阵 · §7 负面清单 · §8 未复验边界
- **`desktop.md`**（Claude Desktop）：§1 通道全景 · §2 四条通道逐条 · §3 标识符与 DeviceRegistry · §4 开关汇总 · §5 rowPk 的遥测去向 · §6 Desktop→CLI 耦合（二进制/env/共享配置根/OTel 注入） · §7 指纹面（提示词/头/日志包） · §8 原生模块 · §9 负面清单 · §10 未找到与需补证
- **`linked.md`**（跨端关联）：§1 BYOK 未登录仍发出的请求 · §2 唯一机械 join · §3 关联路径逐条 · §4 已证伪机制 · §5 指纹面两端对照 · §6 切断措施 · §7 静态不可判定项
- **`desktop-event-catalog.md`**：722 事件清单（数据附录）
- **`android.md`**：Android 端（单独立篇，跨平台）
- 每篇开头另有「全景：按使用场景看上行数据」，按用户实际使用方式组织同一批结论，供无完整上下文的读者快速建立整体图景。

## Runtime/Tooling Preferences

- `telemetry/tools/*.py` 仅依赖 Python 标准库（不依赖 `pip` 安装的第三方包，如 `capstone` / `macholib` / `androguard`）。
- 格式化通路为 `bunx prettier@3.9.9`，**必须带 `--print-width 100`**（默认 80 会让行数差约一成，全部行号错位）→ 无独立 `prettier` 可执行文件。
- asar 解包使用 7-Zip 静态二进制（`7zz`，免安装、免 sudo）；被标记为 unpacked 的条目要用同级的 `app.asar.unpacked/` 补齐，`resources/bundled-skills/*.skill` 是 zip、需逐个解开。
- 原生二进制分析不依赖 llvm/objdump：`objdump` / `nm`（binutils）不支持 Mach-O 反汇编，改用 `telemetry/tools/macho.py` + `strings` 转储。
- Android 反编译用 `jadx`（**行号基准，必须为 1.5.1**）与 Android SDK `build-tools` 的 `dexdump` / `apkanalyzer` / `aapt2` / `apksigner`；均不在仓库内，需自备。

## Testing & QA

- **仓库内不存在测试**：无 `*.test.*` / `*.spec.*` / `test/` / `tests/` / `__tests__/`，无 pytest/jest/vitest/mocha 配置，无 `Makefile`/`justfile`/CI 配置；唯一 `package.json`（`desktop/asar-tree/package.json`）无 `scripts` 键。检索：`find . -path ./.git -prune -o \( -name '*.test.*' -o -name '*.spec.*' -o -name test -o -name tests -o -name __tests__ -o -name Makefile -o -name justfile \) -print` → 空。
- 质量控制手段 = 逐条引用核验：定位串重定位 → 定点 read 原文 → 与原始 chunk / `telemetry/native/*.txt` 转储交叉核对 → 标注 `[Observed]`/`[Inference]`。每篇主题文档的结论速览表里，每条结论附一条可复跑的 grep，读者可随时打回原形。
- 三处容易误传的结论（勿再沿用早期说法）：① 自定义 `ANTHROPIC_BASE_URL` **不**关闭 CLI 通道 A，真实效果只关闭通道 C；② CLI **会**经 GrowthBook `apiBaseUrlHost` 明文上报第三方 provider 域名；③ `anthropic-client-platform` **不是**默认发送，仅 Desktop 拉起的会话经 `Lhn()` 注入。
- 可复现性：仓库内无提取脚本，原始安装件与 7-Zip 静态二进制不在仓库中，需自行获取后按 `Reproduction Path` 一节的规则重建各素材树；报告里每条引用都可用该方法逐条核对。
