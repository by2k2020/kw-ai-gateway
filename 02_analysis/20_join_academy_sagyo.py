"""학원 공급(NEIS) × 사교육비(KOSIS) 시도별 결합 분석.

목표: 학원 공급량과 사교육비가 어떻게 연결되는지 산점도 + 상관분석.
"""
from pathlib import Path
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "03_visual"
OUT.mkdir(parents=True, exist_ok=True)

# 시도명 매핑: KOSIS (긴 이름) → NEIS (짧은 이름)
SIDO_MAP = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구",
    "인천광역시": "인천", "광주광역시": "광주", "대전광역시": "대전",
    "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기",
    "강원특별자치도": "강원", "충청북도": "충북", "충청남도": "충남",
    "전북특별자치도": "전북", "전라남도": "전남", "경상북도": "경북",
    "경상남도": "경남", "제주특별자치도": "제주",
}


def parse_tuition(s):
    if not isinstance(s, str):
        return None
    nums = [int(x) for x in re.findall(r"(\d{4,7})", s)]
    nums = [n for n in nums if 1000 <= n <= 5_000_000]
    return sum(nums) / len(nums) if nums else None


def main():
    # 1. NEIS 학원 데이터 → 시도별 집계
    academy = pd.read_parquet(ROOT / "01_data" / "neis_academy.parquet").copy()
    academy["tuition"] = academy["PSNBY_THCC_CNTNT"].apply(parse_tuition)
    sido_acad = academy.groupby("SIDO_NAME").agg(
        n_academy=("ACA_ASNUM", "count"),
        tuition_median=("tuition", "median"),
        capacity_total=("DTM_RCPTN_ABLTY_NMPR_SMTOT", "sum"),
    ).reset_index()
    sido_acad.columns = ["sido", "n_academy", "tuition_median", "capacity_total"]
    print("학원 집계:")
    print(sido_acad)

    # 2. KOSIS 사교육비 → 시도별 최신연도 평균
    kosis = pd.read_parquet(ROOT / "01_data" / "kosis" / "DT_1PE105.parquet").copy()
    kosis["year"] = pd.to_numeric(kosis["PRD_DE"], errors="coerce")
    kosis["value"] = pd.to_numeric(kosis["DT"], errors="coerce")
    kosis["sido_full"] = kosis["C1_NM"].astype(str).str.strip()
    kosis["sido"] = kosis["sido_full"].map(SIDO_MAP)
    kosis["school_level"] = kosis["ITM_NM"].astype(str).str.strip()

    latest = int(kosis["year"].max())
    # 전체 학교급 평균 (ITM "계" 코드 = T00)
    nat = kosis[(kosis["year"] == latest) & (kosis["school_level"].str.startswith("계")) &
                (kosis["sido"].notna())]
    if len(nat) == 0:
        # fallback: 모든 학교급 평균
        nat = kosis[(kosis["year"] == latest) & (kosis["sido"].notna())].groupby("sido", as_index=False)["value"].mean()
    nat = nat[["sido", "value"]].rename(columns={"value": "sagyo_per_student"})
    print(f"\n{latest}년 시도별 1인당 사교육비:")
    print(nat)

    # 3. 결합
    df = sido_acad.merge(nat, on="sido", how="inner")
    print("\n결합 결과:")
    print(df)

    # 4. 시도별 인구 가중 — 학원 밀도 보조 정보용
    # 학원 1개당 수용 가능 학생 수 (정원 합)
    df["capacity_per_academy"] = df["capacity_total"] / df["n_academy"]

    # 5. 산점도: 학원 수 vs 사교육비
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.scatter(df["n_academy"], df["sagyo_per_student"], s=200, alpha=0.7, c="steelblue", edgecolors="white", linewidth=2)
    for _, r in df.iterrows():
        ax.annotate(r["sido"], (r["n_academy"], r["sagyo_per_student"]),
                    fontsize=11, ha="left", va="center", xytext=(7, 0), textcoords="offset points")
    ax.set_xlabel("운영 중 학원 수")
    ax.set_ylabel(f"{latest}년 학생 1인당 월평균 사교육비 (만원)")
    ax.set_title(f"학원 공급 × 사교육비 ({latest})  —  상관계수 r = {df['n_academy'].corr(df['sagyo_per_student']):.3f}")
    ax.grid(alpha=0.3)
    ax.set_xscale("log")
    fig.tight_layout()
    fig.savefig(OUT / "20_scatter_supply_vs_sagyo.png", dpi=120)
    plt.close(fig)
    print("saved 20_scatter_supply_vs_sagyo.png")

    # 6. 산점도: 수강료 중위값 vs 1인당 사교육비
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.scatter(df["tuition_median"] / 10000, df["sagyo_per_student"], s=200, alpha=0.7, c="darkorange", edgecolors="white", linewidth=2)
    for _, r in df.iterrows():
        ax.annotate(r["sido"], (r["tuition_median"] / 10000, r["sagyo_per_student"]),
                    fontsize=11, ha="left", va="center", xytext=(7, 0), textcoords="offset points")
    # 1대1 라인 (학원 1개 다닌다고 가정 시)
    mn = min(df["tuition_median"].min() / 10000, df["sagyo_per_student"].min())
    mx = max(df["tuition_median"].max() / 10000, df["sagyo_per_student"].max())
    ax.plot([mn, mx], [mn, mx], "--", color="gray", alpha=0.5, label="1대1 (학원 1개 다닌다고 가정)")
    ax.set_xlabel("학원 1곳 수강료 중위값 (만원/월)")
    ax.set_ylabel(f"{latest}년 학생 1인당 월평균 사교육비 (만원)")
    ax.set_title(f"학원 수강료 × 1인당 사교육비 ({latest})  —  비율이 곧 동시 수강 학원 수")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "21_tuition_vs_sagyo_ratio.png", dpi=120)
    plt.close(fig)
    print("saved 21_tuition_vs_sagyo_ratio.png")

    # 7. 동시 수강 학원 수 추정 (사교육비 / 학원 수강료)
    df["concurrent_n"] = df["sagyo_per_student"] * 10000 / df["tuition_median"]
    df_sorted = df.sort_values("concurrent_n", ascending=False)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(df_sorted["sido"], df_sorted["concurrent_n"], color="purple")
    ax.invert_yaxis()
    ax.set_title(f"시도별 학생 1인당 동시 수강 학원 수 추정 ({latest})\n(= 1인당 사교육비 ÷ 학원 1곳 수강료 중위값)")
    ax.set_xlabel("동시 수강 학원 수 (개)")
    for i, v in enumerate(df_sorted["concurrent_n"]):
        ax.text(v + 0.05, i, f"{v:.2f}", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "22_concurrent_academy.png", dpi=120)
    plt.close(fig)
    print("saved 22_concurrent_academy.png")

    # 결합 데이터 저장 (다음 분석 단계 입력)
    df.to_csv(ROOT / "01_data" / "joined_sido.csv", index=False, encoding="utf-8-sig")
    print(f"\nsaved joined_sido.csv ({len(df)} rows)")
    print("\n=== 동시 수강 학원 수 Top 5 ===")
    print(df_sorted.head(5)[["sido", "n_academy", "tuition_median", "sagyo_per_student", "concurrent_n"]].to_string(index=False))


if __name__ == "__main__":
    main()
