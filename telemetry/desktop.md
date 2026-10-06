# Claude Desktop — 遥测、身份与上行面

**审计对象**：Claude Desktop **2.9939.2**（macOS/Electron 构建，`desktop/asar-tree/` 为 asar 原样解包，`desktop/main-process-readable/` 为 prettier 化产物）。

**行号基准**：`desktop/main-process-readable/*.js`（per-file 1-based）。chunk 别名：`DZ = index.chunk-DzZc-q0x.js`、`CB = index.chunk-Cb2x-E4A.js`、`PRE = index.pre.js`、`9hg = index.chunk-9hgN2KD3.js`、`CHN = index.chunk-CHNweogn.js`。渲染进程 bundle 是压缩单行文件，引用用「文件名 + 原文片段」而非行号。

**平台范围**：素材只覆盖 macOS 构建；代码内含 Windows 分支（注册表策略、MSIX 包路径等），但各平台的实际安装形态与卸载行为不在本仓库内，相关推断以此为前置。

**范围**：Desktop 自身进程的出站流量、持久标识符、上行字段与关断开关。CLI 见 `cli.md`；两端关联见 `linked.md`；Android 见 `android.md`。

**标注约定**：`[Observed]` = 有原文/行号证据；`[Inference]` = 由代码推出，并写明所依赖的前提。

---

## 0. 结论速览

| # | 问题 | 结论 | 等级 | 复验 |
|---|---|---|---|---|
| 1 | 有没有抓物理硬件码 | **没有。** 整个 `desktop/`（asar 全部 559 文件 + 6 个渲染窗口）对 `machineId`/`IOPlatformUUID`/`ioreg`/`hardwareUUID` 大小写不敏感检索 **0 命中** | `[Observed]` | `grep -rin 'IOPlatformUUID\|getMachineId' desktop/` |
| 2 | 那机器级标识是什么 | 只有**安装级** `ant-did`（UUIDv4，自己生成、写本地文件）；跨重装会变 | `[Observed]` | `grep -rn 'ant-did' desktop/ \| head` |
| 3 | 不登录会发数据吗 | **会。** Sentry 启动即初始化；更新检查把 `device_id=<ant-did>` 明文拼进 URL；一方事件冷启动即排队（未登录时 `user_id="anonymous"`） | `[Observed]` | `grep -n 'device_id=' desktop/main-process-readable/index.chunk-DzZc-q0x.js` |
| 4 | 会把第三方 provider 报出去吗 | **会，明文。** 每条一方事件的 metadata 都带 `inference_provider`/`inference_host`/`inference_base_url`/`inference_host_kind`；Sentry 侧带 tag `inference_provider` | `[Observed]` | `grep -n 'inference_host_kind' desktop/main-process-readable/index.chunk-DzZc-q0x.js` |
| 5 | 会把时区/语言报出去吗 | **会。** 经 Sentry 的 `contexts.culture{locale,timezone}` 上报（`Asia/Shanghai`/`zh-CN` 这种原值） | `[Observed]` | `grep -n 'culture' desktop/main-process-readable/index.pre.js` |
| 6 | 上报主机名吗 | **不报。** Sentry 显式 `includeServerName:!1`；一方事件 metadata 无 hostname 字段 | `[Observed]` | `grep -n 'includeServerName' desktop/main-process-readable/index.pre.js` |
| 7 | 有硬件锚定吗 | **有，但不是读硬件 ID**：DeviceRegistry 用 Secure Enclave 生成 P-256 密钥对，公钥注册到组织，服务端按设备行主键 `rowPk` 区分 | `[Observed]` | `grep -n 'hardwareKeyGetOrCreate' desktop/main-process-readable/index.chunk-DzZc-q0x.js` |
| 8 | 会把本机 CLI 会话报出去吗 | **会。** `desktop_ccd_*` 事件带 `cli_session_id`、`cli_version`、`model`、token 计数、`session_cwd`（路径逐段脱敏） | `[Observed]` | `grep -n 'cli_session_id' desktop/main-process-readable/index.chunk-9hgN2KD3.js` |
| 9 | 会读网页 cookie 并上行吗 | **会。** 主进程读 `anthropic-device-id`/`ajs_anonymous_id`/`lastActiveOrg` 三个 cookie，分别进 OAuth 头、实验事件、org 兜底 | `[Observed]` | `grep -n 'anthropic-device-id' desktop/main-process-readable/index.chunk-DzZc-q0x.js` |
| 10 | 有系统代理探测吗 | 主进程与遥测路径**不读**（无 `scutil --proxy`/`networksetup`）；但原生 `swift_addon` 会读系统代理，用于配置 Cowork 虚拟机的网络（该值不上报）。VPN 探测只存在于 Cowork VM 启动失败这一条极窄路径 | `[Observed]` | `grep -rn 'scutil' desktop/ \| head`；`grep -l CFNetworkCopySystemProxySettings telemetry/native/` |
| 11 | CLI 的 `DISABLE_TELEMETRY` 能关掉 Desktop 吗 | **不能。** 这三个变量在 Desktop 主进程 0 命中；Desktop 的开关是托管配置里的 `disableEssentialTelemetry`/`disableNonessentialTelemetry` | `[Observed]` | `grep -c 'DISABLE_TELEMETRY' desktop/main-process-readable/index.pre.js` |
| 12 | 会向 CLI 子进程注入什么 | 3p 分支下强制 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`、`DISABLE_GROWTHBOOK=1`，并把 `DISABLE_TELEMETRY` 清成空串（**清掉**外部继承值） | `[Observed]` | `grep -n 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC' desktop/main-process-readable/index.chunk-DzZc-q0x.js` |

---

## 全景：按使用场景看上行数据

§0 是按问题列出的结论，以下各节是按通道与字段排列的证据。本节按用户的实际使用方式重新组织同一批结论，说明每种使用方式下有哪些数据离开本机、服务端由此能推断出什么。关键字段名仅在必要时出现，其余细节指回对应小节。

Desktop 与 CLI 的主要差异在于，前者不进行「第一方 / 第三方」的判断。四条通道彼此独立，各有各的开关，互不牵连。由此产生两个容易误判之处。其一，切换 provider 不会使上报停止：改为 BYOK 或第三方部署后，产品事件与更新检查照常发送，只是不再附带凭据、并增加若干标注字段。其二，未登录同样会上报：程序启动时即有一条错误上报、一批产品事件与一次更新检查发出，三者互不依赖（§1）。

**场景 1：安装后首次启动（未登录）**
三条通道同时发出。错误上报携带安装 ID、时区、语言与内存信息；产品事件携带完整的机器画像与所配置的推理端点；更新检查在下载地址的查询串中明文携带该安装 ID。服务端由此获得该机器的系统版本、时区、语言与机型，以及它是否指向第三方端点，全程不需要登录（§2.1–§2.3）。

**场景 2：登录官方账号**
三条通道的行为不变，产品事件开始包含账号与组织信息，错误上报补充组织 ID。登出后事件继续发送，账号字段变为匿名值。

**场景 3：日常聊天**
事件按批发送（满 50 条或每分钟一次）。内容为窗口开关、点击与扩展调用等，不包含聊天正文（§2.2）。

**场景 4：改为 BYOK 或第三方 provider**
三条通道均不停止。产品事件照常发送，并在每条事件中明文携带所配置的第三方域名（含主机名、端口与路径），同时标注部署模式为第三方。唯一的变化是错误上报增加若干标注字段。关闭这些上报依赖托管配置中的开关，与 provider 的切换无关（§2.2、§4）。

**场景 5：在 Desktop 内启动 Claude Code 会话**
这是唯一会把机器、账号与 CLI 会话三者写入同一条事件的场景：单条记录中同时包含安装 ID、账号与组织，以及 CLI 会话 ID。跨端关联即由此建立。同一过程中 Desktop 将登录凭据注入子进程，并强制关闭子进程的遥测，因此子进程自身不外发数据，外发的是 Desktop 自身的事件（§6）。若不需要这种关联，应避免在 Desktop 内启动 Code 或 Cowork 会话。

**场景 6：使用 Cowork 或本地代理**
事件量最大的一族（154 个 `lam_` 前缀），涵盖远程工具桥的注册与派发、文件夹授权与设备状态。仅在 Cowork 虚拟机启动失败这一狭窄路径上会探测虚拟网卡，此时网卡名与服务名经哈希后上报；正常使用时不进行该探测（§7.3）。

**场景 7：连接 Chrome 扩展或使用 computer use**
仅在用户实际连接后发送，内容包括扩展实例 ID（并非机器 ID）、工具调用与权限决策。窗口标题默认不采集（§3.6、§2.6）。

**场景 8：崩溃或报错**
经错误上报通道发送，携带安装 ID、时区语言与系统内存。崩溃转储以原始字节上传，脱敏钩子无法触及，这是全篇脱敏最薄弱的一处（§7.3）。

**场景 9：生成诊断报告或提交反馈包**
诊断报告在用户点击「导出」（仅导出到本地）时同样会发送一条事件；包内脱敏会抹除家目录与用户名，但时区、语言与中文目录名原样保留。反馈包由用户手动提交，携带登录凭据（§7.3、§2.5）。

**场景 10：自动更新**
不受任何遥测开关控制，这也是关闭遥测后程序仍然联网的原因；需要单独关闭更新检查。

**完整关闭的方式**：在托管配置中同时设置 `disableEssentialTelemetry` 与 `disableNonessentialTelemetry`，将 `otlpEndpoint` 留空，并关闭自动更新。需注意这两个开关的适用范围标注为「第三方部署」，且默认值均为发送（§4）。

---

## 1. 出站通道全景

Desktop 一共维护四条遥测类通道 + 若干功能性一方端点：

```
Claude Desktop (Electron 主进程)
 ├── 1. Sentry（essential）        → o1158394.ingest.us.sentry.io     [默认开，冷启动即发]
 ├── 2. 一方产品事件（non-essential）→ claude.ai/api/event_logging/v2/batch  [默认开，722 个事件名]
 ├── 3. 自动更新检查               → api.anthropic.com（或 releases.claude.com）[默认开，URL 带 ant-did]
 ├── 4. OTLP（企业）               → 管理员配置的 collector            [默认关，需 otlpEndpoint]
 └── 5. 功能性端点（非遥测）        → 诊断包/反馈包/OAuth/CLI 二进制下载/模型目录
```

---

## 2. 通道逐条

### 2.1 Sentry（错误与崩溃）

