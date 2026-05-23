"""학원 데이터 1차 EDA — 시도/시군구/분야/가격대 분포.

입력: 01_data/neis_academy.parquet
출력: 03_visual/ 에 PNG 다수
"""
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
    """PSNBY_THCC_CNTNT 텍스트에서 모든 수강료 숫자(원) 추출 → 평균."""
    if not isinstance(s, str):
        return None
    nums = [int(x) for x in re.findall(r"(\d{4,7})", s)]
    nums = [n for n in nums if 1000 <= n <= 5_000_000]  # 합리적 범위
    if not nums:
        return None
    return sum(nums) / len(nums)


def main():
    df = pd.read_parquet(SRC)
    print(f"loaded {len(df):,} rows, {df.shape[1]} cols")

    # NEIS API는 이미 운영 중인 학원만 반환
    active = df.copy()
    print(f"active (모두 운영중): {len(active):,}")

    # 2. 시도별 분포
    sido_cnt = active["SIDO_NAME"].value_counts()
    fig, ax = plt.subplots(figsize=(10, 6))
    sido_cnt.plot(kind="barh", ax=ax)
    ax.set_title("시도별 학원·교습소 수 (운영 중)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(OUT / "01_sido_count.png", dpi=120)
    plt.close(fig)
    print("saved 01_sido_count.png")

    # 3. 분야(REALM_SC_NM) Top 15
    realm_cnt = active["REALM_SC_NM"].value_counts().head(15)
    fig, ax = plt.subplots(figsize=(10, 6))
    realm_cnt.plot(kind="barh", ax=ax)
    ax.set_title("학원 분야 Top 15")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(OUT / "02_realm_top15.png", dpi=120)
    plt.close(fig)
    print("saved 02_realm_top15.png")

    # 4. 수강료 분포
    active["tuition_avg"] = active["PSNBY_THCC_CNTNT"].apply(parse_tuition)
    tuition_by_sido = active.groupby("SIDO_NAME")["tuition_avg"].median().sort_values()
    fig, ax = plt.subplots(figsize=(10, 6))
    tuition_by_sido.plot(kind="barh", ax=ax)
    ax.set_title("시도별 학원 수강료 중위값 (원/월)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(OUT / "03_tuition_by_sido.png", dpi=120)
    plt.close(fig)
    print("saved 03_tuition_by_sido.png")

    # 5. 시군구별 학원 밀도 (Top 30)
    sigungu_cnt = active.groupby(["SIDO_NAME", "ADMST_ZONE_NM"]).size().sort_values(ascending=False).head(30)
    fig, ax = plt.subplots(figsize=(12, 8))
    sigungu_cnt.plot(kind="barh", ax=ax)
    ax.set_title("시군구별 학원 수 Top 30")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(OUT / "04_sigungu_top30.png", dpi=120)
    plt.close(fig)
    print("saved 04_sigungu_top30.png")

    # 6. 요약 통계
    summary = {
        "total_rows": len(df),
        "active": len(active),
        "n_sido": active["SIDO_NAME"].nunique(),
        "n_sigungu": active["ADMST_ZONE_NM"].nunique(),
        "n_realm": active["REALM_SC_NM"].nunique(),
        "tuition_median_won": int(active["tuition_avg"].median()),
        "tuition_p25": int(active["tuition_avg"].quantile(0.25)),
        "tuition_p75": int(active["tuition_avg"].quantile(0.75)),
    }
    print("\n=== summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v:,}")
    pd.Series(summary).to_csv(OUT / "00_summary.csv", encoding="utf-8-sig")


if __name__ == "__main__":
    main()
