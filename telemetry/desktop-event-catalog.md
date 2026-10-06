# Desktop 事件全量清单（722 个）

**本篇是数据附录。** Desktop 的通道、门控与字段说明见 `desktop.md` §2.2；本篇只回答「有哪 722 个事件名、各自的首个调用点在哪」。

**素材与行号基准**：Claude Desktop **2.9939.2**，行号指向 `desktop/main-process-readable/*.js`（prettier 产物，per-file 1-based）。

**提取方法**：以 `grep -rnoE '\("[a-z][a-z0-9_]*", *[{\[]'` 限定遥测前缀族，再逐个验证调用别名（`Q` / `SM` / `eA` / `Von` / `Jz` / `xM` / `Tg` / `jZ` / `logEvent` / `trackEvent` / `onAnalyticsEvent`）确实解析到 `logEvent`（`index.chunk-DzZc-q0x.js:129972` 的 `logEvent: () => Q`）。每条给出**首个**调用点。行号的口径是**含事件名字面量的那一行**，不是调用表达式起始的那一行——多行调用（`M(` 换行之后才是字面量）因此会比调用首行晚一至两行。

**计数**：各族之和 = 722。其中 10 个 `tengu_*` 属内嵌的 Claude Code CLI 代码，不是 Desktop 自身事件。

**已知盲区（本清单不可复现，两个方向都会错）**：这里的数字是「按两种方法合并枚举到的结果」，不是精确总数，也不保证可复现。原方法（下面那条正则）漏掉一批事件，两轮共补入 **36 个**：前一轮补了 `lam_held_routine_release` 与 `cowork_space_migration_outcome` 两个，本轮再补 34 个——其中 25 个可按调用别名确认，另 9 个逐个看过上下文（`{ logEvent: t }` 解构绑定、可选调用 `i?.(name, null)`、以及末句以 `Q(e, …)` 发出的 mint 助手）。补入的名字包括 `lam_remote_tools_device_state`、`lam_documents_*` 一族、`desktop_main_view_*`、`desktop_app_*` 启动性能族与 `desktop_quit_cleanup_summary`。

即便补过一轮，两个方向的缺口仍在。原正则结构上漏三类：多行书写的 `Q(` 换行后接 `"name",`、三参形式 `eA(name, payload, finalizer)`、第二参为 `null` 的调用；别名经参数传递、或事件名由常量表给出时，两种方法都抓不到。反方向上，清单里有 41 个名字用同一套方法复现不出来（多为常量表或变量传名发出）。清单里的名字本身没有编造，722 个全部能在素材树里找到字面量，无一孤儿。判断某个名字是否真为事件时，可靠依据是该字符串**是否为一次调用（可达 `logEvent`）的首个实参**，而不是它长什么样。

另需注意，同一批前缀里混着**不是事件**的同形字面量，二次提取时逐条剔除过：Sentry 的 `tags.source` 取值（`marketplace_plugin_delete`、`remote_plugin_install` 等）、本地 console 日志行（`cowork_memory_sync_*` 一族走 `t.XJ[level]`，带 `[CoworkMemorySync]` 前缀）、settings 存储键（`tengu_tool_memory_cgroup`）、目录名（`cowork_plugins`、`cowork_settings`）、枚举值（`desktop_action`）、会话级开关标志（`cu_lock`），以及两个只作回调标签之用的 `cowork_host_configured` 与 `cowork_remote_api`（后者还与 `marketplace_plugin_op_result` 的 `implementation` 取值同名）。按前缀抓取时这些都会被误收。

**来源**：本清单原属 `03-desktop-first-party-events.md` §4（该分片已删除，可从 git 历史取回）。

---

## 各族触发条件（逐族说明；个体差异见行内提示）

| 族 | 数量 | 触发条件 |
|---|---|---|
| `desktop_*` | 431 | Desktop 主进程自身代码路径：应用启动/退出、窗口与 IPC、更新检查与下载、GPU/进程健康、登录与 OAuth、CCD（Claude Code Desktop）会话生命周期与消息循环、权限决策、内存治理、转写加载、工件、CLI 安装/升级、本地 agent 模式（LAM）桥接等。绝大多数为**状态变更即上报**，无采样。 |
| `lam_*` | 163 | "local agent mode"：远程工具 bridge 注册/派发/权限、电脑使用（computer use）锁与 teach 会话、文件夹授权、设备状态。事件驱动。 |
| `cowork_*` | 27 | Cowork：工件（artifact）创建/共享/发布、memory 同步 push/pull、插件、定时任务、spaces 迁移。事件驱动；`cowork_*_sync_*` 在网络同步成功/失败时上报。 |
| `ccd_simulator_*` | 20 | iOS 模拟器 / Android 模拟器集成（attach/consent/screenshot/gesture/inspect）。**仅当用户启用模拟器工具**时。 |
| `cu_*` | 20 | Computer-use：app helper 崩溃/探测、AX 辅助功能、watch record（录屏讲解）开始/结束/丢弃。 |
| `chrome_bridge_*` | 16 | Claude for Chrome 扩展 WebSocket bridge：连接/握手/配对/工具调用/路由 ack。**仅当扩展被连接**时。 |
| `custom3p_*` | 11 | 第三方/自托管部署：bootstrap 配置解析、本地执行同意、凭据 heal/reject、SSO 静默重授权。**仅 3p 部署**。 |
| `grand_prix_*` | 10 | "Grand Prix" 伙伴应用配对流程（`partner_id`）：pair/list/fill/disconnect/credential-request/teardown。 |
| `marketplace_*` | 7 | 插件市场：上传/删除/同步/迁移/错误。 |
| `remote_plugin_*` | 3 | 远端插件启用位迁移。 |
| `device_registry_*` | 2 | 设备注册（TPM 探测不可用）。 |
| `builtin_websearch_*` | 1 | 内置 WebSearch 工具调用。 |
| `ssh_terminal_*` | 1 | SSH 终端哨兵超时。 |
| `tengu_*` | 10 | **不是 Desktop 自己的事件**：内嵌 Claude Code CLI 代码（chunk `CHNweogn` / `DAdPDze6`）的 analytics，走 CLI 自己的 sink（`sink.logEvent`），见 `cli.md` §2 A。 |

## desktop (431)