- **端点**：`https://2f98127cbffe4740b1f767a2de77d23b@o1158394.ingest.us.sentry.io/4507368973008896`，**硬编码，无环境变量可覆盖**（`SENTRY_DSN`/`SENTRY_ENVIRONMENT`/`sentryDsn` 环境变量 0 命中；`SENTRY_RELEASE` 仅作为构建注入的全局常量出现，不参与覆盖）。SDK 为 `@sentry/electron` 7.12.0。
- **传输**：托管配置下发固定代理或 PAC 脚本时，Desktop 通过 `app.commandLine.appendSwitch` 向 Chromium 网络栈追加 `proxy-server` 与 `proxy-bypass-list`（或 `proxy-pac-url`），日志记为 `[egress-proxy] pinned to …; OS proxy settings ignored`。Sentry 的传输层由 Electron `net.request` 发出，因此错误上报走这个固定代理，不再跟随系统代理；该键未配置时，系统代理才对这条通道生效。
- **触发**：启动即初始化，条件 `!telemetry.disableEssential && process.env.CI == null`；**不要求登录**。
- **标识**：`initialScope.user.id = ant-did`；`tags.deployment_mode = "1p"|"3p"`；运行期再 `setUser({id: zC(), organization_id: <orgUuid>})`。**无 accountUuid/machineId/hostname**。
- **release**：由 `gb()` 取应用名与版本号拼接，`[Inference]` 在本构建为 `Claude@2.9939.2`（`[Observed]` 前提：`package.json` 的 `productName` 为 `Claude`、`version` 为 `2.9939.2`，Electron 在设置 `productName` 时以其作为 `app.name`）。构建期注入的全局常量 `SENTRY_RELEASE = { id: "d3e50475…" }` 只作为渲染进程浏览器 SDK 的默认 release 进入信封；主进程自身的 init 不使用它。主进程转发渲染进程信封时保留 `release`，转发 utility 进程信封时将其删除。
- **指纹字段**：SDK 自动的 `contexts.os/culture` 含 **locale、timezone、kernel_version、memory、boot_time、screen_resolution/density**——中文系统的 `zh-CN` + `Asia/Shanghai` 由此上行。Sentry 侧的跳过脱敏名单还包括 `linux_distro`、`linux_distro_version`、`linux_session_type`、`linux_desktop_environment`、`gpu_compositing`、`gpu_compositing_raw`、`hw_accel_user_disabled`，这些字段原样上报。另有一个名为 `AdditionalContext` 的集成，默认只上报屏幕分辨率与像素密度，机型与厂商两项关闭（`deviceModelManufacturer: false`）；开启时 win32 下执行 `powershell -NoProfile "Get-CimInstance -ClassName Win32_ComputerSystem | ConvertTo-Json"` 读取 `Manufacturer`/`Model`，macOS 下执行 `system_profiler SPHardwareDataType -json` 读取 `machine_model`，结果写入事件的 `contexts.device`。本构建为默认关闭，因此 `device.model` 不含机型。
- **3p 专属**：`setContext("managed_config")` + `setTag("config_source")`/`config_source_remote`/`inference_provider`，仅当 `VQ(config)` 为真（非 1p 部署）时注入。
- **脱敏**：`beforeSend`/`beforeBreadcrumb` 会替换 homedir、appPath、URL userinfo，并按正则过滤 `sk-ant-`、AWS key、`gh*_`、JWT、Windows SID 等。**但没有针对 prompt 文本/文件内容的语义级剥离**——这类内容若经 console/错误消息进入 Sentry，只做通用路径/密钥脱敏。
- **不采集**：窗口标题（`captureWindowTitles:!1`）、截图、渲染 profile、主机名（`includeServerName:!1`）、IP（`sendDefaultPii:!1` → `infer_ip:"never"`）。
- **另附带上报**：除错误与崩溃外还随信封发送三类内容——release-health 会话（`getSessions` 绑定默认 session）、丢弃与限流的 client reports（`sendClientReports: !0`），以及向第一方域注入 trace 头的 `tracePropagationTargets`，其白名单是一条匹配 `anthropic.com`、`claude.ai`、`claude.com`、`ant.dev` 及其子域的正则。
- **出站闸门**：三态 `open/held/blocked`。`gate = thirdParty ? "open" : (restrictedAtSeed ? "blocked" : (holdDisabled ? "open" : "held"))`——**1p 默认 `held`**，即事件先入本地队列等组织合规裁决（5 分钟无裁决超时后按策略放行/丢弃）；**3p 默认直接 `open`**。离线时进队列（`<userData>/sentry/queue/queue-v2.json`，30 天 / 30 条）。
- **渲染进程**：每个窗口 bundle 内联 `@sentry/browser`，DSN 是占位 `https://12345@dummy.dsn/12345`，信封经 `sentry-ipc` 交主进程代发；渲染载荷**不含任何 deviceId/userId/session_id**。
- **关断**：`telemetry.disableEssential`（托管配置）、`process.env.CI`（哪些变量对 Desktop 无效，见 §4）。

### 2.2 一方产品事件（`claude.ai/api/event_logging/v2/batch`）

- **端点**：`POST https://claude.ai/api/event_logging/v2/batch`（基址打包版硬编码，仅 dev 可被 `CLAUDE_AI_URL` 改）。头 `Content-Type` + `x-service-name: claude_desktop`，**默认无凭据**（`Authorization`/`Cookie` 只在远端开关 `3043546415` 返回 `bearer`/`cookie` 时才加，且还要满足 `W().type==="1p"` 与 origin 白名单）。凭据的加挂另有两项条件：该批事件中 accountUuid 恰有一个且等于当前登录账号，orgUuid 不超过一个；任一不满足即退回无凭据上传。一次带凭据请求收到 401 或 403 后，凭据上传停用 6 小时，期间所有批次改为无凭据发送。`bearer` 所用的 telemetry token 不是每次请求都铸造：按账号与 org 的哈希排定，每个 199 分钟周期内只有 20 分钟的窗口可铸造，且要求设备在线；窗口之外该批改用 cookie。
- **批量**：满 50 条或 60–600 秒抖动 flush（远端开关 `2654621331` 可调）；`process.env.CI` 时整批丢弃；失败即丢（有损，不重入队）。
- **载荷**：`{events:[{event_type:"TelemetryEvent", event_data:{event_name, timestamp, user_properties:{user_id}, metadata:"<JSON string>", auth:{organization_uuid?, account_uuid?}}}]}`。
- **metadata 固定字段**（可整机指纹化）：`product_surface: "claude-desktop"`、`deployment_mode`、`config_source(_remote)`、**`inference_provider`/`inference_base_url`/`inference_host`/`inference_host_kind`**、`app_version`、`commit_hash`、`platform`、`arch`、`installer_variant`、`running_under_translation`、`os_version`、`os_release`、`os_build`、`cpu_model`、`total_memory`、`device_class`（按内存分档 `le4|8|16|gt16`）、`free_memory`、`desktop_variant`（恒 `"production"`）、`store_build`（恒 `false`）、`available_memory`（可用内存字节数，取不到时为 `null`）、`app_session_id`、`install_id`、`app_uptime_seconds`、`window_count`、`organization_id`、`hipaa_origin_organization_id`。
- **`inference_host_kind` 是主机名分类结果**，取值为 `unconfigured | anthropic | localhost | private | other`：`localhost`、`127.0.0.1`、`::1` 与 `*.localhost` 归为 `localhost`，内网段与 `.local`/`.lan`/`.internal` 归为 `private`。把本地转发代理（如 `http://127.0.0.1:8080`）配成推理端点时，`inference_host` 与 `inference_host_kind` 原样进入每条事件的 metadata；二者都在 `skipKeys` 白名单内，不脱敏。`inference_base_url` 相反：它取所配端点的 origin 加 path，主机名与路径原样，但整个值要过 `hr()` 逐条替换其中的密钥样式子串（`sk-ant-…`、JWT、云厂商凭据等），因此它不在免脱敏白名单内。
- **`os_build` 的来源**：Windows 上取注册表 `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion` 的 `BuildLabEx`，macOS 上取 `/System/Library/CoreServices/SystemVersion.plist` 的 `ProductBuildVersion`。二者都是安装级稳定、随每条事件上行。
- **事件量级**：**722 个事件名**，按族：`desktop_*` 431、`lam_*` 163、`cowork_*` 27、`ccd_simulator_*` 20、`cu_*` 20、`chrome_bridge_*` 16、`custom3p_*` 11、`grand_prix_*` 10、`tengu_*` 10、`marketplace_*` 7、`remote_plugin_*` 3、`device_registry_*` 2、`builtin_websearch_*` 1、`ssh_terminal_*` 1，其中 10 个 `tengu_*` 属内嵌 CLI 代码而非 Desktop 事件。逐条清单见 `desktop-event-catalog.md`（该文的提取方法有已知盲区，722 是两种方法合并枚举到的结果而非精确总数）。
- **携带本机 CLI 信息**：`desktop_ccd_*` 事件带 `cli_version`、`cli_session_id`、`model`、`permission_mode`、`tool_calls[].tool_name`、`input_tokens`/`cache_*_tokens`、`session_cwd`/`cwd`/`worktree_path`（路径**逐段脱敏** `scrubPaths`）。**不存在独立的「CLI 账号 UUID」字段**，账号统一用 `auth.account_uuid`。
- **脱敏**：`SWe(e,{hipaa})`；`skipKeys` 白名单（`app_version`/`commit_hash`/`platform`/`arch`/`os_*`/`cpu_model`/`app_session_id`/`organization_id`/`inference_provider`/`inference_host`/`inference_host_kind`/`linux_distro_id`/`linux_distro_version_id`/`linux_session_type`/`linux_desktop_environment` 等）**原样通过**；HIPAA 组织走 `vWe()`，把大量字段替换为字面量 `"hipaa_redacted"`。
- **三类关联标识同样明文上行**：`request_id` 先过形状闸 `/^[a-zA-Z0-9:_-]{0,64}$/`，并要求长度小于 40、且未被密钥擦除改动（或命中已知会话 id 形状），通过则原样保留，否则写 `<invalid-id>`；`switch_id` 过 UUID 形状闸，通过则原样保留，否则写 `<non-uuid>`；`backend_error_code` 在 `skipKeys` 白名单内，不做任何处理。HIPAA 组织下三者一律变为 `hipaa_redacted`。服务端由此可把产品事件与 API/会话侧日志按请求标识直接关联。
- **关断**：`telemetry.disableNonessential`（默认 false）。**两条不受它约束**：`CoworkSessionDeletionEvent`（独立 POST，只对 3p 早退，无 `disableNonessential` 判断）与更新检查（见 2.3）。前者请求头只有 `Content-Type` 与 `x-service-name`，不附加任何凭据；单次请求超时 15 秒，最多重试 3 次，仅 5xx 与 429 会重试，两次退避间隔依次为 1 秒与 3 秒。

`[Observed]`（复验：`grep -n 'uploading without a credential' DZ`、`grep -n 'desktop_variant' DZ`、`grep -n 'x-service-name' desktop/main-process-readable/index.chunk-CejZVVRk.js`）

### 2.3 自动更新检查

