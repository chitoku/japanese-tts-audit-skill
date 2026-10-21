# Release procedure · v0.2.0-beta

公開用Repo名は `japanese-tts-audit-skill` です。調査時の `youtube-tts-misreading-pilot` から、制作者向けの点検Skillという役割が分かる名前に変更しました。CLIパッケージ名は `ja-tts-pronunciation-audit`、Skill呼出名は `tts-pronunciation-audit` です。

このフォルダは調査用のwork/や全outputs/から、許可した公開ファイルだけを取り出したものです。キー、アカウント残高、ユーザー端末パス、モデル重み、仮想環境を追加しないでください。

公開前に、ソースのMIT範囲、音声の出典と扱い、docs/verification.mdの実行結果、最終聴取の結果を確認します。最終聴取で修正前も正読だった場合は、その例を誤読修正成功として紹介せず、ASR候補を受けた再生成・保持の実演と記述します。

確認後にGitHubリポジトリへコミット／pushし、`v0.2.0-beta`タグとGitHub prereleaseを作成します。Pythonパッケージは `0.2.0b0` です。PyPI登録やPluginディレクトリへの提出は別作業です。現時点で外部作成・push・タグ発行を行ったという意味ではありません。

添付候補：wheel、sdist、ソースアーカイブ、SHA256SUMS、短い実演。全調査データやモデル重みは添付しません。READMEとリリース本文のリンクは、実際に作成したリポジトリURLに合わせて確認してください。

## Private Repoへの保管

`https://github.com/chitoku/japanese-tts-audit-skill` にPrivate Repoとして保管します。一般公開やリリース発行とは別です。現在の認証にworkflowスコープがないため、自動テスト設定は `docs/github-actions-tests.yml` として同梱し、自動実行を有効にしていません。workflowを登録できる認証で `.github/workflows/tests.yml` へ配置すると有効化できます。
