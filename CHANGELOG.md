# Changelog

## Unreleased

- Add exact script/ASR text selections for manual flags with validated source offsets, a layout-stable selection toolbar, and right-click queue deletion with undo.

- Add Light/Dark/Auto theme selection with OS tracking, browser persistence, theme-aware waveform redraw, and Light promotional screenshots.

- Local `check` now collects Kana Whisper token timestamps in the primary decode by default, writes a validated timing sidecar and timeline page, and preserves separate review state. `--no-timestamps` and timing-failure fallback retain approximate display. `serve --open` opens the timeline; audio-timed pages default to playback follow.
- Add editable manual flags with target/reading/memo, deletion tombstones, undo, and markers in both timeline scales. Keep approved audio and ASR evidence unchanged.
- Improve queue selection/scroll following, verdict colors, readable keyboard help (F follow / M manual), file/session/save-location details, and optional JSON backup.
- Refresh README and sanitized screenshots for articles and full-HD video.

- Add an experimental blue-violet timeline review view: real PCM waveforms, fixed-scale detail and zoomable overview, keyboard verdicts, manual flags, explicit reviewed ranges, and revisioned JSON persistence. Keep the original report view. Add top/bottom panes, a top-right queue, cached draggable waveform tiles, and original-script/kana tracks with all differences and the selected candidate highlighted separately. Use validated audio-derived timestamps when available, with approximate segment projection as fallback.

- Add loopback-only `tts-audit serve`: existing listening UI, direct atomic JSON saving, explicit completion and stale-update conflict protection. Preserve file-only export/import.

## v0.2.0-beta

- 台本と音声を、独立した辞書読みとローカルKana Whisperで照合。
- 音声付きHTML、差分ハイライト、聴取記録の保存・取り込み。
- ASRの分割境界付近の差を、切り位置を変えて一度自動再確認。
- 一文単位の生成・点検・版管理・採用・差し替え・PCM結合。
- 有料生成前の予算予約、要求数上限、通信結果不明時の追加要求停止。
- 他の文の音声・点検参照・判定記録の保持を実音声で確認。
- MITでコード・Skillを公開。音声・モデル・辞書は対象外。

Python配布バージョンは `0.2.0b0`、GitHubリリース名・予定タグは `v0.2.0-beta`。
