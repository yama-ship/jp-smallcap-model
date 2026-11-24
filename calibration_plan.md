# 較正計画(草案 v0.2・オーナー承認待ち)

- 位置づけ:CHARTER 第7章の較正(手計算との照合 → 既知の結果の再現)の計画。CHARTER 第6章により、オーナーの事前承認が必要。PR のマージで承認とし、decisions.md の D-0027 になる。
- 目的:実験器が正しく計算できているかを確かめる。仮説の検証ではない。
- 前提:data_spec v0.3(D-0028。このPRで v0.2 から改める)。無料プランで進める(D-0020)。
- 固定の原則:期間、銘柄の選び方、合格の目安は、計算を始める前にこの計画で数字まで固定する。結果を見てから動かさない。変更が必要になったら、計算を始める前に新しい版としてオーナーの承認を得る。
- 質問:PR の本文に置く。回答に合わせて版を上げてからマージする。
- 作成:Claude(構築者)、2026-11-24。会話 https://claude.ai/code/session_01UR6KMencQ76zSADRxdRD3p
- 版の履歴:v0.1 では、French の作り方・J-Quants の項目名・Actions キャッシュの条件を原本で確かめられていなかった。2026-11-24 に原本で確かめ(第7節)、期間と作り方を直して v0.2 とした。

## 1. 期間

