# Claude Android（com.anthropic.claude）遥测 / 指纹 / 隐私面

**本篇是仓库内唯一的非 macOS 平台文档。** 既有素材树（`desktop/`、`cli/`）只覆盖 macOS 构建（见 `AGENTS.md` 前置说明）；本篇素材为仓库根目录的 **Play 分发 base APK**，与 Desktop/CLI 不共享代码，故单独立篇。

- **制品**：`claude.apk`（仓库根，**已 gitignore、不入库**，需自行获取；`sha256 = d4335899898597378ef1ce86b96b948dee01bc31ec1bd7728b1976ff8e3080b3`，39 058 193 B，1802 个 zip 项）
- **本地工作树**：`android/`（**整体 gitignore，不入库**）——`apk-tree/`（APK 原样解包：`classes*.dex`、`assets/`、`res/`）、`jadx-sources/`（jadx 产物，**本篇行号基准**）、`manifest-readable/AndroidManifest.xml`（`apkanalyzer manifest print` 输出）、`dex-strings.txt`（4 个 dex 的 `strings` 合一去重）。
- **性质**：静态分析（拆包 + R8 混淆后的 jadx 产物 + `dexdump -d` 字节码 + `telemetry/tools/dex.py` 字符串→代码交叉引用）为主；**2026-10-06 增补一轮动态验证**（API 33 `google_apis` x86_64 AVD、系统区装 CA 的 mitmproxy、未登录零账号），动态结论标 `[Observed·动态]`，其余运行时结论仍标推断等级。
- **行号基准**：本篇 `文件:行` 指向 **jadx 产物** `android/jadx-sources/<pkg>/*.java`（per-file 1-based 行号，由 `jadx -d … --no-res claude.apk` 生成；`--no-res` 只出代码不出资源）。R8 `-repackageclasses` 把 Anthropic 自有类与多数第三方 SDK 一并重命名进 `defpackage/`，混淆→真名对照见 §0.2。**但并非全部**：`okhttp3/`、`androidx/`、`kotlinx/`、`io/sentry/`、`com/segment/`、`coil3/`、`org/`、`kotlin/`、`google/` 等包名**原样保留** ⇒ 动态验证（如 Frida）可按类名挂钩，无需去猜 `defpackage`。

---

## 0. 素材形态与混淆对照

### 0.1 三棵形态（引用时二选一并在片段中写明）

| 形态 | 位置 | 特征 |
|---|---|---|
| 原始 dex | `android/apk-tree/classes{,2,3,4}.dex` | 未反编译；字符串池 + 字节码权威源 |
| jadx 产物 | `android/jadx-sources/…/*.java` | per-file 1-based 行号；**本篇行号基准** |
| `dexdump -d` | `dexdump -d android/apk-tree/classes.dex` | 仅用于 jadx 无法反编译的 R8 合成方法（`invokeSuspend` / 状态机分发） |

`[Observed]`＝有行号或原文片段证据；`[Inference]`＝由证据推导；`[Observed·动态]`＝2026-10-06 模拟器实测（见 §0 性质）。

### 0.2 混淆→真名对照（本篇反复引用）

| 混淆名 | 真身 | 依据（jadx 产物） |
|---|---|---|
| `defpackage.f11` | App SharedPreferences 门面（文件 `app_prefs`） | `f11.java:354` `getBoolean("third_party_analytics_disabled_for_org", false)` |
| `defpackage.v2x` | `ThirdPartyAnalyticsGate` | `v2x.java:47` 日志标签 `"ThirdPartyAnalyticsGate"` |
| `defpackage.x9t` | Sentry 初始化助手 | `x9t.java:32` DSN 字面量 + `SentryAndroidOptions` |
| `defpackage.akb` | Datadog 凭据（`Created`） | `akb.java:21` `"Created(applicationId=…, service=claude-android)"` |
| `defpackage.skb` | Datadog 初始化（`DatadogCore` builder） | `skb.a` 字节码构造 `Lmm9;`（Configuration）+ `DatadogRumMonitor` |
| `defpackage.mm9` / `fyr` / `hyr` | Datadog `Configuration` / `RumConfiguration` / RUM feature | `mm9.java:53-63` toString 字段名 |
| `defpackage.cf0` / `yb0` / `b6l` / `e6l` | Sift `AndroidDeviceProperties` / `AndroidAppState` / `MobileEvent` / `MobileEventsRequest` | 序列化器描述符（`af0.java:19`、`wb0.java:18`、`z5l.java:17`、`c6l.java:18`） |
| `defpackage.xru` / `yru` / `zru` | Sift 采集 / 上传 / 队列 | `Lxru;` 引用字符串 `android_id`；`Lyru;` 引用 `v3/accounts/{account}/mobile_events`；`zru.java:52` 队列常量 |
| `defpackage.i90` | 分析路由 DI（Segment/native 二选一） | `i90.java:26-33` writeKey 字面量、`:86` `setEnabled(!f11.q())` |
| `defpackage.aow` / `opw` | 应用内日志门面 / 汇接口 | `aow.java:9-11`、`opw` 接口；汇＝Sentry（`bat`）/Datadog（`mlb`）/空（`h3j`） |

---

## 1. 制品、真实性、构建

| 项 | 值 | 证据 |
|---|---|---|
| 包名 / 版本 | `com.anthropic.claude` / versionName `1.260930.20`，versionCode `26093020` | `apkanalyzer apk summary claude.apk` |
| SDK | minSdk 32，targetSdk 37，`debuggable=false` | `apkanalyzer manifest min-sdk/target-sdk/debuggable` |
| 签名 | **v3 通过**，v1/v2 无；`CN=Android, OU=Android, O=Google Inc., L=Mountain View, ST=California, C=US`，RSA 4096，cert SHA-256 `305a1e8a432e5ec0c612b2465359c3b88e3c95d6253599ac6088562b818b64a0`；`Verified for SourceStamp: true` | `apksigner verify -v --print-certs --min-sdk-version 32 claude.apk` |
| Play 分发标记 | `com.android.stamp.source=https://play.google.com/store`、`com.android.stamp.type=STAMP_TYPE_DISTRIBUTION_APK`、`com.android.vending.derived.apk.id=4`、`com.android.vending.splits.required=true` | `AndroidManifest.xml` meta-data |
| split 形态 | base APK；`res/xml/splits0.xml` 只列语言分包 `config.{de,es,fr,hi,in,it,ja,ko,pt}` 与模块 `ondemandone`；base manifest 另声明 `android:requiredSplitTypes="base__abi,base__density"` ⇒ **单独装 base 会 `INSTALL_FAILED_MISSING_SPLIT`，复现安装必须带 ABI + density split** | `aapt2 dump xmltree claude.apk --file res/xml/splits0.xml`；manifest |
| 构建 | R8 **full mode 9.4.14**，`min-api 26`；AGP `9.4.0`（`appMetadataVersion=1.1`） | dex 字符串 `~~R8{"backend":"dex","compilation-mode":"release","min-api":26,"r8-mode":"full","version":"9.4.14"}`；`META-INF/com/android/build/gradle/app-metadata.properties` |
| 原生代码 | **base 内无 `lib/`**（`unzip -l` 命中 0）、`<uses-native-library>` 0、`extractNativeLibs=false`；**但完整应用有原生代码**——ABI split `split_config.arm64_v8a.apk`（5.8 MB）载 9 个 `.so`（`libandroidmath`、`libandroidx.graphics.path`、`libdatastore_shared_counter`、`libopus_jni`、`libsentry-android`、`libsentry`、`libsqliteJni`、`libvoiceclient`、`libwebrtc_apm`），真机 pull 实测 | `unzip -l`、manifest、真机分片 |
| 附带构建元数据 | 根目录 `review.properties`（`client=review`）、`stamp-cert-sha256`、`META-INF/version-control-info.textproto`（`generate_error_reason: NO_SUPPORTED_VCS_FOUND`）、`assets/datadog.buildId`、`assets/sentry-debug-meta.properties` | 解包目录 |

