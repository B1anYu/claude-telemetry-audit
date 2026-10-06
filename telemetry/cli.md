# Claude Code CLI — 遥测、身份与上行面

**审计对象**：Claude Code CLI **2.1.283**，素材为 `cli/modules/mod-0000.js … mod-2152.js`（bun 单文件二进制切分出的 2153 个明文模块）。**行号不可跨格式化版本重定位**，因此本篇的锚点以 `模块名 + grep 串` 为准，行号只作参考。

**范围**：CLI 自身进程的出站流量、持久标识符、上行字段与关断开关。Desktop 的通道见 `desktop.md`；两端能否被关联见 `linked.md`；Android 见 `android.md`。

**标注约定**：`[Observed]` = 有原文/定位串证据；`[Inference]` = 由代码推出的运行时行为，并写明所依赖的 `[Observed]` 前提。

**复验方式**：CLI 模块多为单行大文件（`mod-0365.js` 约 4MB），先 `grep -o` 定位串再小范围读取。注意 `grep` 工具对超大文件只扫前 4MB，尾段匹配会**静默丢失**（见 §8 第 6 条），复验时限定到具体模块文件。

---

## 0. 结论速览

| # | 问题 | 结论 | 等级 | 复验 |
|---|---|---|---|---|
| 1 | 用第三方 API（自建中转/BYOK，只设 `ANTHROPIC_BASE_URL`）就不上报了吗 | **不是。** provider 分类函数不读 `ANTHROPIC_BASE_URL`，遥测通道照开；且第三方 host 会被**明文**上传（§5） | `[Observed]` | `grep -o 'function Ie(){if(wo()'` |
| 2 | CLI 会把第三方 provider 的地址告诉 Anthropic 吗 | **会，且明文。** `apiBaseUrlHost` = `ANTHROPIC_BASE_URL` 的 host，随 GrowthBook 远端 eval 请求体上行 | `[Observed]` | `grep -o 'function rzo(){let e=a.ANTHROPIC_BASE_URL'` |
| 3 | 用 Bedrock / Vertex / Foundry 呢 | **相反：全线静音。** 这些走 `CLAUDE_CODE_USE_*` 显式分类，被判为「非第一方」，通道 A/B/C/E/G 一起关（**例外**：host 托管会话不受此限，见 §5.1） | `[Observed]` | `grep -o 'CLAUDE_CODE_USE_BEDROCK?"bedrock"'` |
| 4 | 事件里的 `provider` 字段上传吗 | **上传**：每个 API 事件（`tengu_api_error`/`_success`/`_query`/fallback 系列…）都带 `provider`，值 = `Ie()` 原值。**但常规终端里它的值恒为 `firstParty`**（非第一方时整个通道关闭，事件发不出去）；**例外**是 host 托管会话会被绕过该分支，此时可为 `bedrock` 等真值（§5.1） | `[Observed]` | `grep -o 'provider:BI()' cli/modules/*.js \| head` |
| 5 | 有没有硬件码 / 物理设备标识 | **没有。** `IOPlatformUUID` 等只被 OTel 的 `hostDetector` 读一次，随后在资源合并处被丢弃；落盘的身份全是随机值 | `[Observed]` | `grep -o 'ATTR_HOST_ID\]:Qf.getMachineId()'` |
| 6 | `.claude.json` 的 `machineID` 是硬件码吗 | **不是**，随机 64-hex；真实硬件码 `host.id` 从不进任何 payload | `[Observed]` | `grep -o 'setGeneratedMachineID'` |
| 7 | 关了遥测还有上行吗 | 有。1P 事件/GB/Datadog 会关，但**模型请求本身**照发，且自动模式会带 `live_cwd`/`home_dir` 原文（§4.4） | `[Observed]` | `grep -o 'live_cwd:o(oe())'` |
| 8 | 事件里的「哈希脱敏」字段安全吗 | **不安全。** `pn()` 无盐 sha256 截断 12 位、`pye()` 用公开常量盐——字典可反查、同名跨用户可关联；且本 build 的脱敏函数 `y/c/Sn` 是**恒等函数** | `[Observed]` | `grep -o 'function r(n){return n}'` |
| 9 | `email` 字段会上报吗 | **不上报**，是空实现（死字段）——但 email 会经 OTel 资源属性 `user.email` 走另一条通道 | `[Observed]` | `grep -o 'email(){return}async emailAsync(){return}'` |
| 10 | 有 Sentry / Statsig 吗 | **都没有**，无 DSN、无 SDK、无出口；门控完全由 GrowthBook 承担 | `[Observed]` | `grep -c 'Sentry.init' cli/modules/*.js` |
| 11 | 主机名会上行吗 | 仅两处 body：`POST /api/auth/trusted_devices` 与 cowork 远程设备注册的 `display_name`（源串形如 `Claude Code on ${…} · macOS`）；**没有任何请求头带主机名** | `[Observed]` | `grep -rn 'Claude Code on ' cli/modules/` |
| 12 | 时区 / 语言会上行吗 | 遥测与请求头里**都没有**（0 命中）；但时区会经模型请求的提示词注入（§4.4） | `[Observed]` | `grep -c 'Accept-Language' cli/modules/*.js` |
| 13 | 模型请求里带身份标识吗 | **带。** 每次 `/v1/messages` 的请求体都含 `metadata.user_id`（一个 JSON 字符串），内有 `device_id`（即本机 `userID`）、`account_uuid`、`session_id`，整个 JSON 上限 512 字节；它属模型请求而非遥测，**任何遥测开关都关不掉**（§4.4） | `[Observed]` | `grep -o 'metadata:Tx(' cli/modules/mod-0365.js` |

---

## 全景：按使用场景看上行数据

§0 是按问题列出的结论，以下各节是按通道与字段排列的证据。本节按用户的实际使用方式重新组织同一批结论，说明每种使用方式下有哪些数据离开本机、服务端由此能推断出什么。关键字段名仅在必要时出现，其余细节指回对应小节。

CLI 的上报行为由一个判断决定：它是否属于「第一方」用户（§1）。该判断只依据 `CLAUDE_CODE_USE_*` 环境变量与凭据类型，不读取 `ANTHROPIC_BASE_URL`。由此产生两条并列的结果。显式声明使用 Bedrock、Vertex 或网关凭据时，CLI 被归为第三方，事件流、实验配置拉取与内部指标一并停止。仅将 `ANTHROPIC_BASE_URL` 指向自建中转并配置普通令牌时，CLI 仍被归为第一方，上述通道全部保持开启，且该中转的域名会作为「当前使用的 API 地址」被明文上报。

最终发往 Anthropic 的数据只有两类。一类是事件流，记录用户行为与本机环境，未登录时同样发送；另一类是周期性的实验配置拉取，其中包含账号信息与 API 地址。对话内容与模型请求发往推理端点，只有当推理端点本身是 Anthropic 时才会到达 Anthropic。

**场景 1：首次启动（未登录任何账号）**
CLI 首次运行时会生成一个随机标识并写入用户目录下的配置文件，该值与硬件无关，删除后重新生成。此后立即开始上报事件，既不要求登录，也不等待用户输入。事件中不含账号信息，但上述随机标识随每条事件发送。服务端由此获得一台新安装的存在、其操作系统与版本，并可将其后续活动关联为同一条记录。此处常见的误读是认为未登录即无数据外发；实际上未登录只是缺少账号字段，环境信息照常上报。

**场景 2：进行一轮对话**
一轮对话过程中会产生若干条事件，内容均属行为类别，包括命令输入、文本粘贴、滚动、字形渲染与窗口状态。提问文本本身不在其中，随事件发送的还有被触达的功能开关名称。服务端由此了解功能的启用情况与使用频率。

**场景 3：让 CLI 修改代码**
上报内容为工具名称、执行成败、耗时与增删行数，不包含文件内容，文件路径也被降级为扩展名与计数。若启用 `OTEL_LOG_TOOL_DETAILS`（默认关闭），完整的命令文本与文件路径会以原文上报，因此不建议开启。服务端由此获得编码活跃度与主要语言。

