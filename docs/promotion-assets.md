# 画面紹介用の画像素材

2026-10-24の実装をChromeで撮影しました。画像は実際のUIの画面です。再利用するときは比率を維持してください。今回の全体画像は約1223px幅のウィンドウで撮影しており、フルHD素材ではありません。

| ファイル | 用途 |
| --- | --- |
| [timeline-review-readme.png](assets/screenshots/timeline-review-readme.png) | Dark表示の全体像 |
| [timeline-review-full.png](assets/screenshots/timeline-review-full.png) | Dark表示の全画面素材 |
| [timeline-review-light-readme.png](assets/screenshots/timeline-review-light-readme.png) | Light表示の全体像 |
| [timeline-review-light-full.png](assets/screenshots/timeline-review-light-full.png) | Light表示の全画面素材 |
| [review-card-and-queue.png](assets/screenshots/review-card-and-queue.png) | 自動検出カード、共通の入力欄、確認キューの切り抜き |
| [audio-timeline-detail.png](assets/screenshots/audio-timeline-detail.png) | 台本・カナ・波形と全体タイムラインの切り抜き |
| [queue-needs-repair.png](assets/screenshots/queue-needs-repair.png) | 要修正の件数と絞り込み |
| [manual-selection-rainbow.png](assets/screenshots/manual-selection-rainbow.png) | 実操作動画8.2秒地点：選択した「ソーサイ」だけを虹色で示す場面（タイムラインの切り抜き） |
| [text-selection-mode.png](assets/screenshots/text-selection-mode.png) | 台本・ASRをなぞる文字選択モード |
| [text-selection-manual-flag.png](assets/screenshots/text-selection-manual-flag.png) | 手動指摘の共通編集欄 |
| [manual-flag-context-menu.png](assets/screenshots/manual-flag-context-menu.png) | 手動指摘の右クリック削除 |

## 素材の意味

- 全体画像は約63秒の実際のv2合成音声と、保存済みのカナASR・聴取結果から作業用コピーを作り、「掘削」を選択して撮影しました。赤はこの実験の人の判定で、検出精度の数値ではありません。
- `text-selection-manual-flag.png` は、制作者が録画した20.47秒の操作動画の16.5秒地点から切り出した画像です。「相殺」のASR文字「ソーサイ」を選び、聞こえた読み「ソーサツ」とメモを入力した操作例です。音声の誤読を確定する実績ではありません。ほかの文字選択・削除画像は作業用コピーでの操作例です。
- 作業用コピーだけを編集し、元の音声・ASR・聴取記録は変更していません。個人の入力パス・ブラウザーURL・認証用トークンは写していません。ファイル名とセッションIDは画面に表示されます。
- 残り件数はこの例の未確認候補数です。正読保証や、音声全体の誤読件数ではありません。時刻は音声の推定または文字列の対応による位置目安です。

## 動画での使い方

全体像 → 音声を聴いて1／2／3で判定 → 文字をなぞって手動追加 → 読みとメモを入力 → Tab・Spaceで再開 → 要修正に絞ってエージェントへ修正を依頼、という流れを紹介できます。虹色の背景やボタンのグローは静止画では動きを示せないため、操作録画で見せてください。

紹介文では「日本語音声の誤読候補を、音声を聴きながら確認するCLI＋Agent Skill」と説明してください。「すべての誤読を自動で直す」「全エンジンで検出精度を検証済み」とは表現しません。

画像は本リポジトリのコードと同じMITで利用できます。合成音声やモデルの権利条件まで変更するものではありません。元音声はこの画像素材集には含めていません。