**[Inference]** 该 DN 是 Google Play App Signing 的通用签名主体（每应用密钥不同、DN 相同），加上 `STAMP_TYPE_DISTRIBUTION_APK` + SourceStamp，判定为**未经重打包的 Play 交付件**；但本文件来自网络下载（同级存在 Windows `Zone.Identifier` 标记），无 Play 联网校验链，故不排除交付后被中间层处理的可能。**（2026-10-06 补：真机 pull 出的 `base.apk` 与本文库根 `claude.apk` sha256 逐字节一致＝`d433…80b3`，此不确定性已消除。）**

应用栈（用于解释后续通道）：Kotlin + Compose Multiplatform（`assets/composeResources`、`assets/peghl/*.peg` 34 个 PEG 语法、`assets/token-highlight.js`）、Cronet（QUIC hint `claude.ai`/`api.anthropic.com`）、Room、WorkManager、Preferences DataStore、Glance 小组件、Firebase FCM、Play Billing 9.1.0、ML Kit、Credential Manager / Google Sign-In、Health Connect（50+ 条 `android.permission.health.*`）。

---

## 2. 遥测通道总表

| # | 渠道 | 端点 | 载荷要点 | 开关 |
|---|---|---|---|---|
| A | **Segment（产品分析主路由）** | `POST https://a-api.anthropic.com/v1/b`；设置 `GET https://a-cdn.anthropic.com/v1/projects/<writeKey>/settings` | gzip JSON `{"batch":[…],"sentAt":…,"writeKey":"LKJN8…"}`；`flushAt=20`、`flushInterval=10s`；磁盘队列 `getDir("segment-disk-queue")` | `fws.setEnabled(!f11.q())` |
| B | **一方事件通道** | `POST https://claude.ai/api/event_logging/v2/batch`，请求头 `x-service-name`（值 `claude-android`）、`x-organization-uuid` | `BatchEventLoggingRequest{events[]}`；元素为多态（判别键 `event_type`） | GrowthBook `cuj_event_logging_config`；WorkManager `EventFlushWorker`（≥5 s） |
| C | **Datadog RUM / APM / Profiling**（dd-sdk-android **3.13.1**） | `https://browser-intake-us5-datadoghq.com/api/v2/rum`、`/api/v2/spans`（头 `DD-API-KEY: <clientToken>`）、`/api/v2/profile`、`https://quota.<site 主机>/api/v2/profiling/quota?session_id=`（`i4s.java:381` `String.format("https://quota.%s/api/v2/profiling/quota?session_id=%s", rzv.K0(dkbVar.a.x, "https://"), str)`） | appId `c93c9f6c-9a16-44b3-818e-43e89aa7ce46`，clientToken `pub024d5761c7eda08a273a93e0dc5b8c12`，`service=claude-android`，`env=prod`，site=**us5**（动态实测） | **额外**：GrowthBook `mobile_datadog_rum_enabled` **或** `is_ant`，且同意已决；profiling 另需 API≥35 |
| D | **Sentry** | `https://o1158394.ingest.us.sentry.io/api/4507346684477440/envelope/`（DSN `319c8a3f…`） | error/transaction + 脱敏后的 breadcrumb；`user.id=account UUID`、tag `current_organization_id` | `r9t` 同意开关（`!f11.q()`） |
| E | **Sift 设备指纹** | `PUT https://api3.siftscience.com/v3/accounts/64e6742e35ba4d3981f27c05/mobile_events`，`Authorization: Basic base64(write key 单值)`（生产 `Basic OTlkZmEyZTcxNg==`） | §5 明细 | `zru.p = !f11.q()`（构造时初始化，运行时可被 `id6#21` 改写，见 §5.4） |
| F | **FCM / FIS** | `https://firebaseinstallations.googleapis.com/v1/projects/<n>/installations[/*/authTokens:generate]`、`https://fcmregistrations.googleapis.com/v1/projects/<n>/registrations/…` | 注册/投递；`delivery_metrics_exported_to_big_query_enabled=true` | 未见开关 |
| G | **Sessions 事件总线** | `POST https://claude.ai/v1/code/sessions/{sessionId}/events` | `SendEventsV2Request{session_id, events[{payload, device_attestation, user_declared_urls}]}` | 会话鉴权，**不受**分析同意门控 |

**不在包内**：OpenTelemetry/OTLP SDK（`io/opentelemetry` 不存在；dex 里的 `opentelemetry` 字符串全是 Sentry 的兼容 stub）；Firebase Analytics SDK；Datadog Logs / Session Replay 模块。

关键证据：

- `[Observed]` Datadog 端点拼接：`n7y.java:28` `String B = yyr.B(dkbVar.a.x, "/api/v2/spans");` + `:29` `hjj.f0(new n6n("DD-API-KEY", dkbVar.b), …)`；site 基址 `jlb.java:5` `y("us1", "browser-intake-datadoghq.com")`、`:29` `this.x = "https://".concat(str2);`。**实测 site 为 `us5`**：`jlb` 枚举含 `US5("us5")`，单参构造拼 `browser-intake-us5-datadoghq.com`（`jlb.java:33`）；`:5` 的 `us1` 只是枚举首项，非实际取值。
- `[Observed]` Datadog 凭据：`akb.java:21` `"Created(applicationId=c93c9f6c-9a16-44b3-818e-43e89aa7ce46, clientToken=pub024d5761c7eda08a273a93e0dc5b8c12, service=claude-android)"`；构造点 `skb.a`（字节码 `classes.dex@0x582d4a` `invoke-direct/range … Lmm9;.<init>:(Lkm9;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;ZLjava/util/Map;Ljava/lang/String;)V`，参数 `(coreConfig, pub024…, env, "prod", "claude-android", true, {}, null)`）。
- `[Observed]` Sentry 初始化：`x9t.java:32` DSN 字面量；`:39` `setEnableAutoSessionTracking(false)`、`:40` `setSendClientReports(false)`、`:43` `setAttachScreenshot(false)`、`:44` `setAttachViewHierarchy(true)`、`:47` `setPropagateTraceparent(true)`、`:49` `setTracesSampleRate(Double.valueOf(0.005d))`、`:53-55` `setEnablePerformanceV2(true)`/`setEnableAppStartProfiling(true)`/`setEnableTimeToFullDisplayTracing(true)`、`:61` `setTombstoneEnabled(true)`；`setUser`/`setSendDefaultPii`/`setReplay*` 全篇未出现（`io.sentry.auto-init=false` ⇒ provider 不初始化，改由 `ClaudeApplication` 手动调 `x9t.a(...)`）。
- `[Observed]` 一方通道的路径与头同源：`event_logging/v2/batch` 与 `x-service-name` 两个字面量的 `const-string` 引用点均为 `Lv80;` 与 `Lew;`（`telemetry/tools/dex.py` 交叉引用，见 §11）。
- `[Observed]` Segment 走 Anthropic 自建代理：`nm9.java:23-24` `this.e = "a-api.anthropic.com/v1"; this.f = "a-cdn.anthropic.com/v1";`；上传 `qrq.java:161-166` `A("https://" + str + "/b")` + `setRequestProperty("Content-Encoding", "gzip")` + `setChunkedStreamingMode(0)`；设置拉取 `hjd.java:379` `"https://" + str + "/projects/" + writeKey + "/settings"`。**`api.segment.io` 只出现在 SDK 自遥测里，且被 `i90.java:70` `znw.x = false;` 关闭。**

---

## 3. 一方事件通道（通道 B）明细

