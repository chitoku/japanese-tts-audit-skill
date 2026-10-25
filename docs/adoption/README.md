# 公開・告知後の導入指標

## 告知時点の基準値

取得開始：2026-10-24 17:56 PDT（2026-10-25 00:56 UTC）。[JSON記録](snapshots/2026-10-25T0057Z/snapshot.json)とGitHub APIの応答、[skills.sh画面](snapshots/2026-10-25T0057Z/skills-page.png)を保存しています。

| 指標 | 基準値 | 読み方 |
| --- | --- | --- |
| GitHub clones | 11 | 返却期間の合計。自己テスト等の取得を含む可能性あり |
| GitHub unique cloners | 2 | 外部利用者2人を意味しない |
| GitHub views / unique visitors | 0 / 0 | 返却データは10月23日まで。告知後の閲覧をまだ測れていない |
| GitHub stars / forks | 0 / 0 | 関心の指標。実利用とは別 |
| GitHub referrers / popular paths | 空 | 流入元のデータなし |
| skills.sh INSTALLS / FIRST SEEN | – / – | 未表示。0件に置き換えない |
| skills.sh詳細ページ | 掲載済み | Skill本文・導入コマンドあり |
| skills.sh検索API | 0件 | 詳細掲載とは別。導入数ではない |
| 計測ONの作者自己テスト | 1回 | 外部利用として扱わない |

GitHubの今回の日次データはUTCの2026-10-10〜10-23です。10月21日6 clones、22日4、23日1。これは公開・告知時点に取得できた基準値であり、公開・告知の効果測定結果ではありません。

告知先：

- [Zenn記事](https://zenn.dev/chitoku/articles/d02d7611901d1f)
- [TWEETOKのX投稿](https://x.com/tweetok/status/2114158580291264681)

## 自己テストとの区別

[計測ONの自己テスト記録](../installation-self-test-2026-10-24.json)は2026-10-24 17:18 PDTの1回です。installイベントのHTTP 200を1件確認しましたが、skills.shの公開数への反映は未確認です。以前の導入テストは計測OFFでした。いずれもGitHubでの取得数には影響する可能性があります。

この基準値取得では導入テストもイベント再送も行っていません。skills.shの重複除外・反映条件が分からないため、後日数値が出ても機械的に1を引いて「外部利用者数」とはしません。作者分は独立した注記として残します。外部導入数・実際の点検実行数は現時点では不明です。

## 今後の記録方法

確認するたびに `snapshots/YYYY-MM-DDTHHMMZ/` を追加し、取得時刻（UTCと現地時刻）、GitHub応答、skills.sh表示・検索応答を保存します。過去の記録は上書きしません。GitHub日次データはUTC日付をキーに比較し、重なる期間を二重加算しないでください。ユニーク数も日次の単純合計にはしません。

GitHub Trafficは直近14日なので、長期推移を残すなら少なくとも週1回程度の保存が必要です。今回は定期実行を設定していません。取得コマンド（認証済みの `gh` が必要）：

```sh
gh api repos/chitoku/japanese-tts-audit-skill/traffic/clones
gh api repos/chitoku/japanese-tts-audit-skill/traffic/views
gh api repos/chitoku/japanese-tts-audit-skill/traffic/popular/referrers
gh api repos/chitoku/japanese-tts-audit-skill/traffic/popular/paths
gh api repos/chitoku/japanese-tts-audit-skill \
  --jq '{stargazers_count,forks_count,subscribers_count,open_issues_count}'
```

skills.shは[詳細ページ](https://www.skills.sh/chitoku/japanese-tts-audit-skill/japanese-tts-audit-skill)のINSTALLSとFIRST SEENを確認します。未表示はnullとして残します。取得・閲覧・導入の指標と、Issues等に寄せられた実際の点検・修正報告は分けて扱います。[指標の詳しい説明](../adoption-and-measurement.md)も参照してください。