日付の計算の根拠:無料プランで取れるのは、上場銘柄一覧・株価四本値・バリュエーション指標・財務情報のいずれも「12週間前〜2年12週間前まで」(J-Quants「契約ごとに利用可能なAPIとデータ格納期間」https://jpx-jquants.com/ja/spec/data-spec 、2026-11-24 確認)。2026-11-24 時点の窓は 2024-09-01〜2026-09-01(data_spec 第2節)。French の日本のデータは、日次で 2026-09-30 まで公開されている(第7節、2026-11-24 確認)。

| 用途 | 期間 | 備考 |
|---|---|---|
| 取得する全期間 | 2024-10-01〜2026-08-31 | 窓に収まるのは、取得日が 2026-11-23〜2026-12-24 のとき(下記) |
| 手計算との照合 | 2025-03-01〜2025-08-31 の営業日 | 6か月。3月末と6月末の基準日を含む |
| 再現(SMB・HML) | 2025-07-01〜2026-08-31 の営業日 | 2025年6月末と2026年6月末の組み替え。2025年6月末の簿価の扱いは第3-2節(質問 Q3) |
| 再現(Mom) | 2025-11-01〜2026-08-31 の営業日 | French は t−251 日の価格を要する(第3-3節)。2024-10-01 から 251 営業日を確実に過ぎた月初から |

- 取得の期限:取得する全期間の始まり(2024-10-01)が窓に入っているのは、取得日が 2026-12-24 までのとき(2024-10-01 + 2年12週間)。終わり(2026-08-31)が窓に入るのは、取得日が 2026-11-23 以降のとき。最初の取得はこの間に行い、取得したデータはキャッシュに残す(data_spec 第6節)。
- 期限を過ぎた場合(事前に決めておく扱い):取得する全期間の始まりを「最初の取得日の窓の始まりの翌月1日」に移す。Mom の比較期間の始まりも、同じ月数だけ後ろに移す。手計算の期間と、SMB・HML の比較期間は変えない。どちらも、移したことを実行記録に残す。
- キャッシュが消えた場合の扱いは data_spec 第6節(v0.3)に従う。

## 2. 手計算との照合

### 2-1. 銘柄の選び方(機械的なルール)

- 対象:手計算の期間(2025-03-01〜2025-08-31)のどこかで上場していた全銘柄(/equities/master と /equities/bars/daily による)。
- 条件(data_spec 第5-1節)ごとに、条件に合う銘柄を集め、銘柄コードの昇順に並べ、乱数で1つ選ぶ。
  1. 配当:期間内に権利落ち日(data_spec 第3節のルールで決めたもの)があり、期間内に分割・併合・上場廃止・無約定日がない銘柄
  2. 分割:期間内に ExRT=1(分割)の日がある銘柄
  3. 無約定日:期間内に、四本値・取引高・売買代金が揃って Null の日(data_spec 第8節)が1日以上ある銘柄。市場全体が止まった日は数えない
  4. 上場廃止:期間内に株価四本値が返る最後の営業日があり(data_spec 第7節)、期間内に20営業日以上の約定がある銘柄
  5. 通常:期間を通して上場し、1〜4 のどれにも当たらず、期間内に配当の権利落ち日もない銘柄
- 乱数:Python 標準の random.Random(20261124) を使い、条件1から5の順に、候補の並びに対して choice を1回ずつ呼ぶ。すでに選んだ銘柄は、後の条件の候補から除く。種(20261124)は、データを見る前にこの計画で決めた。
- 候補が0件の条件は「該当なし」と記録し、別の条件で埋めない。
- 選んだ結果を見て選び直さない。選定は実験器で1回だけ実行し、run ID と銘柄コードを実行記録に残す。選定のコードにバグが見つかって再実行した場合は、バグ修正による再実行として区別して記録する(CHARTER 第7章)。種は変えない。
- data_spec が照合対象に含めるよう求めている「分割またぎ」の配当(第3節)とライツイシュー(第7節)は、上の5条件に入っていない。扱いは質問 Q1。

### 2-2. 照合する項目と合格の目安

手計算と実験器は、同じルール(data_spec)で同じ値を計算する。したがって、差は丸めかバグのどちらかで、近似の誤差は差の理由にならない。

| 項目 | 合格の目安 |
|---|---|
| 調整前の価格、AdjFactor | 完全一致(API の値そのもの) |
| 保有株数(分割・併合のたびに AdjFactor で換算) | 完全一致 |
| 配当(1株あたりの額、権利落ち日、分割で換算した額) | 完全一致 |
| 日次リターン | 各日の差の絶対値が 0.0001%ポイント以下 |
| 現金残高(配当の受取りを含む) | 各日の差の絶対値が 1円以下 |

- data_spec 第5-1節の「リターンの差は0.1%ポイント以内」は案だった。上の理由で、丸めの範囲だけを許す値に固定した。
- 権利落ち日の近似と実際の権利落ち日のずれは、合否には使わず、大きさだけを記録する。
- 手計算の模擬ポートフォリオ:選んだ銘柄を、期間の最初の営業日の終値で、各銘柄100株ずつ買い、期間の終わりまで持つ。現金の初期値は、買付額の合計とちょうど同じにして、買付後の残高を0円とする。手数料は0円とする。

## 3. 既知の結果の再現

比較先は French の Japanese 3 Factors [Daily] の SMB・HML と、Japanese Momentum Factor (Mom) [Daily](ファイルは第7節)。Mkt-RF は使わない(data_spec 第5-2節)。作り方は French の原文(第7節に引用)に合わせ、合わせられない点はここに書く。

### 3-1. 共通

- 対象銘柄:上場銘柄一覧にある内国の普通株式。ETF・REIT などを除く判定に使う項目は、上場銘柄一覧の仕様で確かめて実験器のコードに書き、実行記録に残す。
- 時価総額(ME):バリュエーション指標 API の MktCap(百万円)を使う。自己株式を控除した株式数 × 終値で計算されたもので(J-Quants「バリュエーション指標」https://jpx-jquants.com/ja/spec/eq-valuation 、2026-11-24 確認)、French の市場データと株式数の定義が同じとは限らない。この差は合わせられない点として記録する。
- リターン:調整済み価格と data_spec 第3節の配当で計算する(French 側も配当を含む)。円建てのまま計算する(French は米ドル建て。ロング・ショートだけを比べるので、data_spec 第5-2節の判断のとおり)。
- 6つのポートフォリオはすべて時価加重。

### 3-2. SMB と HML

- 組み替え:毎年6月末。大型株は、6月末の時価総額で上位90%を占める銘柄、小型株は残りの10%(French の原文「Big stocks are those in the top 90% of June market cap for the region」)。
- B/M のブレークポイント:大型株の B/M の 30・70 パーセンタイル。サイズと B/M の独立した 2×3 の分類で6つのポートフォリオを作る。
- SMB = 1/3(SV+SN+SG) − 1/3(BV+BN+BG)、HML = 1/2(SV+BV) − 1/2(SG+BG)。
- 対象:t年12月末と t+1年6月末の時価総額があり、t年の簿価(正の値)がある銘柄(French の原文「market equity data for December of t−1 and June of t, and (positive) book equity data for t−1」)。
- 簿価(BE):財務情報(/fins/summary)の ShEq(自己資本)。当会計期間の種類(CurPerType)が FY の、開示日時で最新のレコード(data_spec 第7節)。B/M = BE ÷ 前年12月末の ME。
  - Eq(純資産)ではなく ShEq を使う。Eq は非支配株主持分などを含むため。
- **合わせられない点(質問 Q3)**:French の「t−1 年の簿価」を、t−1 年中に終わる会計年度と読むと、2025年6月末の組み替えには、3月決算の会社では 2024年3月期の簿価が要る。その決算短信は 2024年5月ごろの開示で、取得する全期間(2024-10-01〜)より前になり、無料プランでは取れない。この計画の案では、2025年6月末の組み替えに限り、2025-06-30 までに開示された最新の通期の簿価(3月決算なら 2025年3月期)を使う。2026年6月末の組み替えは、French の読み方どおり(2025年中に終わる会計年度の簿価)で作る。

### 3-3. Mom(French の日次版)

- 毎営業日に組み替える。t 日のポートフォリオは t−1 日の終わりに作り、t−250 日から t−20 日までの累積リターンで並べる。対象は、t−251 日の終わりの価格と、t−21 日のリターンがある銘柄(French の原文)。
- サイズも毎営業日に分ける。t−1 日の時価総額で上位90%を占める銘柄を大型株とする(90%は3ファクターの原文による。日次モメンタムの原文には割合が書かれていない)。原文には「2x3 sorts on size and lagged momentum ... are formed daily」とあるだけで、サイズの基準の時点は書かれていない。そのため、この読み方を採ったことを記録する。勝ち・負けのブレークポイントは、大型株の累積リターンの 30・70 パーセンタイル。
- Mom(WML)= 1/2(SW+BW) − 1/2(SL+BL)。

### 3-4. 合格の目安

- SMB、HML、Mom のそれぞれで、次の両方を満たすこと:
  - 日次リターンの相関:0.80 以上
  - 変動の大きさの比(自作の標準偏差 ÷ French の標準偏差):0.80 以上 1.25 以下
- 相関の計算は、両方の系列に値がある日だけで行う。日付は、それぞれの系列の日付をそのまま突き合わせる。
- 第3-2節の「合わせられない点」があっても目安は変えない。Q3 の回答で扱いが変わる場合は、計算の前に版を上げる。

## 4. 不合格だったとき

- 目安を下回ったら、発見ではなくバグを疑う(CHARTER 第7章)。原因を探して直し、直した実験器で同じ期間・同じ銘柄・同じ目安で計算し直す。目安は変えない。
- 直したことは、バグ修正による再実行として記録する。直した部分が実験器の核なら、その版を較正済みの版とする。
- 原因が見つからないまま目安を満たさない場合は、そこで止め、オーナーが判断する。その判断は決定ログに残す。

## 5. 記録と保存

- 実行記録(runs/):run ID、コードと設定のコミット、取得したファイルのハッシュ値(SHA-256)、キャッシュの大きさ、選んだ銘柄コード、照合の結果(項目ごとの一致件数と最大の差)、再現の結果(相関と変動の比)、French のファイルを取得した日とそのハッシュ値。市場データそのものは残さない(CHARTER 第8章、data_spec 第6節)。
- 手計算の表はオーナーが作り、市場データを含むため、リポジトリにも会話にも入れない。リポジトリに残すのは照合の結果だけ。手計算に使う元のデータの入手方法は、質問 Q2。
- ホールドアウトの使用履歴(holdout_log.md):取得する全期間(2024-10-01〜2026-08-31)を、較正で使った期間として記録する(CHARTER 第7章「使った期間はホールドアウトの使用履歴に記録する」を、取得して計算に使える状態にした期間と読む)。

## 6. 計算を始める条件

1. この計画と data_spec v0.3 がマージされている(D-0027、D-0028)。
2. キャッシュを保つ定期実行(data_spec 第6節)が動いていて、キャッシュの最終アクセス日時が更新されることを確かめてある。
3. 実験器が、合成データで動くことを確かめてある(CHARTER 第7章)。

## 7. 原本で確かめたこと(2026-11-24)

- French Data Library(https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
  - ファイル:ftp/Japan_3_Factors_Daily_CSV.zip(Fama/French Japanese 3 Factors [Daily])、ftp/Japan_Mom_Factor_Daily_CSV.zip(Japanese Momentum Factor (Mom) [Daily])。
  - 3ファクターの作り方(Data_Library/f-f_3developed.html):「Daily Returns: July 1, 1990 – September 30, 2026」「All returns are in U.S. dollars, include dividends and capital gains」「we sort stocks in a region into two market cap and three book-to-market equity (B/M) groups at the end of each June. Big stocks are those in the top 90% of June market cap for the region, and small stocks are those in the bottom 10%. The B/M breakpoints for a region are the 30th and 70th percentiles of B/M for the big stocks of the region.」「SMB and HML for July of year t to June of t+1 include all stocks for which we have market equity data for December of t−1 and June of t, and (positive) book equity data for t−1.」
  - 日次モメンタムの作り方(Data_Library/f-f_developed_daily_mom.html):「Daily Returns: December 1, 1990 – September 30, 2026」「The 2x3 sorts on size and lagged momentum to construct WML are formed daily. For portfolios formed at the end of day t−1, the lagged momentum return is a stock's cumulative return for day t−250 to day t−20. The momentum breakpoints for a region are the 30th and 70th percentiles of the lagged momentum returns of the big stocks of the region.」「To be included in a portfolio for day t (formed at the end of the day t−1), a stock must have a price for the end of day t−251 and a good return for t−21.」
- J-Quants の仕様
  - 財務情報(https://jpx-jquants.com/ja/spec/fin-summary):「Eq 純資産」「ShEq 自己資本」「CurPerType 当会計期間の種類 [1Q, 2Q, 3Q, 4Q, 5Q, FY]」「CurFYEn 当事業年度終了日」「開示順序の判定には開示日時・時刻(DiscDate・DiscTime)をご参照ください」「決算短信(非連結)を提出する企業では、接頭辞 NC がない項目に個別の値を収録」。
  - データ格納期間(https://jpx-jquants.com/ja/spec/data-spec):Free は、上場銘柄一覧・株価四本値・バリュエーション指標・財務情報が「12週間前〜2年12週間前まで」。
  - バリュエーション指標(https://jpx-jquants.com/ja/spec/eq-valuation):MktCap は「時価総額(百万円)」で、「株式数には、自己株式を控除した株式数を用います」。
- GitHub Actions のキャッシュ:data_spec 第6節(v0.3)に引用。