- `[Observed]` 请求/响应 schema（kotlinx.serialization 描述符）：
  - `uo2.java:18-19` `BatchEventLoggingRequest` → 字段 `events`；
  - `xo2.java:17-19` `BatchEventLoggingResponse` → `accepted_count`、`rejected_count`；
  - `apo.java:18-28` `ProductAnalyticsEventData` → `event_name, event_id, event_timestamp, account_uuid?, organization_uuid?, anonymous_id?, client_platform, client_app, properties, context?`；
  - `j0g.java:18-33` `HealthMetricEventData`（15 字段，含 `session_id?`、`conversation_id?`、`chat_kind?`、`model?`）；
  - `xpf.java` / `jqf.java` = GrowthBook 实验曝光 / 特性求值事件（含 `device_id?`、`session_id?`、`user_attributes?`）。
- `[Observed]` 客户端 DI：`isn.java:54` `new fqd((dt0)…d1q.p, (String)…d1q.q)`，服务名取值 `i90.java:146-148`（`case 26:` → `return "claude-android";`）。
- `[Observed]` 出队：`com/anthropic/claude/observability/EventFlushWorker.java:32` `n = upp.N(5, bxc.SECONDS);`（WorkManager，最短 5 s）。
- `[Observed]` **事件名规模**（dex 字符串池唯一化，命令见 §11）：`claudeai.*` **411**、`mobile.*`（新点分）**75**、`mobile_*`（旧下划线，子串上界）**206**、`dispatch.*` 11、`mcp.*` 22、`mcp_app.*` 13。`[Inference]` 事件名总数（按实现 `c90` 接口的类枚举）约 700 量级，未逐条复核。
- `[Observed]` 路由二选一：`i90.java:60-72` 在 native（`zll`）与 Segment（`fws`）间切换（GrowthBook 覆写 `analytics_native_route_next_launch`）；切到 native 时清掉持久化的 Segment 身份（`remove("segment.userId")`、`remove("segment.traits")`）。`[Inference]` 首次启动默认 pref 为 `false` ⇒ 走 **SEGMENT**。

---

## 4. 身份与设备锚点

| 标识 | 生成/来源 | 落盘 | 上行位置 |
|---|---|---|---|
| 本地 `device_id` | `UUID.randomUUID()`（`rxb.java:7-13`，无硬件输入） | **明文** `SharedPreferences("device_id_prefs")` key `device_id`（`n41.java:102-112`） | 请求头 `Anthropic-Device-ID`（`cfm.java:38`，仅对 API base host 生效）；Segment 上下文字段 `ant_device_id`（`m6b.java:26`） |
| Sift `installation_id` | **`Settings.Secure.ANDROID_ID` 原值** | DataStore `sift_queue` 仅存水位，不存 id | Sift `MobileEvent.installation_id` |
| Segment `userId` / `anonymousId` | `userId = account_uuid`；匿名 id 为 SDK 生成的 UUIDv4 | `segment.userId` / `segment.anonymousId`（SharedPreferences `analytics-android-*`） | Segment 事件体 |
| Sentry 兜底安装 id | 随机 UUIDv4（`System.nanoTime()` 播种的 PRNG，**非 SecureRandom、非 ANDROID_ID**） | `filesDir/INSTALLATION` | Sentry `user.id` 兜底；同值作为 `distinctId` |
| `is_ant` | 内部人员 pref，默认 false | `app_prefs` | 抬升 Sentry 采样到 100%、参与 Datadog 门控、关闭日志脱敏 |

- `[Observed]` `Anthropic-Device-ID` 与同组头（`cfm.java:38`） `hjj.f0(new n6n("Anthropic-Client-Platform", "android"), new n6n("Anthropic-Client-App", str), new n6n("Anthropic-Client-Version", str2), new n6n("Anthropic-Client-Build", …), new n6n("Anthropic-Client-OS-Version", str3), new n6n("Anthropic-Device-ID", str4));`；`p6b.java:31` `this.A = cfm.b(26093020, this.y, "1.260930.20", valueOf, this.w);`，`p6b.java:39,43` 在拦截器 `d(...)` 里以 `if (mih.k(c2rVar.a.d, this.B))` 判断「请求 host == 配置的 API base」后才附加。
- `[Observed]` Sentry 人身份：`m16.java:95-105` `i0Var.x = str; … map.put("current_organization_id", str2); u4.q(i0Var); u4.p("subscription_level", …); u4.p("is_ant", …)`（`user.id`＝account UUID；**无 email/username/ip**）。
- `[Observed]` 受信设备链路：`xad.java:57` `EnrollTrustedDeviceRequest(display_name, device_public_key, reattest_public_key, platform)` → `m93.java:615` `new rt0(2, "auth/trusted_devices")`（常量 2＝POST）；响应 `abd.java:73` `EnrollTrustedDeviceResponse(device_id, device_token, reattest_kid, device_binding_kid)`。
- `[Observed]` 该凭据的落盘是**普通 SharedPreferences**（文件名 `cgy.java:32` `"trusted_device_".concat(str)`），键 `token`（`:157`）、`device_id`（`:130`）、`reattest_kid`（`:146`）、`device_binding_kid`（`:117`）、`device_binding_kid_unavailable_version`（`:124`）；写入点 `szv.java:148` `putString("reattest_kid", str)`。
- `[Observed]` **包内不存在 `androidx.security.crypto`**：反编译树无 `androidx/security` 目录，字符串池中 `EncryptedSharedPreferences`/`MasterKey`/`androidx.security` 命中数为 **0** ⇒ 设备凭据 token 未走 EncryptedSharedPreferences，仅有普通 SharedPreferences 隔离（不属备份 include 列表，见 §8.2）。
- `[Observed]` Play Integrity：`ClientAttestation(play_integrity_token=…)`、`DeviceAttestation(kid=…)`、`IntegrityTokenRequest{nonce=`、`auth/trusted_devices/{device_id}/rotate_reattest`、`trusted_device_attestation_failed`。
- `[Observed]` Sift `installation_id` 的取值链（两处独立证据）：① `telemetry/tools/dex.py`：字符串 `android_id` 的 `const-string` 引用点为 `Lxru;`；② `dexdump -d` `0x30de3c: const-string v8, "android_id"` → `0x30e096: invoke-static {v1, v8} Landroid/provider/Settings$Secure;.getString`；③ `ek0.java:822` `new b6l(zruVar.f.a(), (String) zruVar.e.a(), cf0Var.i, cf0Var, (yb0) null, 16)`，第 3 参即 `cf0` 的 `android_id` 字段。
- `[Observed]` **`installation_id` 的稳定性与变化条件**：该值即系统 `ANDROID_ID`（SSAID）**原值**——无哈希/加盐/截断，App 侧不缓存、不重建，每次采集现读（全 APK 仅 `Lxru;` 两处 `getString`：`0x30e096`→app_state、`0x30e196`→设备属性）。AOSP 生成为 `低 64 位(HMAC-SHA256(每用户随机密钥, App 签名证书))` ⇒ **卸载重装不变**（同设备/同用户/同签名密钥）；**会变**仅当：恢复出厂（或删除用户）、**签名密钥变更**（换渠道/重签/debug↔release）、切到另一用户或工作资料、root/自定义 ROM 改系统 settings 库。用户无任何可用的重置手段。

---

## 5. Sift 设备指纹（通道 E）明细

应用**未内嵌 `com.siftscience.*` SDK**，而是按 Sift mobile-event 方言自实现 schema（`sdk_version` 硬编码 `"1.3.1"`，`cf0.java:100`）。

### 5.1 触发

`[Observed]` `wru.java:16-21`（`Application.ActivityLifecycleCallbacks`）：`onActivityCreated` → `if (zruVar.p) { zruVar.a(zruVar.j, "collection", new xru(zruVar, simpleName, null)); }` ⇒ **每个 Activity 创建都采集一次设备指纹 + 应用状态**（登录前也采，`user_id` 可为 null）。注册点在 `ClaudeApplication.java:251`（`onCreate` 内；`:228` 解析、`:298` `onTerminate` 注销）。此处现读 `zru.p`，故同意切换即时生效（见 §5.4）。