- `desktop_accessibility_support_changed` — `index.chunk-DzZc-q0x.js:131633`
- `desktop_account_switch` — `index.chunk-DzZc-q0x.js:128689`
- `desktop_app_agent_sdk_loaded` — `index.chunk-DzZc-q0x.js:133307`
- `desktop_app_input_ready` — `index.chunk-DzZc-q0x.js:271402`
- `desktop_app_sidebar_painted` — `index.chunk-DzZc-q0x.js:271414`
- `desktop_app_startup_perf` — `index.chunk-DzZc-q0x.js:271518`
- `desktop_artifact_popup_gate` — `index.chunk-DzZc-q0x.js:138386`
- `desktop_browser_env_bridge_open` — `index.chunk-9hgN2KD3.js:734`
- `desktop_ccd_activity_context` — `index.chunk-9hgN2KD3.js:32033`
- `desktop_ccd_agent_remote_control` — `index.chunk-CtwayTMM.js:6394`
- `desktop_ccd_archive_session_auto_mode` — `index.chunk-9hgN2KD3.js:3820`
- `desktop_ccd_artifact_publish_preview` — `index.chunk-DzZc-q0x.js:223374`
- `desktop_ccd_artifacts_reset` — `index.chunk-DzZc-q0x.js:141857`
- `desktop_ccd_aside` — `index.chunk-9hgN2KD3.js:8362`
- `desktop_ccd_attention_mislabel` — `index.chunk-9hgN2KD3.js:817`
- `desktop_ccd_auth_error_result` — `index.chunk-9hgN2KD3.js:57557`
- `desktop_ccd_auto_archive` — `index.chunk-BhndlUKY.js:330`
- `desktop_ccd_auto_update_check` — `index.chunk-DzZc-q0x.js:169609`
- `desktop_ccd_autofix_own_pr_arm` — `index.chunk-9hgN2KD3.js:11880`
- `desktop_ccd_autofix_settled` — `index.chunk-OcYf-Q6a.js:213`
- `desktop_ccd_autofix_wake` — `index.chunk-OcYf-Q6a.js:586`
- `desktop_ccd_background_task_killed_by_teardown` — `index.chunk-9hgN2KD3.js:38643`
- `desktop_ccd_background_task_resolved` — `index.chunk-9hgN2KD3.js:50633`
- `desktop_ccd_background_task_suggested` — `index.chunk-9hgN2KD3.js:50559`
- `desktop_ccd_base_branch_merge` — `index.chunk-9hgN2KD3.js:56867`
- `desktop_ccd_base_fast_forward` — `index.chunk-zPR7Bl2R.js:10932`
- `desktop_ccd_bash_foreground_active` — `index.chunk-DtrkByRj.js:3204`
- `desktop_ccd_bash_interrupt` — `index.chunk-DtrkByRj.js:3060`
- `desktop_ccd_bash_shell_reset` — `index.chunk-DtrkByRj.js:3146`
- `desktop_ccd_bash_stale_interrupted` — `index.chunk-DtrkByRj.js:3128`
- `desktop_ccd_below_boundary_symlink_refused` — `index.chunk-DzZc-q0x.js:130391`
- `desktop_ccd_binary_cache_invalid` — `index.chunk-DzZc-q0x.js:168700`
- `desktop_ccd_binary_prepare_failed` — `index.chunk-DzZc-q0x.js:168941`
- `desktop_ccd_binary_resolved` — `index.chunk-9hgN2KD3.js:22253`
- `desktop_ccd_browser_navigated` — `index.chunk-DzZc-q0x.js:195893`
- `desktop_ccd_btw_child_close` — `index.chunk-BURbyyNT.js:113`
- `desktop_ccd_btw_child_open` — `index.chunk-BURbyyNT.js:82`
- `desktop_ccd_change_cwd` — `index.chunk-9hgN2KD3.js:53648`
- `desktop_ccd_chip_level_change_failed` — `index.chunk-9hgN2KD3.js:53246`
- `desktop_ccd_chip_level_changed` — `index.chunk-9hgN2KD3.js:53226`
- `desktop_ccd_chrome_import` — `index.chunk-CeAIwS0t.js:1184`
- `desktop_ccd_cli_install` — `index.chunk-DzZc-q0x.js:264877`
- `desktop_ccd_cli_install_failed` — `index.chunk-DzZc-q0x.js:264847`
- `desktop_ccd_cli_resume_refused` — `index.chunk-9hgN2KD3.js:59379`
- `desktop_ccd_cli_session_imported` — `index.chunk-9hgN2KD3.js:59621`
- `desktop_ccd_cli_started_turn_result` — `index.chunk-9hgN2KD3.js:16233`
- `desktop_ccd_cli_teardown_outcome` — `index.chunk-9hgN2KD3.js:38759`
- `desktop_ccd_cli_uninstall` — `index.chunk-DzZc-q0x.js:264924`
- `desktop_ccd_cli_uninstall_failed` — `index.chunk-DzZc-q0x.js:264909`
- `desktop_ccd_composer_inp` — `index.chunk-9hgN2KD3.js:21971`
- `desktop_ccd_config_reparse` — `index.chunk-DzZc-q0x.js:159965`
- `desktop_ccd_connector_switch_auto_mode` — `index.chunk-9hgN2KD3.js:3800`
- `desktop_ccd_context_exceeded` — `index.chunk-9hgN2KD3.js:57508`
- `desktop_ccd_context_recovered` — `index.chunk-9hgN2KD3.js:57532`
- `desktop_ccd_delegated_ask_allowed` — `index.chunk-9hgN2KD3.js:5300`
- `desktop_ccd_fork_timing` — `index.chunk-9hgN2KD3.js:17206`
- `desktop_ccd_github_pr_checks_summary` — `index.chunk-9hgN2KD3.js:10210`
- `desktop_ccd_github_rate_limited` — `index.chunk-9hgN2KD3.js:10163`
- `desktop_ccd_governor_pressure` — `index.chunk-9hgN2KD3.js:8207`
- `desktop_ccd_governor_soft_cap_exceeded` — `index.chunk-9hgN2KD3.js:8144`
- `desktop_ccd_governor_throttled` — `index.chunk-9hgN2KD3.js:34170`
- `desktop_ccd_governor_would_evict` — `index.chunk-9hgN2KD3.js:8134`
- `desktop_ccd_governor_yielded` — `index.chunk-9hgN2KD3.js:8154`
- `desktop_ccd_hardlinked_file_read` — `index.chunk-DzZc-q0x.js:130394`
- `desktop_ccd_helper_fork_empty_text` — `index.chunk-9hgN2KD3.js:28640`
- `desktop_ccd_helper_fork_usage` — `index.chunk-9hgN2KD3.js:28251`
- `desktop_ccd_host_handoff` — `index.chunk-CtwayTMM.js:4652`
- `desktop_ccd_host_keep_awake` — `index.chunk-CtwayTMM.js:3386`
- `desktop_ccd_host_storage` — `index.chunk-CtwayTMM.js:3876`
- `desktop_ccd_hotpath_cwd_gone_detected` — `index.chunk-9hgN2KD3.js:43371`
- `desktop_ccd_inline_pastes` — `index.chunk-9hgN2KD3.js:17996`
- `desktop_ccd_interrupt_no_query` — `index.chunk-9hgN2KD3.js:44010`
- `desktop_ccd_keep_awake_held` — `index.chunk-DzZc-q0x.js:162140`
- `desktop_ccd_keep_awake_manual_held` — `index.chunk-DzZc-q0x.js:162287`
- `desktop_ccd_keep_awake_manual_released` — `index.chunk-DzZc-q0x.js:162296`
- `desktop_ccd_keep_awake_released` — `index.chunk-DzZc-q0x.js:162152`
- `desktop_ccd_lazy_worktree_provided` — `index.chunk-9hgN2KD3.js:14566`
- `desktop_ccd_logs_handoff_outcome` — `index.chunk-DzZc-q0x.js:211468`
- `desktop_ccd_mcp_internal_name_claimed` — `index.chunk-9hgN2KD3.js:56347`
- `desktop_ccd_mcp_own_server_handshake_failed` — `index.chunk-9hgN2KD3.js:56341`
- `desktop_ccd_message_cycle_outcome` — `index.chunk-9hgN2KD3.js:1432`
- `desktop_ccd_message_cycle_start` — `index.chunk-9hgN2KD3.js:1361`
- `desktop_ccd_midturn_send` — `index.chunk-9hgN2KD3.js:43857`
- `desktop_ccd_model_change_failed` — `index.chunk-9hgN2KD3.js:53871`
- `desktop_ccd_model_selection_fallback` — `index.chunk-DzZc-q0x.js:251263`
- `desktop_ccd_move_to_cloud` — `index.chunk-CqanYFxR.js:469`
- `desktop_ccd_move_to_cloud_auto_mode` — `index.chunk-9hgN2KD3.js:3846`
- `desktop_ccd_oauth_refresh_declined` — `index.chunk-9hgN2KD3.js:15923`
- `desktop_ccd_oauth_token_pushed` — `index.chunk-9hgN2KD3.js:16003`
- `desktop_ccd_oauth_token_renewal` — `index.chunk-9hgN2KD3.js:16082`
- `desktop_ccd_path_floor_homebrew_added` — `index.chunk-DzZc-q0x.js:180298`
- `desktop_ccd_peer_send_undelivered` — `index.chunk-9hgN2KD3.js:17267`
- `desktop_ccd_pending_echo_reaped` — `index.chunk-9hgN2KD3.js:17302`
- `desktop_ccd_permission_auto_allowed` — `index.chunk-9hgN2KD3.js:4241`
- `desktop_ccd_permission_auto_denied` — `index.chunk-9hgN2KD3.js:4180`
- `desktop_ccd_permission_decisionreason_cache_hit` — `index.chunk-9hgN2KD3.js:7173`
- `desktop_ccd_permission_mode_change_failed` — `index.chunk-9hgN2KD3.js:53132`
- `desktop_ccd_permission_mode_changed` — `index.chunk-9hgN2KD3.js:52938`
- `desktop_ccd_pr_auto_merge_auto_mode` — `index.chunk-9hgN2KD3.js:3834`
- `desktop_ccd_pr_bar_bind` — `index.chunk-9hgN2KD3.js:11636`
- `desktop_ccd_pr_bar_confirm` — `index.chunk-9hgN2KD3.js:11145`
- `desktop_ccd_pr_bar_dismiss` — `index.chunk-9hgN2KD3.js:11936`
- `desktop_ccd_pr_bind_auto_mode` — `index.chunk-9hgN2KD3.js:3842`
- `desktop_ccd_pr_mcp_call` — `index.chunk-CtwayTMM.js:6772`
- `desktop_ccd_preview_idle_teardown` — `index.chunk-9hgN2KD3.js:32441`
- `desktop_ccd_proxy_unreachable` — `index.chunk-9hgN2KD3.js:58621`
- `desktop_ccd_quit_auto_resume` — `index.chunk-9hgN2KD3.js:33695`
- `desktop_ccd_quit_auto_resume_launch_pass` — `index.chunk-9hgN2KD3.js:34756`
- `desktop_ccd_rc_serve_register` — `index.chunk-Cw19c-e2.js:2678`
- `desktop_ccd_rc_serve_session_end` — `index.chunk-Cw19c-e2.js:3860`
- `desktop_ccd_rc_serve_stall` — `index.chunk-Cw19c-e2.js:3956`
- `desktop_ccd_rc_serve_state` — `index.chunk-Cw19c-e2.js:4315`
- `desktop_ccd_rc_serve_summary` — `index.chunk-Cw19c-e2.js:4490`
- `desktop_ccd_rc_serve_ui` — `index.chunk-DzZc-q0x.js:249486`
- `desktop_ccd_rc_serve_work` — `index.chunk-Cw19c-e2.js:3705`
- `desktop_ccd_rc_toolhost_end` — `index.chunk-Cw19c-e2.js:4140`
- `desktop_ccd_rc_toolhost_work` — `index.chunk-Cw19c-e2.js:4172`
- `desktop_ccd_recap_capped` — `index.chunk-9hgN2KD3.js:28804`
- `desktop_ccd_recap_generated` — `index.chunk-9hgN2KD3.js:44942`
- `desktop_ccd_recap_started` — `index.chunk-9hgN2KD3.js:44928`
- `desktop_ccd_remote_attachment_write` — `index.chunk-DF3lSehM.js:609`
- `desktop_ccd_remote_control_auto_enable` — `index.chunk-9hgN2KD3.js:21457`
- `desktop_ccd_remote_control_bridge_failed` — `index.chunk-9hgN2KD3.js:49666`
- `desktop_ccd_remote_managed_settings_fetch` — `index.chunk-J57p5E9t.js:281`
- `desktop_ccd_remote_restart_auto_resume` — `index.chunk-9hgN2KD3.js:34032`
- `desktop_ccd_remote_workspace_policy` — `index.chunk-9hgN2KD3.js:17100`
- `desktop_ccd_resume_bring_home_timing` — `index.chunk-9hgN2KD3.js:40611`
- `desktop_ccd_run_follow_up` — `index.chunk-9hgN2KD3.js:22028`
- `desktop_ccd_scheduled_task_tool_auto_mode` — `index.chunk-9hgN2KD3.js:3855`
- `desktop_ccd_scheduled_tasks_permission_auto_approved` — `index.chunk-9hgN2KD3.js:7197`
- `desktop_ccd_scheduled_tasks_permission_stall_released` — `index.chunk-9hgN2KD3.js:33498`
- `desktop_ccd_scheduled_tasks_run_completed` — `index.chunk-9hgN2KD3.js:57469`
- `desktop_ccd_scratch_files_carried` — `index.chunk-9hgN2KD3.js:53678`
- `desktop_ccd_send_swallowed` — `index.chunk-9hgN2KD3.js:58224`
- `desktop_ccd_send_uuid_reused` — `index.chunk-9hgN2KD3.js:22368`
- `desktop_ccd_session_cleared` — `index.chunk-9hgN2KD3.js:45044`
- `desktop_ccd_session_crash_loop_parked` — `index.chunk-9hgN2KD3.js:58793`
- `desktop_ccd_session_dead_end` — `index.chunk-DzZc-q0x.js:141839`
- `desktop_ccd_session_detached` — `index.chunk-9hgN2KD3.js:51534`
- `desktop_ccd_session_discard_pending` — `index.chunk-9hgN2KD3.js:45548`
- `desktop_ccd_session_file_access` — `index.chunk-DzZc-q0x.js:262847`
- `desktop_ccd_session_idle_pause_declined` — `index.chunk-CtwayTMM.js:13798`
- `desktop_ccd_session_idle_pause_stuck` — `index.chunk-CtwayTMM.js:13807`
- `desktop_ccd_session_idle_paused` — `index.chunk-9hgN2KD3.js:39171`
- `desktop_ccd_session_idle_timeout_cancelled` — `index.chunk-CtwayTMM.js:13829`
- `desktop_ccd_session_idle_timeout_started` — `index.chunk-CtwayTMM.js:13770`
- `desktop_ccd_session_idle_warm_complete` — `index.chunk-9hgN2KD3.js:46457`
- `desktop_ccd_session_idle_warm_failed` — `index.chunk-9hgN2KD3.js:46544`
- `desktop_ccd_session_idle_warm_staggered` — `index.chunk-CtwayTMM.js:13715`
- `desktop_ccd_session_idle_warm_start` — `index.chunk-9hgN2KD3.js:46172`
- `desktop_ccd_session_initialization_failed` — `index.chunk-9hgN2KD3.js:41954`
- `desktop_ccd_session_initialized` — `index.chunk-9hgN2KD3.js:41793`
- `desktop_ccd_session_list_load_failed` — `index.chunk-9hgN2KD3.js:1920`
- `desktop_ccd_session_list_loaded` — `index.chunk-9hgN2KD3.js:1922`
- `desktop_ccd_session_pause_blocked_by_cron` — `index.chunk-9hgN2KD3.js:45730`
- `desktop_ccd_session_pause_blocked_by_lanyard` — `index.chunk-9hgN2KD3.js:45777`
- `desktop_ccd_session_pause_blocked_by_rc` — `index.chunk-9hgN2KD3.js:45766`
- `desktop_ccd_session_pause_blocked_by_wakeup` — `index.chunk-9hgN2KD3.js:45744`
- `desktop_ccd_session_pause_blocked_by_workflow` — `index.chunk-9hgN2KD3.js:45752`
- `desktop_ccd_session_pause_skipped_remote` — `index.chunk-9hgN2KD3.js:45791`
- `desktop_ccd_session_query_error` — `index.chunk-9hgN2KD3.js:58633`
- `desktop_ccd_session_resume_pre_clear` — `index.chunk-9hgN2KD3.js:45689`
- `desktop_ccd_session_rewind_files` — `index.chunk-9hgN2KD3.js:22456`
- `desktop_ccd_session_rewind_rejected_dead_branch` — `index.chunk-9hgN2KD3.js:45090`
- `desktop_ccd_session_rewind_switch_refused` — `index.chunk-9hgN2KD3.js:45327`
- `desktop_ccd_session_rewind_undone` — `index.chunk-9hgN2KD3.js:45293`
- `desktop_ccd_session_rewound` — `index.chunk-9hgN2KD3.js:45204`
- `desktop_ccd_session_start_timing` — `index.chunk-9hgN2KD3.js:1098`
- `desktop_ccd_session_stopped` — `index.chunk-9hgN2KD3.js:39202`
- `desktop_ccd_session_switch_abandoned` — `index.chunk-9hgN2KD3.js:2211`
- `desktop_ccd_session_switch_initiated` — `index.chunk-9hgN2KD3.js:2189`
- `desktop_ccd_session_switch_timing` — `index.chunk-9hgN2KD3.js:21907`
- `desktop_ccd_session_timeout` — `index.chunk-9hgN2KD3.js:33567`
- `desktop_ccd_session_title_check` — `index.chunk-9hgN2KD3.js:23517`
- `desktop_ccd_session_title_offer` — `index.chunk-9hgN2KD3.js:18361`
- `desktop_ccd_session_tool_auto_mode` — `index.chunk-9hgN2KD3.js:3829`
- `desktop_ccd_session_visibility_changed` — `index.chunk-9hgN2KD3.js:46613`
- `desktop_ccd_sessions_recovered` — `index.chunk-9hgN2KD3.js:59762`
- `desktop_ccd_set_model_mid_turn` — `index.chunk-9hgN2KD3.js:53922`
- `desktop_ccd_setting_change_auto_mode` — `index.chunk-9hgN2KD3.js:3808`
- `desktop_ccd_settings_tool` — `index.chunk-CtwayTMM.js:7766`
- `desktop_ccd_shell_env_extraction_failed` — `index.chunk-DzZc-q0x.js:180150`
- `desktop_ccd_shell_env_tls_trust_adopted` — `index.chunk-DzZc-q0x.js:180093`
- `desktop_ccd_side_chat_guard_breach` — `index.chunk-9hgN2KD3.js:28582`
- `desktop_ccd_side_chat_started` — `index.chunk-9hgN2KD3.js:28520`
- `desktop_ccd_side_chat_tool_refused` — `index.chunk-9hgN2KD3.js:28369`
- `desktop_ccd_side_chat_tools_narrowed` — `index.chunk-9hgN2KD3.js:28383`
- `desktop_ccd_side_session_hand_off` — `index.chunk-9hgN2KD3.js:52598`
- `desktop_ccd_side_session_offer` — `index.chunk-9hgN2KD3.js:50698`
- `desktop_ccd_side_session_start_gated` — `index.chunk-9hgN2KD3.js:5877`
- `desktop_ccd_side_session_started` — `index.chunk-9hgN2KD3.js:51121`
- `desktop_ccd_side_session_turn_end` — `index.chunk-9hgN2KD3.js:52624`
- `desktop_ccd_side_session_wake` — `index.chunk-9hgN2KD3.js:52690`
- `desktop_ccd_sleep_auto_resume` — `index.chunk-9hgN2KD3.js:24100`
- `desktop_ccd_sleep_interruption_cleared` — `index.chunk-9hgN2KD3.js:24091`
- `desktop_ccd_sleep_interruption_shown` — `index.chunk-9hgN2KD3.js:24081`
- `desktop_ccd_spawn_tool_parity` — `index.chunk-9hgN2KD3.js:21034`
- `desktop_ccd_start_lock_broken` — `index.chunk-9hgN2KD3.js:15339`
- `desktop_ccd_steer_delivered` — `index.chunk-9hgN2KD3.js:57902`
- `desktop_ccd_steer_detach` — `index.chunk-9hgN2KD3.js:25799`
- `desktop_ccd_storage_cleanup` — `index.chunk-DzZc-q0x.js:253183`
- `desktop_ccd_storage_cleanup_auto_mode` — `index.chunk-9hgN2KD3.js:3850`
- `desktop_ccd_stream_ended_diagnostic` — `index.chunk-9hgN2KD3.js:1490`
- `desktop_ccd_stream_render` — `index.chunk-9hgN2KD3.js:22003`
- `desktop_ccd_task_backlog_dismissed` — `index.chunk-9hgN2KD3.js:51022`
- `desktop_ccd_task_backlog_filed` — `index.chunk-9hgN2KD3.js:50966`
- `desktop_ccd_teleport_snapshot` — `index.chunk-BPZLHR3P.js:239`
- `desktop_ccd_terminal_auto_mode` — `index.chunk-9hgN2KD3.js:3812`
- `desktop_ccd_terminal_pty_closed` — `index.chunk-DtrkByRj.js:1270`
- `desktop_ccd_terminal_pty_evicted` — `index.chunk-DtrkByRj.js:2009`
- `desktop_ccd_terminal_shared_unavailable` — `index.chunk-DtrkByRj.js:1630`
- `desktop_ccd_terminal_spawned` — `index.chunk-DtrkByRj.js:1993`
- `desktop_ccd_thinking_display_flip` — `index.chunk-9hgN2KD3.js:25992`
- `desktop_ccd_transcript_kept_on_delete` — `index.chunk-9hgN2KD3.js:26204`
- `desktop_ccd_transcript_lease_pass` — `index.chunk-9hgN2KD3.js:32574`
- `desktop_ccd_transcript_load_earlier` — `index.chunk-9hgN2KD3.js:48061`
- `desktop_ccd_transcript_read_failed` — `index.chunk-9hgN2KD3.js:56604`
- `desktop_ccd_transcript_unavailable_marked` — `index.chunk-9hgN2KD3.js:46102`
- `desktop_ccd_trust_check_miss` — `index.chunk-9hgN2KD3.js:26445`
- `desktop_ccd_turn_result_wait_expired` — `index.chunk-9hgN2KD3.js:44408`
- `desktop_ccd_turn_scope` — `index.chunk-CtwayTMM.js:836`
- `desktop_ccd_window_tool` — `index.chunk-CtwayTMM.js:8818`
- `desktop_ccd_work_lost_at_relaunch` — `index.chunk-9hgN2KD3.js:26391`
- `desktop_ccd_workflow_consent_policy_wait_ms` — `index.chunk-CtwayTMM.js:16779`
- `desktop_ccd_workflow_consent_write_failed` — `index.chunk-9hgN2KD3.js:7429`
- `desktop_ccd_workflow_usage_consented` — `index.chunk-9hgN2KD3.js:7431`
- `desktop_ccd_worktree_deps_seeded` — `index.chunk-zPR7Bl2R.js:1774`
- `desktop_ccd_worktree_fallback` — `index.chunk-9hgN2KD3.js:21871`
- `desktop_ccd_worktree_fetch_degraded` — `index.chunk-zPR7Bl2R.js:5261`
- `desktop_ccd_worktree_kept_dirty` — `index.chunk-9hgN2KD3.js:39398`
- `desktop_ccd_worktree_kept_dirty_discarded` — `index.chunk-9hgN2KD3.js:47494`
- `desktop_ccd_worktree_lease_violation` — `index.chunk-9hgN2KD3.js:48884`
- `desktop_ccd_worktree_leftovers` — `index.chunk-9hgN2KD3.js:23664`
- `desktop_ccd_worktree_probe_timeout` — `index.chunk-9hgN2KD3.js:26305`
- `desktop_ccd_worktree_recycle` — `index.chunk-hdp_tf5S.js:1140`
- `desktop_ccd_worktree_removed` — `index.chunk-zPR7Bl2R.js:8256`
- `desktop_ccd_worktree_source_ref_fetch` — `index.chunk-zPR7Bl2R.js:5287`
- `desktop_ccd_worktree_tombstone_reaped` — `index.chunk-zPR7Bl2R.js:8931`
- `desktop_ccd_worktree_transcript_migrated` — `index.chunk-9hgN2KD3.js:26110`
- `desktop_ccd_worktree_write_guard_blocked` — `index.chunk-9hgN2KD3.js:6097`
- `desktop_chat_upload_no_reply` — `index.chunk-DzZc-q0x.js:271911`
- `desktop_claude_auth_url_withheld` — `index.chunk-DzZc-q0x.js:97205`
- `desktop_code_deeplink_received` — `index.chunk-DzZc-q0x.js:142639`
- `desktop_code_deeplink_resume_failed` — `index.chunk-DzZc-q0x.js:141934`
- `desktop_code_deeplink_session_received` — `index.chunk-DzZc-q0x.js:142702`
- `desktop_code_project_link_opened` — `index.chunk-DzZc-q0x.js:142737`
- `desktop_config_load` — `index.chunk-DzZc-q0x.js:79776`
- `desktop_design_pdf_export` — `index.chunk-DzZc-q0x.js:204149`
- `desktop_design_window_closed_before_load` — `index.chunk-DzZc-q0x.js:204279`
- `desktop_design_window_http_error` — `index.chunk-DzZc-q0x.js:204271`
- `desktop_design_window_load` — `index.chunk-DzZc-q0x.js:204257`
- `desktop_design_window_load_failed` — `index.chunk-DzZc-q0x.js:204262`
- `desktop_download_checksum_mismatch` — `index.chunk-DzZc-q0x.js:83116`
- `desktop_download_retry` — `index.chunk-DzZc-q0x.js:83090`
- `desktop_download_verified` — `index.chunk-DzZc-q0x.js:83134`
- `desktop_download_web_origin_mark` — `index.chunk-DzZc-q0x.js:181451`
- `desktop_dxt_install_failed` — `index.chunk-DzZc-q0x.js:186025`
- `desktop_dxt_installed` — `index.chunk-DzZc-q0x.js:185992`
- `desktop_dxt_uninstalled` — `index.chunk-DzZc-q0x.js:185764`
- `desktop_enterprise_host_mode_changed` — `index.chunk-DzZc-q0x.js:170016`
- `desktop_feature_exposure` — `index.chunk-DzZc-q0x.js:97996`
- `desktop_file_save_destination` — `index.chunk-DzZc-q0x.js:181649`
- `desktop_gpu_hw_accel_auto_disable` — `index.chunk-DzZc-q0x.js:167671`
- `desktop_gpu_hw_accel_user_toggle` — `index.chunk-DzZc-q0x.js:211675`
- `desktop_gpu_process_gone` — `index.chunk-DzZc-q0x.js:167884`
- `desktop_hardware_buddy_status` — `index.chunk-BI030auL.js:619`
- `desktop_heavy_work_failed` — `index.chunk-CtwayTMM.js:16256`
- `desktop_hybrid_growthbook_fetch` — `index.chunk-DzZc-q0x.js:97692`
- `desktop_hybrid_transition_refused` — `index.chunk-DzZc-q0x.js:140837`
- `desktop_hybrid_usage_metrics_flush` — `index.chunk-BH309KpT.js:660`
- `desktop_inactive_service_paused` — `index.chunk-Cw19c-e2.js:5045`
- `desktop_inference_routing_skip` — `index.chunk-CRUEtWH-.js:89`
- `desktop_initial_activation` — `index.chunk-DzZc-q0x.js:273695`
- `desktop_launch_button_clicked` — `index.chunk-DzZc-q0x.js:226366`
- `desktop_launch_model_nav_refused` — `index.chunk-BxuN4QYz.js:1071`
- `desktop_launch_preview_activation_near_synthetic` — `index.chunk-DzZc-q0x.js:196008`
- `desktop_launch_preview_allowed_origin_added` — `index.chunk-DzZc-q0x.js:225818`
- `desktop_launch_preview_allowed_origin_removed` — `index.chunk-DzZc-q0x.js:225809`
- `desktop_launch_preview_allowed_origins_cleared` — `index.chunk-DzZc-q0x.js:225813`
- `desktop_launch_preview_artifact_fullscreen` — `index.chunk-DzZc-q0x.js:199438`
- `desktop_launch_preview_blocklist_consult_failed` — `index.chunk-DzZc-q0x.js:135451`
- `desktop_launch_preview_chat_pane_bound` — `index.chunk-DzZc-q0x.js:200090`
- `desktop_launch_preview_chat_pane_created` — `index.chunk-DzZc-q0x.js:225764`
- `desktop_launch_preview_clipboard_write` — `index.chunk-DzZc-q0x.js:202059`
- `desktop_launch_preview_config_url` — `index.chunk-BxuN4QYz.js:1061`
- `desktop_launch_preview_credentialed_nav` — `index.chunk-BxuN4QYz.js:1095`
- `desktop_launch_preview_exported` — `index.chunk-DzZc-q0x.js:201837`
- `desktop_launch_preview_external_nav_policy_blocked` — `index.chunk-DzZc-q0x.js:197044`
- `desktop_launch_preview_external_only_site` — `index.chunk-DzZc-q0x.js:196770`
- `desktop_launch_preview_file_access_prompt` — `index.chunk-DzZc-q0x.js:136414`
- `desktop_launch_preview_find_consent_near_synthetic` — `index.chunk-DzZc-q0x.js:196023`
- `desktop_launch_preview_first_frame_fallback` — `index.chunk-DzZc-q0x.js:198666`
- `desktop_launch_preview_gdrive_view_created` — `index.chunk-DzZc-q0x.js:225777`
- `desktop_launch_preview_governed_held_blocked` — `index.chunk-DzZc-q0x.js:193916`
- `desktop_launch_preview_hide_refused` — `index.chunk-DzZc-q0x.js:200594`
- `desktop_launch_preview_link_routed` — `index.chunk-DzZc-q0x.js:196635`
- `desktop_launch_preview_link_routed_external` — `index.chunk-DzZc-q0x.js:226108`
- `desktop_launch_preview_load_failed` — `index.chunk-DzZc-q0x.js:198296`
- `desktop_launch_preview_media_permission_denied` — `index.chunk-DzZc-q0x.js:194509`
- `desktop_launch_preview_nav_redirect_blocked` — `index.chunk-DzZc-q0x.js:196883`
- `desktop_launch_preview_open_in_browser` — `index.chunk-DzZc-q0x.js:225832`
- `desktop_launch_preview_origin_prompt` — `index.chunk-DzZc-q0x.js:136401`
- `desktop_launch_preview_overlap_healed` — `index.chunk-DzZc-q0x.js:200818`
- `desktop_launch_preview_pdf_file_tab` — `index.chunk-DzZc-q0x.js:225685`
- `desktop_launch_preview_pdf_nav_download` — `index.chunk-DzZc-q0x.js:194889`
- `desktop_launch_preview_ssrf_blocked` — `index.chunk-DzZc-q0x.js:193900`
- `desktop_launch_preview_subframe_click_gate` — `index.chunk-BxuN4QYz.js:634`
- `desktop_launch_preview_transcript_link_opened` — `index.chunk-DzZc-q0x.js:196882`
- `desktop_launch_preview_trust_grant_minted` — `index.chunk-DzZc-q0x.js:136321`
- `desktop_launch_preview_viewport_emulation` — `index.chunk-DzZc-q0x.js:202282`
- `desktop_launch_preview_visible_overlap` — `index.chunk-DzZc-q0x.js:200706`
- `desktop_launch_tool_used` — `index.chunk-BxuN4QYz.js:875`
- `desktop_local_agent_mode_session_initialized` — `index.chunk-Cb2x-E4A.js:7301`
- `desktop_login_callback_duplicate_suppressed` — `index.chunk-DzZc-q0x.js:141880`
- `desktop_login_callback_evicted` — `index.chunk-DzZc-q0x.js:142373`
- `desktop_login_callback_received` — `index.chunk-DzZc-q0x.js:142365`
- `desktop_login_failed` — `index.chunk-DzZc-q0x.js:142141`
- `desktop_login_succeeded` — `index.chunk-DzZc-q0x.js:128874`
- `desktop_main_event_loop_stall` — `index.chunk-DzZc-q0x.js:220948`
- `desktop_main_process_crash_reported` — `index.chunk-DzZc-q0x.js:257178`
- `desktop_main_view_http_error` — `index.chunk-DzZc-q0x.js:139235`
- `desktop_main_view_load_failed` — `index.chunk-DzZc-q0x.js:139224`
- `desktop_main_view_load_recovered` — `index.chunk-DzZc-q0x.js:139251`
- `desktop_main_view_load_retry_exhausted` — `index.chunk-DzZc-q0x.js:139041`
- `desktop_main_view_redirect_blocked` — `index.chunk-DzZc-q0x.js:139095`
- `desktop_main_view_render_process_gone` — `index.chunk-DzZc-q0x.js:139306`
- `desktop_main_view_unresponsive` — `index.chunk-DzZc-q0x.js:139268`
- `desktop_managed_config_unreadable` — `index.chunk-DzZc-q0x.js:170034`
- `desktop_mcp_tool_call_gate` — `index.chunk-CtwayTMM.js:11796`
- `desktop_mcp_unexpected_close` — `index.chunk-DzZc-q0x.js:184963`
- `desktop_mdm_config_detected` — `index.chunk-DzZc-q0x.js:170027`
- `desktop_media_permission_probe` — `index.chunk-DzZc-q0x.js:256967`
- `desktop_notification_displayed` — `index.chunk-DzZc-q0x.js:165113`
- `desktop_notification_failed` — `index.chunk-DzZc-q0x.js:165114`
- `desktop_notification_interaction` — `index.chunk-DzZc-q0x.js:165182`
- `desktop_notification_reachability` — `index.chunk-DzZc-q0x.js:165165`
- `desktop_notification_shown` — `index.chunk-DzZc-q0x.js:165399`
- `desktop_notification_suppressed` — `index.chunk-DzZc-q0x.js:165306`
- `desktop_oauth_failed` — `index.chunk-DzZc-q0x.js:127165`
- `desktop_oauth_persist_encryption_unavailable` — `index.chunk-DzZc-q0x.js:127181`
- `desktop_oauth_return_navigate` — `index.chunk-DzZc-q0x.js:142022`
- `desktop_oauth_succeeded` — `index.chunk-DzZc-q0x.js:127162`
- `desktop_oauth_v2_cache_cleared` — `index.chunk-DzZc-q0x.js:128439`
- `desktop_oauth_v2_cache_miss` — `index.chunk-DzZc-q0x.js:128431`
- `desktop_os_open_handlers_ready` — `index.chunk-DzZc-q0x.js:139368`
- `desktop_os_surface_invoked` — `index.chunk-DzZc-q0x.js:142249`
- `desktop_ownership_fix` — `index.chunk-7VnKz3Ls.js:45`
- `desktop_preview_cdp_memory_guard` — `index.chunk-DzZc-q0x.js:190999`
- `desktop_preview_jitless_kill_switch_transition` — `index.chunk-DzZc-q0x.js:193231`
- `desktop_process_memory_high_water` — `index.chunk-DzZc-q0x.js:220589`
- `desktop_process_memory_sample` — `index.chunk-DzZc-q0x.js:220544`
- `desktop_project_detection_failed` — `index.chunk-Dk0Au9Gx.js:284`
- `desktop_quick_entry_dictation_start` — `index.chunk-DzZc-q0x.js:164099`
- `desktop_quick_entry_show` — `index.chunk-DzZc-q0x.js:164073`
- `desktop_quick_entry_submit` — `index.chunk-DzZc-q0x.js:182056`
- `desktop_quit_cleanup_summary` — `index.chunk-DzZc-q0x.js:130483`
- `desktop_quit_guard_prompt` — `index.chunk-DzZc-q0x.js:103518`
- `desktop_quit_handler_timeout` — `index.chunk-DzZc-q0x.js:131299`
- `desktop_quit_watchdog_fired` — `index.chunk-DzZc-q0x.js:131341`
- `desktop_session_title_set` — `index.chunk-CtwayTMM.js:231`
- `desktop_ssh_adoptable_redial` — `index.chunk-9hgN2KD3.js:25206`
- `desktop_ssh_auto_reconnected` — `index.chunk-D0ZMBa2D.js:6692`
- `desktop_ssh_background_readopt` — `index.chunk-9hgN2KD3.js:25048`
- `desktop_ssh_cold_send_held` — `index.chunk-9hgN2KD3.js:35519`
- `desktop_ssh_cold_send_rearmed` — `index.chunk-9hgN2KD3.js:35823`
- `desktop_ssh_cold_send_released` — `index.chunk-9hgN2KD3.js:36165`
- `desktop_ssh_cold_send_sign_in_redelivery` — `index.chunk-9hgN2KD3.js:36111`
- `desktop_ssh_cold_send_stalled` — `index.chunk-9hgN2KD3.js:36091`
- `desktop_ssh_connect_awaiting_person` — `index.chunk-D0ZMBa2D.js:4105`
- `desktop_ssh_connect_interrupted` — `index.chunk-D0ZMBa2D.js:4358`
- `desktop_ssh_connected` — `index.chunk-D0ZMBa2D.js:5647`
- `desktop_ssh_connection_failed` — `index.chunk-D0ZMBa2D.js:5894`
- `desktop_ssh_connection_skipped` — `index.chunk-D0ZMBa2D.js:3866`
- `desktop_ssh_disconnected` — `index.chunk-D0ZMBa2D.js:5987`
- `desktop_ssh_host_mcp_applied` — `index.chunk-9hgN2KD3.js:48606`
- `desktop_ssh_identity_hold_ended` — `index.chunk-D0ZMBa2D.js:4523`
- `desktop_ssh_input_kept_across_loss` — `index.chunk-9hgN2KD3.js:36218`
- `desktop_ssh_kept_input_verdict` — `index.chunk-9hgN2KD3.js:33910`
- `desktop_ssh_mcp_hook_servers_uncovered` — `index.chunk-9hgN2KD3.js:40739`
- `desktop_ssh_orphan_kill` — `index.chunk-9hgN2KD3.js:37147`
- `desktop_ssh_password_remembered` — `index.chunk-D0ZMBa2D.js:4316`
- `desktop_ssh_plugin_sync_failed` — `index.chunk-9hgN2KD3.js:38445`
- `desktop_ssh_process_dormant` — `index.chunk-9hgN2KD3.js:58389`
- `desktop_ssh_process_loss` — `index.chunk-9hgN2KD3.js:25114`
- `desktop_ssh_process_reattached` — `index.chunk-9hgN2KD3.js:37056`
- `desktop_ssh_reachability_watch` — `index.chunk-D0ZMBa2D.js:6462`
- `desktop_ssh_reattach_gap` — `index.chunk-9hgN2KD3.js:37073`
- `desktop_ssh_reconnect_attempt` — `index.chunk-D0ZMBa2D.js:6795`
- `desktop_ssh_reconnect_flapping` — `index.chunk-D0ZMBa2D.js:6006`
- `desktop_ssh_reconnect_held` — `index.chunk-D0ZMBa2D.js:4575`
- `desktop_ssh_reconnect_needs_attention` — `index.chunk-D0ZMBa2D.js:6517`
- `desktop_ssh_reconnect_prolonged` — `index.chunk-D0ZMBa2D.js:6578`
- `desktop_ssh_relaunch_reattach` — `index.chunk-9hgN2KD3.js:24581`
- `desktop_ssh_send_answered_from_last_failure` — `index.chunk-9hgN2KD3.js:43299`
- `desktop_ssh_tool_grant_changed` — `index.chunk-9hgN2KD3.js:24409`
- `desktop_ssh_waiting_input_restored` — `index.chunk-9hgN2KD3.js:46647`
- `desktop_ssh_wake_probe` — `index.chunk-D0ZMBa2D.js:3131`
- `desktop_stealth_update_triggered` — `index.chunk-DzZc-q0x.js:271698`
- `desktop_store_read_stats` — `index.chunk-DzZc-q0x.js:271519`
- `desktop_third_party_history_import` — `index.chunk-Df16ASFW.js:242`
- `desktop_tray_usage_menu_action` — `index.chunk-DzZc-q0x.js:212293`
- `desktop_tray_usage_menu_show` — `index.chunk-DzZc-q0x.js:212325`
- `desktop_universal_link_bounced` — `index.chunk-DzZc-q0x.js:142826`
- `desktop_universal_link_received` — `index.chunk-DzZc-q0x.js:142847`
- `desktop_update_applied` — `index.chunk-DzZc-q0x.js:182912`
- `desktop_update_auto_install` — `index.chunk-DzZc-q0x.js:183176`
- `desktop_update_auto_restart` — `index.chunk-DzZc-q0x.js:183175`
- `desktop_update_available` — `index.chunk-DzZc-q0x.js:182863`
- `desktop_update_check_started` — `index.chunk-DzZc-q0x.js:182851`
- `desktop_update_disabled` — `index.chunk-DzZc-q0x.js:182958`
- `desktop_update_downloaded` — `index.chunk-DzZc-q0x.js:182883`
- `desktop_update_error` — `index.chunk-DzZc-q0x.js:182836`
- `desktop_update_install_failed` — `index.chunk-DzZc-q0x.js:182631`
- `desktop_update_manual_install` — `index.chunk-DzZc-q0x.js:131222`
- `desktop_update_not_available` — `index.chunk-DzZc-q0x.js:182874`
- `desktop_update_relaunch_marker_read` — `index.chunk-DzZc-q0x.js:142936`
- `desktop_update_replacement_failed` — `index.chunk-DzZc-q0x.js:183036`
- `desktop_update_replacement_triggered` — `index.chunk-DzZc-q0x.js:183070`
- `desktop_update_required` — `index.chunk-Cq0kop3I.js:97`
- `desktop_update_rollback_detected` — `index.chunk-DzZc-q0x.js:183093`
- `desktop_update_rollback_unstaged` — `index.chunk-DzZc-q0x.js:182667`
- `desktop_update_stealth_install` — `index.chunk-DzZc-q0x.js:271699`
- `desktop_update_unclean_exit_install` — `index.chunk-DzZc-q0x.js:182406`
- `desktop_wake_scheduler_darkwake_detected` — `index.chunk-DzZc-q0x.js:162582`
- `desktop_wake_scheduler_disabled` — `index.chunk-DzZc-q0x.js:162923`
- `desktop_wake_scheduler_resume_correlation` — `index.chunk-DzZc-q0x.js:162720`
- `desktop_wake_scheduler_schedule_failed` — `index.chunk-DzZc-q0x.js:162670`
- `desktop_wake_scheduler_scheduled` — `index.chunk-DzZc-q0x.js:162660`
- `desktop_wake_scheduler_wake_duration` — `index.chunk-DzZc-q0x.js:162683`
- `desktop_window_open_passthrough` — `index.chunk-DzZc-q0x.js:138400`
- `desktop_windows_app_job_check` — `index.chunk-DzZc-q0x.js:272089`


