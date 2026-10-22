# Japanese TTS Audit Skill · v0.2.0-beta

`japanese-tts-audit-skill` は、日本語ナレーションの**台本＋音声**から、読みの差を音声付きで確認するCLIとAgent Skillです。必要ならAgentが既存のTTSサービスで問題のある文だけを再生成し、CLIで点検・差し替えを管理できます。

試用版です。ASRと辞書の差は誤読確定ではありません。「検出ゼロ」は正読保証ではなく、検出率・適合率は未評価です。現在、実音声の動作確認はApple Silicon Macで行っています。

## まず、APIキーなしで試す

Python 3.10以上（検証環境3.12）。リポジトリのルートで実行します。uvを使用する例です。

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python '.[generation]'
.venv/bin/tts-audit check examples/known-error/audio.mp3 \
  --script examples/known-error/script.txt \
  --readings examples/known-error/readings.json \
  --transcript-json examples/known-error/transcript.json --out outputs/recorded-demo
```

`outputs/recorded-demo/report.html` をブラウザーで開きます。この例は**保存済みのカナ認識を再利用**するため、モデル・APIキー・課金は不要です。「糾弾」を「シュウタン」と聞いたというユーザー報告のある合成音声です。ほかの差も含みます。音声はMIT対象外です。

## 自分の音声をローカル点検

```sh
uv pip install --python .venv/bin/python '.[asr,generation]'
.venv/bin/tts-audit check narration.wav --script script.txt --out outputs/check
```

初回に `sbintuitions/kana-whisper` の重み約3.24GBを取得します。Whisper large-v3-turboの追加学習モデルで、Tinyではありません。MacはMPS、利用可能ならCUDA、それ以外はCPUを選びます。Windows/Linuxの実音声推論は本リリースでは未検証です。

認識時に台本・期待読みのヒントは渡しません。台本はSudachiで別に読みへ変換し、ASRと照合します。点検はローカルで、音声の外部送信・有料ASR API・APIキーは不要です。モデルキャッシュ再利用には `--cache-dir CACHE --offline` を指定します。

レポートは音声、期待読み、カナASR、差のハイライト、絵文字判定、聴取メモを表示します。スペースで現在の音声を再生・停止できます。時刻は認識区間の目安で、単語の正確な時刻ではありません。

### 判定をAgentへ直接渡す：ローカル確認サーバー

```sh
.venv/bin/tts-audit serve outputs/check --open
```

表示されたローカルURLで、同じ聴取画面を開きます。判定・聞こえた読み・メモは `outputs/check/review-state.json` に自動保存されます。ダウンロードやチャットへの添付は不要です。「確認終了」で `status: completed` となり、以後の編集は `draft` に戻ります。保存済み表示を確認してください。未判定・保留が残っていても終了でき、それらの件数は明示して残します。終了は正読保証や再生成許可ではありません。

AgentはHTMLを解析せず、このJSONのrun_id・report_sha256・status・notesを読みます。サーバーは127.0.0.1だけで待ち受け、空きポートと推測困難なセッションURLを使います。Ctrl+Cで停止しても保存内容は残り、同じコマンドで再開できます。別の画面からの古い更新は拒否し、入力は画面に保持します。通常利用の手順とJSONの意味は [ローカル確認の仕様](skills/japanese-tts-audit-skill/references/review-server.md) を参照してください。

HTMLをファイルとして直接開く従来の方式も使えます。その場合、メモはブラウザー内に保存され、HTMLファイルには書き戻しません。JSONを書き出してバックアップします。取り込みは次のとおりです。

```sh
.venv/bin/python -m tts_audit.reviews outputs/check exported-notes.json
```

境界付近の差は、切り位置を変えて自動で一度再確認します。文脈まで一致した差だけ優先度を下げ、元の結果を残します。`--no-boundary-recheck` で無効化できます。保存済み認識の持ち込み時は既定で再認識しません。

## 使っている音声生成サービスとの関係

点検は音声ファイルを入力するため、生成元のサービスを問いません。Skillで修正を進める際は、制作者が使っているサービス・モデル・声・設定を引き継ぎます。Agentから操作できるAPIやツールがあればその方法で該当文を再生成し、なければ制作者にその文の再生成を依頼して、返された音声を再点検します。自動的にElevenLabsへ切り替えません。

文単位のプロジェクト管理は生成元に依存しません。**生成・再生成はエージェントが既存サービスで行い、CLIは音声の取り込み・点検・承認・採用版の差し替えを担当します。** 各サービスのAPIや編集ツールへの接続は、その環境で使える手段をエージェントが選びます。全サービスへの接続をCLIが内蔵しているわけではありません。

## 一文ずつ点検・修正する（任意のTTSサービス）

```sh
.venv/bin/tts-audit sentences init --script script.txt --readings readings.json \
  --out outputs/project --provider external --source-json source.json