### 5.2 `AndroidDeviceProperties` 字段来源（序列化器 `af0.java:19-35`）

| 字段 | 来源 |
|---|---|
| `app_name` / `app_version` | `PackageManager.getApplicationLabel()` / `PackageInfo.versionName`（`=1.260930.20`） |
| `sdk_version` | 硬编码 `"1.3.1"` |
| `mobile_carrier_name` | `TelephonyManager.getNetworkOperatorName()` |
| `mobile_iso_country_code` | `TelephonyManager.getSimCountryIso()`（**SIM 而非网络**） |
| `device_manufacturer` / `device_model` / `device_system_version` / `build_tags` | `Build.MANUFACTURER` / `Build.MODEL` / `Build.VERSION.RELEASE` / `Build.TAGS`（**在 9 参构造器内直接读取**：`cf0.java:94-97`） |
| `android_id` | `Settings.Secure.getString(resolver, "android_id")` |
| `evidence_files_present` | 逐条 `new File(path).exists()` |
| `evidence_packages_present` | 逐条 `PackageManager.getPackageInfo(name, 0)`（命中即加入；`NameNotFoundException` 吞掉） |
| `evidence_properties` | 执行 `getprop`，行内同时含 key 与 value 才计入（key/value 见下） |
| `evidence_directories_writable` | 执行 `mount`，按空格切分取 mountpoint + options，`rw` 且目录名匹配才计入 |
| `installed_apps` | **永远为空**（`cf0.java:112` `this.o = y6d.w;`；`af0.java:34` 标 `installed_apps` 为可选字段，`:47` 掩码分支同样回落 `y6d.w`；包内无全量应用枚举，也无 `QUERY_ALL_PACKAGES`） |

`AndroidAppState`（`wb0.java:18-26`）：`activity_class_name`（`activity.getClass().getSimpleName()`）、`sdk_version`、`battery_level/state/health`、`plug_state`、`network_addresses`（`NetworkInterface` 全部非环回地址，采集点与内容见 §5.2.1）。

### 5.2.1 `network_addresses` 的采集点与内容

`[Observed]` 采集点在 `Lxru;.invokeSuspend`（`classes.dex` 偏移 `0x30df50`–`0x30e080`；R8 状态机，jadx 未反编译，按 §0.1 走 `dexdump -d`）：

```
0x30df50  NetworkInterface.getNetworkInterfaces()      枚举全部接口
0x30df9e  NetworkInterface.getInetAddresses()          逐接口取地址，摊平为一个列表
0x30dff0  InetAddress.isLoopbackAddress()              仅剔除环回
0x30e02e  InetAddress.getHostAddress()
0x30e03e  String.toLowerCase(Locale.ROOT)
0x30e050  substringBefore('%')                         剥掉 IPv6 scope 后缀
0x30e080  Lyb0;.<init>:(Ljava/lang/String;DJJJLjava/util/List;)V   → network_addresses
```

`[Observed]` 过滤条件只有 `isLoopbackAddress()`（仅 `127.0.0.0/8` 与 `::1` 为真），链路本地 `fe80::/64`、ULA、VPN 隧道口均保留，只切掉 `%wlan0` 这类 scope 后缀。全 4 个 dex 中 `isLinkLocalAddress`/`isSiteLocalAddress`/`isAnyLocalAddress`/`isMulticastAddress`/`getInterfaceAddresses`/`NetworkInterface.isUp`/`Inet4Address` 出现次数**均为 0**，确认无第二处地址过滤（唯一 `instance-of Inet6Address` 在无关的 `Lu9q;.b`）。

`[Observed]` `NetworkInterface` 不需要任何权限；读 WiFi SSID/BSSID 在 Android 13+ 需 `NEARBY_WIFI_DEVICES`，本包未申请（`ACCESS_WIFI_STATE` 亦无）。但 manifest **确有** `ACCESS_FINE_LOCATION`/`ACCESS_COARSE_LOCATION`/`ACCESS_NETWORK_STATE`（供其他功能）⇒ 免权限结论应限定在该 API 本身，不可引申为应用无定位能力。

`[Observed]` 该值经 `uc6.java:148` `new b6l(…, (cf0) null, (yb0) obj2, 8)` 进入 APP_STATE 队列（`yb0` 非空、`cf0` 为 null）；`ek0.java:822` 是互补的一路（`cf0` 非空、`yb0` 为 null），走 DEVICE 队列。两路都 PUT 到 Sift `mobile_events`。

`[Observed]` 字段内容是设备本地网卡表中的全部地址，随接入方式变化：

| 接入方式 | 接口 | 地址 |
|---|---|---|
| WiFi | `wlan0` | 内网 IPv4（NAT 后）+ 全球 IPv6 |
| 蜂窝 | `rmnet_data0`（联发科平台为 `ccmni0`） | 运营商 CGNAT 私网 IPv4 + 全球 IPv6 |
| VPN | `tun0` | 隧道口地址 |

`[Observed]` 公网 IPv4 与公网 IPv6 的位置不同。IPv4 家宽普遍 NAT，公网地址是路由器的属性，设备只持有 `192.168.x.x`，`NetworkInterface` 读不到；IPv6 无 NAT，ISP 经 DHCPv6-PD 委派一段（家宽常见 /56–/60），路由器再以 RA/SLAAC 把其中一个 /64 通告进内网，设备以「前缀 + 自算接口标识」拼出全球可路由地址，它就在自己的网卡上，因而可被直接读到。

`[Inference]` 作为关联维度，强度来自前缀而非地址本身：

- IPv6 接口标识受 RFC 4941 隐私扩展控制会轮换（同一前缀下并存 `temporary` 与 `mngtmpaddr stable-privacy` 两条），可识别的一维是**前缀**本身。但**前缀并不长期稳定**：国内家宽走 PPPoE，重拨后 ISP 经 DHCPv6-PD 重新委派，前缀常随之轮换（RIPE-690 把分配分 static / dynamic-non-stable / stable 三档；实测电信约 30 天、联通动态）——故“前缀长期不变、对应固定一条宽带线路”**不成立**，仅在单个租期内稳定。可推断的是**运营商**（高置信：RIR 分配记录权威，实测 IPv6 的 ISP 识别率 85–95%；国内运营商按省注册子块，whois/bgp.tools 可收到 `2409:8728::/48 → China Mobile Group Zhejiang` 这一层）与**省/区域**（中—良）；**市一级弱**（IPv6 定位库 30–55%，亚太最差），公开数据到不了具体一户（顶层块：中国移动 `2409::/32`、中国联通 `2408::/32`、中国电信 `240e::/20`）。
- 蜂窝的前缀随数据上下文重建变动，且一个 UPF/区域地址池由大量用户共用，定位到城市/运营商级。
- 内网 IPv4 复用面广，区分度低。

`[Observed]` VPN 不影响该字段：VPN 的 `Uids` 范围决定流量出口，不改变 `NetworkInterface` 的返回，隧道口与底层网卡地址同时出现。⇒ 该字段是**设备自证**值：出口经 VPN 时出口 IP 会漂到出口地，此字段仍带出真实接入线路的前缀。

`[Inference]` §4 的 `Anthropic-Device-ID` 是随机 UUID、`android_id` 随签名与用户变化，`network_addresses` 是其中唯一由环境而非标识符产生的一维，可用于把同一网段下的多台设备归并（IPv6 委派以 /56–/64 到户，同 /64 下的设备前缀相同）。

### 5.3 探测清单（原文，`glr.java:8-11`）

