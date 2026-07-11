# AIxCTF ClaudeCode AutoResearch / AutoExploit Runtime

文档类型：当前实现口径的一体化工程交接文档
目标：说明 `.claude/` 下 AIxCTF 自动解题 runtime 的架构、边界、状态流和验收标准
状态：已按最新实现更新，替代早期 v1 原文

---

## 1. 一句话定义

```text
ClaudeCode-centered, hook-guarded, controller-loop-and-round-loop-based,
parallel-challenge-capable, stateful, template-guided, skill-assisted,
tool-aware, native-Task-subagent-capable, human-sync-enabled AIxCTF
AutoResearch / AutoExploit Runtime.
```

中文定义：

```text
基于 ClaudeCode 的检查点驱动型、回合状态转移式、工具感知型、
支持原生 Task 子任务与人类进度同步的 CTF 自动研究 / 自动利用运行时。
```

本项目不是 CTF 平台，也不是通用多 agent 编排系统。它是一个可放入 AIxCTF Docker 镜像的挑战解决 runtime。

---

## 2. 系统边界

runtime 负责：

- 从 `/challenge` 或 `CHALLENGE_DIR` 读取 challenge input
- 发现单题或多题 challenge 输入，解析每个 `challenge_id`，并初始化 `$WORKDIR`
- 加载题面、附件、target、metadata 和允许范围
- 分类 pwn / web / unknown
- 在 `RuntimeController` 外层 loop 中按题目状态调度一个或多个 active visit
- 按 round 调用每题独立的 ClaudeCode child process
- 通过 hooks 记录和约束工具调用
- 维护 `state.json`、`rounds/*.json`、`events/*.json`、`progress.jsonl`、`status.json`
- 持久化 `notes.md`、`handoff.md`、`evidence/`、`logs/`、`scripts/`
- 记录 ClaudeCode 原生 Task / Agent 子任务结果
- 旁路同步进度到 Human Sync Agent
- 写出每题 `$WORKDIR/result.json`，以及单题结果或多题汇总 `/output/result.json`

runtime 不负责：

- 攻击题目范围外目标
- GUI 逆向工作流
- 无边界多 agent 自动扩散
- 让 subagent 直接接管全局策略
- 在没有证据的情况下接受 flag

---

## 3. 核心状态转移

系统本质上是大 loop 套小 loop：

```text
RuntimeController outer loop
  -> choose schedulable challenge(s) by state/result status
  -> run up to AIXCTF_MAX_PARALLEL_CHALLENGES active visits
  -> each per-challenge visit
      -> round 1
      -> round 2
      -> ...
  -> solved: mark complete
  -> hard or multi-round unsolved: pause and switch
  -> stop successfully only when all challenges are solved
```

`RuntimeController` 只根据模型输出后的 `state.json`、`round_result`、`result.json`
和调度状态做状态迁移。它不直接判断 exploit 方向，不替代 ClaudeCode 解题，也不从题目内容推断战术。
多题模式下它可以同时运行多个 ClaudeCode 子进程，但每个子进程只绑定一个题目的
`WORKDIR`，不共享 ClaudeCode 上下文。

```text
S_n + H_n + C + K_n
  -> AutoResearch / AutoExploit Execution
  -> ClaudeCode Primary Agent
  -> Tool Events
  -> Hook Evaluation
  -> Native Task / Agent Subtask Records
  -> Reflection
  -> Round Result
  -> Reload latest state.json
  -> S_{n+1}
```

含义：

- `S_n`: 当前 `state.json`
- `H_n`: 当前由模型维护的 `handoff.md`
- `C`: challenge context，包括题面、附件、target、scope、metadata
- `K_n`: 本轮注入的 template / skill / tool / debug / handoff docs
- `Events`: 工具、hook、sync、subtask 事件
- `S_{n+1}`: 由 round result 和 subtask result 合并后的下一状态

