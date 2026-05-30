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
faq = _load("faq", ANALYSIS / "42_faq_matcher.py")
llm = _load("llm", ANALYSIS / "43_llm_answer.py")
sch = _load("sch", ANALYSIS / "44_school_data.py")
rag = _load("rag", ANALYSIS / "45_rag_classifier.py")


@st.cache_data(show_spinner=False, ttl=3600)
def cached_search_school(name: str):
    return sch.search_school(name, limit=10)


@st.cache_data(show_spinner=False, ttl=600)
def cached_schedule(school_dict_str: str, from_ymd: str, to_ymd: str):
    return sch.get_schedule(json.loads(school_dict_str), from_ymd, to_ymd)


@st.cache_data(show_spinner=False, ttl=600)
def cached_meal(school_dict_str: str, from_ymd: str, to_ymd: str):
    return sch.get_meal(json.loads(school_dict_str), from_ymd, to_ymd)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_rag(query: str) -> dict:
    return rag.smart_rag_answer(query)


@st.cache_data(show_spinner=False)
def cached_smart_answer(question: str) -> dict:
    return llm.smart_answer(question)

st.set_page_config(page_title="학교 민원 AI 게이트웨이",
                   page_icon="", layout="wide")

# 세션 상태 (학교 접수함)
if "inbox" not in st.session_state:
    st.session_state.inbox = []