**场景 4：使用 MCP、插件、技能或自定义命令**
此类名称以原文上报，包括技能名、插件名与市场名，中文字符同样保留。用于遮蔽的哈希字段（如 `plugin_id_hash`）可被反查，其盐值缺失或为公开常量。服务端由此获得已安装插件的名称与来源市场。

**场景 5：提交代码或创建 PR**
仅上报操作类别（提交、推送、创建 PR）与次数，不包含分支名与仓库名。远端地址只以哈希形式存在，且该字段在实际代码路径中被丢弃，并未发送。

**场景 6：发生 API 错误、限流或重试**
上报错误类型、状态码、重试次数与超时，错误文本本身只以哈希形式发送。当请求经过网关或代理时，响应头中的网关特征会被原样上报（`intermediary_headers`），这是使用自建中转时最容易被忽略的一项。`provider` 字段只在此类事件中出现，其取值问题见 §5.1。

**场景 7：自动更新**
上报版本迁移、耗时与安装方式，不携带身份信息。

**场景 8：长会话、子代理与后台任务**
上报结构性事件（发生压缩、启动子代理、转入后台）与 token 计数。

**场景 9：关闭遥测之后**
设置 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`（或 `DISABLE_TELEMETRY=1`、`DO_NOT_TRACK=1`）会同时停止事件流、实验配置拉取与内部指标；若只需停止携带 API 地址的实验拉取，可单独设置 `DISABLE_GROWTHBOOK=1`。模型请求不受这些开关影响，自动模式下的工作目录与家目录仍以原文路径随请求发送（§4.4）。

---

## 1. provider 分类：谁算「第一方」

所有遥测闸门都建在同一个分类函数上（`mod-0077.js`）：

```js
function Ie(){if(wo()||y2t()||_2t())return"gateway";
  return a.CLAUDE_CODE_USE_BEDROCK?"bedrock":
         a.CLAUDE_CODE_USE_FOUNDRY?"foundry":
         a.CLAUDE_CODE_USE_ANTHROPIC_AWS?"anthropicAws":
         a.CLAUDE_CODE_USE_ANTHROPIC_GOOGLE_CLOUD?"anthropicGoogleCloud":
         a.CLAUDE_CODE_USE_MANTLE?"mantle":
         a.CLAUDE_CODE_USE_VERTEX?"vertex":"firstParty"}
```
`[Observed]`（`grep -o 'function Ie(){if(wo()'`）

**关键点：`Ie()` 只读 `CLAUDE_CODE_USE_*` 六个环境变量与网关凭据，不读 `ANTHROPIC_BASE_URL`。** 因此：

| 配置 | `Ie()` | 后果 |
|---|---|---|
| 什么都不设 / 只设 `ANTHROPIC_API_KEY` 或 OAuth | `firstParty` | 通道 A/B/C/E/G 全开 |
| 只设 `ANTHROPIC_BASE_URL` 指向自建中转 | `firstParty` | **遥测全开**，且中转 host 被明文上传（§5） |
| `CLAUDE_CODE_USE_BEDROCK` 等显式第三方 | `bedrock`/`vertex`/… | 通道 A/B/C/E/G 全关 |
| 带网关凭据（aud=`claude-gateway` 的 JWT 等） | `gateway` | 同上全关（网关会话另有中继路径，见 §2 通道 D/F2） |

闸门链（`[Observed]`，逐条可 grep）：

```js
function Gn(){return Ie()==="firstParty"}          // 是不是第一方
function t5(){return !Gn()}                         // 「用了第三方 provider」
function e(){if(a.CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST)return!1;return !Gn()}
function Lg(){return e()||wo()!==null||WD()||t()}   // 非第一方 / 网关 / 遥测被关 / 自定义 OAuth
function IB(){return!Lg()}                          // 通道 A 与 G 的总开关
function ky(){let e=process.env.ANTHROPIC_BASE_URL;if(!e)return!0;return _S(e)}
function _S(e){try{let t=new URL(e).host;return["api.anthropic.com"].includes(t)}catch{return!1}}
function Hs(){if(a._CLAUDE_CODE_ASSUME_FIRST_PARTY_BASE_URL)return!0;return ky()}
```

**`Hs()`（base URL 是否第一方）与 `Ie()` 是两回事，这是最容易被写错的地方**：`Hs()` 只被**通道 C（Datadog 错误追踪）**等少数出口使用，不参与 `Lg()`。所以自定义 `ANTHROPIC_BASE_URL` 的真实效果是：

- 通道 A（1P 事件）、B（Datadog logs）、E（内部指标）、G（GrowthBook）→ **不受影响，照开**；
- 通道 C（Datadog 错误追踪）→ **关闭**（`DIo()` 要求 `Hs()`）；
- 设 `_CLAUDE_CODE_ASSUME_FIRST_PARTY_BASE_URL` 可反向强制视为第一方。

> **对旧结论的更正**：本仓库早期分析曾写成「自定义 `ANTHROPIC_BASE_URL` → 通道 A 完全关闭」（该分片已删除，可从 git 历史取回），是把 `Hs()` 误当成了通道 A 的门。逐条复读 `Lg()` 后该说法不成立，本条以本节为准。

---

## 2. 出站通道 A–I

| 通道 | 出口 | 默认 | 总开关 |
|---|---|---|---|
| A 1P 事件（`tengu_*`） | `POST https://api.anthropic.com/api/event_logging/v2/batch` | **开** | `Lg()`（= `IB()` 取反）；GB `tengu_frond_boric.firstParty` |
| B Datadog Logs | `POST https://http-intake.logs.us5.datadoghq.com/api/v2/logs` | **关** | GB `tengu_log_datadog_events`（默认 `false`） |
| C Datadog 错误追踪 | `POST https://browser-intake-us5-datadoghq.com/api/v2/logs` | **关** | GB `tengu_orford_ness`（默认 `false`）+ `DISABLE_ERROR_REPORTING` |
| D OTel 3P（用户自配 OTLP） | `OTEL_EXPORTER_OTLP_*` 指定 | **关** | `CLAUDE_CODE_ENABLE_TELEMETRY` |
| E 1P 内部指标 | `POST https://api.anthropic.com/api/claude_code/metrics` | 条件开 | 组织 opt-out + GB `tengu_cozy_dusk`（仅控间隔） |
| F1 Beta tracing | `${BETA_TRACING_ENDPOINT}/v1/{traces,logs}` | **关** | `ENABLE_BETA_TRACING_DETAILED` + `BETA_TRACING_ENDPOINT` |
| F2 网关/远程会话 OTLP 中继 | `${SESSION_INGRESS_URL}/v1/code/sessions/<id>/worker/otlp/<signal>`；网关走 `${ANTHROPIC_BASE_URL}/v1/<signal>` | **关** | `CLAUDE_CODE_REMOTE`+`SESSION_INGRESS_URL`+`..._SESSION_ID`；或 `ANTHROPIC_AUTH_TOKEN`(gateway) |
| G GrowthBook | `POST https://api.anthropic.com/api/eval/sdk-zAZezfDKGoZuXXKe`（或 `/api/eval-authed/`）；SSE `/sub/<key>` | **开** | `DISABLE_GROWTHBOOK`；同 A 的闸门 |
| H Sentry | **无出口**（无 DSN、无客户端） | — | — |
| I Statsig | **无 SDK、无出口**（仅遗留目录名 `~/.claude/statsig/`） | — | — |

### A. 1P 事件（最大的一条）