设计规则：每次 Execution 都必须外化 durable state，不能只依赖 ClaudeCode 对话上下文。模型
可以在同一次 Execution 内完成多个强关联实验，并在语义 checkpoint 更新 `handoff.md`。
hook
在 ClaudeCode 运行中写入的 `state.json` 是中间检查点；round 结束合并前必须重新读取
最新状态，避免候选 flag、evidence、failure signals 或 subtask artifacts 被旧状态覆盖。

---

## 4. Workspace 布局

Docker 默认 workspace 不是根目录 `/workspace`，而是按 challenge 隔离：

```text
/aixctf-agent/workspace/<challenge_id>/
```

运行时会设置：

```text
WORKDIR=/aixctf-agent/workspace/<challenge_id>
CHALLENGE_DIR=/challenge
OUTPUT_DIR=/output
```

`WORKDIR` 也可以显式覆盖。ClaudeCode 的 current working directory 等于 `$WORKDIR`，所以 agent 优先使用相对路径或 `$WORKDIR/...`。多题并发时，每个 ClaudeCode child process 通过自己的环境变量获得独立 `WORKDIR`，controller 不通过进程全局 `WORKDIR` 切题。

`challenge_id` 解析顺序：

1. `CHALLENGE_ID` 环境变量
2. `metadata.json.challenge_id`
3. `metadata.json.id`
4. challenge 源文件或目录名
5. `unknown`

`challenge_id` 会被清理为单一安全路径段。

`AIXCTF_CHALLENGE_MODE=auto` 为默认发现模式。设置为 `single` 可强制整个
`CHALLENGE_DIR` 作为一道题；设置为 `multi` 可强制按子目录发现多题。

`AIXCTF_MAX_PARALLEL_CHALLENGES` 控制多题模式下同时运行的 active visit 数量。
默认多题为 `2`，单题为 `1`。每个 active visit 拥有一个 ClaudeCode 子进程。

```text
$WORKDIR/
  challenge/
  rounds/
  events/
  subtasks/
  scripts/
  logs/
  evidence/
  sync/
  prompts/
  state_snapshots/
  state.json
  status.json
  progress.jsonl
  notes.md
  handoff.md
  result.json
```

默认 Docker Compose host 映射：

```text
Host path under .claude/          Docker path
sample_challenge/                /challenge:ro
workspace/                       /aixctf-agent/workspace
workspace/<challenge_id>/        /aixctf-agent/workspace/<challenge_id>
workspace/controller_result.json /aixctf-agent/workspace/controller_result.json
local_output/                    /output
local_output/<challenge_id>/     /output/<challenge_id>
```

本地非 Docker 运行时，如果不设置 `WORKDIR`，默认落到 `.claude/workspace/<challenge_id>/`。也可以显式指定临时 workspace：

```bash
WORKDIR=/tmp/aixctf-ws OUTPUT_DIR=/tmp/aixctf-out CHALLENGE_DIR=. \
  AIXCTF_DRY_RUN=1 AIXCTF_MAX_ROUNDS=2 AIXCTF_MAX_ROUNDS_PER_VISIT=1 \
  python3 .claude/entrypoint.py
```

推荐的本地 dry-run：

```bash
CHALLENGE_ID=sample CHALLENGE_DIR=. OUTPUT_DIR=/tmp/aixctf-out \
  AIXCTF_DRY_RUN=1 AIXCTF_MAX_ROUNDS=2 AIXCTF_MAX_ROUNDS_PER_VISIT=1 \
  python3 .claude/entrypoint.py
```

---

## 5. 当前组件图

```text
Runtime Controller
  -> Challenge Loader
  -> Category Classifier
  -> Round Manager
      -> Loop Core
      -> Knowledge Router
      -> Claude Runner
      -> Event Store
      -> Reflection Engine
      -> Human Sync Agent
  -> State Store
  -> Result Collector

ClaudeCode Primary Agent
  -> Bash / Read / Write / Edit / MultiEdit
  -> Native Task tool with subagent_type=general-purpose

Hooks
  -> PreToolUse guard
  -> PostToolUse recorder
  -> Stop evidence guard
```