```

初期化はAPIを呼ばず、音声を生成しません。`--provider external` は既定なので省略できます。`source.json` は元の制作環境の情報です。実際に使用中のサービス・モデル・声・設定を記録し、APIキーは含めません。不明な場合は `--source-json` を省略して初期化できます。

```json
{"provider":"使用中のサービス名","model":"使用中のモデル名","voice":"使用中の声","settings":{}}
```

エージェントが既存サービスで文ごとの音声を生成するか、既存の文単位音声を書き出し、取り込みます。

```sh
.venv/bin/tts-audit sentences import-audio outputs/project --sentence S001 \
  --audio sentence-S001.wav --source-json source.json --note '元の制作環境から取り込み'
.venv/bin/tts-audit sentences check outputs/project --sentence S001 --version latest --cache-dir CACHE --offline
```

`outputs/project/index.html` で文と各版の音声・点検レポートを確認できます。`review` で承認・要修正と根拠を記録します。修正が必要なら、エージェントが**同じサービス・声・設定で該当文だけ**再生成します。かなに開くなど生成専用の変更は別ファイルに残し、元の台本は維持します。

```sh
# 既存サービスで作った修正版を候補として取り込み
.venv/bin/tts-audit sentences import-audio outputs/project --sentence S001 \
  --audio corrected-S001.wav --text-file corrected-S001.txt \
  --source-json source.json --note '既存サービスで該当文のみ再生成'
.venv/bin/tts-audit sentences check outputs/project --sentence S001 --version latest --cache-dir CACHE --offline
.venv/bin/tts-audit sentences review outputs/project --sentence S001 --version latest \
  --verdict approved --basis asr --note '再点検の結果を記録。人の聴取済みとは区別'
.venv/bin/tts-audit sentences select outputs/project --sentence S001 --version v002
```

`v002` は候補の実際の版番号に合わせます。取り込んだだけでは既存の採用版を変更しません。点検・承認後に該当文だけを選び直し、他の確認済み音声を保持します。`--text-file` がない取り込みでは、生成用入力は元台本と同じという仮定を明示します。実際に修正した入力は必ず添えてください。外部サービスの費用はCLIの内蔵予算に自動集計しないため、エージェントがユーザーの予算と既使用分を確認します。

結合は `sentences assemble outputs/project --out outputs/mix`。通常は全採用文の承認が必要です。文ごとの16kHz PCMサンプルを保持して結合し、継ぎ目の試聴音声も出します。話し方・声量・間の自然さは別途確認します。元が連続音声だけの場合、無劣化で該当文を差し替えられるとは限らず、元の編集環境か文単位の書き出しが必要です。詳細は [文単位ワークフロー](skills/japanese-tts-audit-skill/references/sentences.md)。

### 任意：ElevenLabsの内蔵生成アダプター

既存の制作環境がElevenLabsなら、補助機能としてCLIから直接生成する方法も残しています。これを既定の生成先にはしません。

```sh
.venv/bin/tts-audit sentences init --script script.txt --out outputs/eleven-project \
  --provider elevenlabs --model eleven_v3 --voice-id VOICE_ID \
  --budget-usd 15 --baseline-usd PRIOR_RESERVE --max-new-usd NEW_LIMIT
