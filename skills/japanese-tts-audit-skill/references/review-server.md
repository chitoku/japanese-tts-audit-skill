# Local listening server and Agent handoff

Run `tts-audit serve REPORT_DIRECTORY` after `check`, using the same installed Python environment. Optional `--open` opens the timeline in the default browser; `--port 0` selects an available loopback port. Keep the process running while the user listens. Use the actual `timeline_url` printed by the CLI; a file:// report does not support direct saving. No generation API, ASR rerun, paid calls or external upload is involved in serving an existing report.

## State contract

Read `REPORT_DIRECTORY/review-state.json`, not the formatted HTML. It is one atomically replaced JSON document with:

- `schema_version: 1`, `run_id`, `report_sha256` binding labels to report.json. Check both identity fields before using labels.
- `revision`: increments for successful updates, used to reject stale concurrent browser writes.
- `status: draft | completed`, `updated_at`, `completed_at`. The completion button in the traditional report finishes a review round; timeline autosaves stay draft. Editing afterwards returns it to draft and clears completed_at.
- `candidate_count`, `reviewed_count`, `unreviewed_count`, `verdict_counts` and `notes` keyed by finding ID. Notes retain `verdict`, `heard`, `note`, `updated_at` as in exported notes JSON.

`completed` means the user ended this review round, including any explicit uncertainty and unreviewed candidates. It does not certify the full audio, authorize spending, approve sentence adoption or mean every flag is an error. Inspect verdicts and their scope. A target-word judgment does not cover the rest of its sentence. Preserve all original ASR evidence in report.json.

The Agent can read the state when checking progress or wait/poll with bounded execution calls if its environment supports that. The server does not start another Agent or send a message to a chat. Do not claim automatic wakeup or automatic regeneration. Presentation can be native in another Agent UI if it supports playback and writes the same validated state contract, but HTML remains the common interface.

## Persistence and recovery

The server binds to 127.0.0.1 and serves only selected report files under a random session URL. It checks Host/Origin on requests. Do not expose it to the network or present it as a hosted service. Audio seeking supports byte ranges.

The first start can seed notes from listening-notes.json created by the existing import command. Once review-state.json exists it is authoritative; later edits to listening-notes.json or browser caches are not silently imported over it. Restarting the server changes the session URL but preserves the stored state. If report.json changes, the server refuses to combine old labels with the new evidence. Use the correct report directory rather than deleting mismatching human records.

Buttons and notes autosave after a short debounce. The status must say saved or completed before leaving. An interrupted save or HTTP error stays visible; keep the page and use JSON export as a backup. Concurrent stale tabs receive a conflict instead of overwriting someone else’s edits: export unsaved notes, reload current state, and reconcile explicitly. JSON export and the existing import workflow remain available for file-only, offline sharing and backup use.

## Timeline review and manual findings

The timeline uses `audio-timing.json` when validated against the run/audio/transcript and otherwise shows approximate positions. Use Space for playback, F for playback follow, M for manual flags, 1/2/3 for verdicts, Down for the next unreviewed finding, R to replay the selected finding, and ? for help. The header shows session identity, input provenance (if recorded), and the exact save path; JSON backup is optional in server mode.

Manual flags are in `annotations` with `kind: manual_flag` and an M- ID. Their notes may include `target_text`, `expected_reading`, `heard`, and `note`. A note with `deleted: true` is a retained deletion record, not an actionable repair request. Exclude it from active candidates and repairs, while retaining its history on export/import. Never infer that a missing target label or an unreviewed flag confirms an error. Existing machine findings and original audio remain unchanged.
