# 較正計画(草案 v0.3・オーナー承認待ち)

- 位置づけ:CHARTER 第7章の較正(手計算との照合 → 既知の結果の再現)の計画。CHARTER 第6章により、オーナーの事前承認が必要。PR のマージで承認とし、decisions.md の D-0027 になる。
- 目的:実験器が正しく計算できているかを確かめる。仮説の検証ではない。
- 前提:J-Quants Standard を較正の前に契約する(D-0029。D-0020 の契約時期を前倒し)。data_spec v0.3(D-0028)。
- 固定の原則:期間、銘柄の選び方、合格の目安は、計算を始める前にこの計画で数字まで固定する。結果を見てから動かさない。変更が必要になったら、計算を始める前に新しい版としてオーナーの承認を得る。
- 作成:Claude(構築者)、2026-11-24〜25。会話 https://claude.ai/code/session_01UR6KMencQ76zSADRxdRD3p
- 版の履歴:
  - v0.1:French の作り方、J-Quants の項目名、Actions キャッシュの条件を原本で確かめられていなかった。
  - v0.2:原本で確かめて直した。無料プランの窓では、French と同じ時点の簿価がそろわないことが分かった。
  - v0.3(2026-11-25):オーナーの回答(Q1〜Q5)を反映した。Standard を前倒しで契約し、較正の期間を古い2年に移して、French と同じ時点の簿価で再現する。無料プランの取得期限とキャッシュの延命はやめた。

## 1. 期間

### 1-1. 決め方