- **端点**：`GET https://api.anthropic.com/api/desktop/<platform>/<arch>/<feed>/update?device_id=<ant-did>&version=<appVersion>&os_version=<systemVersion>`（`autoUpdate.viaUpdatesHost` 为真时改走 `releases.claude.com`）。URL 末尾还可追加 `&maxVersion=<策略上限>`（仅当设置了 `autoUpdate.dangerousMaxVersion`）。路径中的 `<arch>` 默认为 `universal`，启动后会对实际架构的 URL 发一次探测请求，返回 200 或 404 则改用它（`arm64`，在 ARM 转译下；否则为 `process.arch`，如 `x64`），否则维持 `universal`。
- **关键**：`device_id` = `ant-did` **明文拼在 URL query 里**，启动即发、定时轮询、**与登录无关**。这是全部通道里唯一「未登录也带机器标识出站」的端点之一。
- **关断**：受 `disableAutoUpdates` 控制，**不受任何遥测开关约束**。

### 2.4 OTLP（企业 OTLP 导出）

- **Desktop 内没有完整 OTel SDK**（`OTLPLogExporter`/`NodeSDK`/`resourceFromAttributes`/`com.anthropic.claude_code` 在 `desktop/` 全 0 命中；`package.json` 无 `@opentelemetry/*` 依赖）。Desktop 自己只有一层**手写的 OTLP/HTTP-JSON 日志导出器**，只发 logs、无 metrics、无 traces。
- **端点**：托管配置 `otlpEndpoint` + `/v1/logs`（**固定 http/json**）；**无默认值**——不配就不启动（不是 `localhost:4317`）。`otlpProtocol` 默认 `http/protobuf` 只影响转发给 CLI 的会话。远端下发时 `rejectLoopback`。
- **自身不读 `OTEL_*` 环境变量**：这些名字在 Desktop 代码中只出现于写进子进程环境的路径与白名单，没有一处从 `process.env` 取值。`OTEL_LOG_*` 在 Desktop 侧同样只写不读，其内容豁免由托管配置的 `otlpContentCapture` 决定。
- **鉴权与请求头**（三个托管配置键，均标 `scopes:["3p"]`）：`otlpHeaders` 是静态头；`otlpAuthMode` 取 `none` 或 `inference-credential`，后者会把**用户的推理凭据**作为 `Authorization: Bearer <token>` 发给 collector（schema 自述原文：*“inference-credential sends the user's inference bearer token to the collector as Authorization: Bearer.”*）；`otlpHeadersHelper` 是一个**脚本路径**（`pathKind:"file"`，标 `requiresUserConsent:!0`），运行期执行该脚本、2 秒超时、解析其 stdout 的 JSON 作为请求头，并**覆盖前两者**。
- **触发**：`otlpEndpoint` 有值且 `otlpDesktopLogLevel !== "off"`；**默认级别是 `error`**，即默认只有 `*_failed|*_error|*_crash|*_timeout` 四类后缀事件外发。
- **载荷**：`resourceLogs[0].scopeLogs[0]`，`scope.name = "claude-desktop.events"`，`body.stringValue = <事件名>`，`attributes = <脱敏后的事件属性>`。批处理 `maxQueueSize=1000`、flush 100 条 / 5 秒；单次导出请求超时 10000 毫秒，导出失败的错误上报去重窗口 300000 毫秒。
- **resource 属性里的身份**：`service.name="claude-desktop"`、`service.version`、`claude.deployment_mode`、`host.arch`、`os.type`、`os.version`，以及两处**明文**：**`process.owner` = OS 登录用户名**（`os.userInfo().username`）与 **`enduser.id` = `email ?? upn ?? name`**（企业网关身份，受 `workspace.endUserAttribution` 约束）。**不含 `install_id`/`ant-did`/`session.id`/`account_uuid`**。
- **开关范围**：除 `otlpContentCapture` 外，全部 OTLP 配置项标注 `scopes:["3p"]`（只在第三方部署形态可用），但运行时门控只看「endpoint 是否设置」。**不受 `disableNonessentialTelemetry` 约束**。
- **三个次要配置键**：`otlpResourceAttributes` 是一组自定义 resource 属性，用户或管理员给出的键优先，因此可覆盖自动填充的 `enduser.id`；`otlpTracesEnabled` 决定 spawn 的 Cowork 与 Code 会话是否开启 traces（对应给子进程设 `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` 与 `OTEL_TRACES_EXPORTER=otlp`），未设置或为 `false` 时即使 CLI 侧自开 traces 也不生效；`otlpAttrMaxChars` 限制单个属性长度，允许 256 至 32000，界面显示默认 4000。
- **内容豁免**：`otlpContentCapture` 控制哪些类别不脱敏（`userPrompts`/`assistantResponses`/`toolDetails`/`toolContent`/`rawApiBodies`，默认 `["userPrompts","toolDetails"]`），与 CLI 的 `OTEL_LOG_*` 同义。

### 2.5 其他一方端点（功能性，非遥测）

| 端点 | 方法 | 用途 | 备注 |
|---|---|---|---|
| `/api/desktop/features` | GET | GrowthBook 特性拉取 | 仅配置了 bootstrap 服务器时 |
| `/api/claude_cli_feedback/bundle` | POST | **用户主动**提交 Cowork 反馈包（zip：日志 + 可选 transcript） | UA 形如 `claude-cli/cowork-feedback <platform>-<arch> desktop/<appVersion>`，另带 `Authorization: Bearer <OAuth token>`，超时 60 秒 |
| `/v1/oauth/<orgId>/authorize` | POST | OAuth 授权码换取 | 头集为 `anthropic-version: 2023-06-01`、`Authorization: Bearer <sessionKey>`、`Content-Type`、`anthropic-client-platform: desktop_app` 与 `anthropic-client-version`；`anthropic-device-id` 仅在 cookie 有值时附加 |
| `/api/organizations/<org>/cowork/remote_devices` | GET/POST | 设备注册（公钥） | 见 §3.4 |
| `downloads.claude.ai/*` | GET | VM bundle / CLI 二进制 / 模型目录（5–15 分钟轮询） | 无标识符 |
| 诊断包上传 | — | Help → Generate Diagnostic Report | 上传动作在 renderer，主进程只算 zip 与 `canSend` |

### 2.6 渲染进程与内嵌网页

- 6 个窗口全部落在 `session.defaultSession`（**无 partition**）→ 内嵌的 claude.ai 与桌面共享同一个 cookie jar。
- 主进程**主动读网页 cookie**：`anthropic-device-id`（→ OAuth 请求头 + 实验事件 `device_id`）、`ajs_anonymous_id`（→ 实验事件 `anonymous_id`）、`lastActiveOrg`（→ `organization_uuid` 兜底）。这是「网页 ↔ 桌面」被关联的真实通路。
- **整份托管配置会交给页面**：主视图 preload 把同一个对象挂在 `window.desktopManagedConfig`、`window.desktopEnterpriseConfig` 与 `window.desktopTelemetryConfig` 三个名字下，另单独暴露 `window.desktopDeviceClass` 与 `window.desktopPreferredLanguages`。该对象由主进程构造成 `--desktop-managed-config=<JSON>` 启动参数，内含两个关断标志、`deploymentMode`、`deploymentOrganizationUuid`、`deviceClass`、`preferredSystemLanguages`、`cookielessOrigin`、`appVersion`、`forceLoginOrgUUIDs`、`loginSsoOrgDomain` 等。这段暴露位于 preload 顶层，只以「启动参数是否存在」为条件，不经后文那个 origin 白名单守卫，因此凡是加载 `mainView.js` 的窗口都能读到整份配置。
- **渲染进程内存上报**：主视图 preload 经 IPC 把内存样本交给主进程，字段为 `heapUsedKb`、`heapTotalKb`、`heapLimitKb`、`blinkAllocatedKb`，取自 `process.getHeapStatistics()` 与 `process.getBlinkMemoryInfo()`；首次在页面加载 15 秒后上报，之后每 60 秒一次，且只在顶层框架启用。主进程校验四个字段是 0 至 1 GiB 之间的数字，并要求发送框架是顶层帧、origin 属于 claude.ai/claude.com 及其 preview 域名或 `app://localhost`（`localhost` 与 `*.ant.dev` 仅在开发者放行开关开启时）。样本归一化为字节数后供 `process_renderer_main_view_*` 遥测字段消费，载荷本身不含标识符。
- 除前述六个窗口外，还有两类 3p 企业管理窗口复用 `mainView.js` preload：`custom3p-device-code` 与 `custom3p-setup`。两者加载的都是本地自定义协议地址（`app://localhost/device-code-verify` 与 `app://localhost/setup-desktop-3p`，不是 http(s) 远程地址），但拿到与内嵌 claude.ai 主视图相同的桥接面。
- 主视图页面还会经 `claude.web` 命名空间回传 `WebBuild.reportCommitHash`、`ContentStampReporter.report` 与 `Account.setAccountDetails` 三条控制消息，受 origin 门控。方向是页面到桌面，不是桌面自身的外发。另有一条与主窗口无关的 UA 覆写：CDP 工具链在移动仿真时用 `Emulation.setUserAgentOverride` 把 UA 换成 `Android 14; Pixel 8` 的 Chrome 串。
- egress 白名单表（`claude.ai/api/v2/rum`、`claude.ai/api/event_logging/`、`api.anthropic.com/api/event_logging/` 等）按 `toggleKey` 管控；关闭开关是真的删 CSP。
- 出口表里 renderer-origin 的其余六项为：`datadog-rum`（`{anthropicHost}/api/v2/rum` 与 `browser-intake-*.datadoghq.com` 一族，开关 `disableEssentialTelemetry`）、`segment`（`a-cdn.anthropic.com` 与 `a-api.anthropic.com`，`connect-src`/`script-src`，开关 `disableNonessentialTelemetry`）、`connector-favicons`（`www.google.com/s2/favicons` 与 `*.gstatic.com/faviconV2`，`img-src`）、`artifact-sandbox`（`{artifactIframeHost}`，缺省 `www.claudeusercontent.com`，`frame-src`，附三个资源 CDN）、`mcp-app-sandbox`（`*.claudemcpcontent.com`，`frame-src`，附 `assets.claude.ai`）、`dictation`（`dictationCsp.host`，`connect-src`）。后五项由 `disableNonessentialServices` 控制，`dictation` 无开关。

`[Observed]`（复验：`grep -n 'desktopManagedConfig' desktop/main-process-readable/mainView.js`、`grep -n 'RendererMemoryReporter' DZ`、`grep -n 'mcp-app-sandbox' DZ`、`grep -n 'custom3p-device-code' DZ`）

---

## 3. 标识符

### 3.1 `ant-did`（安装级，唯一的持久机器侧标识）

- 生成：首次需要时 `crypto.randomUUID()`，**与登录无关**；内容以 **base64** 写入 `<userData>/ant-did`，权限 `0600` + `flag:"wx"`。
- 读取校验 UUID 形状；内容非法且是普通文件时 `rmSync` 重建；极端失败回退全零 UUID `00000000-0000-0000-0000-000000000000`。
- 去向：Sentry `user.id`、一方事件 `install_id`、更新检查 URL `device_id`、诊断包 `installId`、**3p 非 hybrid 下作为 `accountUuid`/`tagged_id`**。
- 重置：进程退干净后删除该文件，重启即换新值。**卸载重装是否连带清除取决于代码之外的因素**（安装形态、userData 落点、外部卸载器实现）——本仓库无法定论。

