# Desktop ↔ CLI 联动：两端能否被关联成同一台机器 / 同一个人

**本篇回答的问题**：在同一台机器上同时使用 Claude Desktop 与 Claude Code CLI 时，服务端是否存在可用数据将两端关联；哪些机制成立、哪些常被误认为成立；以及需要切断时应采取哪些措施。

**素材**：A 端 = Claude Desktop 2.9939.2（`desktop/main-process-readable/*.js`，别名 `DZ`/`CB`/`PRE`/`9hg`）；B 端 = Claude Code CLI 2.1.283（`cli/modules/mod-NNNN.js`，单行大文件，用 grep 串定位）。两端各自的通道与标识符见 `desktop.md` 与 `cli.md`。

**标注约定**：`[Observed]` = 有原文/行号证据；`[Inference]` = 由代码推出，并写明前提；`[不可静态判定]` = 依赖服务端下发的门控状态或运行时的网络配置，静态读代码无法定论。

---

## 0. 结论速览

| 场景 | 能否关联 | 依据 |
|---|---|---|
| Desktop 已登录，且在 Desktop 内拉起 Code/Cowork 会话 | 能够关联；不受遥测开关限制 | 同一条事件同时带 `install_id`、`account_uuid` 与 `cli_session_id`；同一 OAuth token 被注入子进程；推理请求体的 `metadata.user_id` 另带 `device_id` 与 `account_uuid` |
| Desktop BYOK / 未登录，CLI 在独立终端运行 | 唯一的机械 join 是出口 IP 加时间窗 | 取决于 Clash 等分流工具是否把两端置于同一出站节点 |
| Desktop 部署形态为 hybrid、3p + provider=anthropic + interactive，或管理员把托管配置的 `telemetry.orgUuid` 填成真实 org UUID | 账号级 / 组织级关联 | 该形态下 `auth.organization_uuid` 是真实 org UUID，可与 CLI 的 org 对齐 |
| Desktop 已登录，且两端同时存在同名插件 / 技能 / 市场 | 条件式；需服务端计算 | CLI 明文上传名称，Desktop 上传无盐 31 乘子滚动哈希，服务端可按同一算法重算比对（§3.6） |

以下两个常见前提在本仓库中均被证伪：

1. 「BYOK / 从未登录意味着 Desktop 未连接过 Anthropic」不成立。一个从未登录的 BYOK Desktop，在默认配置下仍会发出三条携带 `install_id` 的请求（§1），其开关默认值均为发送。
2. 「使用海外时区并清理中文特征即可隔离两端」对 CLI 层没有作用。CLI 的上行载荷中不含 timezone / locale 字段，而持续暴露中国环境的是 Desktop 侧（Sentry 的 `contexts.culture{locale,timezone}`）。

关于「Desktop 上传的第三方 provider 明文（`inference_host`）能否与 CLI 的官方账号关联」：服务端可以看到该安装使用了某个第三方 provider（`inference_host` + `install_id` + `os_build`/`cpu_model`），但代码中不存在任何字段把 `install_id` 与 CLI 侧的 `account_uuid` 连接起来。可用的桥只有四条：IP 与时间，在 Desktop 内启动 CLI，`sha256(ant-did) → userID` 种子（后者只写入 Desktop 的私有会话目录，独立终端读取不到），以及名称哈希的服务端重算（§3.6，需要 Desktop 已登录且两端存在同名物件）。

---

## 1. 未登录 BYOK 的 Desktop 仍会发出的请求

