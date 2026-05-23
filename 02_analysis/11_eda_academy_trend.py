"""학원 설립연도 분석 + 분야별 수강료 + 시도×분야 매트릭스."""
from pathlib import Path
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "01_data" / "neis_academy.parquet"
OUT = ROOT / "03_visual"
OUT.mkdir(parents=True, exist_ok=True)


def parse_tuition(s):
    if not isinstance(s, str):
        return None
    nums = [int(x) for x in re.findall(r"(\d{4,7})", s)]
    nums = [n for n in nums if 1000 <= n <= 5_000_000]
    return sum(nums) / len(nums) if nums else None


def main():
    df = pd.read_parquet(SRC).copy()
    df["tuition_avg"] = df["PSNBY_THCC_CNTNT"].apply(parse_tuition)
    df["estbl_year"] = pd.to_numeric(df["ESTBL_YMD"].str[:4], errors="coerce")

    # 5. 설립연도별 신규 개원 추이 (1990~2025)
    year_cnt = df[(df["estbl_year"] >= 1990) & (df["estbl_year"] <= 2025)].groupby("estbl_year").size()
    fig, ax = plt.subplots(figsize=(11, 6))
    year_cnt.plot(kind="line", ax=ax, marker="o")
    ax.set_title("연도별 학원 신규 등록 추이 (전국, 1990~2025)")
    ax.set_xlabel("등록 연도")
    ax.set_ylabel("신규 등록 학원 수")
    ax.grid(alpha=0.3)
    ax.axvline(2020, ls="--", color="red", alpha=0.5, label="코로나(2020)")
    ax.axvline(2024, ls="--", color="orange", alpha=0.5, label="늘봄1차(2024)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "05_yearly_new_registration.png", dpi=120)
    plt.close(fig)
    print("saved 05_yearly_new_registration.png")

    # 6. 분야별 평균 수강료
    realm_avg = df.groupby("REALM_SC_NM")["tuition_avg"].median().sort_values()
    realm_avg = realm_avg[realm_avg.notna()]
    fig, ax = plt.subplots(figsize=(11, 6))
    realm_avg.plot(kind="barh", ax=ax)
    ax.set_title("학원 분야별 수강료 중위값 (원/월)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(OUT / "06_realm_tuition.png", dpi=120)
    plt.close(fig)
    print("saved 06_realm_tuition.png")

    # 7. 시도×분야 히트맵 (상위 5개 분야만)
    top_realms = df["REALM_SC_NM"].value_counts().head(5).index.tolist()
    pivot = df[df["REALM_SC_NM"].isin(top_realms)].pivot_table(
        index="SIDO_NAME", columns="REALM_SC_NM", aggfunc="size", fill_value=0
    )
    # 시도별 학원 총수 기준 내림차순
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(11, 8))
    im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=20, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("시도 × 학원 분야 매트릭스 (상위 5개 분야)")
    plt.colorbar(im, ax=ax)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, f"{pivot.iat[i,j]:,}",
                    ha="center", va="center", fontsize=8,
                    color="white" if pivot.iat[i, j] > pivot.values.max() / 2 else "black")
    fig.tight_layout()
    fig.savefig(OUT / "07_sido_realm_heatmap.png", dpi=120)
    plt.close(fig)
    print("saved 07_sido_realm_heatmap.png")

    # 8. 코로나 전후 (2015~2019 vs 2020~2024) 신규 개원 변화
    recent = df[(df["estbl_year"] >= 2015) & (df["estbl_year"] <= 2024)].copy()
    recent["period"] = recent["estbl_year"].apply(lambda y: "2015-2019" if y <= 2019 else "2020-2024")
    sido_period = recent.groupby(["SIDO_NAME", "period"]).size().unstack(fill_value=0)
    sido_period["변화율(%)"] = (sido_period["2020-2024"] / sido_period["2015-2019"] - 1) * 100
    sido_period = sido_period.sort_values("변화율(%)")
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = ["red" if v < 0 else "steelblue" for v in sido_period["변화율(%)"]]
    sido_period["변화율(%)"].plot(kind="barh", ax=ax, color=colors)
    ax.set_title("시도별 학원 신규 등록 변화율 (2015~19 → 2020~24)")
    ax.axvline(0, color="black", lw=0.8)
    fig.tight_layout()
    fig.savefig(OUT / "08_covid_change.png", dpi=120)
    plt.close(fig)
    print("saved 08_covid_change.png")

    print("\n=== 요약 ===")
    print(f"2024년 신규 등록: {year_cnt.get(2024, 0):,}개")
    print(f"2020년 신규 등록 (코로나): {year_cnt.get(2020, 0):,}개")
    print(f"2019년 신규 등록 (코로나 전): {year_cnt.get(2019, 0):,}개")
    print(f"전국 시도별 변화율 평균: {sido_period['변화율(%)'].mean():.1f}%")


if __name__ == "__main__":
    main()