- 端点基址是**常量**，只有 `ANTHROPIC_BASE_URL` 恰等于 `https://api-staging.anthropic.com` 时走 staging（`grep -o 'api-staging.anthropic.com'`）。**不跟随自定义 base URL。**
- 请求头：`Content-Type`、`User-Agent: claude-code/2.1.283`、`x-service-name: claude-code`，凭据可用时加 `Authorization: Bearer`/`x-api-key`（`grep -o 'x-service-name":"claude-code'`）。
- 认证头在两条路径上可能被替换或扣留。发送前先取 `authHeadersForSend`；仅当它返回 `reasonCode` 为 `no_api_key` 时，才调用 `UD(endpoint)` 作为回退，且该回退要求 base URL 与 telemetry 端点都是 https 第一方地址，并按 `sk-ant-` 前缀之后的三位字符分流：`api` 归入 `x-api-key`，`oat` 归入 `Authorization: Bearer` 并附 `anthropic-beta`。随后 `Hce(headers, endpoint)` 比对凭据所属 host 与 telemetry 端点 host，不相等时清空认证头并返回 `misrouted_credential`，跨 host 凭据因此不外发。发送中若收到 401，改用基础头集（`Content-Type`、`User-Agent`、`x-service-name`，另加可选的 gzip 头）重试一次，第二次响应即最终结果（`grep -o 'reasonCode:"misrouted_credential"'`）。
- **不要求登录**：`initialize1PEventLogging` 在 init 里无条件调用；workspace trust 未建立时 `shouldSkipAuthForSend` 返回真 → **匿名 POST，但载荷里仍带 `device_id`**。`[Observed]`
- 批次：`maxBatchSize=200`、`batchDelayMs=100`、`maxAttempts=8`（指数退避），失败批次落盘 `<config dir>/telemetry/1p_failed_events.<sessionId>.<runId>.json`（`grep -o '1p_failed_events.'`）。
- 其余队列常量：单次请求超时 `timeout` 默认 10000 毫秒，`baseBackoffDelayMs` 默认 500，`maxBackoffDelayMs` 默认 30000，重试等待为 `min(max(500, 500·attempts²), 30000)`。底层 OTel LogRecordProcessor 的默认值为 `scheduledDelayMillis=10000`（可被 `OTEL_LOGS_EXPORT_INTERVAL` 覆盖）、`maxExportBatchSize=200`、`maxQueueSize=8192`，三者都可被 GrowthBook gate `tengu_1p_event_batch_config` 覆盖。入队前的本地队列上限为 1000 条，超出后丢弃最旧一条并累加 `droppedEventCount`（`grep -o 'var u=1000;function l(){return{eventQueue:\[\]'`）。
- 采样：GB `tengu_event_sampling_config` 按事件名给 `sample_rate`。
- 载荷结构见 §4.1。

### B / C. Datadog（默认关，且都排除第三方 provider）

- B 只发**白名单事件**（约 200 个名字常量），头 `DD-API-KEY: pubea5604404508cdd34afb69e6f42a05bc`（客户端 token 当 API key 用），`hostname:"claude-code"` 是**常量而非真实主机名**。每条日志以 `ddsource:"nodejs"`、`service:"claude-code"`、`env:"external"` 与 `message:<事件名>` 为固定字段，事件属性经 camelCase 转 snake_case 后同时写进平铺键与 `ddtags`。MCP 类事件另有限流：以「事件名 + 服务名」为键开窗，窗口 60000 毫秒内最多放行 10 条，超出部分丢弃并累计到 `droppedSinceLastForward`，该计数随下一次放行的记录带上。发送前的脱敏由删除键集完成，集合含 `mcpServerBaseUrl`、`toolSchemasHash`、`errorMessageHash`、各 `attribution*Hash`、`skill_name_hash`、`plugin_id_hash`、`rh`、`baseUrl` 等；合规态下 `postCurrent` 会把标记为 `builtUnredacted` 的记录整体滤掉。批大小 100，flush 间隔默认 15000 毫秒，单次请求超时 5000 毫秒（`grep -o 'var N=10,O=60000,U=200'`、`grep -o 'var x=\["mcpServerName","mcpServerBaseUrl"'`）。
- C 的载荷含 `host_name_redacted: j5e().slice(0,12)`——名字叫 redacted，实际是 `machineID` 前 12 个十六进制，**同机跨会话稳定可比对**；还有 `user_bucket = sha256(userID)[0:8] mod 30`。其余载荷为 `error{kind,message,stack,fingerprint,handling}`，其中 `message` 截断 4000、`stack` 截断 16000，`handling` 取 `handled`（logError）或 `unhandled`；`error_frames` 取栈帧前 20 条，`feature_flags` 取布尔且在 feature 白名单内的项前 50 个。`fingerprint` 为 `sha256("<errorName>\n<前三条帧>")` 的十六进制前 16 位。载荷另带 `bun_version` 与 `host_os_release`。每进程最多入队 100 条，达到上限时先发一条 kind 为 `ErrorTrackingCapReached` 的哨兵记录再静默。flush 间隔默认 30000 毫秒，批大小 25，单次超时 10000 毫秒；端点查询串固定含 `ddsource=browser`、`dd-api-key`、`dd-evp-origin=browser`、`dd-evp-origin-version=<版本号>` 与 `dd-request-id=<randomUUID>`（`grep -o 'ErrorTrackingCapReached: per-process cap of'`）。
- 两条都以 `Ie()==="firstParty"` 为硬前提，所以 Bedrock/Vertex/网关场景下不可达；`CLAUDE_CODE_ENVIRONMENT_KIND=byoc` 会额外关 B（除非 `CLAUDE_CODE_BYOC_ENABLE_DATADOG`）。
- C 在 `DIo()` 之上还叠加版本与合规条件：`DISABLE_ERROR_REPORTING` 未设、`Lg()` 为假、provider 为 firstParty 且 `Hs()` 为真、版本不低于 `2.1.193`、`PDr()` 为真，最后才看 GrowthBook gate `tengu_orford_ness`（默认 false）。`PDr()` 取合规判定 `xDr()` 的结果，只有 `allowed_taints_clean` 与 `allowed_untaintable` 两种通过：policy-limits 缓存未命中按 deny 处理；命中时若 `allow_error_reporting.allowed` 为 false 则为 `blocked_restriction`；taints 未结算为 `blocked_unsettled`；scopeless OAuth、凭据来源为 `ANTHROPIC_AUTH_TOKEN`、凭据来自 apiKeyHelper 各对应一个 blocked 分支。托管合规限制表把 `allow_error_reporting` 的 `deniedUnder` 定为 `["hipaa","zdr"]`，`requirementId` 为 `HIPAA-R19`。批次发出前会再查一次 `PDr()`，不通过则整批丢弃并写一条 warn 日志（`grep -o 'var t="tengu_orford_ness",n="2.1.193"'`）。

### D / E. OTel 与内部指标

