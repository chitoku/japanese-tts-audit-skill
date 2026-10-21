---
name: japanese-tts-audit-skill
description: Inspect Japanese narration against its script using Kana Whisper and a playable local report. When authorized, generate and repair individual sentences while preserving approved audio. Use for pre-publication TTS proofreading and sentence replacement workflows.
---

# Japanese narration pronunciation audit

Accept the user's script and existing audio. Produce an HTML/JSON report that lets them listen to suspected reading differences. The CLI does the processing; the agent explains what requires confirmation.

For authorized repairs, retain the creator’s existing TTS service, model, voice and relevant settings when available. Use session context or source-project metadata first; ask only for missing settings needed to reproduce the voice. Use the available provider API, CLI, connector or editable source project. Do not switch to ElevenLabs merely because this repository has an ElevenLabs generator. If the existing service cannot be operated, provide the affected sentence and generation-only reading changes for the creator to regenerate, then inspect the returned audio. A service that exposes neither audio nor editable segments may require an export or a manual step.

For sentence-by-sentence generation, repair and assembly supported by the CLI, use [references/sentences.md](references/sentences.md). This mode spends provider credits; inspection of existing audio remains local. A proofreading request alone does not authorize paid generation.

## Run

1. Locate the audio and UTF-8 script. Preserve them. Use an interpreter with `tts_audit` installed; see the repository README for installation. The recognition extra downloads about 3.24 GB on first use. Reuse an existing cache when available. This is local inference, not an API service.
2. Run `python -m tts_audit.cli check AUDIO --script SCRIPT --out NEW_DIRECTORY`. Optional flags: `--readings readings.json` for user-specified readings, `--cache-dir CACHE`, and `--offline` after the model is cached. The equivalent command is `tts-audit check ...`. Use absolute input/output paths if running outside the input directory. `scripts/check.py` is also an entry point using the current interpreter.
3. The default converts the script to expected kana with Sudachi, independently transcribes audio with the pinned Kana Whisper model, and compares them. Never insert the script, desired reading, listening labels, or suspected wrong word into ASR recognition. A user's explicit pronunciation overrides belong only on the script side.
4. Boundary-adjacent differences trigger one automatic shifted-segmentation pass. Check `boundary_recheck.status`: if failed or inconclusive, retain the original candidates. The report lowers priority only when the expected reading plus surrounding context matches in the second pass. Original hypotheses and playable cards stay under the boundary section. This is not a correct verdict. ASR is audio-only in both passes.
5. Open or link `report.html`. Describe candidate count as reading differences needing review, not a count of proven TTS errors. Surface low text/audio alignment, unknown dictionary readings, and any secondary-pass differences. Show the audio with the report so the user can check. If no actionable candidate remains, preserve the original audio; a check-only outcome is a successful workflow and needs no paid regeneration.
6. Mention that playback times identify recognition segments, not exact word boundaries. Notes save in the browser; export JSON for durable sharing/backup. The generated HTML/JSON files do not update with browser edits.

## Interpret

- Distinguish TTS errors, dictionary/G2P mistakes, ASR mistakes, valid alternate readings, and ambiguous sound. "No difference" does not guarantee correct pronunciation.
- Look beyond any original benchmark target: a correct target does not imply the whole sentence is correct.
- Record observed sound separately from claims about its cause. Cross-language-like sounds or dictionary-inexplicable readings do not prove a mechanism.
- This preview uses whole-script sequence alignment and audio segments split near low-energy boundaries. Numeric readings, names, accepted variants, chunk boundaries, and major script/audio differences need care. Use `--readings` for known vocabulary; do not silently rewrite the script or regenerate audio.
- `--readings` changes the detector's expectation, not the TTS audio. If a genuine audio error needs repair within an authorized generation task, keep the canonical script, change only the generation input (e.g. 掘削→くっさく or a supported pronunciation alias), and recheck the entire regenerated audio against the canonical script. Do not retry generation just to satisfy an unstable ASR hypothesis; listen first, keep a budget/attempt limit, and allow rollback.
- For an authorized narration repair, regenerate only the affected sentence using the existing provider and preserve approved audio. The built-in sentence generator supports ElevenLabs; use its sentence project commands when that matches the creator’s workflow. For other services, use their native regeneration/editing tools and the provider-independent `check` command on the returned audio. Do not fabricate ElevenLabs model/voice settings to initialize an external-provider project. Keep canonical text, generation text, audio hashes and review basis together. Check and approve the candidate before selecting it; then inspect joins for pauses, volume and delivery. Existing continuous audio can still be inspected with `check`; sentence generation does not require splitting every incoming recording.
- If recognition fails, report failure rather than interpreting partial audio as a clean pass. The output directory must be new so prior notes/media are preserved.

For transcript import, output fields, privacy and the concrete limitations, read [references/io.md](references/io.md). No telemetry is sent and no leaderboard is maintained by this tool.
