# 導入と利用状況の把握

調査・公開確認日：2026-10-24。リポジトリはPublicです。以下のPrivate環境の記録は公開前の検証として残します。

## 結論

主な導入経路は、Anatomyと同じ **VercelのSkills CLI（`npx skills add`）** にします。Skill単位の導入指標を参照でき、複数のAgent向けに配置できるためです。計測だけのために独自npmラッパーを公開する必要はありません。

ただし、これは**実際に使っている人数・実行回数の全数調査にはなりません**。このプロジェクトの成果は、導入の指標と、任意で届いた利用・誤読検出・修正の報告を分けて扱います。音声や台本を送る必須テレメトリーは導入しません。

以前の議論の保存済み照合記録（開発用 `outputs/review/original-plan-reconciliation.json`）でも、人気、導入、成果、明示同意による任意計測を分けていました。共有チャットは今回のWeb取得では本文を取得できなかったため、全文を再読したとはしていません。[Anatomyの現行README](https://github.com/wheresryan22/anatomy#quick-start)もSkills CLIを先頭にし、git・直接ダウンロードを併記しています。

## 何を数えられるか

| 指標 | 分かること | 分からないこと・取りこぼし |
| --- | --- | --- |
| skills.shのSkill別導入指標 | Skills CLI経由で観測された導入の広がり | 手動コピー、別インストーラー、送信無効・失敗、実行回数、継続利用、ユニークな人の総数 |
| GitHub Trafficのclone・閲覧 | リポジトリへの接触・取得の傾向 | ZIP・Raw取得を含む全取得数、導入完了、Skill利用。cloneには自分や自動処理も混ざり得る |
| GitHub Release添付assetのdownload_count | 配布物ごとの取得回数 | 自動生成Source code ZIP全般の取得統計の代用にはしない。実行や人数でもない |
| npmの独自パッケージのダウンロード | そのパッケージが取得された指標 | キャッシュ再利用・再取得・CIとの対応。`skills`全体のnpm取得数は私たちのSkillの導入数ではない |
| Stars・Forks | 関心・保存・派生 | 利用や効果の証拠ではない |
| 任意の利用報告 | 点検完了、誤警報、検出・修正など具体的な成果 | 報告しない利用。報告者には偏りがある |
| 同意のある実行イベント（将来案） | 対応CLI経由の実行・完了の一部 | Agentが指示を読むだけの利用、改変版、送信OFF、成果の正しさ |

これらを合計して「利用者数」と呼びません。経路間の重複を解消できず、漏れと再導入が両方あります。導入数は実利用者数の厳密な下限でもありません。

GitHub Traffic APIは直近14日を返します。長期推移を見るなら定期的に保存し、日付で上書き・重複排除して扱います。14日合計を毎日足してはいけません。保存の自動化は未実装です。[GitHub公式仕様](https://docs.github.com/en/rest/metrics/traffic)

Releaseの添付assetにはdownload_countがあります。現在の公開方針を決めるためだけにReleaseを発行する必要はありません。[GitHub Release asset仕様](https://docs.github.com/en/rest/releases/assets)

## Skills CLIについて確認したこと

公式[FAQ](https://www.skills.sh/docs/faq)では、CLIによる導入イベントがSkill掲載・導入指標の基礎です。これはインストール指標であり、点検の実行数ではありません。集計の表示仕様を確認せず、独立した利用者数や導入成功数として宣伝しません。

ソース確認：Skills CLI 1.7.4、commit `a80e4c9d12d607631249d4d7d059f835d4b2f13a`。

- [telemetry.ts](https://github.com/vercel-labs/skills/blob/a80e4c9d12d607631249d4d7d059f835d4b2f13a/src/telemetry.ts)：installイベントにsource・Skill名・Agent・Skillファイル相対位置等、共通情報にCLI版・検出Agent・CIフラグを扱う実装があります。「匿名」という説明だけで一切情報が出ないとは案内しません。
- [add.ts](https://github.com/vercel-labs/skills/blob/a80e4c9d12d607631249d4d7d059f835d4b2f13a/src/add.ts)：GitHubソースでは公開と確認できた場合に導入イベントを送る実装です。非公開・判定不能は送信をスキップします。選択Skillを送る箇所があるため、個々の導入成功を厳密に計数したものとも断定しません。
- `DISABLE_TELEMETRY=1` または `DO_NOT_TRACK=1` で送信を止められます。この版ではSkills側のセキュリティ監査照会も止まります。GitHubやnpmから取得する通信まで止めるものではありません。
- インストーラーのイベントと、私たちのCLIの通信は別です。`tts-audit`は利用状況を遠隔送信しません。

`npx`はnpmパッケージを実行する仕組みです。ここで実行するのはVercelの`skills`であり、このPython CLIをnpmから入れるという意味ではありません。npmは実行用パッケージをキャッシュします。従ってnpmのダウンロード数から実行数を復元できません。[npm公式npx仕様](https://docs.npmjs.com/cli/v11/commands/npx/)

## READMEの導線

1. 何をAgentへ頼めるか、最初の依頼文を提示する。
2. `npx skills add chitoku/japanese-tts-audit-skill --skill japanese-tts-audit-skill` を主経路にする。既定は現在の制作プロジェクトへ配置。Agentを選択できる。
3. Python CLIの導入は別手順と明示。まず保存済み認識の無料デモ、必要なら約3.24GBの認識モデルを入れる。
4. Codex限定なら `-a codex`、Claude Codeなら `-a claude-code`。全プロジェクト共通の導入は任意の `-g`。
5. Node不要のgit／ZIP／Agentの既存インストーラーも残す。計測の都合で利用を阻害しない。

Skills CLI 1.7.4はNode.js 22.20以上を要求します。[配布CLIの設定](https://github.com/vercel-labs/skills/blob/a80e4c9d12d607631249d4d7d059f835d4b2f13a/package.json)。CodexはローカルSkill配置に対応しますが、OpenAI公式は再利用配布にPluginを推奨しています。今回の複数Agent向け導線としてSkills CLIを選び、Codex Plugin化は別の将来課題にします。[OpenAI公式ガイド](https://learn.chatgpt.com/docs/build-skills)

## 公開時と公開後

- 公開前：認証済み取得と、隔離フォルダでのSkill発見・配置を確認する。私的な制作プロジェクトやグローバル設定へ試験配置しない。
- 公開直後：未認証の新しい環境でREADMEのリモート導入を確認する。skills.shの掲載・指標が実際に表示されるか確認し、確認前にはバッジや導入数を掲げない。
- 初期運用：skills.sh指標、GitHub Traffic、任意の利用報告を別々に記録する。自己テスト・CIは区別できる範囲で注記する。
- 任意報告では、CLI版、Agent、OS、点検完了の可否、誤警報・実際の誤読・修正の有無を尋ねる。音声・台本・パス・秘密情報の提出は求めない。未報告を成功とも失敗とも数えない。
- 継続利用がどうしても必要なら、その時点で明示同意・既定OFFの最小イベントを設計する。今回は追加しない。

ローカルの `report.json` と `review-state.json` はAgentが制作を続けるための記録です。存在しても、作者が集計できる遠隔利用統計にはなりません。

## 今回の検証結果

- 2026-10-24、隔離した制作フォルダで `npx --yes skills@1.7.4 add chitoku/japanese-tts-audit-skill --skill japanese-tts-audit-skill -a codex -y` が成功。既存のGitHub認証でPrivate Repoを取得し、1 Skillを `.agents/skills/` に配置できました。
- ローカルソースからの導入も成功し、Skillに含まれる6ファイルが元と一致しました。グローバル導入は行っていません。
- 両試験とも `DISABLE_TELEMETRY=1 DO_NOT_TRACK=1` を指定。skills.shへの導入計数・掲載は試験していません。CLIを実行するnpmパッケージの取得通信は発生しています。
- GitHub Traffic APIの読み取りも成功。ただしPrivate期間・今回の取得試験を含むため、現在の数を外部利用実績とはみなしません。
- READMEと本資料のローカルリンク・差分書式を確認。保存済み認識の無料デモを現行ソースで実行し、既知の「糾弾」候補とHTML・音声の出力を確認。serveの引数も確認しました。実行コードは変更していないため、ASRモデルの再実行や有料生成、ユニットテストの再実行はしていません。
- 上記の公開前検証時点では一般公開していませんでした。公開後の検証は次節を参照してください。npm公開・GitHub Release発行・遠隔実行計測の追加は行っていません。


## Public公開後の未認証導入（2026-10-24）

ユーザーの明示的な指示でGitHub RepoをPublicへ変更しました。新しい隔離フォルダで次の導入に成功し、配置された6ファイルが配布元のSkillと一致しました。

```sh
npx --yes skills@1.7.4 add chitoku/japanese-tts-audit-skill --skill japanese-tts-audit-skill -a codex -y
```

検証時はGitHubトークン環境変数を除外し、Gitのグローバル・システム設定と認証ヘルパー・追加HTTPヘッダーを無効化しました。PATHから `gh` を除き、対話認証も禁止しました。従って、既存のGitHubログインには依存しない導入です。OS・npmのキャッシュは再利用しており、完全に新しいOS環境の試験ではありません。

自己テストを公開導入の指標に混ぜないため `DISABLE_TELEMETRY=1 DO_NOT_TRACK=1` を指定しました。skills.shの掲載・集計は今回の確認対象外です。既存の制作プロジェクト・グローバルSkill設定・聴取結果は変更していません。GitHub Releaseは発行していません。


## 計測ONの自己導入テスト（2026-10-24）

2026-10-24 17:18（America/Los_Angeles）に、作者の隔離した一時プロジェクトで、計測ONの導入を**1回だけ**実行しました。外部利用者による導入として数えません。グローバル配置・既存の制作環境には触れていません。

```sh
npx --yes skills@1.7.4 add chitoku/japanese-tts-audit-skill \
  --skill japanese-tts-audit-skill -a codex -y \
  --metadata '{"self_test":true,"purpose":"author_listing_verification","date":"2026-10-24"}'
```

`DISABLE_TELEMETRY` と `DO_NOT_TRACK` をこの子プロセスの環境から外し、正常終了と6ファイルの一致を確認しました。送信を生成し直すのではなく、通常のCLIのfetch応答だけをローカルで記録し、installイベントへのHTTP 200を1件確認しています。

直後は詳細ページが未掲載表示、検索結果は0件でした。その後、Chromeで[詳細ページ](https://www.skills.sh/chitoku/japanese-tts-audit-skill/japanese-tts-audit-skill)にSkill本文と導入コマンドが表示されることを確認しました。一方、INSTALLSとFIRST SEENは「–」で、公開導入数の反映は未確認です。検索結果の最終確認は記録JSONを参照してください。イベントのHTTP 200と詳細ページの表示は、公開カウンターへの反映や検索掲載の完了を保証しません。再導入・イベント再送は行っていません。

[自己テストの記録](installation-self-test-2026-10-24.json)に実行日時・件数・照合結果・掲載確認を保存しています。今後表示されるStatsには作者の自己テストが含まれる可能性があると注記し、外部利用者数と区別してください。集計・重複除外のルールが不明なまま「表示数から1を引けば外部利用者数」とは扱いません。