当前实现不包含独立预算控制模块，也不包含 runtime 自行派生的外部子进程式 subagent 编排。子任务由 ClaudeCode primary agent 通过原生 `Task` 工具创建。
并发只发生在题目 visit 层：多个题目可以各自运行一个 ClaudeCode child process；
同一题内部的 native Task 仍由 primary agent 通过 ClaudeCode 原生工具调度。

---

## 6. Runtime Components

### Runtime Controller

实现：`.claude/runner/runtime_controller.py`

职责：

- 发现单题或多题 challenge source
- 为每题初始化独立 workspace
- 在外层 loop 中选择一个或多个 schedulable 题目
- 为每个 ClaudeCode child process 注入独立 `CHALLENGE_ID` 和 `WORKDIR`
- 对当前题执行一个 bounded visit
- 根据状态将题目标记为 `pending` / `active` / `paused` / `solved` / `exhausted`
- 所有题 solved 时成功停止；硬超时或无可调度题时写未完成汇总

### Challenge Scheduler

实现：`.claude/runner/challenge_scheduler.py`

职责：

- 发现 challenge 目录
- 维护题目记录和优先级排序
- 优先调度 pending、失败少、访问少、round 少的题目
- 排除仍在运行的 `active` 题目，避免同一题重复并发
- 将难题或多轮未解题暂停，切换到下一题
- 只消费状态和结果，不判断题目解法

### Round Manager

实现：`.claude/runner/round_manager.py`

职责：

- 选择本轮 docs 和 template
- 构造 round prompt
- 调用 ClaudeCode
- 收集 hook events
- 提取 native Task / Agent subtask result
- 重新读取最新 `state.json` 后再合并 round result，保留 hook 中间状态
- 写入 `rounds/round_XXX.json`
- 更新 `notes.md`；real mode 下保留模型维护的 `handoff.md`
- 注入上一份 handoff 和 interrupted/incomplete Execution 恢复提示
- flush Human Sync Agent

### Claude Runner

实现：`.claude/runner/claude_runner.py`

职责：

- dry-run 模式下生成结构化假结果
- real 模式下调用 `CLAUDE_CODE_CMD`，默认 `claude -p`
- 通过 stdin 传入 prompt，避免 CLI variadic 参数吞掉 prompt
- 设置 child-process-local `WORKDIR`、`CHALLENGE_DIR`、`AIXCTF_ROUND_ID`、`AIXCTF_EXECUTION_ID` 和 Execution 启动时间
- 写入 `logs/claude_round_XXX.log` 和 `.err.log`

### State Store

实现：`.claude/runner/state_store.py`

职责：

- 维护 `state.json`
- 兼容并清理旧状态文件中的历史限制字段
- 维护 `runtime_limits`
- 合并 round result
- 合并 subtask result 的 confirmed facts、falsified hypotheses、open questions、do-not-repeat
- 写入 `state_snapshots/`

### Event Store

实现：`.claude/runner/event_store.py`

职责：

- 以 append-only JSON 文件记录 PreToolUse / PostToolUse 事件
- 使用 `AIXCTF_ROUND_ID` 定位当前 round
- 为 round actions 生成摘要

### Result Collector

实现：`.claude/runner/result_collector.py`

职责：

- 写 `$WORKDIR/result.json`
- 单题模式复制到 `/output/result.json`
- 多题模式复制到 `/output/<challenge_id>/result.json`，总汇总由 `RuntimeController` 写入 `/output/result.json`
- solved 时要求 flag 和 evidence guard 通过
- failed 时保留 handoff、rounds、logs、subtasks 等 artifacts

---

## 7. Runtime Limits

默认限制：

```text
AIXCTF_MAX_ROUNDS=12
AIXCTF_MAX_ROUNDS_PER_VISIT=3
AIXCTF_MAX_SECONDS=7200
AIXCTF_MAX_CMD_SECONDS=7200
AIXCTF_MAX_PARALLEL_CHALLENGES=2  # multi-challenge default
```

含义：

- `max_rounds`: 单题最大 round 数
- `max_rounds_per_visit`: 单次调度访问最多执行多少 round，达到后暂停并切题
- `max_seconds`: runtime 总时长上限
- `max_command_seconds`: 单轮 ClaudeCode 调用上限
- `max_parallel_challenges`: 同时运行的题目 visit 数量