| # | 请求 | 携带标识符 | 门控（默认值 = 发送） |
|---|---|---|---|
| 1 | `POST https://claude.ai/api/event_logging/v2/batch` | `install_id`(=ant-did)、`app_session_id`、`os_version/os_release/os_build/cpu_model/total_memory/device_class`、`inference_provider` / `inference_host`（明文）/ `inference_base_url`、`user_id="anonymous"` | `!telemetry.disableNonessential`（默认 false）；3p 下凭据门 `$in()` 恒返回 `{kind:"none"}`，即以无凭据方式发送 |
| 2 | `GET https://api.anthropic.com/api/desktop/<platform>/<arch>/<feed>/update?device_id=<ant-did>&version=…&os_version=…` | `device_id` = ant-did，明文置于 URL | `disableAutoUpdates`（默认 false），无 3p 跳过分支 |
| 3 | Sentry ingest `*.ingest.us.sentry.io`（DSN 与 1p 相同、硬编码） | `user.id` = ant-did、`contexts.culture{locale, timezone}`、`os.kernel_version`、breadcrumbs（控制台文本与路径） | `!telemetry.disableEssential && !CI`；3p 下闸门为 `thirdParty → "open"`，立即发送，没有 1p 的 hold 阶段 |
| 4 | `GET https://downloads.claude.ai/model-catalog/v1/catalog.json`（5–15 分钟轮询） | 无标识符（`credentials:"omit"`） | 3p 专属，默认启用 |

表中的 `inference_base_url` 取所配推理端点的 origin 加 path，主机名与路径原样上行；它不在免脱敏白名单内，而是经 `hr()` 逐条替换其中的密钥样式子串（`sk-ant-…`、JWT、云厂商凭据等）。同一事件里的 `inference_host` 与 `inference_host_kind` 属白名单，原样通过。

BYOK 下主窗口 URL 为 `app://localhost`（本地 SPA），不加载 claude.ai，也不写入 claude.ai cookie；`anthropic-client-*` 头注入器以 `new URL(PO()).host` 为基准，host 为 localhost 时不注入。因此「网页侧把桌面实例与账号串起来」这条路径在该场景中不存在。

不过本地 SPA 仍有经 `app://` 协议处理器向 Anthropic 出站的通道。处理器把以 `/api/`、`/v1/`、`/v2/` 等前缀开头的路径转发到 `claude.ai`（打包版恒为该主机），出口清单中 `anthropic-telemetry`（`/api/event_logging/`）与 `datadog-rum`（`/api/v2/rum`）正落在该前缀内，分别受 `disableNonessentialTelemetry` 与 `disableEssentialTelemetry` 控制。本仓库不含本地 SPA 产物，无法核实它是否实际发出这两个请求，故该通道的成立以 SPA 发出对应路径为前提。`[Inference]`（依赖「本地 SPA 发出上述路径」这一未复验前提）

另有三处端点经清点在本场景下不产生带标识符的请求。`https://claude.ai/cdn-cgi/trace`（`credentials:"omit"`，无自定义头）由设备桥的服务器时钟采样发出，而设备桥仅在解析出活跃 org/account 后启用，未登录时该采样不被触发。`https://mcp-proxy.anthropic.com/v1/mcp/{server_id}` 只出现在内嵌 CLI 的托管 MCP 常量表里，需要 claude.ai 账号。模型目录的签名旁文件（同 URL 追加 `.raw-sig.json`）不是独立通道：它随 `catalog.json` 在同一次抓取中取回，同样不带标识符。

服务端由此可获得：一台安装的长期轨迹（`install_id`）；该安装正在使用中国区域第三方推理端点的直接证据（`inference_host` 明文加 `deployment_mode:"3p"`）；中国时区与中文环境（`culture`，绑定在 ant-did 上）；以及机型级指纹（`os_build`/`cpu_model`/`total_memory`/`device_class`，非唯一但足以跨重装重识别）。全程无需任何登录。

---

## 2. 唯一的机械 join：出口 IP 加时间窗

- A 端每个请求走 Electron 默认 session，由 Chromium 系统代理解析；A 端没有用户级代理设置，唯一的代理落点是 workspace 的 `egressProxyUrl`/`PacUrl`。
- B 端走 undici/axios 全局 dispatcher，依赖 shell 中的 `HTTPS_PROXY` 指向本地 Clash 端口。
- 同 IP 的条件是：Clash 处于系统代理或 TUN 模式，且规则把 A 的 `claude.ai`、`api.anthropic.com`、`*.ingest.us.sentry.io`、`downloads.claude.ai` 与 B 的 `api.anthropic.com`、`platform.claude.com` 指向同一出站节点。
- 以下任一情况成立即断开：只开本地 HTTP 端口而未设系统代理（此时 B 走 `HTTPS_PROXY`、A 走 DIRECT）；按域名分流；按进程分流（`Claude` 与 `node`/`bun` 分属不同规则）；workspace 配置了 `egressProxyUrl` 使 A 走另一代理；将 Anthropic 域名设为 REJECT。