- D 需要 `CLAUDE_CODE_ENABLE_TELEMETRY ∈ {1,true,yes,on}` 且配了 `OTEL_*_EXPORTER`，且在 workspace trust 接受后才初始化。
- D 的 `user.id = SD()`（即 `.claude.json:userID`）**无条件写入**，不受任何 `OTEL_METRICS_INCLUDE_*` 控制；默认还带 `session.id`、`user.account_uuid`。内容粒度由 `OTEL_LOG_USER_PROMPTS` / `_TOOL_DETAILS` / `_RAW_API_BODIES` 等控制（见 §6）。
- 网关凭据在场时，D 的资源属性改由网关 OIDC 身份补入。宿主凭据槽里存在未固定的 `gatewayAuth` JWT 时，`P1n()` 解析 JWT 载荷并写入 `identity.source`（恒为 `gateway-oidc`）；载荷带 `sub` 时以 `sub` 覆盖 `user.id`，因此「无条件的 `user.id`」在网关场景下让位于 JWT；另按 JWT 内容带上 `user.email` 与 `user.groups`（多个 group 以逗号连接）。这组属性经 `Object.assign` 进入每次事件记录的资源属性，并经 `st()` 并入 3P OTLP provider 的基础资源，因此属**通道 D**；通道 E 的聚合载荷按白名单取值，不含 `identity.*`/`user.*`（`grep -o 'function P1n'`）。
- 六个资源属性开关的默认值为 `OTEL_METRICS_INCLUDE_SESSION_ID=true`、`OTEL_METRICS_INCLUDE_VERSION=false`、`OTEL_METRICS_INCLUDE_ACCOUNT_UUID=true`、`OTEL_METRICS_INCLUDE_ENTRYPOINT=false`、`OTEL_METRICS_INCLUDE_RESOURCE_ATTRIBUTES=true`、`OTEL_METRICS_INCLUDE_REPOSITORY=false`（`grep -o 'OTEL_METRICS_INCLUDE_SESSION_ID:!0,OTEL_METRICS_INCLUDE_VERSION:!1'`）。
- E 的触发条件（`ze(){if(WD())return !1; let e=tr(), r=pt()&&(e==="enterprise"||e==="team"); return VFe()||r}`，其中 `VFe(){if(!Gn())return !1; if(pt())return !1; return !0}`）：遥测未被环境变量关闭，且满足二者之一——**第一方且未用 OAuth 登录**（即 API-key 用户），或 **OAuth 订阅为 `enterprise`/`team`**。个人 `pro`/`max` 订阅被排除。随行字段 `user.customer_type` 相应取 `"api"` 或 `"claude_ai"`（后者另带 `user.subscription_type`）。
- E 的 resource 白名单只有 `service.name/version`、`os.type/version`、`host.arch`、`wsl.version` + `user.customer_type`/`user.subscription_type`——**不含 `host.id`/`host.name`/`process.*`**；`host.arch` 是唯一上报的机器规格。**合规态下会再过滤一遍**：`transformMetricsForInternal` 在 `CNo() || oc("hipaa")` 为真时改用 schema `TDo` 校验，其中 `os.version` 被显式禁用（`"os.version":()=>!1`）——即 HIPAA 组织的载荷里没有 `os.version`，非合规态才按上面的白名单原样上报。（旧分片分别只写了其中一半，容易读成互相矛盾。）
- 指标名：`claude_code.session.count`、`claude_code.lines_of_code.count`、`claude_code.pull_request.count`、`claude_code.commit.count`、`claude_code.cost.usage`、`claude_code.token.usage`、`claude_code.code_edit_tool.decision`、`claude_code.active_time.total`（meter `com.anthropic.claude_code`）。
- D 的协议取自 `OTEL_EXPORTER_OTLP_<SIGNAL>_PROTOCOL`，缺省回落到 `OTEL_EXPORTER_OTLP_PROTOCOL`，合法值只有 `grpc`、`http/json`、`http/protobuf`，取到其他值直接抛错。端点优先取 `OTEL_EXPORTER_OTLP_<SIGNAL>_ENDPOINT`，未设时用 `OTEL_EXPORTER_OTLP_ENDPOINT` 拼接 `/v1/<signal>`。启动时若未设 `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE`，进程把它强制写成 `delta`。导出间隔默认 metrics 60000、logs 5000、traces 5000 毫秒；关闭等待 `CLAUDE_CODE_OTEL_SHUTDOWN_TIMEOUT_MS` 默认 2000 毫秒，flush 等待 `CLAUDE_CODE_OTEL_FLUSH_TIMEOUT_MS` 默认 5000 毫秒。
- 增强路径由 `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA`（或 `ENABLE_ENHANCED_TELEMETRY_BETA`）开启。tracer 名为 `com.anthropic.claude_code.tracing`、版本 1.0.0；span 名共十个：`claude_code.interaction`、`claude_code.llm_request`、`claude_code.tool`、`claude_code.tool.execution`、`claude_code.tool.blocked_on_user`、`claude_code.hook`、`claude_code.subagent.spawn`、`claude_code.compaction`、`claude_code.bash.subprocess`、`claude_code.mcp.rpc`。beta tracing 端点 arm 后，资源属性切到只保留 `session.id` 与 `ccr.session.id`（`grep -o 'process.env.OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE="delta"'`、`grep -o 'getTracer("com.anthropic.claude_code.tracing","1.0.0")'`）。

### G. GrowthBook（本篇的重点）

客户端怎么建、属性里有什么、请求体长什么样，见 §5.2（此处不重复）。这里只记两条：刷新间隔默认 360 分钟（GB `tengu_gb_refresh_interval_minutes` 可调，夹在 5–360）；远端 eval 结果落盘到 `.claude.json` 的 `cachedGrowthBookFeatures` 等键。设了该 flag 时，取值先夹在 5 到 360 之间，再乘 `0.9 + Math.random()*0.2` 的抖动因子，上限仍为 360 分钟。

---

## 3. 标识符：生成、落盘与去向

| 标识符 | 生成 | 落盘 | 去向 |
|---|---|---|---|
| `userID` | `crypto.randomBytes(32).toString("hex")`（64 hex，正则 `^[0-9a-f]{64}$` 校验） | `<config dir>/.claude.json` 键 `userID` | ① 通道 A 的 `device_id`（**每个事件**，未登录也带）② GrowthBook `id`/`deviceID` ③ Datadog `user_bucket` ④ D 的 `user.id` ⑤ API 请求 `device_id` |
| `machineID` | 同模式随机 64 hex | `.claude.json` 键 `machineID` | 仅通道 C 的 `host_name_redacted`（前 12 位） |
| `host.id`（真硬件码） | OTel `hostDetector`：darwin `ioreg … IOPlatformUUID`、linux `/etc/machine-id`、win32 `MachineGuid` | **不落盘** | **无去向**——`st()` 合并资源时只取 `host.arch` |
| `sessionId` | 每会话生成 | 会话文件 | A 的 `session_id`、GB `sessionId`、D 的 `session.id` |
| `accountUuid` / `organizationUuid` | `.claude.json:oauthAccount`，或 `CLAUDE_CODE_ACCOUNT_UUID` / `CLAUDE_CODE_ORGANIZATION_UUID` | `.claude.json` | A 的 `auth.*`、GB `accountUUID`/`organizationUUID`、D 的 `user.account_uuid` |
| `remoteControlMachineId` / `summonSidKey` | UUID / 64 hex 随机 | `.claude.json` | 未发现进入遥测 |
| `coworkRemoteDevice` 密钥对 | **软件生成的 EC P-256**（非 Secure Enclave） | macOS 钥匙串 `Claude Code-device-keys` | cowork 远程设备注册的 `public_key` |

要点：

- **`userID` 与 `machineID` 都是随机值**，与硬件无关；清理配置文件即可重置身份（`[Observed]`，`grep -o 'setGeneratedUserID'`）。
- **唯一读硬件码的地方（`ioreg`/`/etc/machine-id`）结果被丢弃**：`st()` 里 `let i=C.hostDetector.detect(), p=i.attributes?.[k.SEMRESATTRS_HOST_ARCH]?{...}:{}`，只保留 `host.arch`（`grep -o 'SEMRESATTRS_HOST_ARCH'`）。
- `host.id` 的采集按 `process.platform` 惰性分派：darwin 执行 `ioreg -rd1 -c "IOPlatformExpertDevice"` 并解析 `IOPlatformUUID`；linux 依次尝试 `/etc/machine-id` 与 `/var/lib/dbus/machine-id`；freebsd 先读 `/etc/hostid`，失败后回退 `kenv -q smbios.system.uuid`；win32 查询注册表 `MachineGuid`（32 位进程经 `sysnative` 转接）；其余平台只写一条 `could not read machine-id: unsupported platform` 调试日志并返回空值。darwin 分支读取失败时没有回退路径。采集由 `st()` 触发，`st()` 以记忆化保存结果，因此每进程至多执行一次；`st()` 由 `initializeTelemetry` 调用，后者由 `oSe` 经一次性初始化守卫进入，调用点分布在主会话启动路径（beta 遥测标志或 `CLAUDE_CODE_ENABLE_TELEMETRY` 时立即调用，否则延迟到 `telemetry_init` 钩子）、serveOnly 分支、云会话的 headless 打印分支，以及交互式 REPL 启动路径（`setImmediate(oSe, …)`）。
- `.claude.json` 的**真实文件名可变**：若 `<config dir>/.config.json` 存在则优先用它；否则 `.claude${w3()}.json`，其中 `w3()` 随环境取 `""`/`-local-oauth`/`-staging-oauth`/`-custom-oauth`（`grep -o 'function Y9n'`）。
- 第二处读 `/etc/machine-id`（`eNo()`）只用于**本地 UDS 鉴权密钥的命名空间**，不联网。

---

## 4. 上行字段清单

### 4.1 1P 事件载荷

```
{events:[{event_type:"ClaudeCodeInternalEvent", event_data:{
  event_id, event_name, client_timestamp, device_id,   // device_id = userID
  email, auth{account_uuid, organization_uuid}, core{...}, env{...},
  process,                                             // base64(JSON(进程指标))
  skill_name, plugin_name, marketplace_name, mcp_server_name, mcp_tool_name, head_sha,
  additional_metadata                                  // base64(JSON(事件元数据 + additional))
}}]}
```