.venv/bin/tts-audit sentences generate outputs/eleven-project --key-file PRIVATE_KEY_FILE --max-requests SENTENCE_COUNT
```

この任意アダプターはテキスト送信とクレジット消費を伴います。秘密キーはプロジェクトに保存しません。予算は安全側の予約額で請求額とは異なり、他プロジェクト・共有アカウントの利用は自動集計しません。既存のElevenLabsプロジェクトと旧形式の呼び出しは引き続き利用できます。

## Codex Skillとして使う

このRepoには、公式のリポジトリ配置である `.agents/skills/japanese-tts-audit-skill` から `skills/japanese-tts-audit-skill` への参照があります。このリポジトリでCodexを開き、CLIを導入したPython環境を使ってください。

依頼例：

> $japanese-tts-audit-skill この台本と音声を点検して、音声付きの要確認レポートを作ってください。Pythonは .venv/bin/python を使ってください。

別の作業場所で使う場合は、Skillフォルダをインストールし、CLIも別途導入します。Skillだけでは認識依存やモデルは入りません。ローカル配置の現在の規約は [OpenAI公式ガイド](https://learn.chatgpt.com/docs/build-skills) を参照してください。Pluginディレクトリへの登録は本リリースの範囲外です。

## 検証と限界

```sh
.venv/bin/python -m unittest discover -s tests -v
```

テストは、読み照合、ASR境界の再確認、聴取記録、予算、再試行防止、版管理、確認済み音声の保持、PCM結合を検証します。生成APIはモックで、実行しても音声生成費用はかかりません。GitHub Actionsの [自動テスト](.github/workflows/tests.yml) はpush・pull request・手動実行で動きます。Ubuntu / Python 3.12でユニットテストと保存済み認識によるスモークテストを実行します。有料APIやASRモデルは使いません。[初回実行は成功しました](https://github.com/chitoku/japanese-tts-audit-skill/actions/runs/39626915152)。テンプレートは docs/github-actions-tests.yml にも残しています。

実際の誤警報には「経典」をヒョーテンと認識した例、読経の許容読みドッキョウ、ツヅケ／ツズケの表記差、短文での認識の揺れがあります。辞書、ASR、TTS、許容読み、曖昧な音を区別してください。本ツールはJoyo公式の採点実装でも、TTSモデルのリーダーボードでもありません。

クリーン環境で確認した範囲と未確認事項は [検証記録](docs/verification.md)。実利用の報告は任意で、インストール数を実行数や効果とみなしません。遠隔テレメトリーはありません。

## ライセンスと協力

コード・Skill・文書はMITです。合成音声、声モデル、認識モデル、辞書、依存ライブラリはそれぞれ別の扱いです。[第三者部品と音声の注意](THIRD_PARTY_NOTICES.md)／[実例の出典](examples/README.md)。

不具合・聴取結果を共有する方法は [CONTRIBUTING.md](CONTRIBUTING.md)。キー・私的な台本や音声を含めず、共有できる範囲の実行条件と確認範囲を添えてください。

## 開発チェックポイント

2026-10-21時点の到達点、Google／VOICEVOX比較の聴取範囲、参照読みの見逃し、次の製品改善は [プロジェクトの現在地](docs/project-status-2026-10-21.md) にまとめています。[研究記録](research/2026-10-21/README.md) の実験用コードと、インストールされるCLIの機能範囲は異なります。
## 誤読実例の正本・ベンチマーク

今後の収集先は [data/benchmark](data/benchmark/README.md) です。[語と誤読の一覧](data/benchmark/WORDLIST.md) から、期待読み・聴取読み・出典・固定音声にたどれます。初版v0.1.0は1,150表記・2,241例文の台帳と、聴取済み誤読32箇所／誤警報対照9箇所の開発評価セットを含みます。収集報告・要裁定・別読みは採点から分離しています。既存の研究記録はこの台帳の出典として残します。
