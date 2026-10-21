# Japanese TTS Audit Skill · v0.2.0-beta

`japanese-tts-audit-skill` は、日本語ナレーションの**台本＋音声**から、読みの差を音声付きで確認するCLIとAgent Skillです。必要なら一文ずつ生成し、問題のある文だけを再生成・差し替えできます。

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

CLI内蔵の文単位生成・プロジェクト初期化は現在ElevenLabs向けです。他サービスの生成アダプターや汎用の初期化機能は未実装で、外部サービスの費用も内蔵予算には自動集計しません。他サービスではそのサービス側の編集・生成機能と、既存の `tts-audit check` を組み合わせます。

## 一文ずつ生成・修正する

この機能だけはElevenLabsへのテキスト送信とクレジット消費があります。既存音声の点検依頼から、自動的に有料生成へ進むことはありません。

```sh
.venv/bin/tts-audit sentences init --script script.txt --out outputs/project \
  --model eleven_v3 --voice-id VOICE_ID \
  --budget-usd 15 --baseline-usd PRIOR_RESERVE --max-new-usd NEW_LIMIT
.venv/bin/tts-audit sentences generate outputs/project --key-file PRIVATE_KEY_FILE --max-requests SENTENCE_COUNT
.venv/bin/tts-audit sentences check outputs/project --cache-dir CACHE --offline
```

`VOICE_ID`、既使用分の `PRIOR_RESERVE`、今回上限の `NEW_LIMIT`、文数を置き換えてください。秘密キーはリポジトリ外のファイルに保存します。プロジェクトには保存されません。API権限はText to Speechと、含有クレジットを確認するUserの読み取りが必要です。予算計上は安全側の予約で、請求額ではありません。別プロジェクト・共有アカウントでの別利用は自動集計しません。

`outputs/project/index.html` で文の分け方・全バージョンを確認できます。句読点による自動分割を直す場合は、初期化時に `--sentences-json` で指定します。未生成の文だけを生成し、再実行しても既存音声は作り直しません。

修正は `review needs_revision → generate --regenerate → check --version latest → review approved → select` の順で行います。生成しただけでは採用版を変更せず、確認済みの他の文と旧版を保持します。詳細は [文単位ワークフロー](skills/japanese-tts-audit-skill/references/sentences.md)。

結合には `sentences assemble` を使います。通常は全採用文の承認が必要です。未承認を含む試聴用には `--preview` を明示します。各文の16kHz PCMサンプルを変更せず結合し、完全一致を検証します。文間の声量・間・話し方の自然さは、人の聴取で確認します。

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