- `core`：`session_id, model, user_type, is_interactive, client_type`，可选 `betas, entrypoint, agent_sdk_version, swe_bench_*, agent_id, parent_session_id, agent_type, team_name`。
- 事件里的模型名先经 `dun()` 处理再上行。命中服务端下发的遮蔽集合 `servedCatalogMaskedIds` 时，或当客户端处于第一方而该模型既不在服务端下发的公开名单、也不属已知模型族时，模型名被替换为占位符（常量 `pce = "confidential"`）；其余情况原样上行，用户自设的 `ANTHROPIC_MODEL` 串在未被遮蔽表命中时以原文出现（`grep -o 'pce="confidential"'`）。
- `env`（无校验器，逐字）：`platform, platform_raw, arch, node_version, terminal, shell, package_managers, runtimes, is_running_with_bun, is_ci, is_claubbit, is_claude_code_remote, is_local_agent_mode, is_conductor, is_github_action, is_claude_code_action, is_claude_ai_auth, version, build_time, deployment_environment` + 可选 `wsl_version, linux_distro_id/version, linux_kernel, vcs, tags, github_action_ref, claude_code_container_id, claude_code_remote_session_id, github_actions_metadata{actor_id,repository_id,repository_owner_id}` 等。
- `env` 由一条独立采集函数取值。非 Windows 平台把 `uname -s`、`uname -r`、`uname -m` 与探测包管理器、运行时的命令按行拼接后交给 `sh -c` 一次执行；Windows 走 `Windows_NT` 分支，不执行 shell，直接给出 `platformRaw: "win32"` 与处理器架构。文件信号另作补充：`/sys/hypervisor/uuid` 的内容以 `ec2` 开头时产生 `aws-ec2` 信号，`/.dockerenv` 存在时产生 `docker` 信号，二者经映射成为 `deployment_environment` 的取值。同一形状的 `env` 也由一个面向插件的 `$.telemetry` 接口产出，其批次同样发往 `api.anthropic.com/api/event_logging/v2/batch` 并带 `x-service-name: claude-code`；该接口只对内置层级的插件开放（`grep -o 'fileSignals:\[\["aws-ec2"'`）。
- `env.tags` 直接取自环境变量 `CLAUDE_CODE_TAGS` 的原文，按逗号切分并去空白后逐项上行，不经过任何脱敏。该变量由用户或组织自行填写，取值可以是任意字符串，包括中文（`grep -o 'process.env.CLAUDE_CODE_TAGS&&{tags:process.env.CLAUDE_CODE_TAGS}'`）。
- `additional_metadata` **不是 protobuf**，是 `base64(JSON.stringify(...))`；每个 `tengu_*` 事件的自定义元数据都原样落进去。
- `additional` 段除该事件的全部自定义元数据外，还固定携带一批本地状态键，仅在取值存在时写出：`rh`（远端地址归一化后的无盐哈希）、`_PROTO_head_sha`、`coach_mode`、`observer_mode`、`session_kind`、`has_attacher`、`renderer_mode`、`remote_control_lane`、`projects_session`、`subscription_type`、`parent_agent_id`、`cc_prompt_id`、`desktop_app_version`（`grep -o 'additional:{...b&&{rh:b}'`）。
- **默认无字段级脱敏**；只有 HIPAA 合规态（`oc("hipaa")`）才走白名单。
- HIPAA 合规态的字段级处理按校验器决定：某字段有校验器且通过则保留，有校验器但不过则整个键被丢弃；无校验器的字符串一律写为字面量 `hipaa_redacted`，无校验器的字符串数组写成长为 1 的 `[hipaa_redacted]`，无校验器的数字与布尔则被丢弃。`additional_metadata` 在合规态另经 `Ul()` 白名单：数值键只保留 `sample_rate`，其余键须命中该事件专属校验器表，而有条目的仅有 `tengu_retention_sweep`、`tengu_feature_ok`、`tengu_feature_bad`、`tengu_feature_sad`、`tengu_org_policy_denied`、`tengu_policy_limits_fetch`、`tengu_frontmatter_grant_withheld` 七个事件，其余事件的 `additional_metadata` 在合规态被清空（`grep -o 'Ml="hipaa_redacted";function qr(e,n){'`）。
- 错误类事件不上报错误原文。`tengu_api_error` 的 `error` 是合成串，形如 `API error: type=<type> status=<n>`，其中 type 须匹配 `^[a-z][a-z0-9_]{0,63}$`，不匹配则写 `unknown`。未捕获异常与 handler 错误只上报哈希：`error_message_hash = pn(<归一化后的错误文本>)`，host error 另带 `error_code`、`error_constructor` 与 `error_stack_hash`。归一化器 `h$e()` 先截断到 500 字符，再依次替换 URL、email、密钥前缀（`sk-ant`/`sk`/`pk`/`gh*`/`github_pat`/`xox*`）、Windows 与 UNC 路径、Unix 路径、UUID 与 `req_*` 标识、16 位以上十六进制、32 位以上 base64、IPv4、四位以上数字（`grep -o 'function h$e(e){return e.slice(0,500)'`）。
- 名称类字段里 `plugin_name_redacted` 与 `marketplace_name_redacted` 虽带 redacted，但只在来源被判为第三方时才写占位符 `third-party`，官方插件与官方市场在这两个字段里仍是原名。工具名经映射后上行：已知工具映射为别名，`mcp__` 前缀的工具统一写成 `mcp_tool`，其余保留原名。子代理类型 `subagent_type` 与斜杠命令名 `command_name` 均为用户定义的原文（`grep -o 'nS="third-party"'`、`grep -o 'if(e.startsWith("mcp__"))return y("mcp_tool")'`）。

### 4.2 GrowthBook attributes（`Rpn()` / `getUserAttributes`）

`id, sessionId, deviceID, platform, apiBaseUrlHost?, organizationUUID?, accountUUID?, userType?, subscriptionType?, rateLimitTier?, organizationRole?, subscriptionCreatedAt?, firstTokenTime?, email?, appVersion?, githubActionsMetadata?, releaseChannel?, entrypoint?, sessionOrigin?, atisPin?, hasUsedRemoteSession?, hasRemoteEnvironment?, slackTagConnected?`（`[Observed]`，`grep -o 'getUserAttributes:()=>Rpn()'`）

`email` 恒 `undefined`（见 §7）。曝光事件 `GrowthbookExperimentEvent` 的信封携带 `event_id`、`experiment_id`、`variation_id`、`device_id`（即 `userID`）、`account_uuid`、`organization_uuid`、`session_id`、`user_attributes`、`experiment_metadata` 与 `environment`，其中 `environment` 恒为 `production`；只有 `user_attributes` 子对象被构造成只放 `appVersion`。因此「只带 `appVersion`」仅对 `user_attributes` 成立，事件本身仍带设备标识与账号标识，与上表的身份字段并无隔离。

### 4.3 请求头（发往 api.anthropic.com）