### 3.2 `sha256(ant-did)` → CLI 的 `userID`（唯一跨端种子）

- Desktop 在**它自己拉起的** CLI 会话里，把 `sha256(ant-did)` 的 64 位 hex 写进该会话的 `.claude.json` 的 `userID` 字段，而 CLI 对该字段的校验正是 `^[0-9a-f]{64}$`。
- **写入路径精确为**：`<userData>/local-agent-mode-sessions/<accountId>/<orgId>[/agent]/<sessionId>/.claude/<.claude.json 或 .claude-*-oauth.json>`——是**会话级私有目录**，不是全局 `~/.claude.json`，也不是 `<userData>/sessions/<id>`。文件名可变（目录里若已有 `-staging-oauth`/`-local-oauth`/`-custom-oauth` 变体就写那个）。
- **写入的四个前提**（缺一不写）：① GrowthBook 门 `2220415149` 为开（**bundle 内无静态默认，状态由服务端下发，静态不可判定**）；② 会话**首轮**（`isFirstTurn`）；③ 账号已解析（`currentAccountId && currentOrgId` 均非 null——**未登录时直接抛错被吞掉，不写入**）；④ `ant-did` 可读。
- **独立终端 CLI 读不到**：CLI 读 `join(CLAUDE_CONFIG_DIR || homedir(), ".claude<suffix>.json")`，未设环境变量时是 `~/.claude.json`，与上述会话目录**无交集**。只有 Desktop 内部拉起 CLI 时把 `CLAUDE_CONFIG_DIR` 指向会话目录，种子才生效。

### 3.3 账号级 / 组织级

- `account_uuid`：来自 claude.ai 登录态（内存 store `current-account`，导航即 reset，`allowStale:false`）。**未登录时为 `"anonymous"`**。登出后事件仍上报，但不带 `auth` 块。
- `organization_uuid`：`telemetryOrgUuid()` = `creds.telemetryOrgKey ?? mintedAnthropicOrgUuid() ?? yRe(K())`；3p 未配置 `deploymentOrganizationUuid` 时是**共享占位常量** `00000000-…-000000000000`（无区分度）；兜底读 claude.ai 的 `lastActiveOrg` cookie。
- **3p 非 hybrid 特例**：`accountUuid` 被替换成 `ant-did`（`resolve3pIdentity`），tagged_id 形如 `cowork_3p_<ant-did>`。
- hybrid 模式下账号身份落盘到 `~/Library/Application Support/Claude-3p/claude_desktop_config.json` 的 `hybridIdentity` 段。

### 3.4 DeviceRegistry（设备级密码学身份）

- **不是读硬件 ID，是在硬件里生成密钥**：`@ant/claude-native` 的 `hardwareKeyGetOrCreate(keyId)`，keyId = `device-registry-<accountUuid>` 或 `device-registry-<accountUuid>:g<N>`，macOS 走 Secure Enclave（P-256）。
- 公钥 SPKI 的指纹 `sha256(spki)` 与服务端设备目录匹配得到行主键 `rowPk`（UUID）。
- **跨重装稳定性取决于 Keychain 项，而非硬件派生**：密钥由 `SecKeyCreateRandomKey` 随机生成，`kSecAttrAccessibleWhenUnlockedThisDeviceOnly` 使其不随备份迁移，代码也不写 `kSecAttrSynchronizable`，因而不同步 iCloud。代码语义是「找不到就重建」：Keychain 项缺失时新建密钥，重建后公钥改变，服务端设备行失配并走 `row_pk_no_row` 重新注册，同一台机器于是在遥测里出现新的 `rowPk`。该密钥证明的是「同一 Keychain 生命周期内的同一个安装」，不是可用于跨重装追踪的机器标识。`[Inference]` 重建路径依赖 `[Observed]` 的 `hardwareKeyNotFound` 串、`SecItemDelete` 导入与 JS 的 `row_pk_no_row` 分支。
- 落盘：`ant-device-registry.json`（rowPk 缓存）、`ant-device-key-generation.json`（轮换代际）；私钥由原生模块保管。
- 用途：会话文件签名、`X-Device-Attestation`、设备注册。**指纹从不出机，但匹配出的 `rowPk` 会作为 `device_id` 进入遥测事件**（详见 `linked.md`）。
- 轮换：`rotateKey`（30 秒限流）换代际，旧 rowPk 作废 → 同一台机器在遥测里表现为两个 device_id。
- **设备身份链路的 API 与签名不查遥测配置**：目录 GET、签名断言与 `rotateKey` 都不读 `telemetry.disableNonessential`，该开关只决定事件是否 POST。所有入口先经 `W0(accountUuid)` 校验 UUID 形状并要求它是当前登录账号，否则抛 `signed_out`；`Dk()` 在 `isLoggedOut` 时返回 null。`rotateKey` 在本 bundle 内没有自发调用点，只出现在 IPC 处理器表与渲染进程封装里，`notifyRegistered`/`getOwnRowPk`/`setKeylessBridgeRowPk` 亦然，暴露面限于 claude.ai 顶层 frame，因此实际触发者是 claude.ai 页面。`[Inference]`（依据：全目录仅上述几处出现 `rotateKey`，且 force 参数由页面侧 IPC 传值。）
- **设备探测与注册失败时的两条事件**：分类器把异常消息映射为 `no_tpm`、`entitlement`、`linux`、`native_missing`、`key_state_unreadable`、`other` 六个取值（七条分支，`no_tpm` 有两条入口）。`no_tpm` 分支发 `device_registry_no_tpm_probe_code`，字段 `no_tpm_probe_code`；其余分支发 `device_registry_unavailable_probe_code`，字段 `unavailable_probe_reason` 与 `unavailable_probe_code`。两个 probe code 都从异常文本里按正则抓 `0x[0-9a-fA-F]{8}` 或 `NTE_[A-Z_]+`，抓不到则写字面量 `no-code-token`。两条事件各自按 accountUuid 去重，同一账号只发一次。

### 3.5 cookie 类与设备档次 header

- `anthropic-device-id`：claude.ai 网页写入，Desktop **只读不写**；无值时 OAuth 头不发、事件里报 `"unknown"`。
- `ajs_anonymous_id`：Segment 遗留匿名 ID，进实验事件 `anonymous_id`。
- 每次 API 请求的 `anthropic-client-*` 头：`anthropic-client-platform: desktop_app`、`anthropic-client-app: com.anthropic.claudefordesktop`、`anthropic-client-version`、`anthropic-client-device-class`（`le4|8|16|gt16`）、`anthropic-client-total-memory-gb`。**只有档次与内存量级，无唯一 ID。**

### 3.6 三个容易记错的区分

1. **`deviceId`（`DZ` 里 95 处）不是机器 ID**，是 Claude for Chrome **扩展实例 ID**；真正的机器侧持久标识是 `install_id`（`ant-did`）。
2. **`machineID` 不在 Desktop 里**——它是 CLI 的随机 64-hex，Desktop 既不读也不写。
### 3.7 两个「主机」相关标识的来路

遥测里的「主机」标识有两个不同来源，容易读反。`host_hash`（`desktop_ccd_session_initialized` 等事件带的字段）的输入是远端主机键：ssh 的 `host:port` 或 WSL 发行版名，经每安装随机盐与 org:account 身份混合后取 16 位十六进制摘要。本机主机名不参与该哈希。本机主机名的去向只有一处，即 `remoteToolsDeviceName`：它由 `os.hostname()` 截断到 48 字符后缓存，随桥的 connect 帧以 `device_name` 发出；渲染进程的设备展示名另用 `scutil --get ComputerName` 并在失败时退回 `os.hostname()`。这两个值都不进任何产品遥测事件的字段——`device_name` 在事件载荷中不存在。

`analyticsNameHash` 是一个无盐的 31 乘子哈希，形态同 Java 的 `String.hashCode`（`h = 31h + c`、种子 0），**不是 djb2**（djb2 用 33 乘子与 5381 种子）。实现对输入逐字符做 `t = (t << 5) - t + charCode`、每步取 32 位，最后输出 `t & 4294967295` 的十进制字符串；唯一的前置处理是剥掉 `__gb__` 前缀。区分度来自调用点自己把 org id 拼在输入前面，例如 `cli_hash` 用 `orgId + cliName`、`skill_name_hash` 用 `orgUuid + skillName`、`plugin_uid` 用 `${orgId}:${pluginId}`，拼接不在函数内部。字面量 `desktop-telemetry-scrub-v1:` 不是这个哈希的盐，它只出现在三处：org id 缺失时 `sWe` 返回的占位值、HIPAA 变体的盐、以及把 MCP server 配置键与扩展 id 哈希进 GPU 与诊断包的非 org 路径。`folder_hash`/`host_hash`/`repo_hash` 走的是另一个 helper `folderTelemetryId`：`sha256(每安装随机盐 \0 org:account 身份 \0 规范路径)` 取前 16 位十六进制，与 `analyticsNameHash` 不是同一个函数。`[Inference]` 该哈希非线性、且前缀是 128-bit org UUID，故这些哈希不可反查；但它不是密码学哈希，也没有 secret 盐。

`[Observed]`（复验：`grep -n 'host_hash: s(e)' desktop/main-process-readable/index.chunk-9hgN2KD3.js`、`grep -n 'remoteToolsDeviceName' DZ`、`grep -n 'function Roe(e)' DZ`）

---

## 4. 开关汇总

| 开关 | 取值 | 影响 | 证据 |
|---|---|---|---|
| `telemetry.disableEssential`（flatKey `disableEssentialTelemetry`，默认 `false`） | `true` | 关闭 Sentry 初始化；向 CLI 子进程传 `DISABLE_ERROR_REPORTING=1` | `PRE:43007`、`DZ:176356` |
| `telemetry.disableNonessential`（flatKey `disableNonessentialTelemetry`，默认 `false`） | `true` | 关闭一方事件 flush 与诊断包上传 | `DZ:130007`、`DZ:208782` |
| `disableNonessentialServices`（flatKey 同名，默认 `false`） | `true` | 关闭连接器图标（favicon 代理）、artifact 预览 iframe 与 MCP Apps widget iframe（`*.claudemcpcontent.com`）三类非必需出站请求 | `DZ:42198` |
| `process.env.CI` | 任意 | 不初始化 Sentry、不上传一方事件 | `PRE:43007`、`DZ:130014` |
| `CLAUDE_USER_DATA_DIR` | 路径 | 改 userData（连带改 `ant-did` 等落盘位置）；`Hu()` 不再追加 `-3p` | `DZ:48066` |
| `CLAUDE_AI_URL` | URL | 仅 dev 构建可改一方事件基址（打包版恒 `https://claude.ai`） | `DZ:79925` |
| `otlpEndpoint` / `otlpDesktopLogLevel` 等 | — | Desktop 自身 OTLP 导出（默认关，默认级别 error） | `DZ:256642` |
| `SENTRY_NAME` | 任意 | 可覆盖 Sentry `serverName`（默认已被 `includeServerName:!1` 关闭） | `PRE:13455` |
| GrowthBook 门 `2220415149` | 服务端下发，**无静态默认** | 控制 §3.2 的 `userID` 播种 | `CB:16987` |
| GrowthBook 门 `2214981414` | 服务端下发，无静态默认 | 控制 rowPk 的「预期/强制刷新」：置真时把缓存里未确认的 `pku1:` 条目当作未解析，并在桥 `open` 时强制重走目录匹配 | `DZ:214470`、`DZ:215200`、`DZ:216933` |
| GrowthBook 门 `1924247864` | 同上 | 模拟后端不可用：`getAvailability` 直接返回 `{available:false, reason:"no_tpm"}`，密钥创建路径抛 `DeviceRegistry: simulated no_tpm` | `DZ:214627`、`DZ:214839`、`DZ:215437` |
| GrowthBook 门 `1310358601` | 同上 | 禁用服务端时钟偏移：置真时断言签发时间取本地时钟，事件里 `clock_offset_decision` 记为 `disabled` | `DZ:214463`、`DZ:214497` |
| GrowthBook 门 `2427043945` | 同上 | 调整桥的密钥轮换间隔（`start()` 里订阅该键，变更即更新 `lastRotateIntervalMs`） | `DZ:216592` |
| `CLAUDE_DEV_FORCE_GATES` | 逗号分隔 gate id | **仅未打包构建**可强制开门（打包产物无效） | `DZ:98036` |