## lam (163)

- `lam_auto_mode_always_allow_overridden` — `index.chunk-CW7e72sW.js:2082`
- `lam_bridge_abandon_deregister` — `index.chunk-DzZc-q0x.js:238782`
- `lam_bridge_device_reload` — `index.chunk-DzZc-q0x.js:218688`
- `lam_bridge_dispatch_seed_skipped` — `index.chunk-DzZc-q0x.js:240151`
- `lam_bridge_dispatch_seed_written` — `index.chunk-DzZc-q0x.js:240204`
- `lam_bridge_event_attestation` — `index.chunk-D0DKKP9Q.js:385`
- `lam_bridge_followup_fast_path` — `index.chunk-DzZc-q0x.js:240449`
- `lam_bridge_ingress_token_refresh` — `index.chunk-DzZc-q0x.js:240319`
- `lam_bridge_interrupt_received` — `index.chunk-DzZc-q0x.js:240539`
- `lam_bridge_local_mcp_reannounce` — `index.chunk-BdiCQFUS.js:105`
- `lam_bridge_local_mcp_retry` — `index.chunk-BdiCQFUS.js:143`
- `lam_bridge_message_forwarded` — `index.chunk-DzZc-q0x.js:241230`
- `lam_bridge_permission_auto_denied` — `index.chunk-DzZc-q0x.js:240737`
- `lam_bridge_permission_posted` — `index.chunk-DzZc-q0x.js:241058`
- `lam_bridge_permission_resolved` — `index.chunk-DzZc-q0x.js:240520`
- `lam_bridge_poll_gave_up` — `index.chunk-DzZc-q0x.js:239795`
- `lam_bridge_poll_reregister` — `index.chunk-DzZc-q0x.js:239806`
- `lam_bridge_reconnect_persisted_session` — `index.chunk-DzZc-q0x.js:241484`
- `lam_bridge_registration_completed` — `index.chunk-DzZc-q0x.js:239462`
- `lam_bridge_registration_failed` — `index.chunk-DzZc-q0x.js:239493`
- `lam_bridge_session_bound` — `index.chunk-DzZc-q0x.js:240031`
- `lam_bridge_session_collision` — `index.chunk-DzZc-q0x.js:239948`
- `lam_bridge_session_created` — `index.chunk-DzZc-q0x.js:241515`
- `lam_bridge_stale_turn_rearm` — `index.chunk-DzZc-q0x.js:240665`
- `lam_bridge_stale_turn_reset` — `index.chunk-DzZc-q0x.js:240678`
- `lam_bridge_stop_task_received` — `index.chunk-DzZc-q0x.js:240569`
- `lam_bridge_system_resumed` — `index.chunk-DzZc-q0x.js:240793`
- `lam_bridge_transport_cap_redispatch` — `index.chunk-DzZc-q0x.js:240356`
- `lam_bridge_transport_closed` — `index.chunk-DzZc-q0x.js:240086`
- `lam_bridge_transport_connected` — `index.chunk-DzZc-q0x.js:240109`
- `lam_bridge_transport_dead` — `index.chunk-DzZc-q0x.js:240337`
- `lam_bridge_transport_reconnect_capped` — `index.chunk-DzZc-q0x.js:240243`
- `lam_bridge_unexpected_v1_work` — `index.chunk-DzZc-q0x.js:239894`
- `lam_bridge_user_message_received` — `index.chunk-DzZc-q0x.js:240411`
- `lam_builtin_tool_auto_mode` — `index.chunk-Cb2x-E4A.js:13402`
- `lam_cli_plugin_exec` — `index.chunk-Cb2x-E4A.js:4727`
- `lam_cli_plugin_exec_completed` — `index.chunk-Cb2x-E4A.js:4756`
- `lam_cli_plugin_oauth` — `index.chunk-DzZc-q0x.js:106680`
- `lam_cli_plugin_policy_sync` — `index.chunk-Cb2x-E4A.js:15375`
- `lam_cli_plugin_stub_provision` — `index.chunk-DzZc-q0x.js:205748`
- `lam_cowork_managed_dirs_migration` — `index.chunk-DzZc-q0x.js:236554`
- `lam_cowork_root_info` — `index.chunk-Cb2x-E4A.js:16357`
- `lam_dispatch_auto_reset` — `index.chunk-Cb2x-E4A.js:18201`
- `lam_dispatch_list_projects` — `index.chunk-BnxrnbfJ.js:440`
- `lam_dispatch_list_sessions` — `index.chunk-Cb2x-E4A.js:12179`
- `lam_dispatch_read_transcript` — `index.chunk-Cb2x-E4A.js:12243`
- `lam_dispatch_send_message` — `index.chunk-BnxrnbfJ.js:381`
- `lam_dispatch_start_code_task` — `index.chunk-BnxrnbfJ.js:310`
- `lam_dispatch_start_task` — `index.chunk-BnxrnbfJ.js:174`
- `lam_documents_conflict_recovered` — `index.chunk-Cb2x-E4A.js:6859`
- `lam_documents_tool_error` — `index.chunk-Cb2x-E4A.js:6853`
- `lam_documents_write_call` — `index.chunk-Cb2x-E4A.js:6856`
- `lam_feature_support_evaluated` — `index.chunk-DzZc-q0x.js:163407`
- `lam_folder_grant_refused_protected` — `index.chunk-DJ7PvxxQ.js:547`
- `lam_global_instructions_restored` — `index.chunk-Cb2x-E4A.js:9399`
- `lam_held_routine_release` — `index.chunk-DzZc-q0x.js:261126`
- `lam_hipaa_gate_blocked` — `index.chunk-CtwayTMM.js:2523`
- `lam_hipaa_log_retention_pass` — `index.chunk-ByNfDjmK.js:81`
- `lam_hipaa_pref_synced` — `index.chunk-DzZc-q0x.js:97459`
- `lam_hipaa_session_retention_pass` — `index.chunk-DkWfC5oE.js:87`
- `lam_host_loop_session_started` — `index.chunk-Cb2x-E4A.js:12046`
- `lam_host_loop_spawn_settings` — `index.chunk-Cb2x-E4A.js:14753`
- `lam_host_loop_spawn_settings_swept` — `index.chunk-CW7e72sW.js:1824`
- `lam_idle_grace_expired` — `index.chunk-Cb2x-E4A.js:16417`
- `lam_idle_grace_hit` — `index.chunk-Cb2x-E4A.js:18834`
- `lam_internal_mcp_server_created` — `index.chunk-CtwayTMM.js:11325`
- `lam_max_turns_hit` — `index.chunk-Cb2x-E4A.js:7641`
- `lam_mcp_server_connected` — `index.chunk-B-e6-3-o.js:675`
- `lam_mcp_server_connection_failed` — `index.chunk-B-e6-3-o.js:659`
- `lam_mcp_server_disconnected` — `index.chunk-DzZc-q0x.js:102763`
- `lam_mcp_servers_setup_summary` — `index.chunk-CtwayTMM.js:12692`
- `lam_mcp_tool_call_completed` — `index.chunk-CtwayTMM.js:11214`
- `lam_mcp_tool_call_stalled` — `index.chunk-CtwayTMM.js:11243`
- `lam_message_cycle_outcome` — `index.chunk-Cb2x-E4A.js:18547`
- `lam_message_cycle_start` — `index.chunk-Cb2x-E4A.js:15263`
- `lam_model_selection_fallback` — `index.chunk-DzZc-q0x.js:237400`
- `lam_mount_demoted` — `index.chunk-Cb2x-E4A.js:20976`
- `lam_plugin_binary_asset_provision` — `index.chunk-CwacCE28.js:360`
- `lam_porter_handoff_claim_binding` — `index.chunk-C6vqfZUf.js:2630`
- `lam_project_sync_failed` — `index.chunk-DzZc-q0x.js:261617`
- `lam_remote_auto_save` — `index.chunk-Dpbk5XYH.js:4677`
- `lam_remote_commit` — `index.chunk-Dpbk5XYH.js:4287`
- `lam_remote_create_artifact` — `index.chunk-Dpbk5XYH.js:4975`
- `lam_remote_files_api_attachment_staged` — `index.chunk-CW7e72sW.js:2280`
- `lam_remote_folder_consent_outcome` — `index.chunk-CW7e72sW.js:1571`
- `lam_remote_folder_grant_changed` — `index.chunk-Dpbk5XYH.js:1217`
- `lam_remote_folder_markers` — `index.chunk-CW7e72sW.js:3291`
- `lam_remote_folder_skills_staged` — `index.chunk-CW7e72sW.js:3356`
- `lam_remote_get_device_info` — `index.chunk-DzZc-q0x.js:218175`
- `lam_remote_list_artifacts` — `index.chunk-Dpbk5XYH.js:5092`
- `lam_remote_list_dir` — `index.chunk-Dpbk5XYH.js:3575`
- `lam_remote_request_delete_permission` — `index.chunk-Dpbk5XYH.js:5284`
- `lam_remote_request_folder_access` — `index.chunk-Dpbk5XYH.js:2987`
- `lam_remote_stage` — `index.chunk-Dpbk5XYH.js:3713`
- `lam_remote_tools_device_state` — `index.chunk-DzZc-q0x.js:215688`
- `lam_remote_update_artifact` — `index.chunk-Dpbk5XYH.js:5032`
- `lam_scheduled_store_launcher_era_denied` — `index.chunk-Cb2x-E4A.js:8797`
- `lam_scheduled_task_hung_run_reap` — `index.chunk-Cb2x-E4A.js:17956`
- `lam_scheduled_task_stale_run_reaped` — `index.chunk-Cb2x-E4A.js:17934`
- `lam_scheduled_task_stale_run_skipped` — `index.chunk-Cb2x-E4A.js:17920`
- `lam_scheduled_task_tool_auto_mode` — `index.chunk-Cb2x-E4A.js:13384`
- `lam_session_app_quit` — `index.chunk-Cb2x-E4A.js:6730`
- `lam_session_archived` — `index.chunk-Cb2x-E4A.js:19728`
- `lam_session_deleted` — `index.chunk-Cb2x-E4A.js:19925`
- `lam_session_deletion_failed` — `index.chunk-CW7e72sW.js:2024`
- `lam_session_first_token` — `index.chunk-Cb2x-E4A.js:7472`
- `lam_session_initialization_failed` — `index.chunk-Cb2x-E4A.js:14956`
- `lam_session_mcp_servers_resolved` — `index.chunk-Cb2x-E4A.js:14579`
- `lam_session_query_error` — `index.chunk-Cb2x-E4A.js:7438`
- `lam_session_rewind` — `index.chunk-Cb2x-E4A.js:19412`
- `lam_session_rewind_aborted` — `index.chunk-Cb2x-E4A.js:19358`
- `lam_session_rewind_rejected_dead_branch` — `index.chunk-Cb2x-E4A.js:19381`
- `lam_session_start_attempted` — `index.chunk-Cb2x-E4A.js:15354`
- `lam_session_step_completed` — `index.chunk-Cb2x-E4A.js:15392`
- `lam_session_stopped` — `index.chunk-Cb2x-E4A.js:19677`
- `lam_session_timeout` — `index.chunk-Cb2x-E4A.js:6658`
- `lam_session_turn_completed` — `index.chunk-Cb2x-E4A.js:7614`
- `lam_sessions_cache_prune` — `index.chunk-DzZc-q0x.js:205099`
- `lam_sessions_disk_cleanup` — `index.chunk-DzZc-q0x.js:205291`
- `lam_sessions_disk_low` — `index.chunk-DzZc-q0x.js:205274`
- `lam_shared_plugin_cache` — `index.chunk-Cb2x-E4A.js:13771`
- `lam_sp_variant_resolved` — `index.chunk-Cb2x-E4A.js:10080`
- `lam_space_memory_tool_call` — `index.chunk-DimsU4DE.js:117`
- `lam_stop_button_completed` — `index.chunk-CW7e72sW.js:1977`
- `lam_stop_button_received` — `index.chunk-CW7e72sW.js:1965`
- `lam_storage_cleanup` — `index.chunk-DzZc-q0x.js:242166`
- `lam_stream_ended_diagnostic` — `index.chunk-Cb2x-E4A.js:7817`
- `lam_system_prompt_built` — `index.chunk-Cb2x-E4A.js:10184`
- `lam_system_sleep` — `index.chunk-Cb2x-E4A.js:6689`
- `lam_system_wake` — `index.chunk-Cb2x-E4A.js:6703`
- `lam_tool_permission_renotify` — `index.chunk-9hgN2KD3.js:4324`
- `lam_tool_permission_requested` — `index.chunk-9hgN2KD3.js:7285`
- `lam_tool_permission_responded` — `index.chunk-9hgN2KD3.js:4293`
- `lam_tool_permission_stalled` — `index.chunk-9hgN2KD3.js:7299`
- `lam_vm_auto_reinstall_triggered` — `index.chunk-DzZc-q0x.js:179694`
- `lam_vm_bundle_delta_applied` — `index.chunk-DzZc-q0x.js:177880`
- `lam_vm_bundle_delta_failed` — `index.chunk-DzZc-q0x.js:177741`
- `lam_vm_bundle_download_completed` — `index.chunk-DzZc-q0x.js:179003`
- `lam_vm_bundle_download_failed` — `index.chunk-DzZc-q0x.js:179079`
- `lam_vm_bundle_sweep` — `index.chunk-DzZc-q0x.js:178643`
- `lam_vm_cache_decompress_completed` — `index.chunk-DzZc-q0x.js:178746`
- `lam_vm_cache_decompress_failed` — `index.chunk-DzZc-q0x.js:178731`
- `lam_vm_download_skipped_nospace` — `index.chunk-DzZc-q0x.js:178886`
- `lam_vm_heartbeat_failure` — `index.chunk-DzZc-q0x.js:177955`
- `lam_vm_kernel_bug_detected` — `index.chunk-DzZc-q0x.js:177129`
- `lam_vm_oneshot_exited` — `index.chunk-DzZc-q0x.js:178199`
- `lam_vm_oom_kill_detected` — `index.chunk-DzZc-q0x.js:176991`
- `lam_vm_process_exited` — `index.chunk-DzZc-q0x.js:177250`
- `lam_vm_process_spawned` — `index.chunk-DzZc-q0x.js:178334`
- `lam_vm_shutdown_completed` — `index.chunk-DzZc-q0x.js:179454`
- `lam_vm_shutdown_failed` — `index.chunk-DzZc-q0x.js:179463`
- `lam_vm_startup_completed` — `index.chunk-DzZc-q0x.js:179556`
- `lam_vm_startup_failed` — `index.chunk-DzZc-q0x.js:179394`
- `lam_vm_startup_step` — `index.chunk-DzZc-q0x.js:178378`
- `lam_vm_warm_download_completed` — `index.chunk-B9vFJEp2.js:134`
- `lam_vm_warm_download_failed` — `index.chunk-B9vFJEp2.js:144`
- `lam_vm_warm_download_started` — `index.chunk-B9vFJEp2.js:104`
- `lam_vm_warm_promote_completed` — `index.chunk-B9vFJEp2.js:239`
- `lam_vm_warm_promote_failed` — `index.chunk-B9vFJEp2.js:225`
- `lam_vm_warm_promote_skipped_nospace` — `index.chunk-B9vFJEp2.js:197`
- `lam_web_fetch_policy_blocked` — `index.chunk-Cb2x-E4A.js:8424`
- `lam_workflow_consent_write_failed` — `index.chunk-Cb2x-E4A.js:9079`
- `lam_workflow_usage_consented` — `index.chunk-Cb2x-E4A.js:9084`