- SDK 兜底：`Accept`、`User-Agent`、`X-Stainless-Lang/Package-Version/OS/Arch/Runtime/Runtime-Version`、`X-Stainless-Retry-Count`、可选 `X-Stainless-Timeout`、`anthropic-dangerous-direct-browser-access: true`、`anthropic-version: 2023-06-01`。
- 请求头由 SDK 的合并函数逐层合成，层序为 SDK 默认头、认证头、CLI 的 `defaultHeaders`、单次请求头，最后是调用点自定义头。同一层内重复的同名键依次追加；跨层遇到同名键时先删除已累积值再追加，因此后层覆盖前层。`J` 里的 `User-Agent` 因而覆盖 SDK 默认 UA，而 `X-Stainless-*` 没有后层同名键，全部保留。OAuth 凭据对应的 `anthropic-beta` 取值是常量 `oauth-2025-04-20`，只在 OAuth 认证分支附加（`grep -o 'up="oauth-2025-04-20"'`）。
- CLI 自加（`J`）：`x-app`（`cli`/`cli-bg`）、`User-Agent: claude-cli/2.1.283 (external, <entrypoint>)`、`X-Claude-Code-Session-Id`、条件头 `x-claude-remote-container-id`、`x-claude-remote-session-id`、`x-client-app`、`x-claude-code-agent-id`、`x-claude-code-parent-agent-id`、`x-claude-code-request-class`、`x-claude-code-agent-type`、`x-claude-code-prompt-id`；`CLAUDE_CODE_ADDITIONAL_PROTECTION` 时加 `x-anthropic-additional-protection: true`。
- **`anthropic-client-platform` 不是默认带的**：唯一注入点是 `wit()`，门控 `Lhn(){let e=a.CLAUDE_CODE_ENTRYPOINT; return e==="claude-desktop"||e==="local-agent" ? a.CLAUDE_CODE_DESKTOP_APP_VERSION : void 0}`（`mod-0033.js`）。即只在**由 Desktop 拉起**的会话里注入，值 `anthropic-client-platform: desktop_app` + `anthropic-client-version: <Desktop 版本>`；**独立终端 CLI 的 `/v1/messages` 不带该头**。另一处 `jg()`（`mod-0004.js`，默认返回 `claude_code_cli`）只服务辅助端点，不进 `J`。（`grep -o 'anthropic-client-platform":"desktop_app"'`）
- 入口类型 `CLAUDE_CODE_ENTRYPOINT` 除决定上述头以外，还经另外三条通路标记桌面端发起的会话。辅助端点的 `anthropic-client-platform` 由 `jg()` 直接映射，`local-agent` 对应 `claude_code_local_agent`。事件载荷中，`env.is_local_agent_mode` 仅当该变量等于 `local-agent` 时为真，`core.entrypoint` 取白名单内的原值（集合含 `local-agent`、`claude-desktop`、`claude-desktop-3p`），`additional_metadata` 内另有 `desktop_app_version`。推理请求的 `User-Agent` 尾部同取该变量，Desktop 拉起的会话为 `claude-cli/2.1.283 (external, local-agent)`。这些标记说明会话由桌面应用发起，本身不是设备标识（`grep -o 'isLocalAgentMode:process.env.CLAUDE_CODE_ENTRYPOINT==="local-agent"'`）。
- 另有一组辅助端点，其请求头与推理端点不同。OAuth 角色查询 `GET /api/oauth/claude_cli/roles` 只带 `Authorization: Bearer`，不附 `User-Agent`；建 API key 的 `POST /api/oauth/claude_cli/create_api_key` 附 `User-Agent: claude-code/2.1.283`。设备登记的 `POST /api/auth/trusted_devices` 在请求体里写 `display_name`（主机名），头为 `Authorization` 与 `Content-Type`。claude.ai / console 侧的会话辅助端点（session ingress、teleport、environment_providers、v1/sessions、worker/record-created-pr 等）统一走 `Nw()` 构造的头：`Authorization: Bearer`、`Content-Type: application/json`、`anthropic-version: 2023-06-01`、`anthropic-client-platform: jg()`，各调用点再附 `x-organization-uuid`，CCR 相关者另附 `anthropic-beta: ccr-byoc-2025-07-29`；CCR 工具宿主请求以 `anthropic-client-feature: ccr` 标记。`x-organization-uuid` 只落在这些辅助端点上，`/v1/messages` 不带该头（`mod-0255.js` 中 0 命中）（`grep -o 'function Nw(e){return{Authorization:'`）。
- OAuth 流程的上行面同样不含设备标识。端点常量在 `mod-0029.js`：`TOKEN_URL` 为 `https://platform.claude.com/v1/oauth/token`，`API_KEY_URL` 与 `ROLES_URL` 在 `api.anthropic.com` 下，浏览器授权页在 `platform.claude.com/oauth/authorize`。换 token 与刷新 token 两个 `POST` 只带 `Content-Type: application/json`，既不附 `User-Agent`，也不附任何设备头；全库检索 `anthropic-device-id` 为 0 命中。例外是网关凭据刷新路径（日志前缀 `[gateway-refresh]`），它以 `application/x-www-form-urlencoded` 提交并附 `User-Agent: claude-code/2.1.283`（`grep -o 'TOKEN_URL:"https://platform.claude.com/v1/oauth/token"'`）。
- **没有** device class / total memory / cpu model / os build / 主机名 / 时区 / 语言（均 0 命中）。
- `X-Stainless-OS/Arch/Runtime-Version` 是 CLI 唯一的「OS 家族 + 架构 + node 版本」出口，粒度粗于 Desktop。
- 配置指纹对象 `yN()` 一次算出四个布尔：是否配置了 HTTP(S) 代理环境变量（`https_proxy`）、是否设置了 `ANTHROPIC_CUSTOM_HEADERS`（`custom_headers`）、是否设置了 `NODE_EXTRA_CA_CERTS`（`extra_ca_certs`）、是否设置了 `CLAUDE_CODE_CLIENT_CERT`（`client_cert`），另有 `provider`、`base_url`、`base_url_gateway`。该对象整体只作为 `route` 字段挂在本机日志（`cli_api_error`、`cli_api_route_observed`、`cli_stream_failed`）上；真正进入上行错误事件的只有其中两个——`tengu_api_error` 与 `tengu_stream_no_events` 经 `G7()` 带上 `https_proxy` 与 `extra_ca_certs`，`custom_headers` 与 `client_cert` 没有对应的上行字段。证书类配置另有一条上行路径：启动事件 `tengu_startup_telemetry` 带 `has_node_extra_ca_certs`、`has_client_cert`、`has_use_system_ca`、`has_use_openssl_ca` 与 `cert_store`（`CLAUDE_CODE_CERT_STORE` 的值），同样只记布尔与枚举。`ANTHROPIC_CUSTOM_HEADERS` 的值本身经 `wit()` 解析后作为真实请求头发往 Anthropic，事件层面不反映（`grep -o 'custom_headers:Boolean(a.ANTHROPIC_CUSTOM_HEADERS)'`）。

### 4.4 模型请求面（不是遥测，但同样上行且不受遥测开关约束）

- **自动模式服务端上下文**（默认开，GB `tengu_smooth_chipmunk` 默认 `true`）：`{permission_mode, platform, live_cwd, home_dir, rule_roots, trusted_directories, network, rules, case_insensitive_paths, auto_mode, is_remote_mode, classify_all_shell, user_identity}`，另加 `git_state{cwd, root, branch, default_branch, visibility{...}}`。**`live_cwd`/`home_dir`/`trusted_directories` 是原文路径（可含中文）**，`o=DT` 只做 Windows 盘符规整，不是脱敏（`grep -o 'live_cwd:o(oe())'`）。
- **会话上下文的 `gitStatus` 段**同样把宿主仓库元数据写进 system prompt：`Current branch:`、`Main branch:`、`Git user:`（`git config user.name`）、`Status:`（`git status --short --branch` 原文，含文件名）、`Recent commits:`（`git log --oneline -n 5` 的标题）；同一上下文段另写入账号邮箱（`userEmail`）。这些内容随每次 `/v1/messages` 上行。设置 `ANTHROPIC_UNIX_SOCKET` 时不带 `userEmail`；整个 `gitStatus` 段由 `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS`（或 settings 里的 `includeGitInstructions:false`）门控，置位后不生成该段。`/commit-push-pr` 类命令的上下文另含 `SAFEUSER` 与 `whoami` 两行，分别取 `process.env.SAFEUSER` 与 `process.env.USER`；三者均为原文，中文用户名与邮箱随会话上行（`grep -o 'This is the git status at the start of the conversation'`、`grep -o 'function iTt(){let e=a.CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS'`）。
- **`/v1/messages` 请求体的 `metadata.user_id`**：每次消息请求都带，是一个 JSON 字符串。它由 `Tx()` 构造并挂在请求的 `metadata` 上（`grep -o 'metadata:Tx('` 共 4 个调用点，其中一个是主对话请求，另两个是 `quota_check` 与 `verify_api_key` 探针）。字符串内固定含 `device_id`（即 `.claude.json` 的 `userID`）、`account_uuid` 与 `session_id`，另可带 `parent_session_id`、`ti`、`tk`；`CLAUDE_CODE_EXTRA_METADATA` 提供的键会并入，但 `ti/os/sb/he/uf/ap/tk` 这几个保留键被过滤（`grep -o 'new Set(\["ti","os","sb","he","uf","ap","tk"\])'`）。整个 JSON 有 **512 字节上限**（常量 `Ope=512`），超限时先丢弃自定义部分，仍超则回落到基础键集。这条属于模型请求体而非遥测通道，因此任何遥测开关都管不到它。
- **提示词注入的时区**：`mcp_datetime_parse` 的 `- Local timezone: +08:00` 与 routines skill 的 IANA 名。
- **`user_identity`**：`$USER`/`GITHUB_ACTOR`/git email，被 `/[^a-zA-Z0-9._-]/g` 清洗后进服务端上下文。
- 遥测里路径一律降级为 bool/计数/扩展名（`cwd_is_home`、`fileExtension`、`refused_paths` 计数），**未发现任何 1P 事件携带 cwd/文件路径原文**。
- 遥测侧的路径信息还以若干具名字段出现。`tengu_init` 带 `remote_host_class`（远端地址 host 的分类）、`is_git`、`has_remote`；`tengu_context_size` 带 `has_user_email`（布尔）与 `project_file_count_rounded`（计数）；目录搜索事件带 `subdir`，取值为所搜索目录的种类字面量（调用点观测到 `agents`、`commands`、`output-styles`）；路径相关事件带 `isFilePathAbsolute`。自动模式服务端上下文另有字节预算：变量部分被裁剪到 256000 字节，整体上限为 1040000 字节；整段超上限时该次上下文被放弃并上报 `tengu_auto_mode_context_withheld`，仅静态部分即超 256000 字节时上报 `tengu_auto_mode_context_static_over_budget`，两者只带字节数与计数（`grep -o 'var QPe=256000,Qbo=1040000'`）。