```java
a = ugb.R("/system/app/Superuser.apk", "/sbin/su", "/system/bin/su", "/system/xbin/su",
          "/data/local/xbin/su", "/data/local/bin/su", "/system/sd/xbin/su",
          "/system/bin/failsafe/su", "/data/local/su", "/su/bin/su");
b = ugb.R("com.noshufou.android.su", "com.noshufou.android.su.elite", "eu.chainfire.supersu",
          "com.koushikdutta.superuser", "com.thirdparty.superuser", "com.yellowes.su",
          "com.koushikdutta.rommanager", "com.dimonvideo.luckypatcher", "com.chelpus.lackypatch",
          "com.ramdroid.appquarantine", "com.devadvance.rootcloak", "de.robv.android.xposed.installer",
          "com.saurik.substrate", "com.devadvance.rootcloakplus", "com.zachspong.temprootremovejb",
          "com.amphoras.hidemyroot", "com.formyhm.hideroot");
c = hjj.f0(new n6n("[ro.debuggable]", "[1]"), new n6n("[ro.secure]", "[0]"));
d = ugb.R("/system", "/system/bin", "/system/sbin", "/system/xbin", "/vendor/bin", "/sbin", "/etc");
```

`[Observed·动态]` **四张表的 `evidence_*` 结果字段在设备上恒为空**——不止 `evidence_packages_present`（targetSdk 37 + `<queries>` 未声明 root 包名 ⇒ Android 11+ `getPackageInfo` 抛 `NameNotFoundException`），另两路还各有**结构性 bug**。详见 **§5.5**。

### 5.4 上传、队列、重试

- `[Observed]` 端点/方法：路径字面量 `v3/accounts/{account}/mobile_events`（`Lyru;`）+ 基址 `https://api3.siftscience.com/`（`ij1.java:66` case 18）；方法常量 3＝`PUT`（三元在 `p2e.java:182`：`i != 1 ? i != 2 ? i != 3 ? … : "PATCH" : "PUT" : "POST" : "GET"`；等价显式版 `:162-173` `x(int)`）。
- `[Observed]` 认证：`Authorization: Basic base64(UTF-8(write key))`——base64 输入**只有 write key 单个字符串**，account 仅进 URL 路径占位符（`rt0.e("account", …)`），**不是** `account:key`（构造点 `ymi.java:1251` `"Basic ".concat(vk2.b(vk2.f, zzv.Z(j3qVar.y)))`）。凭据硬编码于 `ud0.java:41-48`：生产 `("64e6742e35ba4d3981f27c05", "99dfa2e716")`、staging `("64e6742e35ba4d3981f27c08", "88af42bf8a")`；对应头值 `Basic OTlkZmEyZTcxNg==` / `Basic ODhhZjQyYmY4YQ==`。
- `[Observed]` 队列：`zru.java:52-53` `APP_STATE` 队列容量 8 / 1 min 间隔，`DEVICE` 队列容量 0（逐个刷）+ 1 h 同指纹去重窗口；水位持久化在 DataStore `datastores/sift_queue.preferences_pb`（keys `app_state_last_upload_ms`、`device_event_time_ms`、`device_fingerprint`）；启动时 `deleteSharedPreferences("siftscience")` 清旧 SDK 残留。
- `[Observed]` 重试：`zru.java:26-30`（`r =` 在 `:29`）`r = ugb.R(new xwc(upp.N(0, SECONDS)), new xwc(upp.N(3, SECONDS)), new xwc(upp.N(12, SECONDS)));`；200=ACCEPTED、400=REJECTED、`status==null`=NO_ANSWER、其他状态重试、耗尽=REFUSED，仅消费 HTTP 状态码。
- `[Observed]` 上报结果也打点：事件 `sift.upload{outcome, status_code, event_kind, event_count, attempts}`。
- `[Observed]` 请求体**确为 gzip**（原稿“未找到压缩器”系漏看）：`yru.invokeSuspend` 内联 okio 链——`0x30e652` 建 `Los3`(Buffer) → `0x30e65c` 建 `Ltsf`(GzipSink) → `0x30e666` 建 `Lp8q`(BufferedSink) → `0x30e686` 写出序列化 JSON → `0x30e696` 取成 `cy3`(RequestBody)。`[Observed·动态]` 实体 283 B / 解压 432 B，头未撒谎。
- `[Observed]` 门控读取 `zru.p`。**该字段并非“仅构造时写入”**：除构造器（`o4u.java:202` Hilt provider，值 `!f11.q()`）外，另有运行时写入点 `id6.java:195-208`（case 21）：`if (zruVar.p != z) { zruVar.p = z; if (!z) { /* 取消在途采集 */ } }`。启动协程（`ClaudeApplication.onCreate`）把该 setter 装进 `v2x.g` ⇒ **登录（`app/main/j.java:704`）与组织切换（`dtm.java:24`）会实时改写 `zru.p`**（走 `v2x.e()` → `a(true)` 先置 `false` 并取消在途采集，待组织策略解析后再恢复）。故原稿“同意开关进程启动时固定、会话中切换不生效”**不成立**；`wru.onActivityCreated` 每次现读，切换即时生效。

### 5.5 【重要】Sift 的 root/tamper 取证恒等于零 —— 两处结构性 bug

> 这套“root 检测 / 防篡改取证”**在任何设备上都出不了结果**——真机 user build 一样永久为空。它不是“探针弱”，是**死的**。

`[Observed·动态]`（API 33 模拟器 + `adb root` + ftrace + 静态双证）：`evidence_*` 四个结果字段在设备上全空，其中两路是**与 exec 无关的结构性 bug**（exec 通路已由 ftrace 证实正常，avc 标注 `untrusted_app` + `app=com.anthropic.claude`）：

- **`evidence_properties`（`glr.c` = `[ro.debuggable]/[1]`、`[ro.secure]/[0]`）恒空**：命令确为**裸 `getprop`**（argc=0；实测 + 静态 `filled-new-array` 双证，排除“`getprop <key>`”假说）；空的原因是 `ro.debuggable`/`ro.secure` 属 `userdebug_or_eng_prop` 属性区，**`untrusted_app` 无权读**——app 侧 `getprop` 仅 498 行 vs shell 侧 872 行，针对性读为空、area 文件 `EACCES`。
- **`evidence_directories_writable`（`glr.d`）恒不命中**：实现按 `/proc/mounts` 的列序取 `parts[1]`/`parts[3]`，但实际执行的是 toybox **`mount`**（`0x30e310` `const-string "mount"`），其输出为 `[1]="on"`、`[3]="type"` ⇒ 下标**永远取错**，`rw` 判定永不成立。
- **`evidence_packages_present` 恒空**：包可见性所致，见 §5.3。
- `evidence_files_present`（`glr.a` 的 `File.exists()`）是四者里唯一实现正确的，但在干净设备上自然也是空。

⇒ 若目的是评估“它到底能探到什么”，答案是**探不到任何东西**；Sift 这条 root/环境取证在 release（user build）上**彻底失效**。

---

## 6. 三家 SDK 的配置细节

### 6.1 Sentry

- 采样：`setTracesSampleRate(0.005)`；`setTracesSampler`（`jwp.t`）——`is_ant` ⇒ `1.0`；`auto.ui.activity` + `MainActivity` + `ui.load` ⇒ `0.00125`；其余返回 null 继承 0.005。
- 传播：`setTracePropagationTargets`（主机白名单含 `claude.ai`、`claude.com`、`anthropic.com`、`ant.dev`、`claudeusercontent.com`，另加 `10.0.2.2`/`localhost`/`127.0.0.1` 等开发主机）。
- 脱敏链（`beforeSend`/`beforeSendTransaction`/`beforeBreadcrumb` 组合）：consent 门 → 致命事件镜像成应用事件 `mobile.sentry.event` → 非致命事件按 `is_ant` + 安装级随机比丢弃（`o6b.java:15-16`：非 FATAL 且 `is_ant==false` 且 `e3q.c() >= 0.25` ⇒ 丢弃）→ 可忽略异常类型过滤（网络/IO/SSL/`ClaudeRegionUnavailableException`）→ UUID/`session_*`/`cse_*`/`req_*` 占位替换 → HTTP span URL 重写（受远端旗标控制）。`http.query`/`http.fragment` **恒定**重写且敏感键（`search`、`q`、`query`、`prefix`、`path`）哈希。
- HTTP breadcrumb 记录 URL/method/status/长度，**不含请求响应体**（body 仅在 Replay 的 Network Details 路径读取，而 Replay 未启用）。
- `assets/sentry-debug-meta.properties`：`io.sentry.ProguardUuids=8ede339e-a877-31bf-9bb7-645fa7ca53b7`（R8 mapping uuid，随事件作 debug image 上报；mapping 本体不在此 APK）。

