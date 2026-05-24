"""1000개 테스트 결과 분석 + 자동 보고서 생성 (마크다운).

출력:
  - 05_submission/test_report_1000.md (전체 보고서)
  - 03_visual/test_confusion_matrix.png (혼동행렬)
  - 03_visual/test_risk_distribution.png (위험도 분포)
"""
from pathlib import Path
import json
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import numpy as np

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "01_data" / "test_results_1000.json"
OUT_MD = ROOT / "05_submission" / "test_report_1000.md"
OUT_VIS = ROOT / "03_visual"
OUT_VIS.mkdir(parents=True, exist_ok=True)


def classify_predicted(category: str) -> str:
    """LLM 출력 카테고리 → 정당/모호/악성 3분류."""
    c = (category or "").strip()
    if "악성" in c:
        return "악성"
    if "모호" in c:
        return "모호"
    if "정당" in c:
        return "정당"
    return "기타"


def main():
    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    print(f"총 {len(data)}건")

    # 에러 분리
    errors = [r for r in data if "error" in r]
    ok = [r for r in data if "error" not in r]
    print(f"  성공 {len(ok)} / 실패 {len(errors)}")

    df = pd.DataFrame(ok)
    df["predicted"] = df["category"].apply(classify_predicted)
    df["expected"] = df["expected"].str.strip()
    df["correct"] = df["predicted"] == df["expected"]

    # 1. 전체 정확도
    accuracy = df["correct"].mean()
    print(f"\n전체 정확도: {accuracy*100:.1f}%")

    # 2. 카테고리별 정확도 (recall)
    per_cat = df.groupby("expected").agg(
        n=("id", "count"),
        correct=("correct", "sum"),
    )
    per_cat["recall"] = per_cat["correct"] / per_cat["n"]
    print(per_cat)

    # 3. 혼동 행렬
    confusion = pd.crosstab(df["expected"], df["predicted"], margins=True, margins_name="합계")
    print("\n혼동 행렬:")
    print(confusion)

    # 4. 위험도 분포 (정답 기준)
    risk_by_expected = df.groupby("expected")["risk_score"].describe()
    print("\n카테고리별 위험도 분포:")
    print(risk_by_expected)

    # 5. 오분류 사례 (false negative — 악성을 정당으로)
    fn_malicious = df[(df["expected"] == "악성") & (df["predicted"] != "악성")]
    print(f"\n악성 → 비악성 오분류 (false negative): {len(fn_malicious)}건")

    # 6. 비용·토큰 집계
    total_in = df["in_tokens"].sum()
    total_out = df["out_tokens"].sum()
    cache_read = df["cache_read"].sum() if "cache_read" in df.columns else 0
    cost = (total_in - cache_read) * 0.80 / 1e6 + cache_read * 0.08 / 1e6 + total_out * 4.0 / 1e6

    # ===== 시각화 1: 혼동 행렬 =====
    cm = pd.crosstab(df["expected"], df["predicted"])
    order = [c for c in ["정당", "모호", "악성"] if c in cm.index or c in cm.columns]
    cm = cm.reindex(index=order, columns=order, fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(cm.columns))); ax.set_xticklabels(cm.columns)
    ax.set_yticks(range(len(cm.index))); ax.set_yticklabels(cm.index)
    ax.set_xlabel("예측 (AI)"); ax.set_ylabel("정답 (사람)")
    ax.set_title(f"분류 혼동 행렬 (n={len(df)}, 정확도 {accuracy*100:.1f}%)")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            v = cm.iat[i, j]
            ax.text(j, i, f"{v}", ha="center", va="center",
                    color="white" if v > cm.values.max() / 2 else "black", fontsize=13)
    plt.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(OUT_VIS / "test_confusion_matrix.png", dpi=120)
    plt.close(fig)

    # ===== 시각화 2: 위험도 분포 =====
    fig, ax = plt.subplots(figsize=(10, 5))
    for cat, color in [("정당", "#2D9C5F"), ("모호", "#F59E0B"), ("악성", "#E64A4A")]:
        sub = df[df["expected"] == cat]["risk_score"]
        if len(sub) > 0:
            ax.hist(sub, bins=20, alpha=0.55, label=f"{cat} (n={len(sub)})", color=color)
    ax.axvline(0.45, ls="--", color="gray", label="주의 임계 0.45")
    ax.axvline(0.65, ls="--", color="red", label="악성 임계 0.65")
    ax.set_xlabel("AI 위험도 점수"); ax.set_ylabel("질문 수")
    ax.set_title("정답 카테고리별 AI 위험도 분포")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_VIS / "test_risk_distribution.png", dpi=120)
    plt.close(fig)

    # ===== 보고서 마크다운 =====
    md = []
    md.append("# 🧪 1000개 질문 자체 테스트 보고서\n")
    md.append(f"**생성일**: 2026-05-24")
    md.append(f"**모델**: claude-haiku-4-5-20251001 (Full-context RAG, 60건 사례)")
    md.append(f"**테스트 방식**: Claude로 자동 생성한 학부모 질문 1,000개 → AI 분류 → 정답 대비 정확도\n")

    md.append("## 📊 핵심 지표\n")
    md.append(f"| 항목 | 값 |\n|---|---:|\n"
              f"| 전체 질문 | {len(data):,}건 |\n"
              f"| 성공 분류 | {len(ok):,}건 ({len(ok)/len(data)*100:.1f}%) |\n"
              f"| JSON 파싱 실패 | {len(errors):,}건 |\n"
              f"| **전체 정확도** | **{accuracy*100:.1f}%** |\n"
              f"| 비용 (Haiku + caching) | **${cost:.3f}** |\n"
              f"| 토큰 (input/output) | {total_in:,} / {total_out:,} |\n"
              f"| Cache read (90% 절감) | {cache_read:,} 토큰 |\n")

    md.append("## 🎯 카테고리별 정확도 (Recall)\n")
    md.append("| 정답 | 건수 | 정답 맞춘 수 | Recall |\n|---|---:|---:|---:|")
    for cat, row in per_cat.iterrows():
        md.append(f"| {cat} | {row['n']:,} | {row['correct']:,} | {row['recall']*100:.1f}% |")
    md.append("")

    md.append("## 🔀 혼동 행렬\n")
    md.append("![혼동 행렬](../03_visual/test_confusion_matrix.png)\n")
    md.append("```")
    md.append(confusion.to_string())
    md.append("```\n")

    md.append("## 📈 위험도 분포\n")
    md.append("![위험도 분포](../03_visual/test_risk_distribution.png)\n")

    md.append("## ⚠️ 결정적 오분류 — 악성을 비악성으로 (False Negative)\n")
    md.append(f"교권 침해 가능 케이스를 놓친 사례 **{len(fn_malicious)}건** "
              f"(전체 악성 {len(df[df['expected']=='악성'])}건 중)\n")
    if len(fn_malicious) > 0:
        md.append("샘플 10건:")
        md.append("| # | 입력 | AI 분류 | AI 위험도 |\n|---|---|---|---:|")
        for _, r in fn_malicious.head(10).iterrows():
            md.append(f"| {r['id']} | {r['text'][:60]}… | {r['category']} | {r['risk_score']:.2f} |")
        md.append("")

    md.append("## 📊 위험도 통계 (정답 카테고리별)\n")
    md.append("```")
    md.append(risk_by_expected.round(2).to_string())
    md.append("```\n")

    md.append("## 💡 결론\n")
    if accuracy >= 0.85:
        verdict = f"⭐⭐⭐⭐⭐ 정확도 {accuracy*100:.1f}% — 시연·정식 도입 모두 적합"
    elif accuracy >= 0.75:
        verdict = f"⭐⭐⭐⭐ 정확도 {accuracy*100:.1f}% — 시연 적합, 정식 도입은 추가 학습 권장"
    elif accuracy >= 0.65:
        verdict = f"⭐⭐⭐ 정확도 {accuracy*100:.1f}% — 시연 가능, 정식 도입 전 미세조정 필수"
    else:
        verdict = f"⭐⭐ 정확도 {accuracy*100:.1f}% — 학습 데이터·프롬프트 보강 필요"
    md.append(verdict + "\n")
    md.append(f"- 평균 응답 시간: 약 5~10초 (Haiku full-context 200K)")
    md.append(f"- 비용: ${cost:.3f} / 1000건 = **${cost*1000/1000:.4f}/건**")
    md.append(f"- prompt caching 90% 절감 적용으로 정식 도입 시 비용 매우 낮음\n")

    md.append("## 🔬 한계 + 정식 도입 시 개선\n")
    md.append("- 학습 데이터 60건은 시연 수준. 정식 도입 시 교육부 교권보호위 의결문 수천 건 미세조정 필요.")
    md.append("- 일부 미묘한 경계 케이스 (모호 vs 정당)는 사람 검증 권장.")
    md.append("- 시도교육청별 학칙·관행 차이 반영을 위한 학교별 fine-tuning 가능.\n")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"\n✅ 보고서 저장: {OUT_MD}")
    print(f"   시각화 2장: {OUT_VIS}/test_confusion_matrix.png, test_risk_distribution.png")


if __name__ == "__main__":
    main()
