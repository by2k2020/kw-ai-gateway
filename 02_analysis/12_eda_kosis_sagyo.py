"""사교육비 시계열 EDA — DT_1PE105 (시도×학교급×연도)."""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "01_data" / "kosis" / "DT_1PE105.parquet"
OUT = ROOT / "03_visual"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    df = pd.read_parquet(SRC)
    # 사교육비는 만원 단위
    df["year"] = pd.to_numeric(df["PRD_DE"], errors="coerce")
    df["value"] = pd.to_numeric(df["DT"], errors="coerce")  # 만원
    # 컬럼 정리
    df = df.rename(columns={
        "C1_NM": "sido",
        "ITM_NM": "school_level",
    })
    # ITM_NM strip
    df["school_level"] = df["school_level"].astype(str).str.strip()
    df["sido"] = df["sido"].astype(str).str.strip()

    print("연도 범위:", df["year"].min(), "~", df["year"].max())
    print("\n학교급(ITM_NM):", df["school_level"].unique())
    print("\n시도(C1_NM):", sorted(df["sido"].unique()))

    # 1. 전국 평균 사교육비 시계열 (학교급별)
    nat = df[df["sido"] == "전국"]
    pivot1 = nat.pivot_table(index="year", columns="school_level", values="value", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(11, 6))
    pivot1.plot(ax=ax, marker="o", lw=2)
    ax.set_title("전국 학생 1인당 월평균 사교육비 시계열 (학교급별)")
    ax.set_xlabel("연도")
    ax.set_ylabel("사교육비 (만원/월)")
    ax.grid(alpha=0.3)
    ax.legend(title="학교급", loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "09_sagyo_national_trend.png", dpi=120)
    plt.close(fig)
    print("saved 09_sagyo_national_trend.png")

    # 2. 시도별 2024(또는 최신) 평균 사교육비 (전체 학교급 평균)
    latest = df["year"].max()
    avg_t = df[(df["year"] == latest) & (df["school_level"].str.contains("계|평균", regex=True))]
    if len(avg_t) == 0:
        avg_t = df[df["year"] == latest].groupby("sido")["value"].mean().reset_index()
    else:
        avg_t = avg_t.groupby("sido", as_index=False)["value"].mean()
    avg_t = avg_t[avg_t["sido"] != "전국"].sort_values("value", ascending=False)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(avg_t["sido"], avg_t["value"], color="steelblue")
    ax.invert_yaxis()
    ax.set_title(f"{int(latest)}년 시도별 학생 1인당 월평균 사교육비")
    ax.set_xlabel("만원/월")
    for i, v in enumerate(avg_t["value"]):
        ax.text(v + 0.5, i, f"{v:.1f}", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "10_sagyo_sido_latest.png", dpi=120)
    plt.close(fig)
    print("saved 10_sagyo_sido_latest.png")

    # 3. 최근 5년 시도별 사교육비 증가율
    yr_n = int(latest)
    yr_5 = yr_n - 5
    recent = df[(df["year"].isin([yr_5, yr_n])) &
                (df["sido"] != "전국") &
                (df["school_level"].str.contains("계|평균", regex=True))]
    if len(recent) == 0:
        recent = df[(df["year"].isin([yr_5, yr_n])) & (df["sido"] != "전국")].groupby(["sido", "year"], as_index=False)["value"].mean()
    pv = recent.pivot_table(index="sido", columns="year", values="value", aggfunc="mean")
    pv["증가율(%)"] = (pv[yr_n] / pv[yr_5] - 1) * 100
    pv = pv.sort_values("증가율(%)", ascending=False)
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = ["#d62728" if v > pv["증가율(%)"].median() else "#1f77b4" for v in pv["증가율(%)"]]
    ax.barh(pv.index, pv["증가율(%)"], color=colors)
    ax.invert_yaxis()
    ax.set_title(f"시도별 사교육비 증가율 ({yr_5} → {yr_n})")
    ax.set_xlabel("증가율 (%)")
    for i, v in enumerate(pv["증가율(%)"]):
        ax.text(v + 0.5, i, f"{v:.1f}%", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "11_sagyo_growth_5yr.png", dpi=120)
    plt.close(fig)
    print("saved 11_sagyo_growth_5yr.png")

    # 핵심 요약
    print("\n=== 핵심 인사이트 ===")
    nat_total = nat[nat["school_level"].str.contains("계|평균", regex=True)].groupby("year")["value"].mean()
    if len(nat_total) > 0:
        first_y = nat_total.index.min()
        last_y = nat_total.index.max()
        print(f"  전국 평균 {first_y}년: {nat_total[first_y]:.1f} 만원/월")
        print(f"  전국 평균 {last_y}년: {nat_total[last_y]:.1f} 만원/월")
        print(f"  {first_y}~{last_y} 증가율: {(nat_total[last_y]/nat_total[first_y]-1)*100:.1f}%")

    print("\n  최신연도 시도 Top 3:")
    print(avg_t.head(3).to_string(index=False))
    print("\n  최신연도 시도 Bottom 3:")
    print(avg_t.tail(3).to_string(index=False))


if __name__ == "__main__":
    main()