### 6.2 Datadog

- 版本 `3.13.1`（`dla.java:80`）；实例名 `_dd.sdk_core.default`。
- 采样：**RUM 会话采样率 = 100%**（原稿“20%”看错了字段）。`fyr` 的三个采样字段彼此独立——`fyr.toString()` 明确 `sampleRate=100.0, telemetrySampleRate=20.0, telemetryConfigurationSampleRate=…`；原稿引的 `hyr.j0 = new fyr(20.0f, …)`（`hyr.java:82`）首参是 **telemetryConfigurationSampleRate**，不是会话采样率。真正的会话采样率被 R8 折叠成常量：`0x33c17a` `const/high16 #0x42c8`（＝`100.0f`）→ `iput v0, Lhyr;.E`（`hyr.java:364`，全 dex 唯一写入点）。`[Observed·动态]` 36/36 条 RUM 载荷 `session_sample_rate=100.0`。
- 请求追踪（APM）：`tlb.java:46` 从 GrowthBook `mobile_observability_config` 读 `datadog_request_trace_sample_rate`，默认 **1.0**、clamp 到 [0,1]；采样决策逐请求随机；OkHttp 拦截器已挂在应用主客户端上。`trace.rate.limit=Integer.MAX_VALUE`、`trace.partial.flush.min.spans=5`、`trace.URLAsResourceNameRule.enabled=false`。
- Profiling：应用启动采样率＝`datadog_rum_profiler_sample_rate × 100`，持续采样率强制 0；仅在 `f11.j() == 2` 且 `Build.VERSION.SDK_INT >= 35` 时启动；开关写 `dd_prefs`（`dd_profiling_enabled`、`dd_profiling_sample_rate`）。
- 标识：**未调用 `setUserInfo`**（全 dex 无该调用）；SDK 自采设备信息；应用另加全局属性 `api_environment`、`platform=android`。
- 一方主机白名单 `skb.java:9`：`claude.ai, claude.com, api-staging.anthropic.com, claude-ai.staging.ant.dev, anthropic.com, ant.dev, claudeusercontent.com, localhost, 127.0.0.1`（用于 trace 注入/关联判断）。
- 设备侧：SharedPreferences `dd_prefs`；缓存目录 `<cacheDir>/datadog-<instance>`；上传走 WorkManager `com.datadog.android.core.UploadWorker`。

### 6.3 Segment

- 初始化：`i90.java:75` 构造 SDK，`:86` `fwsVar.setEnabled(!f11.q())`；插件链含 AndroidContext、AndroidLifecycle、`m6b`（注入 `ant_device_id` + `primary_language`）、参数清理与隐私变换（`qa4.java:68-77`：`linkedHashMap.put("ip", poh.c("REDACTED"))`、`remove("network"/"timezone"/"screen"/"userAgent")`、`linkedHashMap2.remove("id")` 即剔除 `context.device.id`）。
- writeKey 硬编码（`i90.java:26-33`）：生产 `LKJN8LsLERHEOXkw487o7qCTFOrGPimI`、staging/dev `b64sf1kxwDGe1PiSAlv5ixuH0f509RKK`。
- identify traits（`trg.java:52-53` `IdentifyTraits(account_uuid=…, organization_uuid=…, email=…, subscription_level=…, subscription_plan=…)`）— **[Observed] `email` 随 identify 出站**；`m6b` 只把 traits 复制进事件 context 时剔除 `email`（`m6b` 内 `Set z = m6u.G("email")`）。
- 队列：磁盘目录 `segment-disk-queue`，索引 SharedPreferences `analytics-android-<key>`；批包信封含 `writeKey`；重试策略：非 HTTP 错误重试、`400 / ≥500 / 429` 保留重试、其余 4xx/5xx 丢弃。

---

## 7. 同意门控状态机

- `[Observed]` 单一开关 `SharedPreferences("app_prefs")` 的 `third_party_analytics_disabled_for_org`（`f11.java:354-355`），另支持每组织覆写键 `third_party_analytics_disabled_for_org_<org>`（`f11.java:208-210`）。
- `[Observed]` 状态判定 `f11.j()`：`q()`（`third_party_analytics_disabled_for_org`）为 true ⇒ `1`＝禁用；否则 pref 含 `third_party_analytics_policy_resolved` ⇒ `2`＝已决启用；否则 `3`＝待决。
- `[Observed]` 扇出 `v2x.java:25-73`：写 pref → Datadog 同意（`xjb.a(null).k(!z ? w8y.w : w8y.x)`）→ 产品分析 `zoo.setEnabled(!z)` → Sentry → Sift；四路各自打印 `"… consent change failed"` 日志。**注意** `v2x.f`(Sentry)/`v2x.g`(Sift) 的**字段初值**是空实现（`v2x.java:14-15` `new iyw(2)`/`new iyw(3)`，`iyw.java:35-40` case 2/3 直接返回），**但启动时会被覆盖为真实现**：`ClaudeApplication.onCreate` 起的协程（`j93`/`vk`/`vx`）把 `id6#20`/`id6#21` 分别 `iput-object` 进 `v2x.f`/`v2x.g`（`classes3.dex 0x2647d2`/`0x2647f8`；二者即 `(r9t|zru).setEnabled(Z)V`）。⇒ 原稿“槽是空实现”**不成立**；Sentry 另有独立类 `r9t`（`ClaudeApplication` 构造时 `new r9t(!pyy.u(...q()))`），而 Sift 的实时开关就是 `id6#21`（见 §5.4）。（`v2x.f/g` 唯一写入点、装入对象类型 `(f17,y07,r9t)` 与自 `onCreate` 的逐跳为 `[Observed]`；selector→真实现的分支号属 `[Inference]`，R8 合并续体、jadx 未反编译。）
- `[Observed]` 服务端来源：**原稿把 `PUT /v1/privacy-consents`（头 `x-organization-uuid`，`clo.java:12`）当作第三方分析开关的服务端来源，经复核不成立**——该端点实测载荷类型 `xxy` 的 `consent_type` 硬编码为 `memory.sensitive_info`（调用者 `y8t`），与 `third_party_analytics` 无关联；org 级开关更可能来自账号/组织数据（`m16.java` 的 `r9zVar`）。GrowthBook 旗标注册表 `vbf.java:143-145` 仅含 `mobile_datadog_rum_enabled`、`cuj_event_logging_config`；`third_party_analytics` 出现在 `dde.java:20`（Feature 枚举）与 `p5b.java`，但**查无与 `zru`/Sift 的引用关系**。
- `[Observed]` **默认态不一致**：Sentry / Segment / Sift 为 `!disabled`（`disabled` 默认 false ⇒ **默认开**）；Datadog 额外要求 `mobile_datadog_rum_enabled` 或 `is_ant`，且同意状态需为已决。Sift 的 `zru.p` 构造时取 `!f11.q()`（默认开），运行时可被组织策略改写（见 §5.4）。
- 未见门控：FCM/推送、通道 G（sessions 事件）。

### 7.1 对外披露面（应用内文案 + 隐私政策 + 子处理者）

复核（2026-10-05）结论：**公网 IP 属“明确披露”，网卡级网络地址属“笼统覆盖”，且无用户可见开关** ⇒ 定性应从“越界采集”降级为“披露粒度不足”。