## cowork (27)

- `cowork_3p_diagnostic_bundle` — `index.chunk-DzZc-q0x.js:208902`
- `cowork_artifacts_auto_publish_failed` — `index.chunk-DzZc-q0x.js:234416`
- `cowork_artifacts_auto_published` — `index.chunk-DzZc-q0x.js:234422`
- `cowork_artifacts_bridge_call` — `index.chunk-DzZc-q0x.js:235794`
- `cowork_artifacts_created` — `index.chunk-DzZc-q0x.js:234276`
- `cowork_artifacts_deleted` — `index.chunk-DzZc-q0x.js:234492`
- `cowork_artifacts_imported` — `index.chunk-DzZc-q0x.js:234553`
- `cowork_artifacts_share_pulled` — `index.chunk-DzZc-q0x.js:234797`
- `cowork_artifacts_shared` — `index.chunk-DzZc-q0x.js:234675`
- `cowork_artifacts_unshared` — `index.chunk-DzZc-q0x.js:234730`
- `cowork_artifacts_updated` — `index.chunk-DzZc-q0x.js:234367`
- `cowork_artifacts_verified` — `index.chunk-DJ7PvxxQ.js:1417`
- `cowork_artifacts_version_restored` — `index.chunk-DzZc-q0x.js:234444`
- `cowork_consolidate_memory_called` — `index.chunk-Cb2x-E4A.js:13462`
- `cowork_memory_sync_pull` — `index.chunk-Cb2x-E4A.js:383`
- `cowork_memory_sync_push` — `index.chunk-Cb2x-E4A.js:443`
- `cowork_memory_sync_stopped` — `index.chunk-Cb2x-E4A.js:340`
- `cowork_remote_attestation` — `index.chunk-DzZc-q0x.js:214646`
- `cowork_scheduled_task_migration_reverted` — `index.chunk-DzZc-q0x.js:231463`
- `cowork_scheduled_tasks_auto_migrated` — `index.chunk-Cb2x-E4A.js:6280`
- `cowork_scheduled_tasks_auto_migration_sweep` — `index.chunk-Cb2x-E4A.js:5978`
- `cowork_scheduled_tasks_inventory` — `index.chunk-DzZc-q0x.js:232326`
- `cowork_scheduled_tasks_run_completed` — `index.chunk-Cb2x-E4A.js:6442`
- `cowork_skill_saved` — `index.chunk-DJ7PvxxQ.js:232`
- `cowork_space_inventory_item` — `index.chunk-Cb2x-E4A.js:1438`
- `cowork_space_migration_outcome` — `index.chunk-DzZc-q0x.js:252763`
- `cowork_spaces_inventory` — `index.chunk-Cb2x-E4A.js:1430`

