# Human Sync

The sync layer is a fail-open side channel. Hooks and round management append structured events to `$WORKDIR/sync/events.jsonl`. `HumanSyncAgent` summarizes round progress and optionally submits it through `MntnSkillAdapter`.

If no endpoint is configured, sync attempts are written to `$WORKDIR/sync/spool.jsonl` and never block solving.