- `[Observed]` **应用内无任何提及网络地址/IP 采集的文案**：`resources.arsc` 全量字符串与 dex 全文检索，“网络地址 / 接口地址 / IP”均无对应披露句，也无分析/第三方开关 UI。引导页仅一句笼统的 `I consent to collection and use of my personal information in accordance with the Privacy Policy.`（`onboarding_v2_terms_consent_privacy_links`，`bp10.java:396`）；隐私设置页仅 `privacy_data_privacy_p1/p2` 泛文案。唯一的门是服务端 `third_party_analytics_disabled_for_org`（见 §7 上文）。
- `[Observed]` 隐私政策 `https://www.anthropic.com/legal/privacy` 明确列举 “Device and Connection Information … **connection information** … **IP address** (including information about the location of the device derived from your IP address) … **identifiers**”——类别级覆盖；隐私中心 `privacy.claude.com/en/articles/11186740` 明说 IP 用于粗粒度定位且 **“cannot be toggled off”**。
- `[Observed]` **Sift 被点名列为子处理者**：`anthropic.com/subprocessors`（→ `trust.anthropic.com/subprocessors`）载 “Sift — Fraud and abuse detection — United States — All products except Claude for Government”（双源快照互证）。
- `[Inference]` 结论：`network_addresses`（读本机网卡表所得，非仅出口 IP）**未被逐项披露**，政策以“设备与连接信息”类别覆盖，Sift 以反欺诈子处理者身份点名；用户无可见开关，不能“所见即所得”地关掉 Sift 一类分析。既非“零披露”，也达不到“明确披露 + 可控”。

---

## 8. 攻击面与 release 残留

### 8.1 导出组件（`exported=true`）

| 组件 | 权限 | 备注 |
|---|---|---|
| `DeepLinkActivity` | **无** | `claude://` **任意 host**；https App Link `autoVerify` 仅 `claude.ai`、`claude-ai.staging.ant.dev`；唯一输入校验是针对 `/api/mcp/auth_callback` 的 state 待定集；其余一律连 extras 一起转发 MainActivity |
| `AssistantOverlayActivity` | 无 | `ACTION_ASSIST` / `ACTION_VOICE_ASSIST` |
| `androidx.health.platform.client.impl.sdkservice.HealthDataSdkService` | **无** | 导出绑定服务（第三方库组件） |
| `MainActivity` | 无 | launcher |
| `PermissionsRationaleActivity` / `ViewPermissionUsageActivity`(alias) | alias 有 `START_VIEW_PERMISSION_USAGE` | 仅打开隐私政策页 |
| `ClaudeWidgetConfigActivity` | 无 | 小组件配置 |
| 语音三件套 / Glance / WorkManager / Billing / GMS / Firebase receiver 等 | 均有系统或签名级权限 | 低风险 |

全部 provider 均 `exported=false`（含 `FileProvider` authority `com.anthropic.claude.provider`，路径为 `cache-path /tmp/` 下的 `tmp_camera`/`tmp_draft`/`tmp_chart`）。

`[Observed·动态]` 本节**只覆盖 base APK**。各 `config.*`（ABI/密度/语言）分片 manifest 已核，**无组件**；但 on-demand 模块 `ondemandone` 未取到，其 manifest 未纳入——完整攻击面须补。

### 8.2 网络与备份

- `[Observed]` `res/xml/network_security_config.xml` 仅一条 `<base-config cleartextTrafficPermitted="false"/>`：**无 `<pin-set>`（未配置证书固定）**、无 `debug-overrides`、无明文例外。
- `[Observed]` `allowBackup=true`；`backup_rules.xml` 与 `data_extraction_rules.xml` 均只 include `sharedpref: app_prefs.xml`、`app_stats.xml`（云备份 + 设备迁移）。`app_prefs` 内含 `app_magic_link_pending_email`、`app_known_account_ids`、`app_remembered_account`、`api_base_url`、`debug_hub_backend_auth_token` 等键；会话 cookie 存于独立文件 `user_cookies_*`，**不在**备份/迁移范围。`[Inference]` 未显式 exclude 的其他域（db/files）默认行为受 `dataExtractionRules` 语义约束，需真机核实。

### 8.3 release 中可见的 dev / internal 面

- `[Observed]` 内建 internal settings 路由：`EndpointSelectionScreen`（可选 `Production` / `Staging` / `Localhost`=`http://localhost:8000` / `AndroidEmulatorLocalhost`=`http://10.0.2.2:8000`）、`GrowthBookOverrideScreen`、`GrowthBookFeatureJsonEditor`、`NetworkSimulationScreen`、`PushSettingsScreen`；`debug_force_*` 系列 pref 键。
  - `[Inference]` 明文被 `cleartextTrafficPermitted=false` 挡在平台层，除非走绕过 NSL 的 socket 路径。
- `[Observed]` staging 主机编入 release 且注册为 App Link：`claude-ai.staging.ant.dev`（manifest）、`staging.claudeusercontent.com`、`frame.staging.claudeusercontent.com`、`sandbox/staging.claudemcpcontent.com`、`api.claude-ai.staging.ant.dev`。
- `[Observed]` WebView：MCP app 与 Office/PDF 预览均 `setJavaScriptEnabled(true)`、`setAllowFileAccess(false)`、`setAllowContentAccess(false)`；两个 JS bridge 仅暴露 `postMessage(String)`（`mcpAppBridge`、`_claude_bridge`），新版走 `WebMessageListener` 且限源（`https://` + artifact frame 主机）；本地内容经 `loadDataWithBaseURL(null, …)` 或 `shouldInterceptRequest` 拦截 `https://pdfproxy.local/document.pdf`、`https://officeproxy.local/file`（后者限 10/30 MiB）；PDF/Office/XLSX 预览脚本从 jsdelivr / cdn.sheetjs.com 拉取，**带 SRI integrity**；语法高亮为本地 `assets/highlight.min.js` + `peghl/*.peg`。

### 8.4 内嵌标识（均属按设计公开，非私钥）

| 值 | 位置 | 备注 |
|---|---|---|
| `AIzaSyCXwR57UpRfok8poBStnqrHKxnzFG8cx-Y` | manifest `com.google.android.geo.API_KEY` | Google 客户端 key，应受包名+签名限制 |
| `AIzaSyBHforeFMPxWZg51b3HRS3-nHUIfUfNSso` / `AIzaSyDUHK0y-xkW5lwNiHodVVZ9Wl5YC7_TxkY` | dex | Firebase 客户端 key（两套环境） |
| `https://319c8a3f…@o1158394.ingest.us.sentry.io/4507346684477440` | `x9t.java:32` | Sentry DSN（只写） |
| `c93c9f6c-…` / `pub024d5761c7eda08a273a93e0dc5b8c12` | `akb.java:21` | Datadog RUM appId + 客户端 token（只写遥测） |
| `LKJN8LsLERHEOXkw487o7qCTFOrGPimI` / `b64sf1kxwDGe1PiSAlv5ixuH0f509RKK` | `i90.java:26-33` | Segment writeKey（prod / staging） |
| `64e6742e35ba4d3981f27c05`+`99dfa2e716` / `…27c08`+`88af42bf8a` | `ud0.java:41-48` | Sift account + write key（prod / staging） |
| `1062961139910-…apps.googleusercontent.com` | dex | Google Sign-In OAuth client id |

**未发现**：`sk-ant-` 密钥、JWT、PEM、Bearer 长令牌、Datadog/Sentry 私有 API key。

---

## 9. 与 Desktop / CLI 的对照（跨端）