## ccd_simulator (20)

- `ccd_simulator_access_toggle` — `index.chunk-DBDF46Lo.js:3816`
- `ccd_simulator_annotate` — `index.chunk-DBDF46Lo.js:3749`
- `ccd_simulator_approval_decision` — `index.chunk-DBDF46Lo.js:3788`
- `ccd_simulator_attach` — `index.chunk-DBDF46Lo.js:3606`
- `ccd_simulator_consent_decision` — `index.chunk-DBDF46Lo.js:3797`
- `ccd_simulator_consent_waived` — `index.chunk-DBDF46Lo.js:3806`
- `ccd_simulator_detach` — `index.chunk-DBDF46Lo.js:3639`
- `ccd_simulator_impression` — `index.chunk-DBDF46Lo.js:3560`
- `ccd_simulator_inspect` — `index.chunk-DBDF46Lo.js:3752`
- `ccd_simulator_manual_gesture` — `index.chunk-DBDF46Lo.js:3739`
- `ccd_simulator_repin_decision` — `index.chunk-DBDF46Lo.js:3809`
- `ccd_simulator_screenshot` — `index.chunk-DBDF46Lo.js:3746`
- `ccd_simulator_session_summary` — `index.chunk-DBDF46Lo.js:3648`
- `ccd_simulator_setup_cta` — `index.chunk-DBDF46Lo.js:3577`
- `ccd_simulator_setup_probe_failed` — `index.chunk-DBDF46Lo.js:3590`
- `ccd_simulator_setup_step` — `index.chunk-DBDF46Lo.js:3570`
- `ccd_simulator_shutdown` — `index.chunk-DBDF46Lo.js:3770`
- `ccd_simulator_stream_settings` — `index.chunk-DBDF46Lo.js:3775`
- `ccd_simulator_tool_call` — `index.chunk-DBDF46Lo.js:3693`
- `ccd_simulator_video_recording` — `index.chunk-DBDF46Lo.js:3761`