# ===== Palantir-style 다크/시안 CSS 주입 =====
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700;800&display=swap');
.stApp { background: #0B1320; }
section[data-testid='stSidebar'] {
    background: #14264A !important;
    border-right: 1px solid #00B4D8;
}
section[data-testid='stSidebar'] * { color: rgba(255,255,255,0.85) !important; }
section[data-testid='stSidebar'] h1, section[data-testid='stSidebar'] h2,
section[data-testid='stSidebar'] h3 { color: #00B4D8 !important; font-family: 'JetBrains Mono', monospace !important; letter-spacing: 0.06em; font-weight: 700 !important; }
section[data-testid='stSidebar'] input, section[data-testid='stSidebar'] select {
    background: #0B1320 !important; color: white !important; border: 1px solid #00B4D8 !important;
}
.main h1, .main h2, .main h3 { color: #E2E8F0 !important; font-family: 'Inter', sans-serif; letter-spacing: -0.02em; }
.main p, .main li, .main label, .main span, .main div { color: #CBD5E0 !important; }
.main .stMarkdown strong { color: #00B4D8 !important; }
button[kind='primary'], button[data-testid='baseButton-primary'] {
    background: #00B4D8 !important; color: #0B1320 !important; border: none !important;
    font-family: 'JetBrains Mono', monospace; font-weight: 700; letter-spacing: 0.05em;
}
button[kind='secondary'] { background: #14264A !important; color: white !important; border: 1px solid #00B4D8 !important; }
textarea, input[type='text'] {
    background: #14264A !important; color: white !important; border: 1px solid #2D3748 !important;
    font-family: 'Inter', sans-serif;
}
[data-testid='stMetricValue'] { color: #00B4D8 !important; font-family: 'JetBrains Mono', monospace; }
[data-testid='stMetricLabel'] { color: rgba(255,255,255,0.6) !important; font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.1em; }
.stAlert { background: #14264A !important; border-left: 4px solid #00B4D8 !important; }
.stAlert * { color: white !important; }
hr { border-color: #2D3748 !important; }
[data-testid='stExpander'] { background: #14264A !important; border: 1px solid #2D3748 !important; }
[data-testid='stExpander'] * { color: white !important; }
.element-container, .stContainer { color: white; }
[data-testid='stRadio'] label { color: white !important; }
[data-testid='stRadio'] label p { color: rgba(255,255,255,0.85) !important; font-family: 'JetBrains Mono', monospace; font-size: 13px; letter-spacing: 0.04em; }
.stCaption { color: rgba(255,255,255,0.5) !important; font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: 0.08em; }
[data-testid='stSidebarNav'] { background: #14264A !important; }
</style>""", unsafe_allow_html=True)


# 사이드바
st.sidebar.title("SCHOOL COMPLAINT AI GATEWAY")
st.sidebar.markdown("**제8회 교육 공공데이터 AI활용대회**")
st.sidebar.markdown("일반 / AI 활용 아이디어 기획")
st.sidebar.markdown("---")
mode = st.sidebar.radio(
    "사용자 모드 선택",
    [
        "PARENT — AI 도우미",
        "SCHOOL — 접수 민원 분석",
        "EDU AUTHORITY — 시도 현황",
        "SYSTEM — 소개·데이터",
    ],
)
st.sidebar.markdown("---")
st.sidebar.markdown("### MY SCHOOL")
school_query = st.sidebar.text_input("학교명 검색", placeholder="예: 한빛초")
if school_query:
    schools = cached_search_school(school_query)
    if schools:
        opts = {f"{s['name']} ({s['sido']})": s for s in schools}
        chosen = st.sidebar.selectbox("학교 선택", list(opts.keys()))
        st.session_state.school = opts[chosen]
        st.sidebar.success(f"LINKED · {st.session_state.school['name']}")
    else:
        st.sidebar.warning("검색 결과 없음")
elif "school" in st.session_state:
    st.sidebar.info(f"현재: {st.session_state.school['name']}")

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
### 활용 교육 공공데이터
- **NEIS Open API (실시간)**: 학교정보·학사일정·급식
- 교육부 교권보호위원회 (data.go.kr 15137983)
- 교육부 2024 교육활동 침해 실태조사 (korea.kr 156688735)
- KOSIS 사교육비조사 (DT_1PE105)

### AI 모델
1. **학교 FAQ + 공지·통신문 통합 검색** (TF-IDF + cosine)
2. **Claude Haiku 4.5** 자연어 답변 생성
3. 민원 분류기 (정당/모호/악성)
4. 위험도 평가 + 학교용 리포트
"""
)

# =========================================================
# 1. 학부모 모드
# =========================================================
if mode.startswith("PARENT"):
    st.title("PARENT  ·  AI 도우미")
    st.markdown(
        "**무엇이 궁금하신가요?** 학교 표준 답변을 즉시 알려드리고, "
        "혹시 모를 **교권 침해 사례**도 함께 보여드립니다. "
        "정식 민원이 필요하면 그때 학교에 분석 리포트와 함께 전달합니다."
    )

    c1, c2 = st.columns([2, 1])
    with c1:
        complaint = st.text_area(
            "질문·요청·민원 내용을 자유롭게 작성해 주세요",
            height=180,
            placeholder="예: 통학로에 신호등이 없어 매일 위험합니다. / 우리 아이가 알레르기가 있어요. / 선생님께 감사 표현하고 싶습니다.",
        )
    with c2:
        parent_name = st.text_input("작성자 (선택)", value="익명")
        grade = st.selectbox("자녀 학년", ["미입력"] + [f"{x}" for x in
                                                  ["초1", "초2", "초3", "초4", "초5", "초6",
                                                   "중1", "중2", "중3", "고1", "고2", "고3"]])

    if st.button("ASK AI", type="primary", use_container_width=True):
        if not complaint.strip():
            st.error("내용을 입력해 주세요.")
        else:
            with st.spinner("의미 기반 사례 검색 + AI 분류·답변 생성 중..."):
                rag_res = cached_rag(complaint)
                # 학교 FAQ 별도 검색 (RAG와 별개로 표준 답변 박스)
                faqs = faq.find_faqs(complaint, top_k=3)
            st.session_state.last_rag = rag_res
            st.session_state.last_faqs = faqs

    if "last_rag" in st.session_state:
        rag_res = st.session_state.last_rag
        faqs = st.session_state.get("last_faqs", [])
        school = st.session_state.get("school")

        st.markdown("---")

        # ===== 우리 학교 실시간 정보 (학교 선택 시) =====
        if school:
            st.markdown(f"### 우리 학교: **{school['name']}** ({school['sido']})")
            from datetime import date, timedelta
            today = date.today()
            from_ymd = today.strftime("%Y%m%d")
            to_ymd = (today + timedelta(days=14)).strftime("%Y%m%d")
            colS1, colS2 = st.columns(2)
            with colS1:
                with st.expander("향후 2주 학사일정 (실시간)", expanded=False):
                    try:
                        events = cached_schedule(json.dumps(school), from_ymd, to_ymd)
                        if events:
                            for e in events[:10]:
                                st.caption(f"**{e['ymd']}** · {e['event']}")
                        else:
                            st.caption("일정 없음")
                    except Exception as ex:
                        st.caption(f"조회 실패: {ex}")
            with colS2:
                with st.expander("이번 주 급식 (실시간)", expanded=False):
                    try:
                        meals = cached_meal(json.dumps(school), from_ymd,
                                            (today + timedelta(days=5)).strftime("%Y%m%d"))
                        if meals:
                            for m in meals[:3]:
                                st.caption(f"**{m['ymd']} {m['type']}**\n\n{m['dishes'][:120]}")
                        else:
                            st.caption("급식 정보 없음")
                    except Exception as ex:
                        st.caption(f"조회 실패: {ex}")
            st.markdown("---")

        # ===== STEP 1: 답변 (RAG full-context LLM) =====
        smart = {
            "mode": "llm" if rag_res.get("answer") else "faq",
            "faqs": faqs,
            "llm": {
                "answer": rag_res.get("answer", ""),
                "model": "claude-haiku-4-5-20251001",
                "input_tokens": rag_res.get("in_tokens", 0),
                "output_tokens": rag_res.get("out_tokens", 0),
            },
        }
        mode = smart.get("mode", "faq")
        faqs = smart.get("faqs", [])
        llm_res = smart.get("llm")

        SRC_ICON = {"FAQ": "", "공지사항": "", "가정통신문": "",
                    "학교 운영 매뉴얼": ""}

        # ===== STEP 1: 학교 표준 답변 (FAQ 매칭 시) =====
        if faqs:
            st.markdown("## 학교의 표준 답변")
            st.caption("학교 FAQ·공지·가정통신문에서 강매칭 (관련도 0.30+)")
            for i, f in enumerate(faqs[:2], 1):
                src = f.get("source", "FAQ")
                icon = SRC_ICON.get(src, "")
                with st.container(border=True):
                    st.markdown(f"### {icon} [{src}] {f['question']}")
                    st.markdown(f"**답변**: {f['answer']}")
                    if f.get("link"):
                        st.markdown(f"****: {f['link']}")
                    st.caption(f"카테고리: {f['category']}  ·  관련도: {f['similarity']:.2f}")

        # ===== STEP 2: RAG 분류기 답변 =====
        if rag_res.get("error"):
            st.error(f"AI 답변 생성 실패: {rag_res['error']}")
        else:
            st.markdown("---")
            st.markdown("## AI 도우미 답변 (RAG)")
            st.caption(
                f"KR-SBERT 의미 검색 + Claude Haiku 분류·답변 통합  ·  "
                f"토큰 in {rag_res.get('input_tokens','-')} / out {rag_res.get('output_tokens','-')}"
            )
            with st.container(border=True):
                st.markdown(rag_res["answer"])

            with st.expander("AI가 참고한 유사 사례 Top 5 (의미 검색)"):
                for c in rag_res.get("top_cases", []):
                    st.markdown(f"**[{c['category']}]** (유사도 {c['similarity']:.2f})")
                    st.write(f"- 사례: {c['text']}")
                    st.write(f"- 판정: {c['verdict']}")
                    st.write(f"- 근거: {c['rationale']}")
                    st.markdown("---")

        # ===== STEP 3: 교권 침해 사전 점검 (RAG 결과 기반) =====
        if not rag_res.get("error"):
            st.markdown("---")
            st.markdown("## 교권 침해 사전 점검")
            st.caption("RAG 분류 결과 — AI가 의미·맥락을 함께 판단합니다.")

            risk = rag_res["risk_score"]
            category = rag_res["category"]
            is_high = "악성" in category and risk >= 0.5
            is_mid = "모호" in category or (("악성" in category) and risk < 0.5) or (0.3 <= risk < 0.5)
            color = "" if is_high else ("" if is_mid else "")
            k1, k2 = st.columns([1, 2])
            k1.metric("교권침해 위험도", f"{color} {risk:.2f} / 1.00")
            k2.metric("AI 분류", category)

            reasoning = rag_res.get("reasoning", "")
            if is_high:
                st.error(f"**악성 위험** — 교권 침해 가능성 높음\n\n**근거**: {reasoning}")
            elif is_mid:
                st.warning(f"WARNING · 검토 필요\n\n**근거**: {reasoning}")
            else:
                st.success(f"OK · 정당한 민원\n\n**근거**: {reasoning}")

        # ===== STEP 4: 진행 결정 =====
        st.markdown("---")
        st.markdown("### 이제 어떻게 하시겠습니까?")
        cc1, cc2, cc3, cc4 = st.columns(4)
        with cc1:
            if st.button("RESOLVED — 종료", use_container_width=True, type="primary"):
                st.session_state.pop("last_rag", None)
                st.session_state.pop("last_faqs", None)
                st.success("학교에 연락하지 않고 해결되어 모두에게 도움이 됐어요. ")
                st.balloons()
                st.stop()
        with cc2:
            if st.button("RESET", use_container_width=True):
                st.session_state.pop("last_rag", None)
                st.session_state.pop("last_faqs", None)
                st.rerun()
        with cc3:
            if st.button("CANCEL", use_container_width=True):
                st.session_state.pop("last_rag", None)
                st.session_state.pop("last_faqs", None)
                st.success("민원 제출을 취소했습니다. 신중한 판단 감사합니다.")
                st.rerun()
        with cc4:
            if st.button("SUBMIT (리포트 동봉)",
                         use_container_width=True, type="secondary"):
                # 학교 모드용 리포트 생성 (분류기 기반)
                report = rep.generate_report(complaint or "", parent_name, grade)
                report["rag"] = rag_res  # RAG 결과 첨부
                st.session_state.inbox.append(report)
                st.success(f"학교 접수함에 전달. 현재 {len(st.session_state.inbox)}건")

# =========================================================
# 2. 학교 모드
# =========================================================
elif mode.startswith("SCHOOL"):
    st.title("SCHOOL — 접수 민원 분석")
    st.markdown("학부모 게이트웨이로 접수된 민원과 AI 분석 리포트입니다.")

    if not st.session_state.inbox:
        st.info("아직 접수된 민원이 없습니다. '학부모 모드'에서 민원을 제출해 보세요. (시연용 샘플도 좋습니다)")
        if st.button("시연용 샘플 민원 3건 자동 생성"):
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

        if st.button("접수함 비우기"):
            st.session_state.inbox = []
            st.rerun()

# =========================================================
# 3. 교육청 모드
# =========================================================
elif mode.startswith("EDU"):
    st.title("교육청 — 교권 보호 현황 대시보드")
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
        st.markdown("### 정책 시사점")
        st.info(
            "- **보호자 가해 비중이 7%대에서 10.9%로 급증** (2024) — 시스템 도입 시급\n"
            "- **유치원·초등은 보호자 가해 30~100%** — 우리 시스템 핵심 타겟층\n"
            "- 보호자 가해 1위 = **'정당 교육활동 부당간섭' 20%** — 우리 게이트웨이가 직접 막을 수 있는 유형"
        )

# =========================================================
# 4. 시스템 소개
# =========================================================
else:
    st.title("ℹ학교 민원 AI 도우미 + 게이트웨이 — 시스템 소개")
    st.markdown(
        """
## 무엇을 푸는가
2023 서이초 사건 이후 교사는 악성 민원에 노출되고, 학부모는 어디에 어떻게 물어볼지 모릅니다.
교육부는 2024년 교권보호5법·2025년 학교민원시스템을 추진 중이지만, **민원 입수 단계의 AI는 없습니다.**

본 시스템은 학부모-학교 사이에 **AI 도우미 + 게이트웨이**를 두어:

| 단계 | 누가 | 무엇을 |
|---|---|---|
| 1 | 학부모 | 게이트웨이에 질문·요청 입력 |
| 2 | AI | **학교 표준 답변(FAQ) 즉시 제공** ← 메인 기능 |
| 3 | 학부모 | "해결됨" 자체 종료 OR "정식 민원 검토" 선택 |
| 4 | AI | 정식 민원 검토 시: 분류 + 유사 사례 + 위험도 |
| 5 | 학부모 | 자가 점검 후 제출 결정 |
| 6 | AI | 제출 시 학교용 분석 리포트 자동 생성 |
| 7 | 학교 | 리포트 기반 차분한 대응 |

→ **학부모 정보 만족 + 충동 민원 자체 종료 + 교사 보호 + 진짜 민원만 학교 도달**

## 활용 교육 공공데이터

| # | 데이터셋 | 출처 | 용도 |
|---|---|---|---|
| 1 | 교육부 교권보호위원회 개최 현황 | data.go.kr 15137983 | 시계열 + 정책 효과 측정 |
| 2 | 교육부 2024 교육활동 침해 실태조사 | korea.kr 156688735 | 학교급·유형·가해주체별 진본 |
| 3 | NEIS 학원교습소정보 (138,259건) | open.neis.go.kr | 학교 인근 환경 변수 |
| 4 | KOSIS 사교육비조사 (2009~2025) | kosis.kr DT_1PE105 | 학습 부담 ↔ 민원 발생 가설 |

## AI 모델 4종

1. **학교 FAQ 매처** — TF-IDF + cosine, 30개 FAQ에서 Top 3 즉시 답변
2. **민원 분류기** — 카테고리 11종 (정당/모호/악성)
3. **유사 사례 RAG 검색** — 30건 사례 라이브러리, Top 3 + 판정·근거
4. **위험도 평가 + 리포트 생성** — 룰 + 템플릿, 학교 단계별 권장 절차

## 기대 효과

| 사용자 | 효과 |
|---|---|
| 학부모 | "내 질문에 즉시 답을 주는 도우미" — 정보 만족 + 학교 방문 부담 ↓ |
| 교사 | 악성 민원 직접 노출 ↓ + 정당한 민원만 분석 리포트와 함께 도달 |
| 학교장 | 리포트 기반 사전 검토 + 표준 대응 절차 자동 안내 |
| 교육청 | 시도별 추이 모니터링 + 정책 효과 측정 |
        """
    )