- Standard で取れるのは「10年前まで」(J-Quants「契約ごとに利用可能なAPIとデータ格納期間」https://jpx-jquants.com/ja/spec/data-spec 、2026-11-24 確認。上場銘柄一覧・株価四本値・バリュエーション指標・財務情報のいずれも同じ)。仕様には「10年前まで」とだけあり、ここでは取得した日から日単位で10年前までと読む。
- French の簿価の時点:t年6月末の組み替えには「the fiscal year ending in calendar year t-1」の簿価を使う(French「Variable Definitions」、第7節)。
- 最初の時期の決め方:t−1 暦年中に終わる会計年度の決算短信は、最も早いもの(1月決算)で t−1 年の2〜3月ごろに開示される。2026年11月〜12月に取得すると、10年前は 2016年11月〜12月になる。
  - t=2018(t−1=2017)なら、2017年中に終わる会計年度の開示はすべて 2017年2月以降で、取得できる。
  - t=2017(t−1=2016)なら、2016年1〜10月に終わる会計年度の開示が 2016年11月より前になり、取得できない。
  - したがって、French と同じ時点の簿価がそろう最初の組み替えは 2018年6月末で、較正の期間は 2018-07-01 から始める。

### 1-2. 固定する期間

| 用途 | 期間 |
|---|---|
| 取得する全期間 | 2017-02-01〜2020-06-30 |
| 再現(SMB・HML・Mom) | 2018-07-01〜2020-06-30 の営業日 |
| 手計算(条件1・3・4・5の共通の期間) | 2019-03-01〜2019-08-31 の営業日 |
| 手計算(条件2・6の銘柄ごとの期間) | 第2-1節の決め方による |

- 取得する全期間の始まり(2017-02-01)は、2017年中に終わる会計年度の開示と、Mom に要る t−251 日の価格(2018年7月の最初の営業日から数えて、2017年6〜7月ごろ)の両方を含むように決めた。
- 取り直せる期間:取得する全期間がすべて10年の範囲に入っているのは、取得日が 2027-02-01 まで(2017-02-01 の10年後)。この日を過ぎると、古い側から取り直せなくなる。キャッシュが消えたときの扱いは第5節(質問 Q1)。
- 直近の期間は、研究とホールドアウトのために使わずに残す(オーナーの指示、2026-11-25)。

## 2. 手計算との照合

### 2-1. 銘柄の選び方(機械的なルール)

- 対象:それぞれの条件の期間のどこかで上場していた全銘柄(/equities/master と /equities/bars/daily による)。
- 条件ごとに、条件に合う銘柄を集め、銘柄コードの昇順に並べ、乱数で1つ選ぶ。
  1. 配当:共通の期間内に権利落ち日(data_spec 第3節のルールで決めたもの)があり、期間内に分割・併合・上場廃止・無約定日がない銘柄
  2. 分割(分割またぎを兼ねる):再現の期間(2018-07-01〜2020-06-30)の中に、ExRT=1(分割)の日があり、その分割が配当の基準日と開示日の間にある(data_spec 第3節の「分割またぎ」の印が付く)銘柄。候補が0件なら、共通の期間内に ExRT=1 の日がある銘柄から選び、分割またぎを確かめられなかったことを記録する
  3. 無約定日:共通の期間内に、四本値・取引高・売買代金が揃って Null の日(data_spec 第8節)が1日以上ある銘柄。市場全体が止まった日は数えない
  4. 上場廃止:共通の期間内に株価四本値が返る最後の営業日があり(data_spec 第7節)、期間内に20営業日以上の約定がある銘柄
  5. 通常:共通の期間を通して上場し、1〜4 のどれにも当たらず、期間内に配当の権利落ち日もない銘柄
  6. ライツイシュー:再現の期間の中に ExRT=3 の日がある銘柄。候補が0件なら「該当なし」と記録する
- 条件2と6の銘柄の手計算の期間:その出来事の日(分割またはライツイシューの権利落ち日)がある月の2か月前の月の初日から、3か月後の月の末日まで(6か月)。取得する全期間の外に出る部分は切り詰める。
- 乱数:Python 標準の random.Random(20261124) を使い、条件1から6の順に、候補の並びに対して choice を1回ずつ呼ぶ。すでに選んだ銘柄は、後の条件の候補から除く。種(20261124)は、データを見る前に v0.1 で決めたものをそのまま使う。
- 候補が0件の条件は「該当なし」と記録し、別の条件で埋めない(条件2の代わりの候補は上に書いたとおり)。
- 選んだ結果を見て選び直さない。選定は実験器で1回だけ実行し、run ID と銘柄コードと手計算の期間を実行記録に残す。選定のコードにバグが見つかって再実行した場合は、バグ修正による再実行として区別して記録する(CHARTER 第7章)。種は変えない。

### 2-2. 照合する項目と合格の目安

手計算と実験器は、同じルール(data_spec)で同じ値を計算する。したがって、差は丸めかバグのどちらかで、近似の誤差は差の理由にならない。

| 項目 | 合格の目安 |
|---|---|
| 調整前の価格、AdjFactor | 完全一致(API の値そのもの) |
| 保有株数(分割・併合のたびに AdjFactor で換算) | 完全一致 |
| 配当(1株あたりの額、権利落ち日、分割で換算した額) | 完全一致 |
| 日次リターン | 各日の差の絶対値が 0.0001%ポイント以下 |
| 現金残高(配当の受取りを含む) | 各日の差の絶対値が 1円以下 |

- 権利落ち日の近似と実際の権利落ち日のずれは、合否には使わず、大きさだけを記録する。
- 手計算の模擬口座:銘柄ごとに別の口座として計算する。その銘柄の手計算の期間の最初の営業日の終値で100株買い、期間の終わりまで持つ。現金の初期値は買付額とちょうど同じにして、買付後の残高を0円とする。手数料は0円とする。

### 2-3. 手計算の元データ

- オーナーのパソコンで、選んだ銘柄について、手計算の期間に必要な分だけを J-Quants API から一度だけ取得する(オーナーの回答 Q2、2026-11-25)。手順は `tools/handcalc/README.md`。
- 取得するもの:株価四本値(手計算の期間)と、財務情報(開示日が手計算の期間の始まりの12か月前から、終わりの3か月後まで。配当の実績値と、分割またぎの推定に使う前回の配当・予想配当を含めるため)。
- 置き場所はオーナーが決めた1つのフォルダに限る。会話にもリポジトリにも入れない。
- 較正が終わったら、そのフォルダを削除し、削除した日を STATE.md に記録する。

## 3. 既知の結果の再現

比較先は French の Japanese 3 Factors [Daily] の SMB・HML と、Japanese Momentum Factor (Mom) [Daily](ファイルは第7節)。Mkt-RF は使わない(data_spec 第5-2節)。作り方は French の原文(第7節に引用)に合わせる。

### 3-1. 共通

- 対象銘柄:上場銘柄一覧にある内国の普通株式。ETF・REIT などを除く判定に使う項目は、上場銘柄一覧の仕様で確かめて実験器のコードに書き、実行記録に残す。
- 時価総額(ME):バリュエーション指標 API の MktCap(百万円)。自己株式を控除した株式数 × 終値で計算されたもの(J-Quants「バリュエーション指標」、2026-11-24 確認)。French の市場データと株式数の定義が同じとは限らない。この差は合わせられない点として記録する。
- リターン:調整済み価格と data_spec 第3節の配当で計算する(French 側も配当を含む)。円建てのまま計算する(French は米ドル建て。ロング・ショートだけを比べるので、data_spec 第5-2節の判断のとおり)。
- 6つのポートフォリオはすべて時価加重。

### 3-2. SMB と HML

- 組み替え:毎年6月末(2018年、2019年)。大型株は、6月末の時価総額で上位90%を占める銘柄、小型株は残りの10%。
- B/M のブレークポイント:大型株の B/M の 30・70 パーセンタイル。サイズと B/M の独立した 2×3 の分類で6つのポートフォリオを作る。
- SMB = 1/3(SV+SN+SG) − 1/3(BV+BN+BG)、HML = 1/2(SV+BV) − 1/2(SG+BG)。
- 対象:t−1 年12月末と t 年6月末の時価総額があり、t−1 暦年中に終わる会計年度の簿価(正の値)がある銘柄。
- 簿価(BE):財務情報(/fins/summary)の ShEq(自己資本)。t−1 暦年中に終わる会計年度(CurFYEn が t−1 年)で、当会計期間の種類(CurPerType)が FY のレコードのうち、t 年6月末までに開示されたもので、開示日時が最新のもの(data_spec 第7節)。B/M = BE ÷ t−1 年12月末の ME。
  - Eq(純資産)ではなく ShEq を使う。Eq は非支配株主持分などを含むため。French の BE の定義(株主資本に繰延税金などを加え、優先株を引く)とは完全には一致しない。この差は合わせられない点として記録する。

### 3-3. Mom(French の日次版)

- 毎営業日に組み替える。t 日のポートフォリオは t−1 日の終わりに作り、t−250 日から t−20 日までの累積リターンで並べる。対象は、t−251 日の終わりの価格と、t−21 日のリターンがある銘柄。
- サイズも毎営業日に分ける。t−1 日の時価総額で上位90%を占める銘柄を大型株とする(90%は3ファクターの原文による。日次モメンタムの原文には割合が書かれていない)。原文には「2x3 sorts on size and lagged momentum ... are formed daily」とあるだけで、サイズの基準の時点は書かれていない。そのため、この読み方を採ったことを記録する。勝ち・負けのブレークポイントは、大型株の累積リターンの 30・70 パーセンタイル。
- Mom(WML)= 1/2(SW+BW) − 1/2(SL+BL)。

### 3-4. 合格の目安

- SMB、HML、Mom のそれぞれで、次の両方を満たすこと:
  - 日次リターンの相関:0.80 以上
  - 変動の大きさの比(自作の標準偏差 ÷ French の標準偏差):0.80 以上 1.25 以下
- 相関の計算は、両方の系列に値がある日だけで行う。日付は、それぞれの系列の日付をそのまま突き合わせる。

## 4. 不合格だったとき

- 目安を下回ったら、発見ではなくバグを疑う(CHARTER 第7章)。原因を探して直し、直した実験器で同じ期間・同じ銘柄・同じ目安で計算し直す。目安は変えない。
- 直したことは、バグ修正による再実行として記録する。直した部分が実験器の核なら、その版を較正済みの版とする。
- 原因が見つからないまま目安を満たさない場合は、そこで止め、オーナーが判断する。その判断は決定ログに残す。

## 5. 記録と保存

- 実行記録(runs/):run ID、コードと設定のコミット、取得したファイルのハッシュ値(SHA-256)、キャッシュの大きさ、選んだ銘柄コードと手計算の期間、照合の結果(項目ごとの一致件数と最大の差)、再現の結果(相関と変動の比)、French のファイルを取得した日とそのハッシュ値。市場データそのものは残さない(CHARTER 第8章、data_spec 第6節)。
- 手計算の表はオーナーが作り、市場データを含むため、リポジトリにも会話にも入れない。リポジトリに残すのは照合の結果だけ。
- キャッシュが消えたら、Standard で同じ期間を取り直す(data_spec 第6節)。取り直したファイルのハッシュ値が前回と違えば、提供側の訂正として記録する。2027-02-01 を過ぎてから消えた場合の扱いは、質問 Q1 の回答で決める。
- ホールドアウトの使用履歴(holdout_log.md):取得する全期間(2017-02-01〜2020-06-30)を、較正で使った期間として記録する(CHARTER 第7章)。

## 6. 計算を始める条件

1. この計画、data_spec v0.3、CHARTER v1.2 がマージされている(D-0027〜D-0029)。
2. Standard を契約し、GitHub Actions から 2017年の日付のデータが取れることを確かめてある(取れた件数だけを確かめ、中身はログに出さない)。
3. 実験器が、合成データで動くことを確かめてある(CHARTER 第7章)。

## 7. 原本で確かめたこと(2026-11-24〜25)

- French Data Library(https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
  - ファイル:ftp/Japan_3_Factors_Daily_CSV.zip(Fama/French Japanese 3 Factors [Daily])、ftp/Japan_Mom_Factor_Daily_CSV.zip(Japanese Momentum Factor (Mom) [Daily])。
  - 3ファクターの作り方(Data_Library/f-f_3developed.html):「Daily Returns: July 1, 1990 – September 30, 2026」「All returns are in U.S. dollars, include dividends and capital gains」「we sort stocks in a region into two market cap and three book-to-market equity (B/M) groups at the end of each June. Big stocks are those in the top 90% of June market cap for the region, and small stocks are those in the bottom 10%. The B/M breakpoints for a region are the 30th and 70th percentiles of B/M for the big stocks of the region.」「SMB and HML for July of year t to June of t+1 include all stocks for which we have market equity data for December of t−1 and June of t, and (positive) book equity data for t−1.」
  - 簿価の時点(Data_Library/variable_definitions.html):「The book-to-market ratio used to form portfolios in June of year t is book equity for the fiscal year ending in calendar year t-1, divided by market equity at the end of December of t-1.」「BE is the book value of stockholders equity, plus balance sheet deferred taxes and investment tax credit (if available), minus the book value of preferred stock.」(このページは米国のデータ(Compustat)についての説明で、国際版に同じ定義を当てはめるのは、この計画の読み方)
  - 日次モメンタムの作り方(Data_Library/f-f_developed_daily_mom.html):「Daily Returns: December 1, 1990 – September 30, 2026」「The 2x3 sorts on size and lagged momentum to construct WML are formed daily. For portfolios formed at the end of day t−1, the lagged momentum return is a stock's cumulative return for day t−250 to day t−20. The momentum breakpoints for a region are the 30th and 70th percentiles of the lagged momentum returns of the big stocks of the region.」「To be included in a portfolio for day t (formed at the end of the day t−1), a stock must have a price for the end of day t−251 and a good return for t−21.」
- J-Quants の仕様
  - 財務情報(https://jpx-jquants.com/ja/spec/fin-summary):「Eq 純資産」「ShEq 自己資本」「CurPerType 当会計期間の種類 [1Q, 2Q, 3Q, 4Q, 5Q, FY]」「CurFYEn 当事業年度終了日」「開示順序の判定には開示日時・時刻(DiscDate・DiscTime)をご参照ください」「決算短信(非連結)を提出する企業では、接頭辞 NC がない項目に個別の値を収録」。
  - データ格納期間(https://jpx-jquants.com/ja/spec/data-spec):Standard は、上場銘柄一覧・株価四本値・バリュエーション指標・財務情報が「10年前まで」。
  - バリュエーション指標(https://jpx-jquants.com/ja/spec/eq-valuation):MktCap は「時価総額(百万円)」で、「株式数には、自己株式を控除した株式数を用います」。
  - 株価四本値(https://jpx-jquants.com/ja/spec/eq-bars-daily)と財務情報:銘柄コード(code)と期間(from/to)、または開示日付(date)を指定する。レスポンスに pagination_key があれば、それを付けて続きを取る。
- GitHub Actions のキャッシュ:data_spec 第6節(v0.3)に引用。