两端还共享同一份 CDN 资源：`https://downloads.claude.ai/model-catalog/v1/catalog.json` 被双方逐字拉取，A 每 5–15 分钟轮询且凭据设为 omit，B 做条件请求只带 `If-None-Match`，两端都不带账号或安装标识。该 URL 上的两条拉取流因此只能靠源 IP 与时间接近来归并，属于同 IP 的旁证而非身份键。

两端的时间尺度不对称：A 的事件批量满 50 条即冲，否则按基准 60 s 定时并乘 0.5–1.5 倍抖动（30–90 s），可配区间为 60–600 s，退出清理阶段再冲一次，更新检查约每 1 h 一次；B 的批量上限 200 条、单次超时 10 s，推理请求实时。两端时间戳均为 UTC，没有任何字段把两条时间线绑定，时间窗只能作为统计性启发。

需要注意：Clash 使两端都能到达 Anthropic，也因此可能使两端共享同一出口 IP，而共享出口 IP 恰是最强的关联面。若要求匿名，分流规则必须显式设计。

---

## 3. 关联路径逐条

### 3.1 从 Desktop 内启动 Code/Cowork 会话 —— 最强的关联路径，不受遥测门控限制

`desktop_ccd_*` 事件携带 `cli_session_id`、`cli_version`、`model` 与 token 计数，且同一条事件中同时含有 `install_id` 与 `account_uuid`；同一过程中 Desktop 把同一个 OAuth token 注入子进程（`CLAUDE_CODE_OAUTH_TOKEN`，运行期还会热推更新）。

因此一条记录即可完成机器、账号与 CLI 会话三者的关联。该路径不经过 GrowthBook 门控，关闭 CLI 遥测亦无法阻止，因为记录由 Desktop 自身发出。

另有一条独立的绑定位于推理路径上：CLI 每次 `/v1/messages` 的请求体都携带 `metadata.user_id`，其中 `device_id` 取该进程实际使用的 `userID`。在 Desktop 拉起的会话中，若 `sha256(ant-did)` 的播种生效，`device_id` 即为该值，与同一请求内的 `account_uuid` 构成安装与账号的直接绑定。该绑定不经过任何遥测通道，同样无法用遥测开关阻止（见 `cli.md` §4.4）。

### 3.2 `sha256(ant-did)` → CLI `userID` 种子 —— 设计上存在的桥，受多重前提限制

- 写入路径为会话私有目录：`<userData>/local-agent-mode-sessions/<accountId>/<orgId>[/agent]/<sessionId>/.claude/.claude.json`，不是全局 `~/.claude.json`（Desktop 从不把 `userID` 写入后者）。
- 四个前提缺一不可：① GrowthBook 门 `2220415149` 为开（bundle 内无静态默认，由服务端下发）；② 会话首轮；③ 账号已解析（未登录时直接抛错并被吞掉）；④ `ant-did` 可读。
- 独立终端 CLI 读取 `join(CLAUDE_CONFIG_DIR || homedir(), ".claude<suffix>.json")`，与上述目录无交集，因此读取不到种子，会自行生成独立的随机 64-hex 值。

因此该桥在独立终端场景下不成立；只有当 CLI 由 Desktop 拉起（此时 `CLAUDE_CONFIG_DIR` 被指向会话目录）时才生效。

### 3.3 Desktop 内登录官方账号

`auth.account_uuid` / `organization_uuid` 与 `install_id` 出现在同一事件中，构成账号级关联。本场景（从不登录）不成立。

### 3.4 真实 org 只在三种部署形态下出现

- hybrid（bootstrap URL 携带真实 orgUuid）；
- 3p + provider=anthropic + interactive（经 `/api/oauth/profile` 取得真实 org）；
- 管理员把托管配置的 `telemetry.orgUuid`（扁平键 `deploymentOrganizationUuid`）填成真实 org UUID。

