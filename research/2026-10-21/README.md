# 2026-10-21 research checkpoint

Read [project status](../../docs/project-status-2026-10-21.md) first. This is exploratory evidence for a creator-facing CLI/Skill, not a leaderboard or a held-out benchmark.

- `google-voicevox-summary.json`: all 2,000 paired sentences processed; raw machine differences and conservative budget reservation.
- `google-voicevox-listening.json`: selected human judgments, 101 non-unreviewed sentences per engine. Raw verdicts include lexical/reference issues.
- `google-voicevox-reviewed-cases.json`: script and recorded recognition for reviewed cases. No audio or model weights.
- `history-results.json`: all 200 history-narration scripts and stored recognition, plus current candidate classification. No new ASR was run for contextual reference corrections.
- `history-listening.json`: 100 reviewed sentences across all 100 terms, and explicit human error notes that conflict with a correct whole-sentence button. Partner-context judgments are not inferred.
- `history-context-reading-overrides.json`: contextual corrections for 人足 and standalone 米; kept separate from original recognition evidence.
- `history-reading-acceptance-addenda.json` and `history-reading-explanations.json`: documented alternative readings and why they were accepted.
- `additional-targets.json`: 捕物／捕り物 proposed for future coverage. The new example sentences have not been synthesized.
- `history-verification.json`: integrity validation at generation completion, before subsequent human listening. Its `human_listening_not_performed` field describes that earlier validation snapshot, not the current review completion.

## Local experiment tools

`local-experiment-tools/` archives the experimental runner, report publisher, alignment-to-HTML highlighter, loopback review server, UI, authored corpus and tests. These are **not installed CLI commands**. They retain the original project layout assumptions (`work/`, `outputs/`, a pre-existing VOICEVOX service and local MLX Kana Whisper runtime). Do not run them directly in this research folder expecting a portable environment. Missing model/engine assets and the live `review-state.json` remain in the original local workspace.

The generic package under `src/tts_audit/` does not yet incorporate all experimental UI and contextual-reference fixes. In particular, dictionary and ASR agreement can conceal a shared contextual reading error. See the status document for the next product milestone.

No API keys, credentials, authentication/session configuration, remote tunnel, model weights, or bulk audio are included. The repository remains private.

## Attribution

Dictionary-derived headword/readings data uses JMdict, copyright James William BREEN and the Electronic Dictionary Research and Development Group, under CC BY-SA 4.0. See [dictionary attribution](history-dictionary-attribution.txt) and https://www.edrdg.org/edrdg/licence.html. The surrounding CLI code remains MIT; dictionary data is separately licensed. Narration examples were authored for this project. VOICEVOX audio credit, for audio retained locally: VOICEVOX 青山龍星. No audio is bundled in this snapshot.

## 継続収集の正本

このフォルダは実験時点の記録です。今後の語・用例・誤読観測と固定音声の管理は [data/benchmark](../../data/benchmark/README.md) に統合しました。参照セットの初版はv0.1.0で、採点対象と収集報告を区別し、元の判定を上書きせず保存しています。