ClaudeCode native Task / Agent 子任务运行在 primary agent 会话内，受单轮 ClaudeCode 调用上限约束。helper 工具可以自行使用更短的局部命令超时。

---

## 8. Round Contract

每个 round 必须回答：

- research question
- hypothesis
- experiment
- observations
- evidence
- conclusion
- state delta
- candidate flags
- confirmed flag
- failure reason
- next experiment
- task results
- do-not-repeat

ClaudeCode final response 应包含 JSON：

```json
{
  "research_question": "",
  "hypothesis": "",
  "experiment": "",
  "observations": [],
  "evidence": [],
  "conclusion": "",
  "state_delta": {},
  "candidate_flags": [],
  "confirmed_flag": null,
  "failure_reason": null,
  "next_experiment": "",
  "task_results": [],
  "do_not_repeat": []
}
```

runtime 会优先从 stdout 解析该 JSON；如果 stdout 被包装或夹在文本中，会尝试从 fenced JSON、balanced JSON、tool event log 中恢复。

---

## 9. Native Task / Agent Subagents

当前口径：

- primary agent 根据上下文压力或局部任务复杂度，自行调用 ClaudeCode 原生 `Task`
- `subagent_type` 只允许 `general-purpose`
- hook payload 中该工具可能显示为 `Task`，也可能显示为 `Agent`
- runtime 将 `Task` 和 `Agent` 统一视为 native subagent surface
- runtime 不再 shell out `claude -p` 创建子 agent

适合委派的任务：

- pwn offset discovery
- gadget search
- libc / ld 分析
- web route discovery
- auth / session review
- HTTP failure debugging
- log summarization

不适合委派的任务：

- 简单 `ls`、`file`、`checksec`、一次性 `curl`
- 需要全局策略连续性的任务
- “solve the whole challenge” 这类无边界目标
- 任何要求修改 runtime 控制面文件的任务

subtask artifacts：

```text
$WORKDIR/subtasks/task_XXX/
  input.json
  output.md
  result.json
  handoff.md
```

`result.json` 结构：

```json
{
  "protocol_version": "aixctf.task-handoff/v1",
  "subtask_id": "task_001",
  "type": "claudecode_native_task",
  "agent_type": "general-purpose",
  "status": "confirmed|falsified|inconclusive|blocked",
  "conclusion": "",
  "confidence": 0.0,
  "evidence": [],
  "facts_added": [],
  "hypotheses_falsified": [],
  "next_recommendation": "",
  "do_not_repeat": []
}
```

PreToolUse 对 native subagent 的约束：

- 只允许 `general-purpose`
- 禁止嵌套 `claude -p`
- 禁止明确读写 runtime 控制面：`state.json`、`result.json`、`rounds/`、`events/`、`sync/`、`.claude/`
- 允许 prompt 中出现 “do not write state.json” 这类负向约束
- 网络工具仍受 allowed scope 限制

---

## 10. Hook Checkpoint Layer

实现目录：`.claude/hooks/`

### PreToolUse

职责：

- 解析 tool name 和 input
- 阻止危险命令
- 阻止无边界扫描
- 阻止 scope 外网络访问
- 阻止 agent 写 runtime-owned files
- 校验 native Task / Agent prompt
- 记录 pending event
- emit `tool_started` 或 `tool_blocked`

### PostToolUse

职责：

- 保存 stdout / stderr 到 `logs/`
- 提取 candidate flags
- 检测失败信号
- 将 native Task / Agent 结果持久化到 `subtasks/task_XXX/`
- 更新 `state.json` artifacts
- emit `tool_finished`、`failure_signal_detected`、`candidate_flag_found`、`subtask_completed` / `subtask_blocked`

### Stop

职责：

