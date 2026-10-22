# Saved VOICEVOX recognition regression cases

`voicevox_reviewed_spans.json` contains 44 generated Japanese sentences and their saved, independently obtained Kana Whisper transcripts. Audio and model weights are not bundled. No paid API is needed.

The 15 `error_spans` came from one listener's reviewed pronunciation differences. Tests require those script spans to remain priority candidates. They do not assert full-clip correctness or measure recall on unflagged audio. These examples were used during development and are not a held-out benchmark. Ambiguous sound, contradictory labels and accepted alternate readings are excluded from positive gold spans.
