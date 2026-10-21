# Inputs and outputs

`--readings` accepts a JSON object, for example `{"市場":"いちば","私":"わたし"}`. Longest matching original phrases override dictionary readings; readings are not sent to recognition. Changes apply to all occurrences, so split input or review carefully when the same spelling needs different readings in one script.

`--transcript-json` accepts `{ "audio_sha256": "SHA256_OF_ORIGINAL_FILE", "segments": [{"start_s":0,"end_s":8,"text":"カナノニンシキケッカ"}] }`. Segments must be ordered, nonoverlapping and cover the complete audio. Imported ordinary kanji text is not a kana transcript. Import is for reusing recognition, not supplying human labels as recognition.

Boundary rechecking defaults on for local recognition. A finding within six recognized kana of an internal cut triggers one additional full-audio pass, with low-energy cuts at least three seconds away from the suspect cuts. This is a kana-distance heuristic, not exact word timing. Additional local compute can approach a second full pass. `--no-boundary-recheck` disables it. Transcript imports do not silently start ASR; add `--boundary-recheck` explicitly to recognize the same audio again with the cached model.

`report.json` retains all first-pass `findings`. `review_priority: low_boundary` means the difference was not reproduced and at least six expected kana on either side (or the available edge context) matched on pass two, with at least 80% overall alignment. This is evidence of segmentation sensitivity, not a human correctness label. `boundary_recheck` records the second transcript, all secondary differences, and per-finding decisions. Persistent, uncertain, failed, or dictionary-uncertain checks retain normal priority. Second-pass-only differences remain visible in diagnostics; they are not automatically promoted to proven errors. A zero-priority report is not a guarantee that the full audio is correct.

Output directory:
- `report.html`: playable local review interface; keep beside `audio.wav`.
- `report.json`: candidate spans in script, expected and observed kana, segment-level times, dictionary warnings, model/cache/run provenance.
- `transcript.json`: reusable kana segments bound to the original audio hash.
- `audio.wav`: locally decoded/resampled review audio, 16 kHz PCM16.

The page includes original script and recognized kana. HTML text is escaped. Review notes use a per-run browser-storage key; storage on local file URLs depends on the browser. Export notes JSON for a durable copy. Original source audio/script are not modified. Default inference is local; model retrieval contacts Hugging Face, not an audio recognition API. Nothing is submitted to an external project or published automatically.

Candidate classification is provisional. Normalization treats common long-vowel forms and particles alike but is not the official Joyo Kana-CER normalization/scoring implementation. The report is a review assistant, not a validated automatic pronunciation-error detector.
