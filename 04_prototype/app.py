"""제8회 교육 공공데이터 AI활용대회 — 출품작 프로토타입.

「AI 기반 학교 교권 보호 어시스턴트」
학부모 자가 점검 + 학교용 분석 리포트 + 교육청용 정책 모니터
"""
from pathlib import Path
import sys
import json
import importlib.util
import streamlit as st
import pandas as pd
import plotly.express as px

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS = ROOT / "02_analysis"
DATA = ROOT / "01_data"

# 분류기·리포트 모듈 동적 import
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

clf = _load("clf", ANALYSIS / "40_classifier_rag.py")
rep = _load("rep", ANALYSIS / "41_report_generator.py")

st.set_page_config(page_title="학교 민원 AI 게이트웨이",
                   page_icon="🛡️", layout="wide")

# 세션 상태 (학교 접수함)
if "inbox" not in st.session_state:
    st.session_state.inbox = []

# 사이드바
st.sidebar.title("🛡️ 학교 민원 AI 게이트웨이")
st.sidebar.markdown("**제8회 교육 공공데이터 AI활용대회**")
st.sidebar.markdown("일반 / AI 활용 아이디어 기획")
st.sidebar.markdown("---")
mode = st.sidebar.radio(
    "사용자 모드 선택",
    [
        "👨‍👩‍👧 학부모 — 민원 자가 점검",
        "🏫 학교 — 접수 민원 분석 리포트",
        "🏛 교육청 — 시도별 교권 보호 현황",
        "ℹ️ 시스템 소개 & 활용 데이터",
    ],
)
st.sidebar.markdown("---")
st.sidebar.markdown(
    """
### 활용 교육 공공데이터
- 교육부 교권보호위원회 개최 현황 (data.go.kr 15137983)
- NEIS 학원교습소정보 (전국 138,259건)
- KOSIS 사교육비조사 (DT_1PE105, 2009~2025)

### AI 모델
1. 민원 분류 (TF-IDF + cosine)
2. 유사 사례 검색 (RAG)
3. 위험도 평가 + 리포트 생성
4. 시도별 5년 시계열 예측
"""
)

# =========================================================
# 1. 학부모 모드
# =========================================================
if mode.startswith("👨"):
    st.title("👨‍👩‍👧 학부모 — 민원 자가 점검")
    st.markdown(
        "민원을 학교에 직접 제출하기 전, **AI가 과거 유사 사례를 검색하고 "
        "교권 침해 가능성을 분석**해 드립니다. 신중한 민원 = 우리 아이의 학교가 더 좋아집니다."
    )

    c1, c2 = st.columns([2, 1])
    with c1:
        complaint = st.text_area(
            "민원 내용을 자유롭게 작성해 주세요",
            height=180,
            placeholder="예: 우리 아이가 수업 시간에 자리 옮겨졌다고 모욕감을 느꼈답니다. 담임 교체를 요청합니다.",
        )
    with c2:
        parent_name = st.text_input("작성자 (선택)", value="익명")
        grade = st.selectbox("자녀 학년", ["미입력"] + [f"{x}학년" for x in
                                                  ["초1", "초2", "초3", "초4", "초5", "초6",
                                                   "중1", "중2", "중3", "고1", "고2", "고3"]])

    if st.button("🔎 AI 자가 점검 실행", type="primary", use_container_width=True):
        if not complaint.strip():
            st.error("민원 내용을 입력해 주세요.")
        else:
            r = rep.generate_report(complaint, parent_name, grade)
            st.session_state.last_report = r

    if "last_report" in st.session_state:
        r = st.session_state.last_report
        st.markdown("---")
        st.markdown("## 🔎 자가 점검 결과")

        # 위험도 표시
        risk = r["risk_score"]
        color = "🔴" if risk >= 0.6 else ("🟡" if risk >= 0.3 else "🟢")
        k1, k2, k3 = st.columns(3)
        k1.metric("위험도 점수", f"{color} {risk:.2f} / 1.00")
        k2.metric("AI 분류", r["predicted_category"])
        k3.metric("긴급도", r["urgency"])

        if risk >= 0.6:
            st.error(f"**{r['risk_label']}**\n\n{r['recommend_self_check']}")
        elif risk >= 0.3:
            st.warning(f"**{r['risk_label']}**\n\n{r['recommend_self_check']}")
        else:
            st.success(f"**{r['risk_label']}**\n\n{r['recommend_self_check']}")

        st.markdown("### 📚 과거 유사 사례 (Top 3)")
        for i, c in enumerate(r["similar_cases"], 1):
            with st.expander(
                f"{i}. [{c['category']}] 유사도 {c['similarity']:.2f} — {c['verdict']}"
            ):
                st.write(f"**사례 원문**: {c['text']}")
                st.write(f"**판정 근거**: {c['rationale']}")

        st.markdown("---")
        st.markdown("### 🚦 어떻게 하시겠습니까?")
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            if st.button("🔄 내용 수정·재작성", use_container_width=True):
                del st.session_state.last_report
                st.rerun()
        with cc2:
            if st.button("❌ 민원 제출 취소", use_container_width=True):
                del st.session_state.last_report
                st.success("민원 제출을 취소했습니다. 신중한 판단 감사합니다.")
                st.rerun()
        with cc3:
            if st.button("📨 학교에 정식 제출 (분석 리포트 동봉)",
                         use_container_width=True, type="primary"):
                st.session_state.inbox.append(r)
                st.success(f"학교 접수함에 전달했습니다. (현재 접수: {len(st.session_state.inbox)}건)")

