# 画面紹介用の画像素材

2026-10-23時点の実装を、実際のv2合成音声のレポートから撮影しました。画像はブラウザーで実際に描画した画面です。画面デザインのモックアップではありません。

| ファイル | 用途 |
| --- | --- |
| [timeline-review-readme.png](assets/screenshots/timeline-review-readme.png) | README・記事向けの全体像（1600×1000） |
| [timeline-review-1920x1080.png](assets/screenshots/timeline-review-1920x1080.png) | 動画向けの全画面素材（フルHD・16:9） |
| [timeline-review-light-readme.png](assets/screenshots/timeline-review-light-readme.png) | Light表示のREADME・記事用（1600×1000） |
| [timeline-review-light-1920x1080.png](assets/screenshots/timeline-review-light-1920x1080.png) | Light表示の動画用（フルHD・16:9） |
| [review-card-and-queue.png](assets/screenshots/review-card-and-queue.png) | 台本と認識結果の比較、確認キューを説明する切り抜き |
| [audio-timeline-detail.png](assets/screenshots/audio-timeline-detail.png) | 台本・カナ・波形、全体タイムラインを説明する切り抜き |
| [text-selection-manual-flag.png](assets/screenshots/text-selection-manual-flag.png) | Light表示：文字選択からの手動指摘（1600×1000） |
| [manual-flag-context-menu.png](assets/screenshots/manual-flag-context-menu.png) | Light表示：手動指摘の右クリック削除（1600×1000） |

## 素材の意味

- 「節約」を選択した場面。台本側は「セツヤク」、元のカナASRは「カイツヤク」。赤は、この実験で人が「修正が必要」と判定した状態です。元のASR・聴取結果を使い、宣伝用に誤読や判定を作っていません。
- 元の判定データを作業用コピーに読み込み、選択位置と表示サイズだけを調整して撮影しています。元のセッションや確認結果を変更していません。
- 個人のファイルパス・ブラウザーのURL・認証用トークンは写していません。ファイル名とセッションIDは撮影用に置き換えています。
- 赤は検出精度の数値を意味しません。残り件数はこの例の未確認候補数で、音声全体の正読保証や誤読の件数ではありません。
- 時刻はKana Whisperの音声から推定したものです。厳密な単語境界ではありません。

文字選択と右クリックメニューの2枚は、操作を説明するため作業用コピーに新しい未確認の手動指摘を追加して撮影しています。これは新たに誤読を発見・聴取確認したという実績ではありません。元の判定データは変更していません。

## 動画での使い方

全画面で位置関係を紹介 → カードの「セツヤク／カイツヤク」へ寄る → 下のタイムラインで音声を確認する流れを説明 → 「1：問題なし／2：修正が必要／3：保留」と自動保存を見せる、という順に使えます。画像は静止画素材です。操作や音声を伴う実演の録画は別途必要です。

紹介文では「日本語音声の誤読候補を、音声を聴きながら確認するCLI＋Agent Skill」と説明してください。「すべての誤読を自動で直す」「全エンジンで検出精度を検証済み」とは表現しません。

画像は本リポジトリのコードと同じMITで利用できます。合成音声やモデルの権利条件まで変更するものではありません。元音声はこの画像素材集には含めていません。