`disableEssentialTelemetry` 与 `disableNonessentialTelemetry` 都带 `remotePolicy: { default: true, applyUnverified: true }` 与 `failClosedValue: true`，求值点在 `PRE:30781-30789` 的 `$H`/`eU` 与 `PRE:30846-30850` 的 `_U`。这组标注的含义是：远端下发的策略值即使未经校验也直接生效，其默认值为 `true`；托管配置整体不可读、或某个值解析失败时，该键取 `failClosedValue`，即按「已关闭遥测」处理。因此「默认发送」只成立于配置可正常读取的情形，配置损坏时结果相反。

托管配置有三个来源：macOS 读 MDM plist，路径为 `/Library/Managed Preferences/com.anthropic.claudefordesktop.plist`（`index.pre.js:40323`「`path: "/Library/Managed Preferences/com.anthropic.claudefordesktop.plist",`」）与 `/Library/Managed Preferences/<user>/com.anthropic.claudefordesktop.plist`（`:40330` 为带用户名的那条）；Windows 读 GPO 注册表 `SOFTWARE\Policies\Claude`（`index.chunk-cHD0d5Ah.js:7220`「`q = "SOFTWARE\\Policies\\Claude",`」，经同文件 `:7444` 以 `WIN_REGISTRY_KEY` 导出）；Linux 读 `/etc/claude-desktop/managed-settings.json`（`index.pre.js:15894`「`etc_file: "/etc/claude-desktop/managed-settings.json",`」）。三处都不存在时视为无托管配置（`:15895`「`none: "managed configuration",`」；同一张表里另有 `:15892`「`plist: "MDM profile",`」与 `:15893`「`registry: "GPO registry policy",`」）。

**明确无效**（Desktop 主进程/渲染进程 0 命中）：`DISABLE_TELEMETRY`、`DO_NOT_TRACK`、`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`、`DISABLE_ERROR_REPORTING`、`ANTHROPIC_BASE_URL`（不改变任何 Desktop 通道的目标）、`SENTRY_DSN`。

**3p 分支向 CLI 子进程注入**（这是「桌面内拉起的 CLI 不泄露」的原因）：

```js
DISABLE_GROWTHBOOK: "1",
DISABLE_TELEMETRY: t.telemetry.disableNonessential ? "1" : "",   // ← 显式清空外部继承值
...((t.telemetry.disableNonessential || c) && { CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1" }),
DISABLE_ERROR_REPORTING: t.telemetry.disableEssential ? "1" : "",
```
（`DZ:176344-176362`，`c` = gateway + `ANTHROPIC_API_KEY` 情形；1p 分支不注入。）

---

## 5. DeviceRegistry 的遥测去向：指纹不出机，但 `rowPk` 会

这是「有没有机器级关联」的关键一环，容易读反：

- **`sha256(spki)` 指纹从不离开本机**：三个使用点全在本地比对（校验缓存行、enclave 不可读时目录自检、`id` + 指纹双匹配）。全仓没有任何地方把 `fp` 放进请求体或事件。
- **但它匹配出的服务端设备行主键 `rowPk` 会进两类通道**：
  1. **设备注册/证明 API**（`claude.ai/api/organizations/<org>/cowork/remote_devices`、`/v1/code/sessions/<s>/files`、`/v1/code/devices/reconnected`、`wss://bridge.claudeusercontent.com/devices/<org>_<acct>/…`）：`X-Device-Attestation: creg_<rowPk>.<issuedAtMs>.<sig>`、body `device_attestation.kid=creg_<rowPk>`、`target_device_id=<rowPk>`、ws `connect.device_id=<rowPk>`。三个具体落点：`/v1/code/devices/reconnected` 是 `POST`，body 为 `{"device_id": <rowPk>}`，并带 `x-organization-uuid` 头；CCR trigger 的 body 里 `target_device_id: <rowPk>`，值来自签名结果的 `b.signed.rowPk`；本地也把 rowPk 当机器在用——org 设置里的 `cowork_bound_device.device_id` 与本机 `deviceRowId` 做大小写不敏感的字符串相等比较，不相等即拒绝。
  2. **产品遥测事件**：`lam_remote_tools_device_state.device_id`（= `rowPk`，UUID）+ `device_id_source`（`keyed`/`keyless`）。**HIPAA 组织下被 `vWe` 归零为 `hipaa_redacted`**。HIPAA 之外另有三处只暴露「rowPk 是否解析成功」而不含 rowPk 值本身：`cowork_remote_attestation.row_pk_resolved` 是布尔，取自 `H3r()`；`lam_remote_folder_grant_changed.row_pk_resolved` 是同一个布尔；`cowork_space_migration_outcome` 的 `finalizeMetadata` 只回 `{ device_id_source }`，不带 `device_id`。
- 本地缓存：`ant-device-registry.json`（格式 `pk1:<fp>:<rowPk>`，**指纹在这里**）、`ant-device-key-generation.json`（轮换代际）、`<userData>/appdata/ccd-ids.json`（telemetry id 盐）。
- 匹配入口是 `GET /api/organizations/<orgUuid>/cowork/remote_devices`，**只带路径参数、无自定义头**，`[Inference]` 认证靠同源 claude.ai cookie ⇒ **必须已登录且有 org**。
- **轮换的后果**：`rotateKey` 换代际后旧 rowPk 作废 → 同一台机器在遥测里表现为**两个 device_id**。

`[Observed]`（复验：`grep -n 'X-Device-Attestation' DZ`、`grep -n 'pk1:' DZ`、`grep -n 'lam_remote_tools_device_state' DZ`）

---

## 6. Desktop → CLI 的耦合面

### 6.1 CLI 二进制从哪来

Desktop **自带一套 CLI 分发与自更新**，解析优先级（顺序即优先级）：`local_override`（用户自选路径）→ `preseed_in_place`（随包预置）→ `required_version`（当前 pin）→ `fallback_version`（任意已装版本）→ `none`。下载物落地 `<storageDir>/<version>/claude`，带 `.verified` 标记与 manifest checksum 校验；另有 `claude-ssh` 远程助手。Desktop 自己为这些解析结果发 `desktop_ccd_binary_resolved` 事件（**是 Desktop 事件，不是 CLI 事件**）。

### 6.2 spawn 时的环境变量

组装顺序（后者覆盖前者）：继承 `process.env` → 登录 shell 提取的 `PATH` → 用户在 Desktop 设置里配的 env（safeStorage 解密）→ 托管配置的 proxy env → **核心 CCD env** → OTEL env → 删除名单。

核心 CCD env（`EJ()`）逐字要点：

```js
CLAUDE_CODE_ENTRYPOINT: "claude-desktop" | "claude-desktop-3p",   // local agent 路径覆写为 "local-agent"
ANTHROPIC_BASE_URL: e.apiHost,
CLAUDE_CODE_OAUTH_TOKEN: e.oauthToken,                            // 凭据注入
CLAUDE_CODE_DESKTOP_APP_VERSION: n.type === "3p" ? "" : a.app.getVersion(),
...(e.localAgent && { CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST: "1" }),
```

- `CLAUDE_CODE_DESKTOP_APP_VERSION` 的存在，正是 CLI 侧 `Lhn()` 门控 `anthropic-client-platform: desktop_app` 注入的来源（见 `cli.md` §4.3）。
- 运行期还会热推 token：`pushCcdTokenToSession` → `enqueueControl({type:"update_environment_variables", variables:{CLAUDE_CODE_OAUTH_TOKEN}})`。
- 3p 分支额外注入的 `DISABLE_*` / `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 见 §4。
- **CLI 在派生子进程时会剥掉入口标记**：当环境里的 `CLAUDE_CODE_ENTRYPOINT` 取值为 `claude-vscode`、`claude-desktop` 或 `claude-desktop-3p` 之一时，该变量在子进程环境中被删除，同一处还按大小写不敏感地剥掉 `CLAUDE_CODE_SAFE_MODE`、`CLAUDE_CODE_SIMPLE`、`CLAUDE_CODE_RESTRICTED`。因此 Desktop 注入的入口标记只作用于被直接拉起的那一层进程，不向更下层的子进程传递（`grep -o 'O=new Set(\["claude-vscode","claude-desktop","claude-desktop-3p"\])'`）。
- **各条 spawn 路径对宿主环境的继承方式并不相同**。Code 标签页整体继承 `process.env`；本地 agent 路径先保持 `EJ()` 构造的值，另从 `process.env` 只额外带入 `HOME`、`LOGNAME`、`SHELL`、`TERM`、`USER`、`CLAUDE_CODE_TMPDIR` 六个变量；SDK 被直接调用时，调用方给了 `env` 就整体替换，否则继承全部 `process.env`；3P host CLI 与 Cowork/VM 沙箱均不以 `process.env` 起手，其中 VM 路径另硬编码 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`；Desktop 自带的终端与 SSH shell 则整体继承 `process.env`。

### 6.3 Desktop 会打开子进程的遥测导出

托管配置中一旦设置了 `otlpEndpoint`，Desktop 在生成会话环境变量时不仅自己导出，还会把 CLI 子进程的遥测一并打开并指向同一个 collector（`DZ:179907-179950` 的 `fgr`）。注入的变量包括 `CLAUDE_CODE_ENABLE_TELEMETRY="1"`、`OTEL_METRICS_EXPORTER` 与 `OTEL_LOGS_EXPORTER`（均取 `"otlp"`），以及可选的 `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA="1"` 与 `OTEL_TRACES_EXPORTER="otlp"`，另有 `OTEL_EXPORTER_OTLP_ENDPOINT`、`OTEL_EXPORTER_OTLP_PROTOCOL`、可选 `OTEL_EXPORTER_OTLP_HEADERS`、`OTEL_SERVICE_NAME` 与 `OTEL_RESOURCE_ATTRIBUTES`。未配置 endpoint 时退化为只给 `OTEL_SERVICE_NAME` 与 `OTEL_RESOURCE_ATTRIBUTES`。