第三种不限于诊断包：该值经 `telemetryOrgUuid()` 进入每一条常规事件的 `organization_id` 与 `auth.organization_uuid`。字面字段名 `deployment_organization_uuid` 只出现在诊断包事件、诊断包 manifest 与 renderer argv 三处，但同一配置值本身随常规事件上行，其中 argv 带的是解析后的 `telemetryOrgUuid()`，manifest 与诊断包事件带的是配置原文。判定完全取决于取值：管理员写成真实 Anthropic org UUID 时，join 在常规事件上即成立；写成自生成 UUID 或占位值时，导出诊断包同样不成立。

其余情况下 `organization_uuid` 不是真实 org，而是：

- 由 provider 配置确定性派生的 UUIDv8（`sha1(盐 ‖ "<provider>:<identity>")`，identity 视 provider 取 host+path+clientId、projectId、resource 或 ssoAccountId）；
- 或占位常量（provider 为 anthropic/mantle 且非 interactive）。

两种取值的共同点是没有个体区分度，且与官方账号的 UUID 无映射关系，因此不构成 join key。但派生 UUID 是「同一第三方 provider 配置」的稳定分组标签——同一 gateway 加同一 clientId 的所有用户共享该值，服务端可用它给 A 归类，仍无法连到 B。

上述形态之外，进程内的时序会额外制造一个真实 org 的瞬时来源。组织缓存 `wk` 是模块级内存变量，初值 null，只有写入没有清空：cookie 监听、`brn()` 与 `Ek()` 的第二步都会写它，而没有任何模式切换会重置它。事件的 org 取值为 `telemetryOrgUuid() ?? await Ek()`；3p 非交互且未配置组织时前者为 null，`Ek()` 的第一步会在重新解析之前直接返回缓存值。因此同一进程若先以 1p 或 hybrid 形态把真实 org 写进 `wk`，再切换到 3p，之后发出的事件仍会带上该真实 org，直到进程结束；重启后 `wk` 回到 null，残留消失。该路径与 §4 表「曾登录过官方账号」一行并不冲突：那一行描述的是全新 3p 进程（cookie 无法写入 `wk`、`Ek()` 第二步取回占位或派生值），此处描述的是同一进程内先解析出真实 org、再切换部署形态的时序。`[Inference]`（依赖两个 `[Observed]` 前提：`wk` 无清空点，且 `Ek()` 第一步先于 `orgUuidOverride()` 返回）

### 3.5 会把主机名绑定到账号的两条窄口

- CLI 的 `POST /api/auth/trusted_devices` 请求体含 `display_name: "Claude Code on <hostname> · macOS"`，受远端 flag `tengu_sessions_elevated_auth_enforcement`（默认 false）约束。
- Cowork 远程设备注册的 `display_name` 为同一字符串。

这是两端唯一的主机名上行路径（没有任何请求头携带主机名），因此环境清理时需把主机名一并纳入。

### 3.6 名称哈希：服务端可重算的一路

Desktop 把插件与技能名称统一送入一个**无盐滚动哈希**（31 乘子、种子 0、无符号 32 位转十进制串），只在账号上下文存在时写入事件。**它不是 djb2**——djb2 用 33 乘子与 5381 种子，照 djb2 重算这四个字段会得到完全不同的值（详见本节末）。

| 字段 | 取值 | 定位 |
|---|---|---|
| `plugin_uid` | `H("<orgId>:<pluginId>")` | `index.chunk-CwacCE28.js:1676`「`plugin_uid: t.IY(\`${r}:${n.id}\`),`」 |
| `plugin_id_hash` | `H(orgId + pluginId)` | `index.chunk-Cb2x-E4A.js:4730`「`plugin_id_hash: s && o.pluginId ? t.IY(s + o.pluginId) : void 0,`」 |
| `cli_hash` | `H(orgId + cliName)` | `index.chunk-Cb2x-E4A.js:4731`「`cli_hash: s && o.cliName ? t.IY(s + o.cliName) : void 0,`」 |
| `skill_name_hash` | `H(orgUuid + skillName)` | `index.chunk-DJ7PvxxQ.js:235`「`skill_name_hash: t.IY(t.wG(a) + n),`」 |

