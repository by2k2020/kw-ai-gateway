"""AI 모델 2 — 학원 공급 ↔ 사교육비 회귀 + 늘봄 시나리오 시뮬레이션.

구성:
  1. OLS 회귀: 1인당 사교육비 ~ 학원 수 + 수강료 + 학원당 정원 (시도 16개)
  2. 시나리오: 늘봄 확대로 학원 수요 X% 흡수 시 사교육비 변화 (4단계)

산출:
  - 03_visual/32_regression_diagnostic.png
  - 03_visual/33_simulation_scenarios.png
  - 01_data/simulation_result.csv
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import statsmodels.api as sm

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "01_data" / "joined_sido.csv"
OUT_VIS = ROOT / "03_visual"
OUT_DAT = ROOT / "01_data"

SCENARIOS = {
    "보수적 (10%)":     0.10,
    "기본 (20%)":       0.20,
    "적극적 (30%)":     0.30,
    "최대확장 (50%)":   0.50,
}


def main():
    df = pd.read_csv(SRC).copy()
    print(f"시도 데이터: {len(df)}개")
    print(df.head())

    # ===== 1. OLS 회귀 =====
    # Y = 1인당 사교육비 (만원), X = 학원 수, 수강료(만원), 학원당 정원
    df["tuition_man"] = df["tuition_median"] / 10000   # 만원 단위
    df["log_n_academy"] = np.log(df["n_academy"])      # 학원 수는 로그 변환
    X = df[["log_n_academy", "tuition_man", "capacity_per_academy"]].copy()
    X = sm.add_constant(X)
    y = df["sagyo_per_student"]

    model = sm.OLS(y, X).fit()
    print("\n=== OLS 회귀 요약 ===")
    print(model.summary())

    df["predicted"] = model.predict(X)
    df["residual"] = y - df["predicted"]

    # 시각화 1: 회귀 진단 (실측 vs 예측)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    ax = axes[0]
    ax.scatter(df["predicted"], y, s=150, alpha=0.7, color="steelblue", edgecolor="white", lw=1.5)
    for _, r in df.iterrows():
        ax.annotate(r["sido"], (r["predicted"], r["sagyo_per_student"]),
                    xytext=(5, 5), textcoords="offset points", fontsize=9)
    mn, mx = y.min() - 5, y.max() + 5
    ax.plot([mn, mx], [mn, mx], "--", color="gray", alpha=0.6, label="완벽 예측선")
    ax.set_xlabel("회귀 모델 예측값 (만원)")
    ax.set_ylabel("실제 사교육비 (만원)")
    ax.set_title(f"회귀 적합도  R²={model.rsquared:.3f}, adj.R²={model.rsquared_adj:.3f}")
    ax.legend()
    ax.grid(alpha=0.3)

    ax = axes[1]
    df_sorted = df.sort_values("residual")
    colors = ["#d62728" if v < 0 else "#2ca02c" for v in df_sorted["residual"]]
    ax.barh(df_sorted["sido"], df_sorted["residual"], color=colors)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("잔차 (실제 - 예측, 만원)")
    ax.set_title("시도별 잔차 — 모델이 못 잡는 지역 특성")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(OUT_VIS / "32_regression_diagnostic.png", dpi=120)
    plt.close(fig)
    print("\nsaved 32_regression_diagnostic.png")

    # ===== 2. 늘봄 시나리오 시뮬레이션 =====
    # 가정: 늘봄 흡수율 r → 학원 수요 r% 감소 → 사교육비 r% 감소 (1차 근사)
    # 추가 정교화: 늘봄 대체 가능한 분야(입시·예능 등 = 약 80%)에만 적용 → r * 0.8
    SUBSTITUTABLE_RATIO = 0.8  # 늘봄으로 대체 가능한 사교육 비중 (입시·보습 + 일부 예능)

    sim_rows = []
    for sname, ratio in SCENARIOS.items():
        effective = ratio * SUBSTITUTABLE_RATIO
        for _, r in df.iterrows():
            new_sagyo = r["sagyo_per_student"] * (1 - effective)
            saved = r["sagyo_per_student"] - new_sagyo
            sim_rows.append({
                "scenario": sname,
                "absorb_ratio": ratio,
                "sido": r["sido"],
                "sagyo_before": r["sagyo_per_student"],
                "sagyo_after": new_sagyo,
                "monthly_saving_per_student": saved,
                "annual_saving_per_student": saved * 12,
            })
    sim = pd.DataFrame(sim_rows)
    sim.to_csv(OUT_DAT / "simulation_result.csv", index=False, encoding="utf-8-sig")

    # 시각화 2: 시나리오별 시도 사교육비 변화 (4 패널)
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    for ax, (sname, ratio) in zip(axes.flat, SCENARIOS.items()):
        sub = sim[sim["scenario"] == sname].sort_values("sagyo_before", ascending=True)
        ypos = np.arange(len(sub))
        ax.barh(ypos, sub["sagyo_before"], color="lightgray", label="현재 (2025)")
        ax.barh(ypos, sub["sagyo_after"], color="steelblue", label=f"늘봄 시나리오: {sname}")
        ax.set_yticks(ypos)
        ax.set_yticklabels(sub["sido"])
        ax.set_title(f"늘봄 흡수율 {int(ratio*100)}%  →  사교육비 {int(ratio*100*SUBSTITUTABLE_RATIO)}% 감소")
        ax.set_xlabel("월평균 사교육비 (만원)")
        ax.legend(loc="lower right", fontsize=9)
        ax.grid(alpha=0.3, axis="x")
    fig.suptitle("늘봄 확대 시나리오별 시도 사교육비 변화 (대체가능 비중 80% 가정)", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT_VIS / "33_simulation_scenarios.png", dpi=120)
    plt.close(fig)
    print("saved 33_simulation_scenarios.png")

    # 시각화 3: 시나리오별 전국 총 절감액 (학생 1인당 연간)
    summary = sim.groupby("scenario")["annual_saving_per_student"].mean().reset_index()
    summary["scenario_order"] = summary["scenario"].map({k: i for i, k in enumerate(SCENARIOS)})
    summary = summary.sort_values("scenario_order")
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(summary["scenario"], summary["annual_saving_per_student"],
                  color=["#a8d5e2", "#5ba8c4", "#2e7fb8", "#1d4f8b"])
    ax.set_title("늘봄 시나리오별 학생 1인당 연간 사교육비 절감액 (전국 평균)")
    ax.set_ylabel("연간 절감액 (만원/학생)")
    for b, v in zip(bars, summary["annual_saving_per_student"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f}만원",
                ha="center", fontsize=11, fontweight="bold")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(OUT_VIS / "34_simulation_summary.png", dpi=120)
    plt.close(fig)
    print("saved 34_simulation_summary.png")

    # 핵심 요약 출력
    print("\n=== 시나리오 요약 (전국 평균 연간 절감액) ===")
    print(summary[["scenario", "annual_saving_per_student"]].round(1).to_string(index=False))

    # 회귀 계수 해석
    print("\n=== 회귀 계수 해석 ===")
    print(f"  log(학원 수) 1단위 증가 (학원 수 e배) → 사교육비 {model.params['log_n_academy']:+.2f} 만원")
    print(f"  수강료 1만원 증가 → 사교육비 {model.params['tuition_man']:+.3f} 만원")
    print(f"  학원당 정원 1명 증가 → 사교육비 {model.params['capacity_per_academy']:+.4f} 만원")


if __name__ == "__main__":
    main()
