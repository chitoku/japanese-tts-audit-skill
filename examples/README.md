# Small examples

`known-error/` はElevenLabs Multilingual v2 / Junで生成した一文です。ユーザーが「糾弾」をシュウタンと聞いたと報告しました。カナASRにもシュータンが現れ、ほかの語にも差があります。報告は対象語等の範囲であり、人が全文の参照転記を確定したデータではありません。`readings.json` の「何→なに」は文脈に合わせた台本側の期待読みです。

`asr-match/` はElevenLabs v3 / Junで生成した「建立」を含む一文です。カナASRと独立Scribeは原稿と一致しましたが、人の聴取による全文正読保証ではありません。

`transcript.json` は保存済みの音声のみからのカナ認識で、音声SHA-256と結び付いています。サンプルの持ち込みテストは新たなASR推論ではありません。新規推論は `--transcript-json` を外して実行します。

上記2例の音声は本プロジェクト用に有料プランで生成したデモです。第三者のYouTube音声は含みません。音声はコードのMIT対象外で、声やモデルの権利を提供するものではありません。詳細はリポジトリのTHIRD_PARTY_NOTICES.mdを参照してください。

[voicevox-sentence-repair/](voicevox-sentence-repair/README.md) はローカルVOICEVOXで実行した、エージェント経由の一文修正・再点検・差し替えです。修正前後と他の確認済み音声の保持を確認できます。音声：VOICEVOX:青山龍星。新規生成は1回、有料API費用$0。修正後の採用根拠はASRで、人の再聴取はまだです。