---

## 5. 第三方 provider 的暴露面（重点）

### 5.1 显式第三方：通道整体关闭（注意：不是「不上报 provider 字段」）

`CLAUDE_CODE_USE_BEDROCK/VERTEX/FOUNDRY/ANTHROPIC_AWS/ANTHROPIC_GOOGLE_CLOUD/MANTLE` 或网关凭据 → `Ie()` 非 `firstParty` → `e()` 为真 → `Lg()` 为真 → `IB()` 为假 → 通道 A/B/C/E/G 全关。

**这里有个容易读反的地方，需要说清**：事件元数据里的 `provider: BI()`（`BI(){return c(Ie())}`，`c` 在本 build 是恒等函数，所以值就是 `Ie()` 原值）是**照常拼进每个 API 事件**的——字段本身并不缺席。真正的机制是：

- 常规终端：provider 非第一方 ⇒ 承载该字段的事件**发不出去**（`Lg()` 为真）；能发出去时值又只能是 `firstParty`。⇒ **服务端拿不到有信息量的值**，但这不等于「字段不上传」。
- **host 托管会话是例外**：`e(){if(a.CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST)return!1;return !Gn()}`——这一分支被绕过，`IB()` 保持为真，于是值**可以**是 `bedrock`/`vertex` 等真值。Desktop 的 local-agent 会话会设 `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1`（见 `desktop.md` §6.2）。

⇒ 一句话：**字段恒在事件里（当事件能发时）；值在常规终端里无信息量，在 host 托管下才有。**

### 5.2 隐式第三方（BYOK / 自建中转）：**明文上传 host**

这是最实质的一条。GrowthBook 属性里有一个专门字段：

```js
function rzo(){let e=a.ANTHROPIC_BASE_URL;if(!e)return;
  try{let n=new URL(e).host;if(n==="api.anthropic.com")return;return n}catch{return}}
```
`[Observed]`（导出名 `getApiBaseUrlHost`，`grep -o 'function rzo(){let e=a.ANTHROPIC_BASE_URL'`）

它被塞进 `Rpn()`：`...h&&{apiBaseUrlHost:h}`，而 `Rpn()` 就是这个客户端的 `getUserAttributes`：

```js
let s=this.deps.getUserAttributes(), g="sdk-zAZezfDKGoZuXXKe", h="https://api.anthropic.com/", ...
let v=new vi({apiHost:h, clientKey:g, attributes:s, remoteEval:!0,
  cacheKeyAttributes:["id","organizationUUID","slackTagConnected","atisPin"], ...});
```

remoteEval 模式下 SDK 的每个请求体是固定的 `{attributes:e.getAttributes(), forcedVariations, forcedFeatures, url}`，POST 到 `https://api.anthropic.com/api/eval/sdk-zAZezfDKGoZuXXKe`（`tengu_gb_eval_authed_enable` 为真时走 `/api/eval-authed/`，还会带 OAuth 头）。

**因此**：只设 `ANTHROPIC_BASE_URL=https://<自建中转域名>` 的用户（`Ie()` 仍判 `firstParty`，`IB()` 为真，GrowthBook 照跑），会把 `apiBaseUrlHost = <自建中转域名>` **明文**发给 api.anthropic.com，随行还有 `deviceId`(=userID)、`sessionId`、`accountUUID`、`organizationUUID`、`subscriptionType`、`entrypoint`、`platform`、`atisPin`。

### 5.3 中转网关的响应头也会回传

`tengu_api_error` 等事件携带从**响应头**解析出的中间层特征：`intermediary_headers[]`（观察名单含 `via, x-cache, x-served-by, x-varnish, cf-ray, x-forwarded-for, x-squid-error, proxy-authenticate, server-timing, x-cloud-trace-context` 等；前缀族含 `x-envoy-, x-apigee-, x-akamai-, x-zscaler-, x-amzn-, x-ms-, x-goog-` 等）、`server`、`apigee_fault_source/code`、`gateway`/`gateway_version`。在 BYOK 场景下通道 A 未关，这些随事件上行。

### 5.4 关断