| 维度 | Desktop 2.9939.2 | CLI 2.1.283 | Android 1.260930.20 |
|---|---|---|---|
| 错误上报 | Sentry（org `o1158394`） | Datadog Logs（`http-intake.logs.us5`，默认关） | Sentry（**同 org**，project `4507346684477440`）+ Datadog RUM/APM 直连 |
| 一方事件端点 | `claude.ai/api/event_logging/v2/batch` | 同路径（`tengu_*`） | **同路径**，头 `x-service-name: claude-android` |
| 事件命名空间 | `desktop_*` / `tengu_*` | `tengu_*` | `claudeai.*`（**与 web 侧一致**）+ `mobile.*` |
| 机器级标识 | `ant-did`（`install_id`，随更新检查/事件上报） | `.claude.json userID` | `device_id_prefs` 随机 UUID（+ Sift 用 ANDROID_ID 原值） |
| 配置下发 | GrowthBook | GrowthBook | GrowthBook（`mobile_datadog_rum_enabled`、`cuj_event_logging_config`、`third_party_analytics`） |
| 独有 | 桌面进程/文件系统面 | 终端/文件系统面 | **Sift 设备指纹**（网络地址 + 电量 + root 探测——后者实测失效，见 §5.5）、Play Integrity 受信设备、Datadog RUM **100%** 会话采样 |

跨端可关联键：**account UUID / organization UUID**（三者都上行）；Sentry 侧共享 org 号 `o1158394`（但 CSV/DSN 不同项目）。**不存在**机械的机器级共享键：Android 无 Desktop 的 `ant-did`，Desktop/CLI 无 `ANDROID_ID`/`device_id_prefs`；两端 join 仍回到 `24-join-keys-desktop-cli.md` 的结论口径（IP + 时间窗 + 账号）。

---

## 10. 未解 / 需真机确认

> 动态验证（2026-10-06，同 §0 性质）**已收口**：冷启动 120 s 内通道 A/B/C/E 有流量，D Sentry 0 envelope（但带 `sentry-trace` 传播头），F/G 无。已确认 Sift 链路**无模拟器检测**（仅 Sentry 打 `device_is_emulator` tag）。下列 3 / 4 / 6 已结案。

1. FCM 主注册 POST 的完整 URL（只还原到 `https://fcmregistrations.googleapis.com/v1/projects/` + `/registrations/`）。
2. 首启产品分析路由（SEGMENT vs NATIVE）取决于远端 GrowthBook；本地默认 pref ⇒ SEGMENT。
3. ~~Sift `evidence_packages_present` 在 Android 11+ 是否恒空~~ **已结案**；并连带发现四路 `evidence_*` 全恒空（§5.5）。
4. ~~Sift 请求体是否真的 gzip~~ **已结案**：确为 gzip（§5.4）。
5. 备份语义：`dataExtractionRules` 未列出的域（db/files）在真机上的实际行为。
6. ~~RUM 会话采样率的确切取值~~ **已结案**：100%（§6.2）。
7. Datadog profiling 的实际生效条件（需 API≥35 设备 + 服务端下发 `mobile_observability_config`）。
8. Sift 运行时开关链路中 `selector`→真实现的映射（`vk`=11 / `vx`=17 / `j93`=26）为 `[Inference]`（R8 合并续体、jadx 未反编译），需真机确认 `v2x.f/g` 覆盖与 `zru.p` 运行时改写。

---

## 11. 复现方式

```bash
# 0) 取件：claude.apk 需自行获取（已 gitignore，不入库；置于 <repo>/claude.apk）
sha256sum claude.apk   # 期望 d4335899898597378ef1ce86b96b948dee01bc31ec1bd7728b1976ff8e3080b3

# 1) 素材落位（= 本地工作树 android/，整体 gitignore）
unzip -q -o claude.apk -d android/apk-tree            # 原样解包：classes*.dex / assets / res / resources.arsc
mkdir -p android/manifest-readable
apkanalyzer manifest print claude.apk > android/manifest-readable/AndroidManifest.xml
for f in android/apk-tree/classes*.dex; do strings -a -n 6 "$f"; done | sort -u > android/dex-strings.txt
jadx -d /tmp/jadxout -j 8 --no-res --log-level warn claude.apk \
  && mv /tmp/jadxout/sources android/jadx-sources     # 本篇行号基准

# 2) 清单 / 权限 / 签名（v3 + Play SourceStamp）
apkanalyzer apk summary claude.apk
apkanalyzer manifest permissions claude.apk
$ANDROID_HOME/build-tools/35.0.0/apksigner verify -v --print-certs --min-sdk-version 32 claude.apk

# 3) 资源 XML（网络/备份/分包/限制）
aapt2 dump xmltree claude.apk --file res/xml/network_security_config.xml
aapt2 dump xmltree claude.apk --file res/xml/data_extraction_rules.xml
aapt2 dump xmltree claude.apk --file res/xml/splits0.xml

# 4) 字符串 → 归属类（telemetry/tools/dex.py，仅 stdlib；传 .apk 时自动遍历全部 classes*.dex）
python3 telemetry/tools/dex.py xref claude.apk android_id                              # → Lxru;.invokeSuspend
python3 telemetry/tools/dex.py xref claude.apk 'v3/accounts/{account}/mobile_events'   # → Lyru;.invokeSuspend
python3 telemetry/tools/dex.py xref claude.apk x-service-name                          # → Lv80;/Lew;.invokeSuspend
python3 telemetry/tools/dex.py code android/apk-tree/classes.dex 'Lxru;'               # 类方法表 + code_off
python3 telemetry/tools/dex.py strings claude.apk 'a-api.anthropic.com'                # 字符串池检索

# 5) R8 合成方法（jadx 无法反编译者）走字节码
dexdump -d android/apk-tree/classes.dex | awk '/Class descriptor  : .Lxru;/,/^  Class descriptor/'
dexdump -d android/apk-tree/classes.dex | grep -n 'getNetworkInterfaces\|isLoopbackAddress'   # §5.2.1 采集点 → 0x30df50 段

# 6) 事件名规模（字符串池唯一化）
grep -oE 'claudeai\.[a-z0-9_.]+' android/dex-strings.txt | sort -u | wc -l   # 411
grep -oE 'mobile\.[a-z0-9_.]+'   android/dex-strings.txt | sort -u | wc -l   # 75
grep -oE 'mobile_[a-z0-9_.]+'    android/dex-strings.txt | sort -u | wc -l   # 206（子串上界）
```

**`const-string` 交叉引用**（把字符串字面量定位到具体类/方法）由仓库内工具 `telemetry/tools/dex.py` 完成：解析 `string_ids` → `class_defs`/`class_data_item` → `code_item` 指令流，匹配 `const-string`(0x1a) / `const-string/jumbo`(0x1b) 的字符串索引并打印持有类与方法签名。它也是本分片多数「字面量 → 归属类」证据的来源（`android_id → Lxru;.invokeSuspend`、`v3/accounts/{account}/mobile_events → Lyru;.invokeSuspend`、`event_logging/v2/batch` 与 `x-service-name → Lv80;/Lew;.invokeSuspend`），且能在 jadx 放弃反编译的方法（`invokeSuspend` 被 R8 重写成状态机）上给出行号级定位之外的等价锚点（`code_off` 与 `dexdump -d` 的偏移一致）。注意 `class_data_item` 的 `method_idx_diff` 在 `direct_methods` 与 `virtual_methods` 两个数组内**各自**累加（工具已分别处理）。

**`xref` 的适用范围**：`dex.py xref` 匹配 `const-string` 指令，只对字符串字面量有效。若目标是 API 调用（如 `NetworkInterface.getNetworkInterfaces`），它在 dex 中以 `method_id` 引用（`invoke-static` 的操作数）出现，名字虽在 `string_ids` 中，却不是任何 `const-string` 的目标，`xref` 会打印字符串索引但报不出归属类；这类调用需 `dexdump -d` 反汇编后按 `invoke-*` 指令定位（§5.2.1 即此法）。字段访问（`iget`/`sget` 的 `field_id`）同理。

**素材的 gitignore 状态**：`android/`（含 `jadx-sources/` 194 MB、`apk-tree/` 48 MB）与 `claude.apk*` 均已写入 `.gitignore`，只存在于本地工作树；引用它们时按仓库相对路径写（同 `desktop/`、`cli/` 的写法），但**不要**期望 `git clone` 后存在。