# =========================================================
# 2. 학교 모드
# =========================================================
elif mode.startswith("🏫"):
    st.title("🏫 학교 — 접수 민원 분석 리포트")
    st.markdown("학부모 게이트웨이로 접수된 민원과 AI 분석 리포트입니다.")

    if not st.session_state.inbox:
        st.info("아직 접수된 민원이 없습니다. '학부모 모드'에서 민원을 제출해 보세요. (시연용 샘플도 좋습니다)")
        if st.button("🎬 시연용 샘플 민원 3건 자동 생성"):
            samples = [
                "선생님이 우리 아이한테 숙제 안 했다고 야단쳤다는데 사과 받고 싶어요.",
                "통학로에 신호등이 없어서 매일 위험합니다. 학교에서 시청에 정식 요청 부탁드려요.",
                "이번주에만 다섯 번째 민원입니다. 우리 아이 학습 자세, 친구 관계, 점심 메뉴 모두 문제입니다.",
            ]
            for s in samples:
                st.session_state.inbox.append(
                    rep.generate_report(s, parent_name="시연용", student_grade="초3")
                )
            st.rerun()
    else:
        df = pd.DataFrame([{
            "id": i,
            "긴급도": r["urgency"],
            "위험도": r["risk_score"],
            "카테고리": r["predicted_category"],
            "민원 요약": r["complaint_text"][:60] + "…",
        } for i, r in enumerate(st.session_state.inbox)])
        st.dataframe(df, use_container_width=True, height=200)

        idx = st.selectbox("상세 리포트를 볼 민원 ID", df["id"].tolist())
        st.markdown("---")
        report = st.session_state.inbox[idx]
        st.markdown(rep.report_to_markdown(report))

        if st.button("🗑 접수함 비우기"):
            st.session_state.inbox = []
            st.rerun()

