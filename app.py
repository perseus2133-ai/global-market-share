"""
글로벌 점유율 높은 국내 알짜 종목 찾기
- 소재/부품/장비, 화장품, 의류 등 니치 글로벌 강자 발굴
- Streamlit 기반 웹 앱
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf
import time

st.set_page_config(
    page_title="글로벌 경쟁력 국내 알짜 종목",
    page_icon="🔍",
    layout="wide",
)

# ── 팝업 스타일 (3D 그림자 효과 - 전체 카드 통합) ──
st.markdown("""
<style>
@keyframes popIn {
    from { opacity: 0; transform: translateY(-12px) scale(0.95); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}
/* 팝업 컨테이너 마커 바로 다음 stVerticalBlock에 3D 효과 */
.popup-marker + div > div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    border: 1px solid rgba(180,185,200,0.5) !important;
    box-shadow:
        0 24px 80px rgba(0,0,0,0.22),
        0 10px 30px rgba(0,0,0,0.14),
        0 3px 8px rgba(0,0,0,0.08) !important;
    animation: popIn 0.28s ease-out;
    background: linear-gradient(150deg, #ffffff 0%, #f8f9fc 100%) !important;
    position: relative;
    z-index: 10;
}
.popup-marker + div > div[data-testid="stVerticalBlockBorderWrapper"] > div {
    padding: 20px 24px !important;
}
/* 숨김 닫기 버튼 */
.close-trigger-wrap { height: 0; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ── 비밀번호 인증 ──
def check_password():
    """비밀번호 확인"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("🔒 로그인")
    password = st.text_input("비밀번호를 입력하세요", type="password")
    if st.button("로그인", use_container_width=True):
        try:
            correct_pw = st.secrets["password"]
        except (KeyError, FileNotFoundError):
            st.error("secrets.toml에 password를 설정해주세요.")
            st.stop()
            return False
        if password == correct_pw:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    return False

if not check_password():
    st.stop()

# ──────────────────────────────────────────────
# 업종별 데이터: 한국 기업 + 글로벌 경쟁사
# 각 기업에 "글로벌 점유율 추정치"와 "핵심 제품/강점" 포함
# ──────────────────────────────────────────────
SECTOR_DATA = {
    # ── 반도체 장비 ──
    "반도체 장비": {
        "description": "반도체 후공정 장비, 테스트 장비, 검사 장비 등",
        "kr": [
            ("042700.KS", "한미반도체", "글로벌 TC본더 점유율 80%+, 후공정 핵심장비"),
            ("058470.KQ", "리노공업", "반도체 테스트 소켓 글로벌 점유율 30%+"),
            ("095340.KQ", "ISC", "IC 테스트소켓 글로벌 2위"),
            ("131970.KQ", "두산테스나", "반도체 후공정 테스트 전문"),
            ("036930.KQ", "주성엔지니어링", "ALD 증착장비 글로벌 3위권"),
            ("095610.KQ", "테스", "CVD/ALD 장비 글로벌 경쟁력"),
        ],
        "global": [
            ("ASML", "ASML"),
            ("AMAT", "Applied Materials"),
            ("LRCX", "Lam Research"),
            ("KLAC", "KLA Corp"),
            ("TER", "Teradyne"),
        ],
    },
    # ── 반도체/디스플레이 소재 ──
    "반도체/디스플레이 소재": {
        "description": "포토레지스트, 식각가스, CMP슬러리, OLED 소재 등",
        "kr": [
            ("005290.KQ", "동진쎄미켐", "포토레지스트 국내 1위, EUV PR 개발"),
            ("357780.KQ", "솔브레인", "반도체 식각액 글로벌 점유율 20%+"),
            ("033240.KS", "자화전자", "카메라모듈 액추에이터 글로벌 1위"),
            ("272290.KQ", "이녹스첨단소재", "OLED 소재 글로벌 경쟁력"),
        ],
        "global": [
            ("ENTG", "Entegris"),
            ("CCMP", "CMC Materials"),
        ],
    },
    # ── 2차전지 소재 ──
    "2차전지 소재": {
        "description": "양극재, 음극재, 전해액, 분리막 등 배터리 핵심 소재",
        "kr": [
            ("247540.KQ", "에코프로비엠", "하이니켈 양극재 글로벌 Top3"),
            ("003670.KS", "포스코퓨처엠", "양극재+음극재 글로벌 Top5"),
            ("066970.KS", "엘앤에프", "양극재 글로벌 경쟁력"),
            ("278280.KQ", "천보", "전해질(LiFSI) 글로벌 1위"),
        ],
        "global": [
            ("ALB", "Albemarle"),
            ("SQM", "SQM"),
            ("BYDDY", "BYD"),
        ],
    },
    # ── 화장품/K-뷰티 ──
    "화장품/K-뷰티": {
        "description": "K-뷰티 브랜드, ODM/OEM, 화장품 소재 등",
        "kr": [
            ("192820.KS", "코스맥스", "화장품 ODM 글로벌 1위"),
            ("161890.KS", "한국콜마", "화장품 ODM 글로벌 2위"),
            ("090430.KS", "아모레퍼시픽", "K-뷰티 대표, 글로벌 Top10"),
            ("051900.KS", "LG생활건강", "후/숨 브랜드 아시아 강자"),
            ("018290.KQ", "브이티", "시카 라인 글로벌 히트, 일본 1위"),
            ("078520.KS", "에이블씨엔씨", "미샤 브랜드"),
        ],
        "global": [
            ("EL", "Estee Lauder"),
            ("COTY", "Coty"),
            ("LRLCY", "L'Oreal"),
        ],
    },
    # ── 의류/패션 ──
    "의류/패션": {
        "description": "글로벌 확장 중인 K-패션, OEM 의류 기업",
        "kr": [
            ("383220.KS", "F&F", "MLB/Discovery 글로벌 확장, 중국 대박"),
            ("105630.KS", "한세실업", "의류 OEM 글로벌 Top5, 나이키/자라 납품"),
            ("002790.KS", "아모레퍼시픽홀딩스", "아모레퍼시픽 지주사"),
        ],
        "global": [
            ("NKE", "Nike"),
            ("ADDYY", "Adidas"),
            ("LULU", "Lululemon"),
            ("CPRI", "Capri Holdings"),
        ],
    },
    # ── 자동차 부품 ──
    "자동차 부품": {
        "description": "전장부품, 모터, 변속기 등 글로벌 완성차 납품",
        "kr": [
            ("012330.KS", "현대모비스", "자동차 모듈/부품 글로벌 Top7"),
            ("204320.KS", "HL만도", "조향/제동/ADAS 글로벌 경쟁력"),
            ("298040.KS", "효성중공업", "전력기기 글로벌 Top5"),
            ("018880.KS", "한온시스템", "차량 열관리 글로벌 1위"),
            ("011210.KS", "현대위아", "4WD/AWD 구동계 글로벌 3위권"),
        ],
        "global": [
            ("DNZOY", "Denso"),
            ("BWA", "BorgWarner"),
            ("APTV", "Aptiv"),
            ("MGA", "Magna International"),
        ],
    },
    # ── 조선/해양 장비 ──
    "조선/해양": {
        "description": "조선소, 선박엔진, 해양플랜트 기자재",
        "kr": [
            ("009540.KS", "HD한국조선해양", "조선 글로벌 1위 그룹"),
            ("329180.KS", "HD현대중공업", "조선 수주 글로벌 Top3"),
            ("042660.KS", "한화오션", "특수선/잠수함 강자"),
            ("010140.KS", "삼성중공업", "LNG선 글로벌 Top3"),
            ("082740.KS", "한화엔진", "선박엔진 글로벌 3위"),
            ("267260.KS", "HD현대일렉트릭", "선박전기시스템 + 변압기 글로벌 강자"),
        ],
        "global": [
            ("IMIRY", "Imabari(참고)"),
        ],
    },
    # ── 방산/우주 ──
    "방산/우주항공": {
        "description": "K-방산 수출 급성장, 우주발사체 등",
        "kr": [
            ("012450.KS", "한화에어로스페이스", "항공엔진 + K9자주포 글로벌 수출"),
            ("047810.KS", "한국항공우주", "KF-21, 훈련기(T-50) 글로벌 수출"),
            ("079550.KS", "LIG넥스원", "유도무기/방공체계 수출 확대"),
            ("064350.KS", "현대로템", "K2전차 + 철도차량 수출"),
        ],
        "global": [
            ("LMT", "Lockheed Martin"),
            ("RTX", "RTX"),
            ("NOC", "Northrop Grumman"),
            ("BA", "Boeing"),
            ("GD", "General Dynamics"),
        ],
    },
    # ── 전자부품/수동소자 ──
    "전자부품/수동소자": {
        "description": "MLCC, 인덕터, 커넥터 등 핵심 전자부품",
        "kr": [
            ("009150.KS", "삼성전기", "MLCC 글로벌 2위(약 25%)"),
            ("009970.KS", "영원무역홀딩스", "참고"),
        ],
        "global": [
            ("6981.T", "Murata(무라타)"),
            ("APH", "Amphenol"),
            ("TEL", "TE Connectivity"),
        ],
    },
    # ── 2차전지 장비 ──
    "2차전지 장비": {
        "description": "배터리 생산 장비, 검사 장비 등",
        "kr": [
            ("137400.KQ", "피엔티", "2차전지 전극공정 장비 Top"),
            ("126700.KQ", "하이비젼시스템", "외관검사장비"),
        ],
        "global": [
            ("6963.T", "Rohm(참고)"),
        ],
    },
    # ── 음식/식품 ──
    "식품/음료": {
        "description": "K-푸드 글로벌 확장, 라면/김/소스 등",
        "kr": [
            ("271560.KS", "오리온", "초코파이 글로벌, 중국/러시아/베트남 1위급"),
            ("097950.KS", "CJ제일제당", "비비고 만두 글로벌 1위, K-푸드 대표"),
            ("003230.KS", "삼양식품", "불닭볶음면 글로벌 폭발 성장"),
            ("021240.KS", "코웨이", "정수기/공기청정기 글로벌 1위"),
        ],
        "global": [
            ("NSRGY", "Nestle"),
            ("KHC", "Kraft Heinz"),
            ("GIS", "General Mills"),
        ],
    },
    # ── 게임 ──
    "게임": {
        "description": "글로벌 게임 시장 점유율 확대 중인 K-게임사",
        "kr": [
            ("259960.KS", "크래프톤", "배틀그라운드 글로벌 매출 Top"),
            ("036570.KS", "엔씨소프트", "리니지 시리즈 아시아 강자"),
            ("112040.KQ", "위메이드", "미르 시리즈"),
            ("263750.KQ", "펄어비스", "검은사막 글로벌"),
        ],
        "global": [
            ("ATVI", "Activision(MS)"),
            ("EA", "EA"),
            ("TTWO", "Take-Two"),
            ("NTES", "NetEase"),
        ],
    },
    # ── 엔터테인먼트/K-콘텐츠 ──
    "엔터/K-콘텐츠": {
        "description": "K-POP, 드라마, 웹툰 등 한류 콘텐츠",
        "kr": [
            ("352820.KS", "하이브", "BTS/세븐틴, 글로벌 음악 시장 Top5 레이블"),
            ("041510.KQ", "에스엠", "에스파/NCT, 글로벌 K-POP"),
            ("122870.KQ", "와이지엔터테인먼트", "블랙핑크, 글로벌 걸그룹 Top"),
        ],
        "global": [
            ("WMG", "Warner Music"),
            ("SPOT", "Spotify"),
            ("UMG.AS", "Universal Music"),
        ],
    },
    # ── 원자력/에너지 ──
    "원자력/에너지 장비": {
        "description": "원전 부품, SMR, 전력기기 등",
        "kr": [
            ("267260.KS", "HD현대일렉트릭", "변압기 글로벌 수주 급증"),
            ("298040.KS", "효성중공업", "초고압 변압기/차단기 글로벌 Top5"),
            ("009830.KS", "한화솔루션", "태양광 셀/모듈"),
            ("034020.KS", "두산에너빌리티", "원전 주기기 글로벌 경쟁력"),
        ],
        "global": [
            ("ETN", "Eaton"),
            ("EMR", "Emerson Electric"),
            ("GE", "GE Vernova"),
        ],
    },
}


# ──────────────────────────────────────────────
# Yahoo Finance 데이터 조회 (yfinance + REST fallback)
# ──────────────────────────────────────────────
@st.cache_data(ttl=600)
def get_fx_rates():
    """환율 조회 (10분 캐시)"""
    rates = {"USD": 1.0}
    pairs = {
        "KRW": "KRWUSD=X", "JPY": "JPYUSD=X", "EUR": "EURUSD=X",
        "GBP": "GBPUSD=X", "CNY": "CNYUSD=X", "HKD": "HKDUSD=X",
        "TWD": "TWDUSD=X", "BRL": "BRLUSD=X",
    }
    for cur, pair in pairs.items():
        try:
            t = yf.Ticker(pair)
            hist = t.history(period="1d")
            if not hist.empty:
                rates[cur] = float(hist["Close"].iloc[-1])
        except Exception:
            pass
    return rates


def _fetch_naver_market_cap(stock_code: str) -> int:
    """네이버 모바일 API에서 시가총액 조회 (yfinance 실패 시 fallback)"""
    try:
        url = f"https://m.stock.naver.com/api/stock/{stock_code}/basic"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            mc = data.get("marketCap") or data.get("totalMarketValue")
            if mc:
                return int(mc)
    except Exception:
        pass
    return 0


def fetch_stock_data(ticker: str) -> dict:
    """개별 종목 데이터 조회 (fast_info + history + income_stmt)"""
    # 실패 시 반환할 기본값
    default_result = {
        "ticker": ticker,
        "name": ticker,
        "market_cap_usd": 0,
        "market_cap_local": 0,
        "revenue_usd": 0,
        "revenue_local": 0,
        "currency": "KRW" if ".KS" in ticker or ".KQ" in ticker else "USD",
        "price": 0,
        "change_pct": 0,
        "volume": 0,
        "volume_date": "",
        "trade_value": 0,
        "per": None,
        "psr": None,
        "fetch_failed": True,
    }
    try:
        stock = yf.Ticker(ticker)

        # fast_info: v8 chart API 사용 (인증 불필요, Streamlit Cloud 호환)
        fi = stock.fast_info
        market_cap = fi.get("marketCap", 0) or fi.get("market_cap", 0)
        if not market_cap:
            # Naver API fallback (한국 종목만)
            if ".KS" in ticker or ".KQ" in ticker:
                code = ticker.replace(".KS", "").replace(".KQ", "")
                market_cap = _fetch_naver_market_cap(code)
            if not market_cap:
                return default_result

        currency = fi.get("currency", "USD")
        fx = get_fx_rates()
        rate = fx.get(currency, 1.0)
        market_cap_usd = market_cap * rate

        price = fi.get("lastPrice", 0) or fi.get("last_price", 0)
        prev_close = fi.get("previousClose", 0) or fi.get("previous_close", 0)
        chg_pct = ((price - prev_close) / prev_close * 100) if prev_close and price else 0

        # 거래량 + 거래일: history에서 조회
        volume = 0
        volume_date = ""
        try:
            hist = stock.history(period="5d")
            if hist is not None and not hist.empty:
                last_row = hist.iloc[-1]
                volume = int(last_row.get("Volume", 0))
                volume_date = str(hist.index[-1].date())
        except Exception:
            pass

        # 매출액 + 순이익: income_stmt에서 조회
        revenue = 0
        net_income = 0
        try:
            inc = stock.income_stmt
            if inc is not None and not inc.empty:
                for label in ["Total Revenue", "Operating Revenue", "Revenue"]:
                    if label in inc.index:
                        val = inc.loc[label].dropna()
                        if not val.empty:
                            revenue = int(val.iloc[0])
                            break
                for label in ["Net Income", "Net Income Common Stockholders"]:
                    if label in inc.index:
                        val = inc.loc[label].dropna()
                        if not val.empty:
                            net_income = int(val.iloc[0])
                            break
        except Exception:
            pass

        # income_stmt 실패 시 financials로 시도
        if not revenue:
            try:
                fins = stock.financials
                if fins is not None and not fins.empty:
                    for label in ["Total Revenue", "Operating Revenue", "Revenue"]:
                        if label in fins.index:
                            val = fins.loc[label].dropna()
                            if not val.empty:
                                revenue = int(val.iloc[0])
                                break
                    if not net_income:
                        for label in ["Net Income", "Net Income Common Stockholders"]:
                            if label in fins.index:
                                val = fins.loc[label].dropna()
                                if not val.empty:
                                    net_income = int(val.iloc[0])
                                    break
            except Exception:
                pass

        revenue_usd = revenue * rate if revenue else 0

        # PER / PSR 계산
        per = round(market_cap / net_income, 1) if net_income and net_income > 0 else None
        psr = round(market_cap / revenue, 1) if revenue and revenue > 0 else None

        # 거래대금 = 거래량 × 현재가
        trade_value = volume * price if volume and price else 0

        return {
            "ticker": ticker,
            "name": stock.ticker,
            "market_cap_usd": int(market_cap_usd),
            "market_cap_local": int(market_cap),
            "revenue_usd": int(revenue_usd),
            "revenue_local": int(revenue) if revenue else 0,
            "currency": currency,
            "price": price,
            "change_pct": round(chg_pct, 2),
            "volume": volume,
            "volume_date": volume_date,
            "trade_value": int(trade_value),
            "per": per,
            "psr": psr,
            "fetch_failed": False,
        }
    except Exception:
        return default_result


@st.cache_data(ttl=600)
def fetch_naver_financial(stock_code: str) -> pd.DataFrame | None:
    """네이버 모바일 API에서 연간 재무 데이터 (실적 + 컨센서스 추정) 조회"""
    try:
        url = f"https://m.stock.naver.com/api/stock/{stock_code}/finance/annual"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None

        data = r.json()
        fi = data.get("financeInfo")
        if not fi:
            return None

        # 기간 헤더
        periods = fi["trTitleList"]
        period_keys = [p["key"] for p in periods]
        period_labels = []
        for p in periods:
            label = p["title"].strip(".")
            if p["isConsensus"] == "Y":
                label += "(E)"
            period_labels.append(label)

        # 주요 항목만 선택
        key_items = ["매출액", "영업이익", "당기순이익", "영업이익률", "ROE",
                     "EPS", "PER", "BPS", "PBR", "주당배당금"]
        rows = []
        for row in fi["rowList"]:
            title = row["title"]
            if title not in key_items:
                continue
            vals = []
            for pk in period_keys:
                col = row["columns"].get(pk, {})
                v = col.get("value", "-")
                vals.append(v if v else "-")
            rows.append({"항목": title, **{label: val for label, val in zip(period_labels, vals)}})

        if not rows:
            return None

        return pd.DataFrame(rows)
    except Exception:
        return None



@st.cache_data(ttl=600)
def fetch_sector_data(sector_name: str) -> dict:
    """업종 전체 데이터 조회 (10분 캐시) - 매출액 기준 리스트내비중"""
    sector = SECTOR_DATA[sector_name]
    kr_tickers = [(t, n) for t, n, _ in sector["kr"] if ".KS" in t or ".KQ" in t]
    gl_tickers = [(t, n) for t, n in sector["global"]]
    all_tickers = [t for t, _ in kr_tickers + gl_tickers]

    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_stock_data, t): t for t in all_tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            data = future.result()
            results[ticker] = data

    # 매출액 기준 리스트내비중 및 순위
    total_revenue = sum(r["revenue_usd"] for r in results.values()) or 1

    # 매출액 순으로 글로벌 순위 부여
    all_companies = []
    for ticker, data in results.items():
        all_companies.append({
            "ticker": ticker,
            "revenue_usd": data["revenue_usd"],
        })
    all_companies.sort(key=lambda x: x["revenue_usd"], reverse=True)
    global_rank_map = {c["ticker"]: i + 1 for i, c in enumerate(all_companies)}
    total_companies = len(all_companies)

    kr_results = []
    kr_success = 0
    kr_fail = 0
    for ticker, name, desc in sector["kr"]:
        r = results.get(ticker)
        if not r:
            continue
        failed = r.get("fetch_failed", False)
        if failed:
            kr_fail += 1
        else:
            kr_success += 1
        share = r["revenue_usd"] / total_revenue * 100
        rank = global_rank_map.get(ticker, 0)
        kr_results.append({
            "종목코드": ticker.replace(".KS", "").replace(".KQ", ""),
            "기업명": name,
            "핵심강점": desc,
            "매출액(원)": r["revenue_local"],
            "매출액(USD)": r["revenue_usd"],
            "시가총액(원)": r["market_cap_local"],
            "시가총액(USD)": r["market_cap_usd"],
            "리스트내비중": round(share, 1),
            "글로벌순위": rank,
            "전체기업수": total_companies,
            "글로벌순위표시": f"{rank}/{total_companies}위",
            "현재가": r["price"],
            "등락률": r["change_pct"],
            "통화": r["currency"],
            "거래량": r["volume"],
            "거래대금": r["trade_value"],
            "거래일": r["volume_date"],
            "PER": r["per"],
            "PSR": r["psr"],
            "조회실패": failed,
        })

    gl_results = []
    gl_success = 0
    gl_fail = 0
    for ticker, name in sector["global"]:
        r = results.get(ticker)
        if not r:
            continue
        failed = r.get("fetch_failed", False)
        if failed:
            gl_fail += 1
        else:
            gl_success += 1
        share = r["revenue_usd"] / total_revenue * 100
        rank = global_rank_map.get(ticker, 0)
        gl_results.append({
            "기업명": name,
            "티커": ticker,
            "매출액(USD)": r["revenue_usd"],
            "시가총액(USD)": r["market_cap_usd"],
            "리스트내비중": round(share, 1),
            "글로벌순위": rank,
            "글로벌순위표시": f"{rank}/{total_companies}위",
        })

    kr_total_share = sum(k["리스트내비중"] for k in kr_results)

    return {
        "kr": kr_results,
        "global": gl_results,
        "kr_total_share": round(kr_total_share, 1),
        "total_revenue": total_revenue,
        "fetched": kr_success + gl_success,
        "failed": kr_fail + gl_fail,
        "total": len(all_tickers),
    }


def format_krw(val):
    """원화 시가총액 포맷"""
    if val >= 1e12:
        return f"{val/1e12:.1f}조"
    if val >= 1e8:
        return f"{val/1e8:,.0f}억"
    return f"{val:,.0f}"


def format_usd(val):
    """USD 시가총액 포맷"""
    if val >= 1e12:
        return f"${val/1e12:.2f}T"
    if val >= 1e9:
        return f"${val/1e9:.1f}B"
    if val >= 1e6:
        return f"${val/1e6:.0f}M"
    return f"${val:,.0f}"


def format_trade_value(val):
    """거래대금 포맷"""
    if not val:
        return "-"
    if val >= 1e12:
        return f"{val/1e12:.1f}조"
    if val >= 1e8:
        return f"{val/1e8:,.0f}억"
    if val >= 1e6:
        return f"{val/1e6:,.0f}백만"
    return f"{val:,.0f}"


# ──────────────────────────────────────────────
# Streamlit UI
# ──────────────────────────────────────────────

st.title("🔍 글로벌 경쟁력 높은 국내 알짜 종목")
st.caption("소부장(소재/부품/장비) · 화장품 · 의류 · 방산 · K-콘텐츠 등 니치 글로벌 강자 발굴 | **매출액 기준 리스트내비중**")

# 사이드바
with st.sidebar:
    st.header("⚙️ 설정")

    # 업종 카테고리 분류
    categories = {
        "🔧 소재/부품/장비": ["반도체 장비", "반도체/디스플레이 소재", "2차전지 소재",
                         "전자부품/수동소자", "2차전지 장비", "자동차 부품"],
        "🚢 중공업/방산": ["조선/해양", "방산/우주항공", "원자력/에너지 장비"],
        "💄 소비재/콘텐츠": ["화장품/K-뷰티", "의류/패션", "식품/음료", "게임", "엔터/K-콘텐츠"],
    }

    selected_sectors = []
    for cat_name, cat_sectors in categories.items():
        with st.expander(cat_name, expanded=True):
            for s in cat_sectors:
                if st.checkbox(s, value=True, key=f"cb_{s}"):
                    selected_sectors.append(s)

    st.divider()
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# API 상태 확인
fx = get_fx_rates()
krw_rate = fx.get("KRW", 0)
if krw_rate:
    st.info(f"📡 실시간 데이터 (yfinance) | 📊 **매출액 기준 리스트내비중** | 환율: 1 USD = {1/krw_rate:,.0f} KRW | 캐시: 10분\n\n※ 이 수치는 조회된 기업 간 매출 비중이며 실제 글로벌 시장점유율과 다릅니다.")
else:
    st.warning("환율 데이터를 불러오지 못했습니다. USD 기준으로 표시됩니다.")

if not selected_sectors:
    st.warning("좌측에서 업종을 선택해 주세요.")
    st.stop()

# 전체 분석 실행
all_kr_stocks = []
sector_summaries = []

progress = st.progress(0, text="데이터 수집 중...")
for i, sector_name in enumerate(selected_sectors):
    progress.progress((i + 1) / len(selected_sectors), text=f"[{sector_name}] 조회 중...")
    data = fetch_sector_data(sector_name)

    if data["kr"]:
        for item in data["kr"]:
            item["업종"] = sector_name
        all_kr_stocks.extend(data["kr"])

        sector_summaries.append({
            "업종": sector_name,
            "한국기업수": len(data["kr"]),
            "한국합산비중": data["kr_total_share"],
            "업종전체매출": data["total_revenue"],
            "fetched": data.get("fetched", 0),
            "failed": data.get("failed", 0),
        })

progress.empty()

# 조회 성공/실패 현황 표시
total_fetched = sum(s.get("fetched", 0) for s in sector_summaries) if sector_summaries else 0
total_failed = sum(s.get("failed", 0) for s in sector_summaries) if sector_summaries else 0
if total_failed > 0:
    st.caption(f"📡 데이터 조회 완료: 성공 {total_fetched}건 / :red[실패 {total_failed}건]")

if not all_kr_stocks:
    st.error("조회된 데이터가 없습니다.")
    # 디버그 정보 표시
    with st.expander("🔧 디버그 정보"):
        st.write("**환율 데이터:**", get_fx_rates())
        test_ticker = "005930.KS"
        st.write(f"**테스트 종목 ({test_ticker}):**")
        try:
            t = yf.Ticker(test_ticker)
            fi = t.fast_info
            st.write("fast_info 키:", list(fi.keys()) if hasattr(fi, 'keys') else dir(fi))
            st.write("fast_info 내용:", {k: fi[k] for k in ['marketCap', 'market_cap', 'lastPrice', 'last_price', 'currency'] if k in fi})
        except Exception as e:
            st.write(f"fast_info 에러: {e}")
        try:
            inc = t.income_stmt
            st.write("income_stmt shape:", inc.shape if inc is not None else "None")
            if inc is not None and not inc.empty:
                st.write("income_stmt index:", list(inc.index[:10]))
        except Exception as e:
            st.write(f"income_stmt 에러: {e}")
        result = fetch_stock_data(test_ticker)
        st.write(f"**fetch_stock_data 결과:** {result}")
    st.stop()

# ── 탭 구성 ──
tab1, tab2, tab3 = st.tabs(["📊 종합 랭킹", "📋 업종별 상세", "📈 차트 분석"])

# ── 탭1: 종합 랭킹 ──
with tab1:
    st.subheader("리스트내비중 TOP 종목 (매출액 기준)")

    # 중복 제거 (같은 종목이 여러 업종에 있을 수 있음)
    seen = set()
    unique_stocks = []
    for s in sorted(all_kr_stocks, key=lambda x: x["리스트내비중"], reverse=True):
        if s["종목코드"] not in seen:
            seen.add(s["종목코드"])
            unique_stocks.append(s)

    # 거래 기준일 표시
    vol_dates = [s["거래일"] for s in unique_stocks if s.get("거래일")]
    vol_date_str = vol_dates[0] if vol_dates else ""

    # 주요 지표 카드
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("분석 종목 수", f"{len(unique_stocks)}개")
    with col2:
        top_share = unique_stocks[0]["리스트내비중"] if unique_stocks else 0
        st.metric("최고 비중 (매출)", f"{top_share:.1f}%")
    with col3:
        avg_share = sum(s["리스트내비중"] for s in unique_stocks) / len(unique_stocks) if unique_stocks else 0
        st.metric("평균 비중", f"{avg_share:.1f}%")
    with col4:
        st.metric("분석 업종", f"{len(selected_sectors)}개")

    if vol_date_str:
        st.caption(f"📅 거래량 기준일: **{vol_date_str}**")

    # 종목 리스트 (기업명 옆 📊 버튼 포함)
    for idx, s in enumerate(unique_stocks):
        code = s["종목코드"]
        name = s["기업명"]
        price_str = f"{s['현재가']:,.0f}원" if s["통화"] == "KRW" else f"${s['현재가']:,.2f}"
        chg = s["등락률"]
        chg_icon = "🔺" if chg > 0 else ("🔻" if chg < 0 else "▬")
        vol_str = f"{s['거래량']:,.0f}" if s.get("거래량") else "-"
        tv_str = format_trade_value(s.get("거래대금", 0))

        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([0.3, 1.4, 0.5, 0.9, 0.7, 0.9, 0.9, 0.5])
        c1.markdown(f"**{idx+1}**")
        c2.markdown(f"**{name}** · {s['핵심강점'][:30]}")
        # 📊 버튼: 이미 열려있으면 닫기 (토글)
        def toggle_popup_t1(c=code):
            if st.session_state.get("popup_tab1") == c:
                st.session_state.pop("popup_tab1", None)
            else:
                st.session_state["popup_tab1"] = c
        c3.button("📊", key=f"fin_t1_{code}", help=f"{name} 실적·컨센서스", on_click=toggle_popup_t1)
        if s.get("조회실패"):
            c4.markdown(":red[조회실패]")
            c5.markdown("")
        else:
            c4.markdown(f"`{price_str}`")
            c5.markdown(f"{chg_icon} {abs(chg):.1f}%")
        c6.caption(f"거래량 {vol_str}")
        c7.caption(f"거래대금 {tv_str}")
        c8.markdown(f"[네이버](https://finance.naver.com/item/main.nhn?code={code})")

        # 📊 팝업: 해당 종목 버튼을 눌렀을 때 - 전체 통합 3D 카드
        if st.session_state.get("popup_tab1") == code:
            st.markdown('<div class="popup-marker"></div>', unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown(f"#### 📊 {name} ({code}) 연간 실적 & 컨센서스")
                with st.spinner("조회 중..."):
                    df_fin = fetch_naver_financial(code)
                if df_fin is not None and not df_fin.empty:
                    st.dataframe(df_fin, use_container_width=True, hide_index=True)
                    st.caption("출처: 네이버 증권 | (E) = 컨센서스 추정치")
                else:
                    st.warning("재무 데이터를 불러올 수 없습니다.")
                    st.markdown(f"[네이버 증권에서 직접 확인](https://finance.naver.com/item/coinfo.naver?code={code})")

    # 팝업 바깥 클릭 닫기: 숨김 버튼 + JS
    if st.session_state.get("popup_tab1"):
        st.markdown('<div class="close-trigger-wrap">', unsafe_allow_html=True)
        if st.button("닫기", key="_auto_close_t1"):
            st.session_state.pop("popup_tab1", None)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        components.html("""
        <script>
        (function(){
            const doc = window.parent.document;
            function handler(e) {
                // 팝업 내부 클릭이면 무시
                const markers = doc.querySelectorAll('.popup-marker');
                for (const m of markers) {
                    const next = m.nextElementSibling;
                    if (next && next.contains(e.target)) return;
                }
                // 📊 버튼 클릭이면 무시 (토글 처리됨)
                const btn = e.target.closest('button');
                if (btn && btn.innerText.trim() === '📊') return;
                // 숨김 닫기 버튼 찾아서 클릭
                const allBtns = doc.querySelectorAll('.close-trigger-wrap button');
                if (allBtns.length > 0) { allBtns[0].click(); }
                doc.removeEventListener('mousedown', handler);
            }
            doc.removeEventListener('mousedown', handler);
            doc.addEventListener('mousedown', handler);
        })();
        </script>
        """, height=0)

# ── 탭2: 업종별 상세 ──
with tab2:
    for sector_name in selected_sectors:
        data = fetch_sector_data(sector_name)
        if not data["kr"]:
            continue

        desc = SECTOR_DATA[sector_name]["description"]

        st.subheader(f"{sector_name}")
        fail_count = data.get("failed", 0)
        fail_text = f" | :red[조회실패: {fail_count}건]" if fail_count else ""
        st.caption(f"{desc} | 한국 합산 리스트내비중(매출): **{data['kr_total_share']}%** | 업종 전체 매출: {format_usd(data['total_revenue'])}{fail_text}")

        col_kr, col_gl = st.columns([3, 2])

        with col_kr:
            st.markdown("**🇰🇷 국내 상장 기업**")
            kr_vol_dates = [k["거래일"] for k in data["kr"] if k.get("거래일")]
            if kr_vol_dates:
                st.caption(f"📅 거래량 기준일: **{kr_vol_dates[0]}**")

            kr_sorted = sorted(data["kr"], key=lambda x: x["글로벌순위"])
            for k in kr_sorted:
                code = k["종목코드"]
                price_str = f"{k['현재가']:,.0f}원" if k["통화"] == "KRW" else f"${k['현재가']:,.2f}"
                chg = k["등락률"]
                chg_icon = "🔺" if chg > 0 else ("🔻" if chg < 0 else "▬")
                vol_str = f"{k['거래량']:,.0f}" if k.get("거래량") else "-"
                tv_str = format_trade_value(k.get("거래대금", 0))

                r1, r2, r3, r4, r5 = st.columns([0.3, 1.5, 0.5, 1, 0.5])
                r1.markdown(f"**{k['글로벌순위표시']}**")
                r2.markdown(f"**{k['기업명']}** · {k['핵심강점'][:25]}")
                def toggle_popup_t2(c=code, sn=sector_name):
                    if st.session_state.get(f"popup_t2_{sn}") == c:
                        st.session_state.pop(f"popup_t2_{sn}", None)
                    else:
                        st.session_state[f"popup_t2_{sn}"] = c
                r3.button("📊", key=f"fin_t2_{sector_name}_{code}", help=f"실적·컨센서스",
                          on_click=toggle_popup_t2)
                if k.get("조회실패"):
                    r4.markdown(":red[조회실패]")
                else:
                    r4.markdown(f"`{price_str}` {chg_icon}{abs(chg):.1f}%")
                r5.markdown(f"[네이버](https://finance.naver.com/item/main.nhn?code={code})")
                st.caption(f"거래량 {vol_str} · 거래대금 {tv_str} · 비중 {k['리스트내비중']:.1f}%")

                # 팝업 - 실적 테이블만
                if st.session_state.get(f"popup_t2_{sector_name}") == code:
                    st.markdown('<div class="popup-marker"></div>', unsafe_allow_html=True)
                    with st.container(border=True):
                        st.markdown(f"#### 📊 {k['기업명']} ({code}) 연간 실적 & 컨센서스")
                        with st.spinner("조회 중..."):
                            df_fin2 = fetch_naver_financial(code)
                        if df_fin2 is not None and not df_fin2.empty:
                            st.dataframe(df_fin2, use_container_width=True, hide_index=True)
                            st.caption("출처: 네이버 증권 | (E) = 컨센서스 추정치")
                        else:
                            st.warning("재무 데이터를 불러올 수 없습니다.")

            # Tab2 팝업 바깥 클릭 닫기
            active_popup_t2 = st.session_state.get(f"popup_t2_{sector_name}")
            if active_popup_t2:
                st.markdown('<div class="close-trigger-wrap">', unsafe_allow_html=True)
                if st.button("닫기", key=f"_auto_close_t2_{sector_name}"):
                    st.session_state.pop(f"popup_t2_{sector_name}", None)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

                components.html("""
                <script>
                (function(){
                    const doc = window.parent.document;
                    function handler(e) {
                        const markers = doc.querySelectorAll('.popup-marker');
                        for (const m of markers) {
                            const next = m.nextElementSibling;
                            if (next && next.contains(e.target)) return;
                        }
                        const btn = e.target.closest('button');
                        if (btn && btn.innerText.trim() === '📊') return;
                        const allBtns = doc.querySelectorAll('.close-trigger-wrap button');
                        if (allBtns.length > 0) { allBtns[allBtns.length-1].click(); }
                        doc.removeEventListener('mousedown', handler);
                    }
                    doc.removeEventListener('mousedown', handler);
                    doc.addEventListener('mousedown', handler);
                })();
                </script>
                """, height=0)

        with col_gl:
            st.markdown("**🌍 글로벌 경쟁사 (참고)**")
            if data["global"]:
                gl_rows = []
                for g in sorted(data["global"], key=lambda x: x["글로벌순위"]):
                    gl_rows.append({
                        "순위": g["글로벌순위표시"],
                        "기업명": g["기업명"],
                        "티커": g["티커"],
                        "매출액(USD)": format_usd(g["매출액(USD)"]),
                        "비중(매출)": f"{g['리스트내비중']:.1f}%",
                    })
                gl_df = pd.DataFrame(gl_rows)
                st.dataframe(gl_df, use_container_width=True, hide_index=True)
            else:
                st.info("경쟁사 데이터 없음")

        st.divider()

# ── 탭3: 차트 ──
with tab3:
    st.subheader("업종별 한국 기업 리스트내비중")

    if sector_summaries:
        summary_df = pd.DataFrame(sector_summaries)
        summary_df = summary_df.sort_values("한국합산비중", ascending=True)

        fig = px.bar(
            summary_df,
            x="한국합산비중",
            y="업종",
            orientation="h",
            text="한국합산비중",
            color="한국합산비중",
            color_continuous_scale="RdYlGn",
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(
            height=max(400, len(summary_df) * 35),
            xaxis_title="한국 기업 합산 리스트내비중 (%)",
            yaxis_title="",
            showlegend=False,
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # TOP 15 종목 리스트내비중 차트
    st.subheader("매출 기준 리스트내비중 TOP 15 국내 종목")
    if unique_stocks:
        top15 = unique_stocks[:15]
        top15_df = pd.DataFrame(top15)
        top15_df = top15_df.sort_values("리스트내비중", ascending=True)

        fig2 = px.bar(
            top15_df,
            x="리스트내비중",
            y="기업명",
            orientation="h",
            text="리스트내비중",
            color="업종",
            hover_data=["종목코드", "핵심강점"],
        )
        fig2.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig2.update_layout(
            height=500,
            xaxis_title="리스트내비중 - 매출 기준 (%)",
            yaxis_title="",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # 업종별 파이 차트
    st.subheader("업종 선택하여 비중 비교")
    selected_pie = st.selectbox("업종 선택", selected_sectors)
    if selected_pie:
        pie_data = fetch_sector_data(selected_pie)
        pie_items = []
        for k in pie_data["kr"]:
            pie_items.append({"기업": k["기업명"], "비중": k["리스트내비중"], "구분": "🇰🇷 한국"})
        for g in pie_data["global"]:
            pie_items.append({"기업": g["기업명"], "비중": g["리스트내비중"], "구분": "🌍 해외"})

        if pie_items:
            pie_df = pd.DataFrame(pie_items)
            fig3 = px.pie(
                pie_df,
                values="비중",
                names="기업",
                color="구분",
                color_discrete_map={"🇰🇷 한국": "#FF6B6B", "🌍 해외": "#4ECDC4"},
                hole=0.4,
            )
            fig3.update_layout(height=450)
            st.plotly_chart(fig3, use_container_width=True)

# 푸터
st.divider()
st.caption("💡 리스트내비중은 조회된 기업들의 **연간 매출액(Revenue)** 합계 대비 비율이며, 실제 글로벌 시장점유율과 다릅니다.")
st.caption("📊 데이터: Yahoo Finance (yfinance) | 환율 자동 변환(KRW→USD)")