会话 resource 的 `service.name` 由目标决定：Cowork 任务为 `cowork`，Code 会话为 `claude-code-desktop`。该 resource 以 `identity: false` 组装，不自动加入 `enduser.id`；企业网关身份改为按需追加到 `OTEL_RESOURCE_ATTRIBUTES`，前提是该会话环境中的 endpoint 与当前配置一致（`TUe` 判定），且远端配置未给出 `enduser.id`。

`wUe()`（`DZ:51508-51517`）随后按信号派生端点：gRPC 使用同一 endpoint，HTTP 使用 `${endpoint}/v1/{logs,metrics,traces}`。VM 与沙箱目标另有 `OTEL_LOGS_EXPORT_INTERVAL="0"`、`OTEL_METRIC_EXPORT_INTERVAL="3000"`、`OTEL_TRACES_EXPORT_INTERVAL="0"` 与 `CLAUDE_CODE_OTEL_DIAG_STDERR="1"`。

会话的 OTLP 协议在两类情形下由 `grpc` 降级为 `http/protobuf`：其一是 Cowork 沙箱，其出口代理不承载 gRPC（`index.chunk-DzZc-q0x.js:51456-51458`，`function yUe(e, t) { return t.sandboxed && e === "grpc" ? "http/protobuf" : e; }`）；其二是 Claude Code 引擎拿到 HTTP 代理时（操作系统代理、`egressProxyUrl`、`egressProxyPacUrl`，或 Claude Code settings 文件中的 `HTTPS_PROXY`/`HTTP_PROXY`；`index.chunk-DzZc-q0x.js:68201-68205`，`function D4e(e) { return e.OTEL_EXPORTER_OTLP_PROTOCOL === "grpc" && (e.grpc_proxy || e.https_proxy || e.HTTPS_PROXY || e.http_proxy || e.HTTP_PROXY) ? { OTEL_EXPORTER_OTLP_PROTOCOL: "http/protobuf" } : {}; }`）。schema 自述另把 Windows 列为同样降级的平台。降级只改协议、不改 endpoint，日志记一条 `OTLP: … export over http/protobuf instead of the configured grpc`。代码里还有第三个触发条件「目标平台缺少 gRPC CA 信桥」（`platformLacksGrpcCaBridge`，`index.chunk-DzZc-q0x.js:179933-179941`「`(t.sandboxed || (t.target === "vm" && t.platformLacksGrpcCaBridge === !0)) &&`」），但本构建四处调用点均传入 `false`，该分支不触发。

SSH 远程会话的环境变量另做一次过滤：当 `OTEL_EXPORTER_OTLP_ENDPOINT` 是回环地址（`localhost` 及其子域、`127.x`、`::1`、`0.0.0.0` 等）时，全部 `OTEL_*` 变量被剔除，只保留 `CLAUDE_*`、`ANTHROPIC_*`、`DISABLE_*`、`ENABLE_TOOL_SEARCH` 与白名单内的键；其依据是远端主机无法访问本机 collector。判定条件与过滤体在 `index.chunk-DzZc-q0x.js:174882-174884`：「`t === "ssh" && e.OTEL_EXPORTER_OTLP_ENDPOINT !== void 0 && jsr(e.OTEL_EXPORTER_OTLP_ENDPOINT) !== !1`」（`jsr` 即回环判定）；被剔除的键由 `:174878` 的 `Hsr` 界定：「`return e.toUpperCase().startsWith("OTEL_") || Object.hasOwn(CUe, e);`」，`CUe` 为白名单表；实际执行在 `:174887`「`a === void 0 || lsr(t) || (r && Hsr(t)) || ((n?.has(t) || Vsr(t)) && (i[t] = a));`」。