## cu (20)

- `cu_app_dispatch` — `index.chunk-CtwayTMM.js:1382`
- `cu_app_helper_crash` — `index.chunk-DzZc-q0x.js:171243`
- `cu_app_helper_probe` — `index.chunk-DzZc-q0x.js:171228`
- `cu_gate_reconcile` — `index.chunk-DzZc-q0x.js:263669`
- `cu_lock_acquired` — `index.chunk-zaGWxIS8.js:516`
- `cu_lock_released` — `index.chunk-zaGWxIS8.js:289`
- `cu_preference_change` — `index.chunk-DzZc-q0x.js:270882`
- `cu_session_config` — `index.chunk-CtwayTMM.js:1438`
- `cu_setting_changed` — `index.chunk-DzZc-q0x.js:270870`
- `cu_takeover_approved` — `index.chunk-DzZc-q0x.js:166440`
- `cu_teach_session` — `index.chunk-Cb2x-E4A.js:18062`
- `cu_tool_call` — `index.chunk-CtwayTMM.js:1513`
- `cu_watch_record_choice` — `index.chunk-DzZc-q0x.js:259664`
- `cu_watch_record_chooser_shown` — `index.chunk-DzZc-q0x.js:259659`
- `cu_watch_record_ended` — `index.chunk-DzZc-q0x.js:259590`
- `cu_watch_record_held_dropped` — `index.chunk-DzZc-q0x.js:259291`
- `cu_watch_record_narration_failed` — `index.chunk-DzZc-q0x.js:259341`
- `cu_watch_record_permission_blocked` — `index.chunk-DzZc-q0x.js:259183`
- `cu_watch_record_pill_hold_timeout` — `index.chunk-DzZc-q0x.js:259861`
- `cu_watch_record_started` — `index.chunk-DzZc-q0x.js:259765`