`H` 的本体是 `index.chunk-DzZc-q0x.js:5012` 的 `Roe`：循环体 `t = (t << 5) - t + e.charCodeAt(n)`，即 31 乘子；`<< 5` 减自身一步到位，容易误读成 djb2。它经同文件 `:5107` 的 `cr = Roe` 与 `:276543` 的 `exports.IY` 导出为 `IY`，而三个调用点的 `t` 都是 `require("./index.chunk-DzZc-q0x.js")`，链条据此闭合。

本树另有一个**真正的 djb2**：`index.chunk-CtwayTMM.js:2441` 的 `hi`，`t = ((t << 5) + t + e.charCodeAt(n)) | 0`、种子 5381，写法是教科书的 33 乘子。但它返回 `((t % 360) + 360) % 360`，是 0–359 的**色相角**，只用于会话配色，与遥测字段无关。两者不可混用。

名称本体不在其中：非官方市场的插件 id 被替换为字面量 `<plugin>@other`（`index.chunk-DzZc-q0x.js:5095`「`return ir(e) ? e : "<plugin>@other";`」），技能名被钳制在 `["my-writing-style","setup-writing-style"]` 与 `"custom"` 之内（`index.chunk-DJ7PvxxQ.js:229`「`w = ["my-writing-style", "setup-writing-style"];`」）。

CLI 对同一批名称不做钳制：`plugin_name`、`marketplace_name`、`skill_name` 经 OTLP 到一方事件的桥接后按原文上行，`_PROTO_` 前缀被去掉，转换函数是恒等（`cli/modules/mod-0131.js`，`grep -o 'skill_name:s(F),plugin_name:s(L),marketplace_name:s(B)'`；该串在全部 2153 个模块中仅此一处）。

两侧合起来是一条需要服务端计算的 join：服务端拿到 CLI 的明文名称后，可按同一算法（§3.6 的 `Roe`）、同一 org 前缀重算，再与 Desktop 的哈希字段比对。前提有三项：同名物件在两端同时存在；服务端能取到 Desktop 侧参与拼接的 org id 并与账号建立映射；需枚举分隔符与大小写变体。该路径不产生两端等值的字节串，与 §4 的「哈希同构」一行并不冲突——那一行说的是没有任何一对算法对同一输入给出相同输出。`[Inference]` 这四个字段要求 `getAccountContext()?.orgId` 非空，所属事件族属 lam/Cowork 域，因此在本篇中心的 BYOK 未登录场景中不发射。

---

## 4. 已证伪的关联机制

以下机制经逐项查证均不成立，列出以避免过度推断。

