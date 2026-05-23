"""교권 침해 진본 데이터 EDA — 시계열 + 학교급별 + 침해주체별 + 유형별.

진본: 01_data/kw/kw_2024_release_tables.json (27개 표)
출력: 03_visual/kw_*.png + 정제된 csv
"""
from pathlib import Path
import re
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "01_data" / "kw" / "kw_2024_release_tables.json"
OUT_VIS = ROOT / "03_visual"
OUT_DAT = ROOT / "01_data" / "kw"
OUT_VIS.mkdir(parents=True, exist_ok=True)


def parse_num(s):
    """'1,197(100%)' → 1197."""
    if not isinstance(s, str) or not s.strip():
        return None
    m = re.search(r"([\d,]+)", s.replace(",", ""))
    return int(m.group(1)) if m else None


# 검색 + 보도자료에서 확보한 시계열 (표 15)
TS_TOTAL = pd.DataFrame({
    "year": [2020, 2021, 2022, 2023, 2024],
    "total": [1197, 2269, 3035, 5050, 4234],
})

# 보호자 가해 시계열 (표 17 합계 열)
PARENT_HARM = pd.DataFrame({
    "year": [2020, 2021, 2022, 2023, 2024],
    "student": [1081, 2098, 2833, 4697, 3773],
    "parent": [116, 171, 202, 353, 461],
    "total": [1197, 2269, 3035, 5050, 4234],
})
PARENT_HARM["parent_ratio"] = PARENT_HARM["parent"] / PARENT_HARM["total"] * 100

# 2024 학교급별 학생/보호자 비교 (표 17 2024합계 행)
SCHOOL_2024 = pd.DataFrame({
    "school": ["유치원", "초등", "중등", "고등", "특수"],
    "student": [0, 493, 2350, 880, 44],
    "parent": [23, 211, 153, 62, 11],
})
SCHOOL_2024["total"] = SCHOOL_2024["student"] + SCHOOL_2024["parent"]
SCHOOL_2024["parent_ratio"] = SCHOOL_2024["parent"] / SCHOOL_2024["total"] * 100

# 2023 보호자 가해 유형별 (표 19에서 발췌)
PARENT_TYPE_2023 = pd.DataFrame({
    "type": ["모욕·명예훼손", "정당 교육활동 부당간섭", "공무·업무방해",
             "협박", "기타", "상해폭행", "정보유통",
             "성적 굴욕감", "손괴"],
    "count": [117, 72, 35, 35, 33, 15, 13, 5, 6],
    "ratio": [33, 20, 10, 10, 9, 4, 4, 1, 2],
})

# 2024 교원 보호 조치 (표 23)
TEACHER_CARE_2024 = pd.DataFrame({
    "type": ["심리상담·조언", "특별휴가부여", "치료·요양",
             "기타", "교사 희망 미조치"],
    "count": [2644, 1036, 463, 440, 112],
})


def vis_1_timeline():
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(TS_TOTAL["year"], TS_TOTAL["total"], "o-", lw=3, color="#1f3a68", markersize=10)
    for _, r in TS_TOTAL.iterrows():
        ax.annotate(f"{r['total']:,}", (r["year"], r["total"]),
                    xytext=(0, 10), textcoords="offset points",
                    ha="center", fontsize=11, fontweight="bold")
    ax.axvline(2023, ls="--", color="red", alpha=0.5)
    ax.text(2023.05, ax.get_ylim()[1]*0.95, "서이초 사건\n(2023.7)",
            color="red", fontsize=10)
    ax.axvline(2024, ls="--", color="green", alpha=0.5)
    ax.text(2024.05, ax.get_ylim()[1]*0.85, "교권보호5법\n(2024.3)",
            color="green", fontsize=10)
    ax.set_title("교권보호위원회 심의 건수 추이 (2020~2024)", fontsize=14, fontweight="bold")
    ax.set_xlabel("학년도"); ax.set_ylabel("심의 건수")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_VIS / "kw_01_timeline.png", dpi=120)
    plt.close(fig)