## chrome_bridge (16)

- `chrome_bridge_browser_selected` — `index.chunk-DzZc-q0x.js:146182`
- `chrome_bridge_connection_failed` — `index.chunk-DzZc-q0x.js:146371`
- `chrome_bridge_connection_started` — `index.chunk-DzZc-q0x.js:146401`
- `chrome_bridge_connection_succeeded` — `index.chunk-DzZc-q0x.js:146482`
- `chrome_bridge_disconnected` — `index.chunk-DzZc-q0x.js:146443`
- `chrome_bridge_handshake_timeout` — `index.chunk-DzZc-q0x.js:146353`
- `chrome_bridge_peer_connected` — `index.chunk-DzZc-q0x.js:146502`
- `chrome_bridge_peer_disconnected` — `index.chunk-DzZc-q0x.js:146526`
- `chrome_bridge_reconnect_exhausted` — `index.chunk-DzZc-q0x.js:146795`
- `chrome_bridge_routing_ack` — `index.chunk-DzZc-q0x.js:146549`
- `chrome_bridge_tool_call_completed` — `index.chunk-DzZc-q0x.js:145714`
- `chrome_bridge_tool_call_error` — `index.chunk-DzZc-q0x.js:145685`
- `chrome_bridge_tool_call_late_result` — `index.chunk-DzZc-q0x.js:146670`
- `chrome_bridge_tool_call_started` — `index.chunk-DzZc-q0x.js:145679`
- `chrome_bridge_tool_call_timeout` — `index.chunk-DzZc-q0x.js:145697`
- `chrome_bridge_transport_selected` — `index.chunk-DzZc-q0x.js:167239`


