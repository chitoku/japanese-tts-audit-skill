# v0.2.0-beta 検証記録

2026-10-21、Apple Silicon Mac / Python 3.12.14。公開用Repoは `japanese-tts-audit-skill`。

## 確認済み

- 新規venvへwheelを通常インストール。editableとsystem-site-packagesは使用せず、インポート元がvenv内であることを確認。
- インストールしたパッケージで31テスト成功。生成APIはモック。
- Repo外の空白を含む作業パスで、同梱音声と保存済み認識からHTML/JSONを生成。
- Skillの実行ラッパーから実際のローカルKana Whisperを動かし、同梱の「糾弾」が要確認候補に入ることを確認。APIキー・有料APIは未使用。
- 新規Python環境ですが、パッケージのダウンロードキャッシュと既存の固定リビジョンのモデル重みを再利用。モデルを含めた新規ダウンロードの検証ではありません。
- 実際のCodex Skillローダーで検出し、検出先がこの公開用Repo内であることを確認。Agentの新規ターンは実行していません。
- 別途行った文単位の制作実演では、一文の差し替え時に他の8文の記録を保持し、結合後の音声サンプルの一致も検証。

## 公開前に残る確認

最終聴取キット（9項目・約42秒）の人による判定は未受領です。ASR間の不一致をTTSの誤読確定とは扱いません。修正前の朝も正読だった場合、誤読修正成功とは紹介しません。完成音声として紹介する場合は通し聴きと文間の自然さも確認します。

自然言語だけでのSkill自動選択、Windows/Linuxでの実音声推論、一般的な検出率・適合率、実利用時の時間短縮は未検証です。GitHub Actionsは下記の追加検証で有効化・実行を確認しました。

クリーン環境検証後、Private Repoへのpushまで進めました。一般公開・タグ・prerelease発行・PyPI公開は行っていません。

## 追加検証：GitHub Actions（2026-10-21）

本人認証でGitHub CLIにworkflow権限を追加し、.github/workflows/tests.ymlを登録しました。RepoはPrivateのままです。push・pull request・workflow_dispatchで実行し、ジョブの権限はcontents: read、上限10分です。

[初回実行](https://github.com/chitoku/japanese-tts-audit-skill/actions/runs/39626915152) は成功しました。対象コミットは e6c7218176b88fd93cb19091a864e74b5b6365bc。Ubuntu / Python 3.12で依存導入、31テスト、保存済み認識のスモークテストが通り、糾弾の要確認候補とreport.html・audio.wavの生成を確認しました。生成APIはモックで、APIキー・有料API・ASRモデルのダウンロードは不要です。

Linuxでの実際のKana Whisper推論を検証するCIではありません。モデルによる点検は上記Apple Siliconで確認しています。一般公開・Release発行はしていません。