def vis_2_parent_harm():
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    ax = axes[0]
    width = 0.35
    x = PARENT_HARM["year"]
    ax.bar(x - width/2, PARENT_HARM["student"], width, label="학생 가해", color="#5ba8c4")
    ax.bar(x + width/2, PARENT_HARM["parent"], width, label="보호자 가해", color="#e64a4a")
    ax.set_title("침해 주체별 건수 (2020~2024)", fontweight="bold")
    ax.set_xlabel("학년도"); ax.set_ylabel("건수")
    ax.legend(); ax.grid(alpha=0.3, axis="y")

    ax = axes[1]
    ax.plot(PARENT_HARM["year"], PARENT_HARM["parent_ratio"], "o-",
            color="#e64a4a", lw=3, markersize=10)
    for _, r in PARENT_HARM.iterrows():
        ax.annotate(f"{r['parent_ratio']:.1f}%", (r["year"], r["parent_ratio"]),
                    xytext=(0, 10), textcoords="offset points", ha="center",
                    fontweight="bold", fontsize=11)
    ax.set_title("보호자 가해 비중 추이 (전체 침해 중)", fontweight="bold")
    ax.set_xlabel("학년도"); ax.set_ylabel("비중 (%)")
    ax.grid(alpha=0.3)
    fig.suptitle("🎯 우리 게이트웨이 시스템이 직접 타겟하는 영역", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT_VIS / "kw_02_parent_harm.png", dpi=120)
    plt.close(fig)


def vis_3_school_2024():
    fig, ax = plt.subplots(figsize=(11, 6))
    x = range(len(SCHOOL_2024))
    width = 0.35
    ax.bar([i - width/2 for i in x], SCHOOL_2024["student"], width,
           label="학생 가해", color="#5ba8c4")
    ax.bar([i + width/2 for i in x], SCHOOL_2024["parent"], width,
           label="보호자 가해", color="#e64a4a")
    ax.set_xticks(list(x)); ax.set_xticklabels(SCHOOL_2024["school"])
    for i, r in SCHOOL_2024.iterrows():
        ax.text(i, max(r["student"], r["parent"]) + 50,
                f"보호자 {r['parent_ratio']:.0f}%",
                ha="center", color="#e64a4a", fontweight="bold")
    ax.set_title("2024년 학교급별 침해 주체 분포 (보호자 비중 표기)",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("건수"); ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(OUT_VIS / "kw_03_school_2024.png", dpi=120)
    plt.close(fig)


def vis_4_parent_types():
    sub = PARENT_TYPE_2023.sort_values("count")
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = ["#e64a4a" if x in ["정당 교육활동 부당간섭", "협박", "공무·업무방해",
                                  "모욕·명예훼손"] else "#a0a0a0" for x in sub["type"]]
    ax.barh(sub["type"], sub["count"], color=colors)
    for i, r in sub.iterrows():
        idx = list(sub["type"]).index(r["type"])
        ax.text(r["count"] + 2, idx, f"{r['count']}건 ({r['ratio']}%)",
                va="center", fontsize=10)
    ax.set_title("2023년 보호자 가해 유형별 분포\n🎯 빨강 = AI 게이트웨이가 직접 막을 수 있는 유형",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("건수")
    fig.tight_layout()
    fig.savefig(OUT_VIS / "kw_04_parent_types.png", dpi=120)
    plt.close(fig)


def vis_5_teacher_care():
    df = TEACHER_CARE_2024.sort_values("count")
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.barh(df["type"], df["count"], color="#1f3a68")
    for i, r in df.iterrows():
        idx = list(df["type"]).index(r["type"])
        ax.text(r["count"] + 30, idx, f"{r['count']:,}",
                va="center", fontweight="bold")
    ax.set_title("2024년 교원 보호 조치 현황 (총 4,697건)",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("건수")
    fig.tight_layout()
    fig.savefig(OUT_VIS / "kw_05_teacher_care.png", dpi=120)
    plt.close(fig)


def main():
    vis_1_timeline()
    vis_2_parent_harm()
    vis_3_school_2024()
    vis_4_parent_types()
    vis_5_teacher_care()
    # 데이터 저장
    TS_TOTAL.to_csv(OUT_DAT / "ts_total.csv", index=False, encoding="utf-8-sig")
    PARENT_HARM.to_csv(OUT_DAT / "parent_harm.csv", index=False, encoding="utf-8-sig")
    SCHOOL_2024.to_csv(OUT_DAT / "school_2024.csv", index=False, encoding="utf-8-sig")
    PARENT_TYPE_2023.to_csv(OUT_DAT / "parent_type_2023.csv", index=False, encoding="utf-8-sig")
    TEACHER_CARE_2024.to_csv(OUT_DAT / "teacher_care_2024.csv", index=False, encoding="utf-8-sig")
    print("✅ 5장 시각화 + 5개 CSV 저장")
    print(f"\n=== 핵심 수치 ===")
    print(f"2024 보호자 가해: 461건 (전체의 10.9%)")
    print(f"우리 시스템 타겟 = 보호자 가해 + 학교급 (특히 유·초)")
    print(f"보호자 가해 1위 유형: 정당 교육활동 부당간섭 (20%)")
    print(f"2024 교원 심리상담 받은 교사: 2,644명 (전체 보호 조치의 56%)")


if __name__ == "__main__":
    main()