| 猜测的关联机制 | 判定 | 依据 |
|---|---|---|
| 共享 session / message / request / run id | 不存在 | A 确实扫描并解析 B 的 `~/.claude/projects/**/*.jsonl`（文件名即 CLI 会话 UUID，并读取 size/mtime/entrypoint/cwd/gitBranch/标题），但只用于本地 UI，不上行（`desktop-event-catalog.md` 里没有任何事件携带该 id）；唯一携带该 id 的 `desktop_ccd_cli_session_imported` 前置账号门，BYOK 未登录时永不产生。`desktop_ccd_session_list_loaded` 的 `entry_point` 只接受 `renderer_boot` 与 `reinit`，该白名单约束的是 Desktop 自身装载会话列表的入口，与终端会话的取舍无关。筛选导入候选的是另一处判断：转录里首个 `entrypoint` 落在自托管集合内即整份丢弃，集合含 Desktop 自身的 `claude-desktop`/`claude-desktop-3p`，以及 `local-agent`、`sdk-cli`、`sdk-ts`、`sdk-py`、`mcp`、`bench`、`claude-code-github-action`、`remote` 族、`claude_in_slack`、`ssh-remote`。终端 CLI 的 entrypoint 不在此列，独立终端会话因此正是该扫描的候选对象；使这些记录不上行的是该行已述的账号门与扫描本身没有对应上行事件，而不是这两个过滤器 |
| message id | 不存在 | B 侧回传 `msg_*` 的路径是死代码（`Met()` 恒 false）；A 在 BYOK 下不调用 messages API。Desktop 另有一条上行 `msg_*` 的通道：删除 Cowork 会话时，它从该会话自身的转录里抽出 assistant 消息 id（`msg_01…`，单份转录上限 10 万条），写入 `CoworkSessionDeletionEvent` 的 `inference_log_ids`，经 `desktop.md` §2.2 所述的那条独立 POST 发出；抽取对象限于 Desktop 自己持有的会话目录，独立终端的转录不在其中，因此不构成本场景的 join。合规态下该事件的 `session_id` 收敛为 `hipaa_redacted`，`inference_log_ids` 先经 `msg_01` 形状闸过滤 |
| 哈希同构 | 不存在（无等值字节串） | 逐算法比对：A 用 31 乘子滚动哈希（十进制、无盐；**不是 djb2**，见 §3.6 末段），B 用 `sha256(x).hex[:12]`；共享常量盐 `claude-plugin-telemetry-v1` 在 A 侧前置、B 侧后置，是陷阱而非桥；A 的 folder/host/repo 哈希带每安装随机盐。**该行仅指两端无等值字节串**；服务端用 CLI 明文重算 Desktop 哈希的一路见 §3.6。另需限定：A 侧名称类哈希（`cli_hash`/`skill_name_hash`/`plugin_uid`/`plugin_id_hash`）**不带任何盐**——事件脱敏器对它们只有一条 HIPAA 归零处理（`Lf(Bf)`，`Bf` 返回 `hipaa_redacted`），非合规态原样通过；其区分度只来自调用点自行拼在输入前的 org 前缀，因此这些哈希非密钥、可跨用户横向比对、可被字典反推。带 org 盐的重算是另一族具名键（`vpn_interfaces`/`connected_vpns`/`bridge_interfaces`/`tool_name`/`server_name`/`extension_name`/`mcp_server_keys` 等，盐的选取见 `desktop.md` §7.3），用的是**同一个函数** `Roe`，只是输入被拼上了 org 前缀——差别在字段族与输入，不在算法 |
| 账号 / 组织同值 | 不存在（本场景） | A 侧 `user_id="anonymous"`、`auth` 整块省略、org 为派生 v8 或占位；B 侧为真实 `account_uuid`/`organization_uuid` |
| 头级共享键 | 不存在 | UA、`Accept-Language`、`X-Stainless-*`、`anthropic-client-*`、`x-app` 全部属于单侧或同名不同值（§5） |
| 桌面侧 `cf_ray` | 本场景不上报 | 取自桥 WS upgrade 响应，上报点要求 `state:"authenticated"`（需有效 org 与 account） |
| 共享文件的内容级桥 | 内容不上行 | A 与 B 都会读写 `~/.claude.json`，但 A 的事件载荷是显式字面量，不含 `userID`/`machineID`/`oauthAccount`；A 新增的键（`chipLevel`/`remoteTrustGrant`）在 CLI 全模块 0 命中 |
| 「曾登录过官方账号」的残留 | 不成立 | `current-account` 是纯内存 store，导航即 reset，重启即空；3p 下 `PO()="app://localhost"`，读取不到 claude.ai cookie。读 cookie 的那一步其实根本不会执行：`Ek()` 在第二步就返回 `orgUuidOverride()` 的值，而 `identity()` 的兜底是恒非空的占位常量；`wk` 内存缓存也只接受域与当前 `PO()` host 匹配的写入，3p 的 host 为 localhost，claude.ai 域的变更进不来。3p 下 `hipaa_origin_organization_id` 同样恒不出现，因为合规判定在 `fu() && type==="3p"` 时直接返回 `unrestricted`。磁盘另有两条不上行的账号残留：`lastKnownAccountUuid` 是持久 KV，只用于身份变更检测，事件读取路径不读它；`hybridIdentity`（键含真实 accountUuid）存在 `claude_desktop_config.json`，切回 3p 的路径只删 `hybridPointer`、不清该键，且它不是 schema 已知键，不进配置快照 |
| CLI 侧 device-class / 内存 / CPU 型号 / 主机名 / 语言 | 0 命中 | 这些字段只存在于 Desktop 侧 |
| Desktop 拉起的子进程经 `transcript_mirror` 回传转录 | 本素材树中无该生产者 | 该帧只在子 CLI 以 `--session-mirror` 启动时产生；该开关在 CLI 帮助文本中标为 SDK 内部并 `.hideHelp()`，由宿主进程消费，CLI 的消息类型表亦将其标为不可见。SDK 仅在调用方提供 `sessionStore` 时才加该开关，而 `desktop/main-process-readable/` 下没有任何分片配置 `sessionStore`，因此本素材树内没有该帧的 Desktop 生产者。CLI 另有一处同名不同义的 `reportMetadata({transcript_mirror:"live"\|"deferred"})`，属 remote-bridge 自身的转录拉取（`grep -o 'new ls("--session-mirror"'`） |