## custom3p (11)

- `custom3p_bootstrap_boot_retry_settled` — `index.chunk-DzZc-q0x.js:125755`
- `custom3p_bootstrap_consent_decided` — `index.chunk-BM9oWqeP.js:127`
- `custom3p_bootstrap_resolved` — `index.chunk-DzZc-q0x.js:124110`
- `custom3p_config_relaunch_auto_restart` — `index.chunk-DzZc-q0x.js:121325`
- `custom3p_config_relaunch_enforced` — `index.chunk-DzZc-q0x.js:121301`
- `custom3p_credential_heal` — `index.chunk-DzZc-q0x.js:125132`
- `custom3p_credential_rejected` — `index.chunk-DzZc-q0x.js:125099`
- `custom3p_idp_silent_reauthorize` — `index.chunk-DJn657_y.js:297`
- `custom3p_left_for_claudeai` — `index.chunk-DzZc-q0x.js:139896`
- `custom3p_self_hosted_assertion` — `index.chunk-DzZc-q0x.js:121765`
- `custom3p_self_hosted_renew_ahead` — `index.chunk-DzZc-q0x.js:122156`

## grand_prix (10)

- `grand_prix_code_prompt_outcome` — `index.chunk-DzZc-q0x.js:154882`
- `grand_prix_credential_request_outcome` — `index.chunk-DzZc-q0x.js:154282`
- `grand_prix_disconnect` — `index.chunk-DzZc-q0x.js:152592`
- `grand_prix_fill_outcome` — `index.chunk-DzZc-q0x.js:153560`
- `grand_prix_list_outcome` — `index.chunk-DzZc-q0x.js:153506`
- `grand_prix_nudge` — `index.chunk-DzZc-q0x.js:152379`
- `grand_prix_pair_outcome` — `index.chunk-DzZc-q0x.js:152575`
- `grand_prix_stub_response` — `index.chunk-DzZc-q0x.js:154788`
- `grand_prix_teardown` — `index.chunk-DzZc-q0x.js:153676`
- `grand_prix_tool_refused` — `index.chunk-DzZc-q0x.js:154836`

## tengu (10)

- `tengu_bridge_message_received` — `index.chunk-DAdPDze6.js:45111`
- `tengu_ccr_init_park_report` — `index.chunk-DAdPDze6.js:49550`
- `tengu_ccr_internal_events_dropped` — `index.chunk-DAdPDze6.js:49356`
- `tengu_ccr_preserved_event_ids_clamped` — `index.chunk-DAdPDze6.js:50611`
- `tengu_feature_bad` — `index.chunk-CHNweogn.js:30824`
- `tengu_feature_ok` — `index.chunk-CHNweogn.js:30821`
- `tengu_feature_sad` — `index.chunk-CHNweogn.js:30827`
- `tengu_managed_settings_os_read` — `index.chunk-CHNweogn.js:41965`
- `tengu_request_user_dialog_response_ignored` — `index.chunk-CHNweogn.js:43588`
- `tengu_tool_cgroup` — `index.chunk-DAdPDze6.js:22639`


## marketplace (7)

- `marketplace_plugin_account_sync_result` — `index.chunk-CwacCE28.js:1870`
- `marketplace_plugin_cli_error` — `index.chunk-DzZc-q0x.js:243344`
- `marketplace_plugin_ipc_error` — `index.chunk-DzZc-q0x.js:246606`
- `marketplace_plugin_migration_done` — `index.chunk-DctdiTRV.js:239`
- `marketplace_plugin_migration_retry` — `index.chunk-DctdiTRV.js:246`
- `marketplace_plugin_op_result` — `index.chunk-CwacCE28.js:1828`
- `marketplace_plugin_stub_manifest_detected` — `index.chunk-CwacCE28.js:1675`

## remote_plugin (3)

- `remote_plugin_enabled_migration_superseded` — `index.chunk-CwacCE28.js:529`
- `remote_plugin_enabled_put_outcome` — `index.chunk-BAiM0EgL.js:343`
- `remote_plugin_entry_pruned` — `index.chunk-CwacCE28.js:2211`

## device_registry (2)

- `device_registry_no_tpm_probe_code` — `index.chunk-DzZc-q0x.js:215415`
- `device_registry_unavailable_probe_code` — `index.chunk-DzZc-q0x.js:215424`

## builtin_websearch (1)

- `builtin_websearch_call` — `index.chunk-DzZc-q0x.js:175157`

## ssh_terminal (1)

- `ssh_terminal_sentinel_timeout` — `index.chunk-DtrkByRj.js:1487`

---