两点值得注意。其一，这组变量由宿主注入，CLI 侧的 `enforceManagedOtelFamilyDominance()` / `hostSpawnOtelClaims()` 会将其排除在 managed settings 的覆盖之外（`cli/modules/mod-0189.js` 的 `dropDominatedOtelKey()` 中有 `if(this.hostSpawnEnvKeys?.has(e.toUpperCase())) return;`），即项目级与企业 settings 无法把这些渠道改指他处。其二，Desktop bundle 内嵌的并不只是遥测契约：`index.chunk-CHNweogn.js` 带有 CLI 的整套 zod settings schema（`cleanupPeriodDays`、`outputStyle`、`statusLine`、`forceLoginMethod` 等逐项可见），`index.chunk-DAdPDze6.js` 带有完整的环境变量注册表（逐项注册 `OTEL_LOGS_EXPORTER`、`DISABLE_TELEMETRY`、`CLAUDE_CODE_ENTRYPOINT`、`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 等）以及 `anthropic-client-platform` 生成器。因此「实现不在 Desktop 中」只对 OTel exporter 成立（`OTLPLogExporter`/`NodeSDK` 在 `desktop/` 零命中），SDK 与 CLI 的主体代码确在包内；随其下载的原生 `claude` 二进制分发的是运行时本体（§2.4）。

注意这与 §4 里 3p 分支注入的 `DISABLE_*` 是两条独立分支：后者只在 3p 形态下出现、作用是关断子进程遥测；本节这组只在配置了 OTLP endpoint 时出现、作用是开启。两者由不同配置驱动，不互相抵消。

`[Observed]`（复验：`grep -c 'CLAUDE_CODE_ENABLE_TELEMETRY' desktop/main-process-readable/index.chunk-DzZc-q0x.js`、`grep -o 'hostSpawnEnvKeys' cli/modules/mod-0189.js`）

### 6.4 共享配置根 `~/.claude`

两端共用同一份用户级配置根（`CLAUDE_CONFIG_DIR` 可改）：

- Desktop **读** `~/.claude.json`、`~/.claude/settings.json`、`~/.claude/projects/**/*.jsonl`、`~/.claude/skills`、`~/.claude/.credentials.json`。
- **会话私有的 `.claude.json` 另有一组字段级读写**：`cachedGrowthBookFeatures`、`cachedArtifactRoster`、`clientDataCache`、`claudeJsonFilename`、`userID`。目标文件在 `.claude.json` 与 `.claude-staging-oauth.json`/`.claude-local-oauth.json`/`.claude-custom-oauth.json` 之间按名排序取首个；读取统一经一个受限入口，单文件上限 8 MiB，非普通文件与多硬链接（`nlink>1`）一律拒读。**该保护不施加于全局 `~/.claude.json`**——后者由另一处投影读取，只取 `projects` 信任位与 `mcpServers` 名单，不做大小与硬链接限制。resume 复制 `.credentials.json` 时还会先删除其中的 `claudeAiOauth.refreshToken` 再落盘，写入权限 `0600`，因此恢复到临时目录的会话不带刷新令牌（`CB:3366-3402`、`CHN:45133-45135`）。
- Desktop **写** `settings.json` 的 `outputStyle`、`projects/*.jsonl`、`output-styles/*.md`、`plugins/{known_marketplaces,installed_plugins}.json`，以及全局 `~/.claude.json` 的项目信任位（`hasTrustDialogAccepted` 等）。resume 会话前，Desktop 会把用户级 `settings.json`（以及 `cowork_settings.json`）复制进一个临时配置目录，复制时删除 `enabledPlugins`、`extraKnownMarketplaces`、`additionalMarketplaces` 三个顶层键与 `env.CLAUDE_CONFIG_DIR`。这三个键是 CLI 决定加载哪些插件与市场的位置，因此被恢复的会话看不到用户级插件配置（`CHN:45108`、`CHN:45121`）。
- **但 Desktop 从不把 `userID` 写进全局 `~/.claude.json`**——`userID` 的唯一写点是会话私有目录（§3.2）。
- Desktop **不读** CLI 的 `machineID`，也**不读** `.claude.json` 的 `oauthAccount`（均 0 命中）。
- Desktop 扫描 `<CCD>/projects/` 恢复转录时，用转录里的 `entrypoint` 做准入：扫描入口传入 `admitEntrypoint: ownEntrypoint`，`ownEntrypoint` 取 Desktop 自身的入口值。过滤函数在转录入口属于一个 Desktop 家族集合（`claude-desktop`、`claude-desktop-3p`、`local-agent`、`sdk-cli`/`sdk-ts`/`sdk-py`、`mcp`、`bench`、`claude-code-github-action`、`remote*`、`claude_in_slack`、`ssh-remote`、`claude-coworker*`）且不等于自身入口时丢弃该转录。因此被排除的是标记为其他 Desktop 部署形态的转录；入口为终端 `cli` 的转录不在该集合内，不受这一条排除。另有一条终端扫描走相反方向：它以空 `admitEntrypoint` 调用同一过滤函数，从而只保留非 Desktop 家族的转录并标为终端会话（`9hg:21092`、`DZ:266845-266864`）。

### 6.5 结论：CLI 关遥测时还剩下什么

若 CLI 关掉遥测而 Desktop 没关：「Desktop 拉起过 CLI」这件事在服务端**仍能归到同一 `account_uuid`**——由 Desktop 自己的 `desktop_ccd_*` 事件（带 `cli_session_id` + `account_uuid` + `install_id`）与同一 OAuth 账号的推理流量两条独立路径保证；但**不能**归到 CLI 自己的 `userID`/`device_id`（那是 CLI 事件字段，CLI 遥控测时根本不上行）。机器级只能在 Desktop 侧归到 `install_id`。`[Inference]`

---

## 7. 指纹面（提示词 / 头 / 日志包）

遥测开关管不住这一层——它随模型请求走。

### 7.1 提示词层

- Desktop 把 `{{currentTimezone}}`、`{{accountName}}`、**宿主绝对路径**写进会话的 system prompt，**每条消息上行**，不受任何遥测开关约束。
- 替换上下文还包含账号邮箱（`{{emailAddress}}` 取登录账号的邮箱地址）。用户选中的文件夹以宿主绝对路径写入：host 模式下每项渲染为 `Folder: <宿主路径>`，整段填入 `{{userSelectedFolders}}`。宿主文件系统被挂载且非 host-loop 模式时，prompt 追加 `Exploring the host filesystem` 一节，说明只读索引挂在 `<cwd>/mnt/.host-home`，并以 `host_fs_skeleton` 段列出宿主家目录下的文件与目录结构。
- Desktop **强制 `TZ=<宿主时区>` 注入 CLI 子进程**——在终端里改 `TZ` 对 Desktop 拉起的会话无效。
- `CLAUDE_CODE_WORKSPACE_HOST_PATHS` 进 env，并被 CLI 用作 OTel 属性 `workspace.host_paths`。
- CLI 侧的 `# Environment` 块无时区/locale/用户名，但 **cwd 是原文**（中文用户名路径会随之上行）；时区另经两处注入（`mcp_datetime_parse` 的 `Local timezone: +08:00` 与 routines skill）。会话上下文的 `gitStatus` 段还会带上分支名、`git status` 文件名、近 5 条 commit 标题、`git config user.name` 与账号邮箱，见 `cli.md` §4.4。

`[Observed]`（复验：`grep -rl 'currentTimezone' desktop/main-process-readable/`、`grep -r 'CLAUDE_CODE_WORKSPACE_HOST_PATHS' desktop/main-process-readable/`）

### 7.2 头层

- **`Accept-Language`**：Electron 默认行为（`network_context_params->accept_language = GenerateAcceptLanguageHeader(app.getLocale())`），**应用代码从不设置、也从不覆写**（`setAcceptLanguages` 在 `desktop/` 0 命中，`appendSwitch("lang")` 0 命中）。中文系统上**所有**走 Electron 默认网络栈的请求都带 `Accept-Language: zh-CN`，包括一方事件批量 POST、更新检查、内嵌 claude.ai 及其加载的第三方主机。
- **`User-Agent`**：Electron 默认 `Claude/2.9939.2 Chrome/<c> Electron/<e>` + 平台令牌，无地区信息但含精确版本。两个变体偏离默认形态：Windows MSIX 构建在末尾追加 ` MSIX`；`launch-preview-*` 分区在创建时去掉 UA 中的 `Electron/<v>` 令牌，使该分区的指纹与主窗口不同。
- **`cf_ray`**：来自响应头，Desktop **剥掉 `-XXX` 机房后缀**后上行（CLI 侧则连后缀一起带——两端归一化不对称，见 `linked.md`）。
- **`anthropic-client-*` 注入**：由默认 session 的 `onBeforeSendHeaders` 注入，含 `anthropic-client-device-class`、`anthropic-client-total-memory-gb`——**这是 Desktop 唯一自报机型/内存的地方（粒度是档次，不是精确值）**。
- 同一处理器还注入 `anthropic-client-os-platform`（`process.platform`）、`anthropic-client-os-version`（系统版本）与固定值 `anthropic-desktop-topbar: 1`，并从环境变量 `CLAUDE_EXTRA_HEADERS_TOKEN` 解码一批头（三段点分 JWT，首段毫秒时间戳、次段 base64 头 JSON、末段以内嵌公钥验签，过期或验签失败即整批丢弃）。`anthropic-desktop-topbar` 与这批 JWT 头只对第一方 host 注入。`anthropic-client-os-platform`/`-os-version` 的范围略宽：在非第一方分支里，处理器还会对 `api.anthropic.com`、`api-staging.anthropic.com`、`api.claude.ai` 三个主机补上同一批客户端头（不含 topbar 与 JWT）。
- **`ANTHROPIC_CUSTOM_HEADERS` 会把自定义头带出去**：Desktop 把静态头与被解析出的凭据头合并，按 `k: v` 逐行拼成字符串写进该环境变量交给子 CLI（`kGt(staticHeaders, resolvedHeaders)` → `wGt`），子 CLI 再把这些值当作**真实请求头**发出。因此在 Desktop 或托管配置里设置的自定义头，其**值会原样到达 Anthropic**；而事件侧并不携带该头的值或存在性——`custom_headers` 这个布尔在全部 CLI 模块中只出现一次（即配置指纹对象 `yN()` 的定义处），且该对象只挂在本机日志上，桌面侧则 0 命中（见 `cli.md` §4.3）。
- **`egressProxyUrl`（托管代理）不上报**：配置项标 `redact: "hostname"`，无任何遥测字段引用它。
- **CCR（远程 Code 会话）通道**的若干请求在头中标记 `anthropic-client-feature: ccr`，并随调用点附 `anthropic-beta: ccr-byoc-2025-07-29` 或 `ccr-triggers-2026-01-30` 与 `x-organization-uuid`。该标记属会话通道，不在遥测链路上。
- **不支持出站客户端证书**。

### 7.3 日志与诊断包

- **唯一上行点是 `cowork_3p_diagnostic_bundle`**，门控 `is3p && !disableNonessential`；注意**用户点「Export」（仅导出本地）也会发同一事件**。其 `system_info` 段为多行文本，含应用版本、平台与架构、OS 版本、CPU 型号与核数、内存总量与可用量，以及 `Host IPv6:` 一行的分类值 `global | ula_only | none`；该值由 `os.networkInterfaces()` 判定，是网络形态分类而非地址。
- **日志时间戳是本地时区且无偏移后缀**——这是**隐式**的 UTC 偏移证据（不是显式的 `+08:00`）。仓库内有实跑验证：脱敏把家目录/用户名抹掉，但 **`TZ=Asia/Shanghai`、`LANG=zh_CN.UTF-8`、中文目录名/文件名/UNC 共享名原样保留**。唯一的时区例外是 `mcp.log` 与 `mcp-server-*.log`，它们用 `toISOString()` 记为 UTC。本地诊断文件 `system-info.txt` 与 `gpu-info.json`（含用户名绝对路径、`Locale`/`System Locale`、`Local Time`）是用户手动导出的本地文件；诊断包内同名 section 采集的是内存生成的文本而非这两个文件，因此它们不进 bundle。
- **Sentry minidump 以原始字节作为 attachment 上传，`beforeSend`/`beforeEnvelope` 均无法触及 ⇒ 不脱敏**。崩溃路径上另有几处派生素材上行：crashpad 的 annotations 以 `crashpad.<key>` 为键并入 Sentry 的 `contexts.electron`，值原样保留；内置 MCP server 的 `stderrTail`（最多 20 行）进入 Sentry 事件的 `extra`，经与日志同源的路径/用户名脱敏。一方事件里的 `shipit_stderr_tail`（更新失败时读 ShipIt 缓存日志尾部）与 `cli_stderr_tail` 在上行前过完整 `scrubLogLine`。
- 本 build **不采集 Windows KB 列表**（os-build section 只有 macOS 分支，字段自述已过期）；profile 目录读取被桩成恒 `null`；`vm_network_mode` 恒为硬编码 `"gvisor"`。
- **VPN 探测范围极窄**：仅在 macOS 且 Cowork 本地 VM 启动失败（`lam_vm_startup_failed`）时触发，探 `utun` 等虚拟网卡与注册的 VPN 服务；网卡名/服务名经哈希后上报，`vpn_active` 是布尔。系统代理另有一处例外，见 §9 第 3 条。
- **`vpn_active` 只取自 `scutil --nc list` 中处于 Connected 的网络服务**，与 `ifconfig` 无关：只创建 `utun` 而不注册系统 VPN 服务的客户端（WireGuard、Tailscale、TUN 模式的代理）会出现 `vpn_interfaces` 有值而 `vpn_active=false`，`error_type` 也不会改写成 `vpn_routing_conflict`。`vpn_interfaces`、`connected_vpns`、`bridge_interfaces` 各自先 `join(",")` 拼成单串再整体哈希，服务端每字段只得到一个哈希值。哈希为 `h*31+c`（种子 0、逐步截断为 int32），盐取组织 uuid，无组织时取公开常量 `desktop-telemetry-scrub-v1:`。`[Inference]` 该盐公开且确定、网卡名取值有限，哈希可被枚举还原；无组织用户共用同一盐，构成跨用户可比的稳定关联键（依赖 `[Observed]` 的哈希实现与 `vpn_active` 布尔原样放行）。

`[Observed]`（复验：`grep -c 'cowork_3p_diagnostic_bundle' DZ` = 1、`grep -o 'invalid-clock (epoch-ms' DZ`）

---

## 8. 原生模块（静态结论）

`desktop/native-unpacked/` 的 10 个原生件只能静态读取（非 macOS 主机不可执行）。结论以**否定**为主，但有几条实质发现。

### 8.1 `@ant/claude-native`（Rust/napi，`claude-native-binding.node`）

- 393 个导入符号 + 12 个 dylib 逐条归位：**无 IOKit / SystemConfiguration / DiskArbitration，无任何机器唯一码读取**——这是「Desktop 不抓硬件码」在原生层的对应证据。该二进制没有弱链接依赖，因此不受 §8 末那条历史读取缺陷影响。
- **Secure Enclave P-256 密钥**：`SecKeyCreateRandomKey` + `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` + data-protection keychain，**不同步 iCloud**。access group `Q6L2SF6YDW.com.anthropic.claude.hwkey`，tag `com.anthropic.claudefordesktop.hwkey.device-registry-<accountUuid>[:gN]`。
- `sha256(spki)` = `rowPk` = 本地缓存里的 `fp` 三值同一；SPKI DER 前 26 字节固定。
- **遥测只带三态 `hw_attestation` 与错误码 token，不带 SPKI/rowPk 值**（`rowPk` 的去向见 §5）。
- `cowork_remote_attestation` 的完整字段为 `proof_kind`（`td_v2_hardware`/`td_v2_software_shim`/`none`）、`hw_attestation`、`hw_unavailable_reason`、`row_pk_resolved`（状态串而非密钥）、`sign_error_code`、`sign_error_probe_code`、`clock_offset_decision`、`clock_offset_ms`、`attestation_form` 与 `duration_ms`；另有 `device_registry_no_tpm_probe_code`、`device_registry_unavailable_probe_code` 两个事件。两个探针码取自同一条正则，只接受 `0x` 加 8 位十六进制、`NTE_*` 名称或字面量 `no-code-token`，不含十进制分支，因此 OSStatus 原文与 SID 片段不会落入字段。
- Windows 侧同一份设备密钥接口由 `userDpapiProtect`/`userDpapiUnprotect` 加 TPM/CNG 承担。在本机 macOS 构建里这两个名字仍有注册点，实现落在 `Not implemented on darwin` 一类的桩分支上。JS 侧把 `PlatformCryptoProvider` 相关失败与「simulated no_tpm」一并归为 `no_tpm`。`[Inference]`「实现为桩」依赖 `[Observed]` 的注册串与 `Not implemented on darwin` 串的相邻关系。

### 8.2 `@ant/claude-swift`（`swift_addon.node`）

- N-API 顶层 17 个组；`ClaudeEvent` 桥共 17 个事件名，`logAnalyticsEvent{eventName,metadata}` 全部交给 JS 队列——**原生自身零网络出口**（全镜像 13 条 URL 全是 Apple/Go 运行时噪声）。
- **读取的硬件事实限于容量类**：`host_statistics64` 与 `mach_host_self` 取主机内存统计，`ProcessInfo` 的 `physicalMemory` 与 `processorCount` 选择器取内存总量与 CPU 核数。这些值用于给 Cowork 虚拟机选定 `memoryGB` 与 `cpuCount`（`startVM` 的第 2、3 个参数），并由 `getHostMemoryInfo()` 返回 `totalBytes`/`availableBytes`/`physicalMemoryGB`。只描述容量，不含唯一码。
- **Cowork 虚拟机的网络有两条路径**：gvisor 用户态网络（内嵌 gvisor-tap-vsock），以及在 macOS 26 及以上优先尝试的 vmnet 连接；vmnet 创建失败或超时后回退到 NAT/DHCP。这条选择只影响 guest 的联网方式，不产生上行字段。
- **Cowork 虚拟机的 MAC / machineIdentifier 是首次随机生成后落盘持久化**（`VZMACAddress.randomLocallyAdministeredAddress`），**不派生自主机**。
- `keychain.deriveBrowserSafeStorageKey` 读 Chrome/Chromium/Brave/Edge/Arc 的 Safe Storage 主密钥，用于「从浏览器导入」，与硬件密钥无交集。
- **唯一原生 Anthropic 链路**是听写 websocket `api/ws/speech_to_text/voice_stream`（凭据由 JS 侧 `api.setCredentials` 注入）。其查询参数包含 `organization_uuid`、`inputDeviceUID` 与 `keyterms`（另以 `x-config-keyterms` 形式打包），即组织标识与所选音频输入设备标识随该连接发出。
- 镜像里的 `sysctl`/`hw.*` 命中**全部归属内嵌 Go runtime**，不构成指纹。

### 8.3 其余原生件

| 模块 | 结论 |
|---|---|
| `computer_use.node` | 无 IOKit、无网络导入（`socket`/`CFNetwork`/`NSURLSession` 0 命中）；注入走 AX 而非 `CGEventPost`。其使用情况只以布尔 `observed_computer_use`（由 `computerUseRuns > 0` 派生）出现在 `cowork_scheduled_tasks_inventory` 事件中，本体无任何上报代码 |
| `node-pty` | 唯一的 `sysctl` 用途是 `pty_getproc` 取 pty 前台进程名；**调用点依赖上游同版本源码，本仓素材内不可复验**（本篇唯一的低复验点） |
| `github-mcp-server` | `NewNoopMetrics()` 空实现 + `telemetry` 0 命中；出站只有 token 与 MCP clientInfo UA。端点字面量含 `api.github.com`、`uploads.github.com`、`raw.githubusercontent.com`、`avatars.githubusercontent.com`、`api.githubcopilot.com`、`insiders.vscode.dev`，以及 GHEC/GHES 模板 `https://api.%s`、`https://uploads.%s` |
| `libmsalruntime_arm64.dylib` | **能力在、调用无**：含 `IOPlatformSerialNumber`/`hw.cputype`/`uname` 实现（MSAIMSIDDeviceId），但返回序列号的 `deviceTelemetryId` 的 `_objc_msgSend$` 桩为 0 ⇒ 本构建活跃路径不带序列号。认证请求会向微软发出 `x-client-*`、`client_info` 与 `x-ms-clitelem` 等客户端遥测，端点字面量含 `login.microsoftonline.com`（及 `.de`/`.us`、`login.partner.microsoftonline.cn`、`login.chinacloudapi.cn`）、`login.windows.net`、`sts.windows.net`；该库随 Office 365 MCP 分发，与 Anthropic 遥测无关 |
| `spawn-helper` | 内嵌 entitlements（TCC Apple-Events 归因到宿主 App） |

`attestedMachRequest` 是一个带代码签名校验的 Mach IPC 入口。原生侧由 `mach-listener` 接收请求，取调用方的 audit token 后以 `anchor apple generic and certificate leaf[subject.OU] = "Q6L2SF6YDW"` 的要求校验，只放行 Anthropic 签名的对端；配套的 `AuthRequest` 类型与 `ASWebAuthenticationSession` 选择器表明该 IPC 的一项职责是替对端完成 OAuth 授权。JS 侧在 grand prix 伙伴链路里调用它，而这条链路的产品事件只带 `partner_id`，不带 IPC 载荷或签名材料。`[Inference]` 该 IPC 承担 OAuth 的结论依赖 `[Observed]` 的 `AuthRequest`/`ASWebAuthenticationSession` 选择器串与 `web_auth.rs` 路径串。

### 8.4 原生采集 API → 输出去向（三分类）

| API | 去向 |
|---|---|
| `readProcessFootprints` | **遥测**（数值聚合） |
| `listTcpListeners` | **模型错误文本**（端口占用者进程名 + PID，仅回环 + 目标端口），**不进遥测** |
| 全机进程枚举 | `/bin/ps -axwwo`，`comm` 仅做 shim 判定后丢弃；`readProcessTree`、`prefetchProcessPrivateMemory`、`getWindowAbove`、`moveWindowBehind` 均**无 JS 调用点**（死接口）。`getActiveWindowHandle` 例外：它读取当前聚焦窗口句柄并缓存，有活跃调用点 |
| `desktop_process_memory_sample` | 遥测，抽样 1/8 + 每 30 样本 1 次，字段全为数值/枚举，**无进程名** |
| `lam_vm_oom_kill_detected` | 遥测；**唯一带进程名的字段**是 `lam_vm_oom_kill_detected.process_name`，其字段自述为 VM 进程名（由本程序派生、非用户命名） |
| `cuListInstalledApps` | 全机已安装应用清单（含 AUMID 与 targetPath）进入模型：`list_apps` 工具返回 `{bundleId, displayName, isRunning, pid}`，清单另注入工具描述的 `<installed-apps>` 段。遥测侧只有派生的 `cu_app_dispatch.app_category` 与 `is_system_app`（`bundleId` 是否以 `com.apple.` 开头），不带上应用清单 |
| `read_clipboard` | 需 `clipboardRead` 授权，未授权时返回 `grant_flag_required`；授权后剪贴板文本进入模型工具结果。对应遥测只有 `desktop_launch_preview_clipboard_write`，字段为 `origin_class`、`kind`、`phase`，**不含文本** |
| 云盘同步 | provider 名经 `enumRegistrySubkeys`/`enumRegistryValues` 从 `SyncRootManager` 等注册表键读出，派生为遥测字段 `cloud_sync_providers`（与 `folder_kinds` 计数同处）；同步根路径进入模型提示词（`{{userSelectedFolders}}`），原始注册表内容不上行 |
| 窗口标题 | **两条模型通道**：@-提及 ≤120 字符 + 整窗 JPEG；CU `app_list_windows` ≤40 字符且限字符集 |
| `low_memory_posture` | 取值域在**服务端下发的 web bundle** 内（本机 renderer grep 0 命中），仅 ≤32 字符 token |

`[Observed]`（复验：`grep -rl 'hardwareKeyGetOrCreate' telemetry/native/`、`grep -rl 'randomLocallyAdministeredAddress' telemetry/native/`、`grep -rl 'IOPlatformSerialNumber' telemetry/native/`、`grep -rl 'NewNoopMetrics' telemetry/native/`、`grep -rl 'readProcessFootprints' telemetry/native/`、`grep -n 'observed_computer_use' DZ`、`grep -n 'process_name' DZ`、`grep -n 'cloud_sync_providers' DZ`）

> **方法论警示（影响所有引用 `DZ` 尾段的结论）**：`grep` 工具只扫文件前 4MB，而 `DZ`（289,971 行）远超此限——尾段匹配会**静默丢失**。复验时务必限定到具体文件/字节窗，不要对整棵素材树盲跑。

`telemetry/tools/macho.py` 的 `dylibs` 列表此前有两处解析缺陷，**本仓库已修复**：`LC_LOAD_WEAK_DYLIB` 与 `LC_REEXPORT_DYLIB` 的常量各少一位十六进制（写作 `0x8000018`/`0x800001F`，应为 `0x80000018`/`0x8000001F`），且把 `LC_ID_DYLIB`（本二进制的 install name）也计入依赖。修复后 `info` 分三段输出：`dylibs`（LOAD/REEXPORT）、`weak dylibs`（运行期可能缺席）、`install name`。此前被静默丢掉的是弱链接依赖，其中 `computer_use.node` 15 条、`swift_addon.node` 14 条，含 `ScreenCaptureKit.framework`、`vmnet.framework`、`libswiftIOKit.dylib` 与一批 Swift 运行时 overlay。

这些**不改变任何既有结论**。本篇的负面结论（无 IOKit、无网络导入、无硬件码）取自 import 符号表与 strings，而不是 dylibs 列表；全篇引用 dylib 清单的只有 §8.1，而那个二进制的弱链接为零。新露出的两条与正文一致：`vmnet.framework` 对应 §8.2 已写的 VM 网络路径，`ScreenCaptureKit.framework` 对应 §8.4 的截屏去向。修复后的列表与一条独立实现的 Mach-O 解析器逐条对照一致。

---

## 9. 负面清单（已证伪 / 易误读）

1. **Desktop 没有机器级硬件标识**，也没有读 `IOPlatformUUID`/`machine-id`/`MachineGuid`/MAC —— 与 Android 端（`android.md` 里 `ANDROID_ID` 原值上报）形成鲜明对比。
2. **不报主机名**：Sentry 显式关闭，一方事件 metadata 无该字段。
3. **系统代理：主进程不读，原生层读**。主进程代码里没有 `scutil --proxy`/`networksetup`；但 `@ant/claude-swift` 导入了 `CFNetworkCopySystemProxySettings` 与 `kCFNetworkProxies*`，用途是把宿主机的代理配置下发给 Cowork 虚拟机内的 guest（strings 里有 `Failed to send host proxy config: `、`PAC script (`）。该值**不上报**。另需注意「不探测代理」不等于「不走代理」——请求仍由 Chromium 网络栈发出，系统代理照常生效；例外是托管配置下发了固定代理或 PAC 脚本时，Desktop 会给网络栈追加 `proxy-server`/`proxy-pac-url` 并记录 `OS proxy settings ignored`，此时系统代理被顶掉（§2.1）。
4. **`DISABLE_TELEMETRY` 等 CLI 开关对 Desktop 完全无效**。
5. **`deviceId` 是浏览器扩展实例 ID**，不是机器 ID（§3.6）。
6. **`inference_provider` tag 只在 3p 注入**（1p 下不写），但 `inference_*` 系列 metadata 字段在事件里恒有。
7. **一方事件默认无凭据**，但不代表不上报——`user_id`/`account_uuid`/`install_id` 仍在 body 里。

---

## 10. 未找到 / 需补证

- 诊断包（support bundle）的**实际上传 URL**：主进程只算 zip 与 `canSend` 标志，上传动作不在主进程 bundle 内，`[Inference]` 由 renderer 执行。
- `admin`/企业托管对 1p 部署的影响：`disableNonessential` schema 标注 `scopes:["3p"]`，1p 下能否被控制台策略置位尚未定位（`remotePolicy.default:true`/`failClosedValue:true` 的求值点已定位，见 §4）。
- `@ant/claude-native` 的 `.node` 未抽出 → `hardwareKeyGetOrCreate` 的具体 keystore 条目名、签名实现、以及是否触碰 `IOPlatformUUID` 级硬件信息**需抽出 .node 才能确认**。
- `@ant/claude-swift` 的 `.node` 未抽出 → `deriveBrowserSafeStorageKey(browser)` 到各浏览器 Keychain 条目的映射只能从错误文案推断。
- Chrome 扩展源码不在范围内 → 扩展 `deviceId` 的生成方式与是否含机器信息未确认。