- 使用 Execution 启动时间与 `handoff.md` mtime 检查本次是否更新
- 首次未更新时阻止停止并要求模型形成 checkpoint
- 第二次仍未更新时允许停止并记录 `checkpoint_incomplete`，避免 hook 死循环
- 运行 evidence guard
- 对未满足证据要求的 solved 状态进行阻断
- 通过时返回空 JSON，避免 additionalContext 触发 ClaudeCode 继续生成

### PreCompact

只匹配自动压缩。它会阻止 compaction，并要求模型先更新 handoff、返回结构化状态、结束
当前 Execution。若 context-limit error 已使本次调用失败，则下一次 fresh Execution 根据
现有 JSON、handoff 和 durable artifacts 恢复。

---

## 11. State Model

`state.json` 核心字段：

```json
{
  "handoff_protocol_version": "aixctf.challenge-handoff/v1",
  "challenge_id": "unknown",
  "category": "unknown",
  "phase": "init",
  "round": 0,
  "solved": false,
  "confirmed_flag": null,
  "candidate_flags": [],
  "allowed_scope": {
    "targets": [],
    "hosts": [],
    "ports": [],
    "urls": []
  },
  "artifacts": {
    "scripts": [],
    "logs": [],
    "evidence": [],
    "subtasks": []
  },
  "research_loop": {
    "current_question": null,
    "current_hypothesis": null,
    "active_strategy": null,
    "known_facts": [],
    "falsified_hypotheses": [],
    "open_questions": [],
    "next_experiment": null
  },
  "runtime_limits": {
    "max_rounds": 12,
    "max_seconds": 7200,
    "max_command_seconds": 7200
  },
  "scheduler": {
    "status": "pending",
    "pause_reason": null,
    "updated_at": null
  },
  "sync": {
    "enabled": true
  }
}
```

`state.json` 是 controller 使用的机器状态；`handoff.md` 是下一次 fresh Execution 读取的
模型语义状态。系统不使用 handoff hash、checkpoint 目录或 session resume。正常结束通过
Stop checkpoint 收口，意外中断通过 `progress.jsonl` 中未闭合的 Execution lifecycle 触发
下一次模型 reconciliation。

状态合并规则：

- confirmed flag 将 phase 置为 `solved`
- candidate flags 只进入候选，不等于 solved
- evidence artifacts 必须真实存在
- subtask `confirmed` facts 合入 `known_facts`
- subtask `falsified` hypotheses 合入 `falsified_hypotheses`
- subtask recommendation 合入 `open_questions`
- failure reason 进入 `failures`

---

## 12. Knowledge Library

目录：

```text
.claude/templates/
  generic.md
  pwn.md
  web.md
  subagent.md

.claude/docs/
  knowledge_index.yaml
  pwn/
  web/
  tools/
  debug/
  handoff/
```

每轮注入限制：

- 1 个 template
- 最多 2 个 skill docs
- 最多 2 个 tool docs
- 最多 1 个 debug doc
- 可选 1 个 handoff doc

`KnowledgeRouter` 根据 category、phase、trigger、failures、known facts、recent docs 选择文档，避免每轮注入过多上下文。

---

## 13. Human Sync

Human Sync 是 fail-open 旁路，不参与求解成败判定。

```text
Hook / Round / Subtask Events
  -> sync/events.jsonl
  -> Human Sync Agent
  -> mntn_skill Adapter
  -> Human Endpoint
```

行为要求：

- endpoint 失败不能让 solver 失败
- 失败同步写入 `sync/spool.jsonl`
- 所有尝试写入 `sync/sync_log.jsonl`
- progress stdout 保持短文本
- 大输出只写日志 artifact

---

## 14. Evidence And Result Policy

solved 必须满足：

- `confirmed_flag` 存在
- evidence artifact 存在
- evidence 中能追溯 flag 来源
- `handoff.md` 解释 flag 如何取得

failed 必须满足：

- `failure_reason` 存在
- 至少一个 `rounds/round_XXX.json`
- `notes.md` 和 `handoff.md` 可用于接续

输出：

```text
$WORKDIR/result.json
/output/<challenge_id>/result.json  # multi-challenge per-challenge result
/output/result.json                 # single result or multi-challenge summary
```