尚存的唯一弱旁路是文件级时序：A 上报 `desktop_ccd_config_reparse{config_file_bytes, config_reparse_cause:"external"}`，B 上报 `tengu_config_stale_write{read_size, write_size, read_mtime, write_mtime}`。两者均无 id 与路径，需服务端按时间线对齐，属弱旁路而非机械键。

---

## 5. 两端指纹面逐项对照

| 项 | Desktop | CLI | 判定 |
|---|---|---|---|
| UA | `Claude/2.9939.2 … Electron/…` | `claude-cli/2.1.283 (external, cli)` / `claude-code/2.1.283` | 客户端判别器，非 join |
| `Accept-Language` | `zh-CN`（Electron 默认，应用从不设置） | 不发 | 单侧 |
| `anthropic-client-device-class` / `-total-memory-gb` / `-os-version` / `-os-platform` | 发送 | 0 命中 | 单侧 |
| `anthropic-client-platform` | `desktop_app`（仅 API 族） | 默认不发；仅 Desktop 拉起的会话经 `Lhn()` 注入为 `desktop_app` | 同名不同值 / 条件性 |
| `x-organization-uuid` | 仅在一方事件批量 POST 上写入，且要求凭据类型为 cookie；3p 下凭据恒为 `{kind:"none"}`，故不发 | 在多个辅助端点上恒带同一 org UUID（environment providers、self-hosted pools、teleport、sessions、session-ingress、oauth org repos 等） | 同名；本场景只有 B 侧出现 |
| `X-Stainless-OS/Arch/Runtime-Version` | 无 | 有 | 单侧 |
| `cf_ray` | 剥掉 `-XXX` 机房后缀后上行 | 保留后缀（归一化恒等） | 两端归一化不对称：CLI 的后缀暴露出口机房 |
| 代理字段 | 不上报（`egressProxyUrl` 标 `redact:hostname`，无遥测引用） | `https_proxy` 布尔值加 `intermediary_headers[]`（含 `x-zscaler-*`/`x-apigee-*`/`x-envoy-*` 前缀族） | 单侧 |
| `request_id` / `switch_id` / `backend_error_code` | A 用自己的 per-request / per-session id，过形状闸或 `skipKeys` 后原样明文 | 只有 `request_id`，同为各自的请求 id；`switch_id` 与 `backend_error_code` 无同名项 | 取值来源互不相干，跨端不期待同值；A 侧推理走第三方，这类字段在 3p 下基本不产生 |
| `device_id` | `install_id`(ant-did) / rowPk | `userID`（64-hex） | 值域不重叠 |
| 时区 / 语言 | Sentry `culture{locale,timezone}` | 载荷无 | 不能作 join |

可以交集的只有 `platform` 与 `arch`（同值域），以及 Linux 上的内核版本串。该粒度不足以单独构成 join。