开关本身见 §6 与全景第 9 条（不重复）。这里只留一条不属于开关矩阵的：**桌面端在 3p 分支拉起 CLI 时会强制注入 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`**，所以**桌面内拉起的 CLI 不漏**，**独立终端 + BYOK 才漏**。

---

## 6. 开关矩阵

### 环境变量

| 变量 | 影响 | 语义 |
|---|---|---|
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | A ✗ B ✗ C ✗ E ✗ G ✗ | 最强开关，任何非空值即生效 |
| `DISABLE_TELEMETRY` / `DO_NOT_TRACK` | 同上全部 ✗ | `DO_NOT_TRACK` 需 `1/true/yes/on` |
| `CLAUDE_CODE_ENABLE_TELEMETRY` | **只开 D** | `1/true/yes/on` |
| `DISABLE_ERROR_REPORTING` | C ✗ | |
| `DISABLE_GROWTHBOOK` | G ✗（连带 B/C 的 GB 门控） | |
| `CLAUDE_CODE_USE_BEDROCK/VERTEX/FOUNDRY/ANTHROPIC_AWS/ANTHROPIC_GOOGLE_CLOUD/MANTLE` | A ✗ B ✗ C ✗ E ✗ | 经 `Ie()` |
| `ANTHROPIC_BASE_URL`（非 api.anthropic.com） | **只 C ✗**（经 `Hs()`）；A/B/E/G 照开 | 见 §1 更正 |
| `_CLAUDE_CODE_ASSUME_FIRST_PARTY_BASE_URL` | 反向解除上面限制 | |
| `CLAUDE_CODE_CUSTOM_OAUTH_URL` | A ✗ B ✗ C ✗ | 值须在批准列表内 |
| `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST` | 解除「非第一方即禁用」分支 | 宿主托管凭据时 |
| `CLAUDE_CODE_ENVIRONMENT_KIND=byoc` | B ✗（除非 `CLAUDE_CODE_BYOC_ENABLE_DATADOG`） | |
| `OTEL_*` 系列 | 只影响 D（端点/协议/头/内容粒度） | 见下 |

`OTEL_LOG_*` 内容粒度：`OTEL_LOG_USER_PROMPTS`（提示词原文 vs `<REDACTED>`）、`OTEL_LOG_ASSISTANT_RESPONSES`（未设时回落到前者）、`OTEL_LOG_TOOL_CONTENT`、`OTEL_LOG_TOOL_DETAILS`、`OTEL_LOG_MANAGED_SETTINGS`、`OTEL_LOG_RAW_API_BODIES`。**项目/本地 settings 只能把遥测关小，不能开大**（`mod-0054.js`：内容变量只能设假值、exporter 变量只能设 `"none"`，且变量名须大写）；企业托管 settings 压倒低信任作用域。

具体清单：项目与本地 settings 能改动的遥测变量为 `OTEL_LOG_RAW_API_BODIES`、`OTEL_LOG_USER_PROMPTS`、`OTEL_LOG_ASSISTANT_RESPONSES`、`OTEL_LOG_TOOL_CONTENT`、`OTEL_LOG_TOOL_DETAILS`、`OTEL_LOG_MANAGED_SETTINGS`、`OTEL_LOGS_EXPORTER`、`ENABLE_BETA_TRACING_DETAILED`、`BETA_TRACING_ENDPOINT`、`ANT_OTEL_LOGS_EXPORTER`。其中三个内容变量（`OTEL_LOG_USER_PROMPTS`、`OTEL_LOG_TOOL_CONTENT`、`OTEL_LOG_TOOL_DETAILS`）只能设假值，三个 exporter 变量（`OTEL_LOGS_EXPORTER`、`OTEL_METRICS_EXPORTER`、`OTEL_TRACES_EXPORTER`）只能设为 `none`，且变量名须大写、启动环境未定义同名变量。托管 settings 压倒低信任作用域时，`dropDominatedOtelKey` 处理的变量族为 `OTEL_EXPORTER_OTLP_*`（各 signal 的 `_ENDPOINT`、`_HEADERS`、`_CLIENT_KEY`、`_CLIENT_CERTIFICATE`）、`OTEL_LOGS_EXPORTER`、`OTEL_TRACES_EXPORTER`、`CLAUDE_CODE_ENABLE_TELEMETRY`、`BETA_TRACING_ENDPOINT`；`otelHeadersHelper` 单独触发一次对 `OTEL_EXPORTER_OTLP_<SIGNAL>_ENDPOINT` 与 `OTEL_EXPORTER_OTLP_ENDPOINT` 的扣留。托管合规限制表（`mod-0154.js`）以 `deniedUnder:["hipaa","zdr"]`、`onCacheMiss:"deny"` 为通用形态，表内含 `allow_error_reporting`（HIPAA-R19）、`allow_send_file`（HIPAA-R37）、`allow_heap_dump`（HIPAA-R38）等键（`grep -o 'Ks=\["OTEL_LOG_RAW_API_BODIES","OTEL_LOG_USER_PROMPTS"'`、`grep -o 'allow_send_file:{deniedUnder:'`）。

### GrowthBook 远端开关（默认值写死在代码里）

| Gate | 默认 | 作用 |
|---|---|---|
| `tengu_frond_boric` | `{}` | `.firstParty===true` 关 A；`.datadog===true` 关 B |
| `tengu_log_datadog_events` | `false` | B 总开关 |
| `tengu_orford_ness` | `false` | C 总开关 |
| `tengu_1p_event_batch_config` | `{}` | 可覆盖 A 的 `path/baseUrl/skipAuth/maxAttempts` 等 |
| `tengu_event_sampling_config` | `{}` | 按事件名采样 |
| `tengu_cozy_dusk` | `300000` | E 上报间隔 |
| `tengu_gb_eval_authed_enable` | `false` | G 改走 `/api/eval-authed/` |
| `tengu_gb_refresh_interval_minutes` | `360` | G 刷新间隔 |

---

## 7. 负面清单（已证伪 / 易误读）

1. **脱敏函数在本 build 里是恒等函数**：`mod-0001.js` `function r(n){return n}`，`y/c/Sn/hr/D2/Vc/…` 全部 `= r`。字段名里的 "redacted/sanitized" **不代表真的脱敏**。
2. 哈希字段可反查：`pn()` = `sha256(x).hex.slice(0,12)`（**无盐**）；`pye()` = `sha256(x + "claude-plugin-telemetry-v1").hex.slice(0,16)`（**公开常量盐**）。同名可跨用户关联。
3. `git_remote_url`、`code`、`mcp_server_name`、`mcp_tool_name` **没有上行**——解构后被丢弃，且 `pmt()` 会删掉一切 `_PROTO_*` 前缀键。
4. `email` 是**死字段**（`email(){}` / `emailAsync(){}` 空实现），不是「登录后带上」（`mod-0131.js`，`grep -o 'email(){return}async emailAsync(){return}'`；该串在全部 2153 个模块中仅此一处）。但 email 会经 D 的资源属性 `user.email` 上行；网关部署下该值由 `gatewayAuth` 的 OIDC JWT 提供，并同时带出 `user.id`（JWT `sub`）、`user.groups` 与 `identity.source`——同属通道 D，不是另一条通道。
5. `slack.*`、`client_reported_auth.*`、`auth.account_id`、`event_metadata_vars`、`anonymous_id` 均为死字段（无生产者）。
6. `terminal.type` 的白名单**不作用于通道 A**；通道 A 的 `env.terminal` 是检测器原始输出（自定义 `TERM_PROGRAM` 会原样上行）。
7. **自定义 `ANTHROPIC_BASE_URL` 不关通道 A**（更正旧 `05` §2 与 §10.1）。
8. **`provider: BI()` 不是「不上传」**：它随每个 API 事件走，值 = `Ie()` 原值；常规终端里恒为 `firstParty`（非第一方时事件发不出去），但 **host 托管会话例外，可取真值**（§5.1）。「取值无信息量」与「字段不存在」是两回事，不应混同。
9. 未找到：`is_tmux`、遥测中的 `cwd`/`project_path`/`branch_name`/`repo_slug`、Sentry 客户端、Statsig SDK、Segment/Amplitude/Mixpanel 上报调用、把遥测写进本地 socket 的代码。
10. 主机名只经两个 body 上行（`/api/auth/trusted_devices`、cowork 设备注册的 `display_name`，源串形如 `Claude Code on ${…} · macOS`），**没有任何请求头带主机名**。
11. 另有几处读取硬件或本机特征，但只用于本地判断，不进入任何上行载荷：Windows 目录同步用 NTFS 的卷序列号（`volumeSerialNumber`）与文件索引号（`indexNumber`）校验文件身份；GCP 凭据库经 `/sys/class/dmi/id/bios_vendor`、`bios_date` 与网卡 MAC 前缀 `^42:01` 判定是否运行在 GCE 上，从而选择凭据来源；路径安全校验用 `os.networkInterfaces()` 判断主机名或 URL 是否指向本机；seatbelt 沙箱模板里出现的 `hw.activecpu` 等 sysctl 名属白名单文本，不是采集。

---

## 8. 未复验 / 边界

1. `tengu_api_custom_529_overloaded_error` 的事件名含 "custom"，但元数据为空 `{}`，**未确认** "custom" 指自定义端点还是自定义错误类型。
2. `tengu_bedrock_setup_*` / `tengu_vertex_probe_*` 等向导事件：推测在进程尚未切到该 provider 时发出（此时 `Ie()` 仍是 `firstParty`，事件可发），**未确认**向导是否先写了 `process.env`。若成立，则「这人在配 Bedrock」会经事件名泄露。`[Inference]`
3. 通道 E 的 `pending_at_shutdown` 路径（`Ot()`/`armShutdownReport`）语义未展开。
4. `tengu_swift_whistle`（OAuth 无 profile scope 时仍附认证头发事件）语义仅 `[Inference]`。
5. 网关判定 `wo()`/`y2t()`/`_2t()` 的确切输入未逐字展开——三者读的都是宿主 credentialSlots（网关凭据/宿主策略），**均不读 `ANTHROPIC_BASE_URL`**；若 BYOK 的 token 恰好带网关 JWT 特征，`Ie()` 会翻成 `gateway` 并关闭全部通道。
6. **`grep` 的 4MB 截断**：本机 `grep` 只扫文件前 4MB，而 `mod-0365.js` 等模块远超此限——尾段匹配会静默丢失。复验本篇任何锚点时，都要限定到具体模块文件，不要对 `cli/modules/*` 盲跑并据「0 命中」下结论。