# =========================================================
# 3. 교육청 모드
# =========================================================
elif mode.startswith("🏛"):
    st.title("🏛 교육청 — 교권 보호 현황 대시보드")
    st.caption("출처: 교육부 2024학년도 교육활동 침해 실태조사 (2025.5.13 발표)")

    ts_path = DATA / "kw" / "ts_total.csv"
    parent_path = DATA / "kw" / "parent_harm.csv"
    school_path = DATA / "kw" / "school_2024.csv"
    type_path = DATA / "kw" / "parent_type_2023.csv"

    if not ts_path.exists():
        st.error("진본 데이터 미수집. 02_analysis/50_kw_eda.py 를 먼저 실행하세요.")
    else:
        ts = pd.read_csv(ts_path)
        parent = pd.read_csv(parent_path)
        school = pd.read_csv(school_path)
        ptype = pd.read_csv(type_path)

        # 핵심 메트릭
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("2024 심의 건수", f"{int(ts['total'].iloc[-1]):,}건",
                  delta=f"{int(ts['total'].iloc[-1] - ts['total'].iloc[-2]):,}")
        k2.metric("보호자 가해 비중", f"{parent['parent_ratio'].iloc[-1]:.1f}%",
                  delta=f"+{parent['parent_ratio'].iloc[-1] - parent['parent_ratio'].iloc[-2]:.1f}%p")
        k3.metric("유치원 보호자 가해", "100%",
                  help="유치원은 학생 가해 불가, 전부 보호자")
        k4.metric("우리 시스템 타겟", f"~{parent['parent'].iloc[-1]:,}건/년",
                  help="2024 보호자 가해 461건이 직접 타겟")

        st.markdown("---")
        c1, c2 = st.columns(2)

        with c1:
            fig = px.line(ts, x="year", y="total", markers=True,
                          title="전국 교권보호위 심의 건수 (2020~2024)",
                          labels={"year": "학년도", "total": "심의 건수"})
            fig.update_traces(line=dict(width=3, color="#1f3a68"), marker=dict(size=10))
            fig.add_vline(x=2023, line_dash="dash", line_color="red",
                          annotation_text="서이초", annotation_position="top")
            fig.add_vline(x=2024, line_dash="dash", line_color="green",
                          annotation_text="교권5법", annotation_position="top")
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            fig = px.line(parent, x="year", y="parent_ratio", markers=True,
                          title="보호자 가해 비중 추이 (전체 침해 중 %)",
                          labels={"year": "학년도", "parent_ratio": "보호자 가해 비중 (%)"})
            fig.update_traces(line=dict(width=3, color="#e64a4a"), marker=dict(size=12))
            st.plotly_chart(fig, use_container_width=True)

        c3, c4 = st.columns(2)
        with c3:
            fig = px.bar(school, x="school", y=["student", "parent"], barmode="group",
                         title="2024 학교급별 침해 주체 분포",
                         labels={"value": "건수", "school": "학교급", "variable": "주체"},
                         color_discrete_map={"student": "#5ba8c4", "parent": "#e64a4a"})
            fig.for_each_trace(lambda t: t.update(name={"student": "학생 가해",
                                                         "parent": "보호자 가해"}[t.name]))
            st.plotly_chart(fig, use_container_width=True)

        with c4:
            fig = px.bar(ptype.sort_values("count"), x="count", y="type", orientation="h",
                         title="2023 보호자 가해 유형 분포",
                         labels={"count": "건수", "type": "유형"})
            fig.update_traces(marker_color="#e64a4a")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.markdown("### 💡 정책 시사점")
        st.info(
            "- **보호자 가해 비중이 7%대에서 10.9%로 급증** (2024) — 시스템 도입 시급\n"
            "- **유치원·초등은 보호자 가해 30~100%** — 우리 시스템 핵심 타겟층\n"
            "- 보호자 가해 1위 = **'정당 교육활동 부당간섭' 20%** — 우리 게이트웨이가 직접 막을 수 있는 유형"
        )

# =========================================================
# 4. 시스템 소개
# =========================================================
else:
    st.title("ℹ️ 학교 민원 AI 게이트웨이 — 시스템 소개")
    st.markdown(
        """
## 🎯 무엇을 푸는가
2023 서이초 사건 이후 교사들은 학부모 악성 민원에 직접 노출되어 있습니다.
교육부는 2024년 교권보호5법, 2025년 학교민원 응답시스템을 추진 중이지만,
**민원이 학교에 도달하기 전 단계의 AI 필터링은 없습니다.**

본 시스템은 학부모-학교 사이에 **AI 게이트웨이**를 두어:

| 단계 | 누가 | 무엇을 |
|---|---|---|
| 1 | 학부모 | 게이트웨이에 민원 입력 |
| 2 | AI | 분류 (정당/모호/악성 위험) + 위험도 점수 |
| 3 | AI | 유사 과거 사례 검색 (RAG) |
| 4 | 학부모 | 자가 점검 후 진행 여부 결정 |
| 5 | AI | 진행 시 학교용 분석 리포트 자동 생성 |
| 6 | 학교 | 리포트 기반 차분한 대응 |

→ **교사 보호 + 학부모 만족 + 교권 침해 사전 예방**

## 📊 활용 교육 공공데이터

| # | 데이터셋 | 출처 | 용도 |
|---|---|---|---|
| 1 | 교육부 교권보호위원회 개최 현황 | data.go.kr 15137983 | 시도별 추이 + 정책 효과 측정 |
| 2 | NEIS 학원교습소정보 (138,259건) | open.neis.go.kr | 학교 인근 학원 환경 변수 |
| 3 | KOSIS 사교육비조사 17년 시계열 | kosis.kr DT_1PE105 | 사교육 격차 ↔ 교권 침해 가설 검증 |

## 🤖 AI 모델 4종

1. **민원 분류기** — TF-IDF + cosine, 카테고리 11종
2. **유사 사례 RAG 검색** — 임베딩, Top-3 사례 + 판정 근거
3. **위험도 평가 + 리포트 생성기** — 룰베이스 + 템플릿
4. **시도별 5년 예측** — Holt-Winters 지수평활

## ✅ 기대효과
- 교사 1인당 악성 민원 노출 감소 → **교권 보호**
- 학부모의 충동적·과도한 민원 사전 자가 점검 → **건강한 학교·가정 관계**
- 교육청은 시도별 추이 모니터링 → **선제적 정책**
        """
    )
