"""AI 모델 1 — 시도별 사교육비 5년 예측 (2026~2030).

방법: Holt-Winters 지수평활(트렌드만, 계절성 없음) + 신뢰구간.
입력: KOSIS DT_1PE105 (2009~2025, 시도×학교급)
출력: 시도별 예측 그래프 + 통합 dataframe
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import warnings

warnings.filterwarnings("ignore")
matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "01_data" / "kosis" / "DT_1PE105.parquet"
OUT_VIS = ROOT / "03_visual"
OUT_DAT = ROOT / "01_data"

SIDO_SHORT = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구",
    "인천광역시": "인천", "광주광역시": "광주", "대전광역시": "대전",
    "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기",
    "강원특별자치도": "강원", "충청북도": "충북", "충청남도": "충남",
    "전북특별자치도": "전북", "전라남도": "전남", "경상북도": "경북",
    "경상남도": "경남", "제주특별자치도": "제주",
}

FORECAST_YEARS = 5


def fit_forecast(ts: pd.Series, n_periods: int = FORECAST_YEARS):
    """Holt linear trend로 n_periods 예측."""
    ts = ts.dropna().sort_index()
    if len(ts) < 5:
        return None, None
    # damped_trend로 장기 폭주·폭락 방지 + 최근 10년만 사용 (구조 변화 반영)
    ts_recent = ts.tail(10) if len(ts) > 10 else ts
    model = ExponentialSmoothing(ts_recent, trend="add", damped_trend=True,
                                 seasonal=None, initialization_method="estimated")
    fit = model.fit(optimized=True)
    future_idx = list(range(int(ts.index.max()) + 1, int(ts.index.max()) + 1 + n_periods))
    pred = fit.forecast(n_periods)
    pred.index = future_idx
    # 잔차 표준편차로 신뢰구간 근사
    resid_std = (ts - fit.fittedvalues).std()
    lo = pred - 1.96 * resid_std
    hi = pred + 1.96 * resid_std
    return pred, (lo, hi)


def main():
    df = pd.read_parquet(SRC).copy()
    df["year"] = pd.to_numeric(df["PRD_DE"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["DT"], errors="coerce")
    df["sido_full"] = df["C1_NM"].astype(str).str.strip()
    df["sido"] = df["sido_full"].map(SIDO_SHORT)
    # ITM_ID T00 = 전체 평균
    avg = df[(df["ITM_ID"] == "T00") & df["sido"].notna()].copy()

    # 시도별 시계열
    pivot = avg.pivot_table(index="year", columns="sido", values="value", aggfunc="mean")
    pivot.index = pivot.index.astype(int)
    print(f"시계열 데이터: {pivot.shape[0]}년 × {pivot.shape[1]}개 시도")
    print(pivot.tail(3))

    # 시도별 예측
    forecasts = {}
    intervals = {}
    for sido in pivot.columns:
        pred, ci = fit_forecast(pivot[sido])
        if pred is not None:
            forecasts[sido] = pred
            intervals[sido] = ci

    pred_df = pd.DataFrame(forecasts)
    print(f"\n예측 결과:")
    print(pred_df.round(1))

    # 시각화 1: 전체 시도 통합 (4x5 small multiple)
    sido_list = list(pivot.columns)
    n = len(sido_list)
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(15, 3 * rows), sharex=True)
    for i, sido in enumerate(sido_list):
        ax = axes[i // cols, i % cols]
        hist = pivot[sido].dropna()
        ax.plot(hist.index, hist.values, "o-", color="steelblue", label="실측")
        if sido in forecasts:
            f = forecasts[sido]
            lo, hi = intervals[sido]
            ax.plot(f.index, f.values, "o--", color="darkred", label="예측")
            ax.fill_between(f.index, lo.values, hi.values, alpha=0.2, color="red")
        ax.set_title(sido, fontsize=11)
        ax.grid(alpha=0.3)
        if i == 0:
            ax.legend(loc="upper left", fontsize=8)
    # 빈 칸 숨김
    for i in range(n, rows * cols):
        axes[i // cols, i % cols].axis("off")
    fig.suptitle("시도별 학생 1인당 월평균 사교육비 — 실측(2009~2025) + 예측(2026~2030)", fontsize=14)
    fig.supxlabel("연도")
    fig.supylabel("사교육비 (만원/월)")
    fig.tight_layout()
    fig.savefig(OUT_VIS / "30_forecast_all_sido.png", dpi=120)
    plt.close(fig)
    print("saved 30_forecast_all_sido.png")

    # 시각화 2: Top 5 + Bottom 3 시도 강조
    latest_year = pivot.index.max()
    sorted_sido = pivot.loc[latest_year].sort_values(ascending=False)
    highlight = sorted_sido.head(5).index.tolist() + sorted_sido.tail(3).index.tolist()
    fig, ax = plt.subplots(figsize=(13, 7))
    cmap = plt.colormaps["tab10"]
    for i, sido in enumerate(highlight):
        hist = pivot[sido].dropna()
        ax.plot(hist.index, hist.values, "o-", color=cmap(i / 8), label=sido, lw=2)
        if sido in forecasts:
            f = forecasts[sido]
            ax.plot(f.index, f.values, "o--", color=cmap(i / 8), alpha=0.7)
    ax.axvline(latest_year, ls="--", color="gray", alpha=0.5)
    ax.text(latest_year + 0.1, ax.get_ylim()[1] * 0.95, "예측 시작", color="gray", fontsize=9)
    ax.set_title("Top 5 + Bottom 3 시도 — 사교육비 17년 추이 + 5년 예측")
    ax.set_xlabel("연도")
    ax.set_ylabel("사교육비 (만원/월)")
    ax.legend(loc="upper left", ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_VIS / "31_forecast_highlight.png", dpi=120)
    plt.close(fig)
    print("saved 31_forecast_highlight.png")

    # 결과 저장
    pred_df.to_csv(OUT_DAT / "sagyo_forecast.csv", encoding="utf-8-sig")
    print(f"\nsaved sagyo_forecast.csv")

    # 핵심 수치
    print("\n=== 예측 요약 ===")
    last = pivot.iloc[-1]
    future = pred_df.iloc[-1]  # 2030
    summary = pd.DataFrame({
        "2025_실측": last,
        "2030_예측": future,
        "5년_증가율(%)": (future / last - 1) * 100,
    }).sort_values("2030_예측", ascending=False)
    print(summary.round(1).to_string())


if __name__ == "__main__":
    main()