事件信封的时间戳与本地时区无关。A 端以 `new Date(Date.now()).toISOString()` 生成 `timestamp`，B 端以 `client_timestamp.toISOString()` 生成同一形式的 UTC ISO 串，调整系统时区只改变显示，不改变上行值。因此时区伪装不改变服务端在信封上看到的时间；仍能暴露真实本机时区的是 A 端 Sentry 的 `culture.timezone`（见上表「时区 / 语言」行）。

传输层指纹只能用于区分，不能用于合并。B 的事件批量走 axios、其余走 undici/Bun fetch，其中代理 CONNECT 的 agent 固定 `ALPNProtocols:["http/1.1"]`；A 的请求走 Electron 默认 session 的 Chromium 网络栈。同一出口 IP 上的两条流因此在 TLS/ALPN 层面即分成两个客户端，方向是分离而非归并。`[Inference]`，依赖上述 `[Observed]` 的两处客户端栈事实；具体的 JA3/JA4 与 h2 SETTINGS 只有服务端可见。

同名头族可作共址旁证而非 join 键：`anthropic-client-platform` 在 A 侧为 `desktop_app`、在 B 侧为 `claude_code_cli`，服务端若按源 IP 与小时聚合请求日志，可看到同一 IP 上同时存在两个客户端；B 的 `cf_ray` 保留 `-XXX` 机房后缀，直接给出 B 的出边缘机房，而 A 的出机房只能由服务端从其源 IP 侧推算。两者一致只说明两端出口地理接近，不构成身份关联。`[Inference]`，依赖上表两行的 `[Observed]`。

---

## 6. 切断措施（按代价从低到高）

1. 避免在 Desktop 内启动 Claude Code 或 Cowork 会话。这是唯一不需要任何门控的强关联路径（§3.1）。
2. 在网络层切断 Desktop 的 Anthropic 出站：在 Clash 规则中对 Desktop 的进程与域名（`claude.ai`、`api.anthropic.com`、`*.ingest.us.sentry.io`、`downloads.claude.ai`、`releases.claude.com`）走 REJECT 或独立出口节点，与 CLI 所用节点分离。代价是更新检查与 model catalog 失效，可先用 `disableAutoUpdates` 关闭后拦截。
3. 在应用层关闭遥测（托管配置 / MDM）：设置 `telemetry.disableEssential=true` 与 `telemetry.disableNonessential=true`，`otlpEndpoint` 留空，`disableAutoUpdates=true`。需注意这两个键的 scope 标注为 `3p`，仅在 BYOK 场景可用。
4. CLI 侧：设置 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`（关闭通道 A/B/C/E/G），不设置 `CLAUDE_CODE_ENABLE_TELEMETRY`，并设置 `DISABLE_GROWTHBOOK=1`。
5. 主机名同样需要清理：trusted-device 注册与 cowork 设备注册的 `display_name` 都携带真实主机名。该行为受默认关闭的远端 flag 约束，但不应依赖该默认值。
6. 在要求更高时，使两端不以同一出口 IP 到达同一 Anthropic 域名（使用不同节点或不同 ASN），并将 Desktop 侧 `inference_host` 的明文上传视为已发生事实——该数据无法撤回。

---

## 7. 静态不可判定项

- GrowthBook 门 `2220415149`（控制 §3.2 的种子写入）：bundle 内无静态默认，生产环境状态由服务端下发决定。
- `disableEssential` / `disableNonessential` 的最终取值：schema 标 `scopes:["3p"]` 且带 `remotePolicy.default:true` / `failClosedValue:true`，无 bootstrap 或远程配置时求值点不在 bundle 内。
- 两端是否使用同一出口 IP：取决于 Clash 等工具的运行时规则，代码不保证。
- 服务端是否实际执行 `sha256(install_id)` 与 CLI `device_id` 的哈希比对：属服务端推断，静态代码无法证实。
- 服务端能否从请求的时间分布反推真实时区：活跃时段集中在 UTC+8 工作时间的模式可作中国时区的旁证，且与客户端是否伪装时区无关。`[Inference]`（依赖前提：事件信封时间戳为 UTC（见 §5），且服务端保留请求到达时间——后者不属静态可读范围）。