---

## 15. Build And Run

Docker build：

```bash
docker build -t aixctf-agent .claude
```

Local dry-run：

```bash
CHALLENGE_ID=sample CHALLENGE_DIR=. OUTPUT_DIR=/tmp/aixctf-out \
  AIXCTF_DRY_RUN=1 AIXCTF_MAX_ROUNDS=2 AIXCTF_MAX_ROUNDS_PER_VISIT=1 \
  python3 .claude/entrypoint.py
```

Real ClaudeCode run：

```bash
CLAUDE_CODE_CMD='claude -p --permission-mode acceptEdits --allowedTools Bash Read Write Edit MultiEdit Task' \
CHALLENGE_ID=sample CHALLENGE_DIR=. OUTPUT_DIR=/tmp/aixctf-out \
AIXCTF_DRY_RUN=0 AIXCTF_MAX_ROUNDS=1 AIXCTF_MAX_ROUNDS_PER_VISIT=1 SYNC_ENABLED=0 \
python3 .claude/entrypoint.py
```

Syntax check：

```bash
python3 -m compileall .claude
```

Diagram render：

```bash
plantuml -tpng docs/architecture/diagrams/*.puml
```

---

## 16. Acceptance Criteria

System：

- workspace 初始化成功
- dry-run 可写出 result
- real mode 可调用 ClaudeCode
- `state.json`、`rounds/*.json`、`events/*.json`、`progress.jsonl`、`status.json` 生成
- `result.json` 写入 workspace 和可选 output

Agent：

- 读取 challenge context
- 分类 pwn / web / unknown
- 每轮形成 research question、hypothesis、experiment、observation
- 选择有限 docs
- 写 logs、scripts、evidence
- 从失败信号中迭代

Hook：

- 记录工具调用
- 阻止危险命令和 scope 外访问
- 阻止写 runtime-owned files
- 支持 native `Task` / `Agent` subagent 持久化
- 提取 candidate flags
- solved 前执行 evidence guard

Quality：

- solved 需要 flag 和 evidence
- failed 需要 handoff 和 failure reason
- subtask result 可追踪到 `subtasks/task_XXX/`
- old context-budget / external subagent references 不应出现在当前实现文档中

---

## 17. Current Implementation Summary

当前实现的主路径：

```text
entrypoint.py
  -> RuntimeController.run()
      -> discover_challenge_sources()
      -> ChallengeScheduler.next_challenge()
      -> activate CHALLENGE_ID / WORKDIR
      -> ChallengeLoader.sync_challenge()
      -> StateStore.load_or_create()
      -> per-challenge visit
          -> RoundManager.run_round()
              -> KnowledgeRouter.select()
              -> build_prompt()
              -> ClaudeRunner.run()
              -> EventStore.collect()
              -> native_task_results_from_events()
              -> ReflectionEngine.build_loop()
              -> write round result
              -> update notes; preserve model-owned handoff
              -> HumanSyncAgent.flush_round()
          -> StateStore.apply_round_result()
          -> emit execution_completed
      -> ResultCollector.write_result()
      -> ChallengeScheduler.update()
  -> controller result summary when multi-challenge
```

当前实现的 subagent 主路径：

```text
ClaudeCode primary agent
  -> native Task tool, subagent_type=general-purpose
  -> hook payload appears as Task or Agent
  -> PreToolUse validates prompt
  -> PostToolUse writes subtasks/task_XXX/*
  -> RoundManager records subtask result path
  -> StateStore merges confirmed facts and recommendations
```

当前实现的核心原则：

```text
每次 fresh Execution 输入显式 state 和 handoff；
强关联实验可在一个 Execution 内连续完成；
正常 Stop 前模型更新 handoff 并输出结构化状态；
中断后从 JSON、handoff 和 durable artifacts 恢复；
hooks 只做确定性检查、记录和轻量状态更新；
native Task 用于局部 bounded 子任务；
全局策略仍由 primary agent 和 StateStore 控制；
Human Sync 是 fail-open 旁路；
最终 result 以 evidence guard 为准。
```
