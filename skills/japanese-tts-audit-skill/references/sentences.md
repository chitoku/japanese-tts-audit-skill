# Sentence production and repair

Use `python -m tts_audit.cli sentences` (or `tts-audit sentences`). Requires the package's `generation` extra for ElevenLabs generation and `asr` extra for local inspection. Existing audio can be imported without a generation API key.

## Retain the creator’s existing provider

Inspection with `tts-audit check` accepts supported audio files regardless of the service that generated them. For repairs, preserve the existing service, model, voice and relevant settings. Use an available provider tool or source-project editor with the user’s spending authorization. Keep the canonical script and other approved audio unchanged; record generation-only pronunciation changes separately. Recheck the complete regenerated sentence, approve before adoption, then listen to joins.

If no provider operation is available, give the creator the sentence and proposed generation input, and inspect the returned file. Do not claim an API request, generation, replacement or cost check occurred unless it actually did. External-provider charges are not tracked by the ElevenLabs budget mechanism.

The CLI’s `sentences init` and `sentences generate` currently assume ElevenLabs models and a voice ID. There is no general Google/other-provider generation adapter or provider-neutral sentence-project initializer yet. Use standalone `check` and the provider’s project workflow for those services; do not invent ElevenLabs settings. `import-audio` can attach an external recording to an already appropriate existing sentence project, with provider/model/voice provenance in `--note`; it does not make the initializer provider-neutral. For a continuous recording without sentence assets, retain the original and use the source editor or request an export before promising lossless replacement.

## Initialize and inspect segmentation

```sh
tts-audit sentences init --script script.txt --readings readings.json --out project \
  --voice-id VOICE_ID --model eleven_v3 \
  --budget-usd 15 --baseline-usd PRIOR_RESERVE --max-new-usd NEW_LIMIT
```

Use the user's known budget and prior spending/reservations. The project enforces its own limits; unrelated provider activity and other projects are not automatically included. The reserve uses $0.30/1,000 reported credits or input characters plus one per request, whichever is greater. It is a conservative accounting convention, not a provider invoice or live price guarantee. Included credits are checked before each request. Do not purchase or enable overage.

Inspect `project/index.html` before generating. The Japanese punctuation splitter is approximate; quotes, dialogue and abbreviations can need manual segmentation. `--sentences-json` accepts an ordered array of strings that must preserve the script apart from whitespace. Canonical script and expected readings are fixed for a project; create a new project if they change.

## Initial generation and check

```sh
tts-audit sentences generate project --key-file PRIVATE_KEY_FILE --max-requests SENTENCE_COUNT
tts-audit sentences check project --cache-dir CACHE --offline
```

Default generation creates missing sentences only; repeating it does not regenerate existing audio. The default request limit is one; choose an explicit batch limit within user authorization. Keys are read locally and never stored in the project. No paid automatic retries occur. A persisted reserved/uncertain request blocks further paid calls until its provider outcome is reconciled; do not clear it blindly.

Inspect each sentence's audit and record adoption evidence:

```sh
tts-audit sentences review project --sentence S001 --verdict approved --basis asr --note 'No actionable difference in this inspection; human hearing not claimed'
```

`approved` means approved for adoption with the recorded basis, not necessarily human-certified pronunciation. Use `--basis human` only for actual user/listener reports covering that sentence. A correct target word alone does not certify the rest of the sentence. Use `needs_revision` for a selected repair target and `uncertain` for unresolved cases. Preserve dictionary alternatives and ASR false positives rather than rewriting correct audio.

## One-sentence repair and adoption

```sh
tts-audit sentences review project --sentence S007 --verdict needs_revision --basis asr --note 'Describe the observed difference and its uncertainty'
tts-audit sentences generate project --sentence S007 --regenerate --text-file corrected-S007.txt --key-file PRIVATE_KEY_FILE --max-requests 1
tts-audit sentences check project --sentence S007 --version latest --cache-dir CACHE --offline
tts-audit sentences review project --sentence S007 --version latest --verdict approved --basis asr --note 'Describe reinspection evidence'
tts-audit sentences select project --sentence S007 --version v002
```

Only a selected sentence marked `needs_revision` can be regenerated. Put the corrected generation text in a separate file; keep the canonical script unchanged. Regeneration adds a candidate and retains the old selected version. `check --version latest` inspects that candidate against the original sentence. `select` requires an approved candidate and changes one sentence pointer. Other sentence files, audits and approvals remain unchanged. Inspect any other differences introduced within the regenerated sentence; do not retry solely to satisfy an unstable ASR.

Use `import-audio project --sentence S007 --audio EXISTING_AUDIO --note PROVENANCE` to bring in a known sentence recording. It is an import, not a claim that the CLI freshly generated it. New imports also retain an existing selected version until explicit approval/selection.

## Assemble and verify preservation

```sh
tts-audit sentences assemble project --out mix-v2 --gap-ms 250
tts-audit sentences status project
```

All selected sentences must be approved; `assemble --preview` explicitly permits a listening draft with unresolved sentences. The mix uses 16 kHz mono PCM without changing source sentence samples, and verifies exact sample equality. `assembly.json` records selected versions, source hashes, sample positions and review basis. Separate join clips allow listening to the transitions. Sample preservation does not guarantee consistent intonation, volume or pauses; joins are not automatically human-reviewed.

If an initial run has no genuine repair target, stop without unnecessary paid regeneration. To exercise replacement using an earlier real failure, keep it as a clearly labeled imported case or a separate reproduction project; do not present a seeded failure as a spontaneous failure of the new run.
