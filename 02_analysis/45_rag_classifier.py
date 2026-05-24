"""AI 모델 6 — Full-context LLM 분류기 (RAG 패턴, 임베딩 단계 제거).

설계 결정 (2026-05-24):
  - sentence-transformers 임베딩 단계 제거 (cold start 14분 문제)
  - 대신 가상 민원 60건 전체를 Claude Haiku 200K context로 전달
  - 정확도 ↑ (모든 사례 봄) + 빠름 (3~5초) + Streamlit Cloud 호환

흐름:
  1. 가상 민원 60건 + 학부모 입력을 Claude Haiku에 전달
  2. Claude가 JSON 출력: {answer, category, risk_score, reasoning, similar_ids}
  3. similar_ids로 Top-5 사례 후처리 표시
"""
from pathlib import Path
import os
import json
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "01_data" / "complaint_samples.json"

_samples = None


def _load_samples():
    global _samples
    if _samples is None:
        with open(SAMPLES, encoding="utf-8") as f:
            _samples = json.load(f)
    return _samples


PROMPT_SYS = """당신은 한국 초·중·고 학교 민원을 분석하는 AI입니다.

학부모 입력 + 라벨링된 가상 사례 60건을 보고 다음을 JSON으로 한 번에 출력하세요:

1. **answer**: 학부모용 친절·간결한 답변 (3~5문장). 학교 표준 절차·법령 근거 안내.
2. **category**: 분류
   - "정당 (안전·학습권·학교폭력·시설·정보·건강·다양성·학사참여 등 세부)"
   - "모호 (대화 권장)"
   - "악성 위험 (부당 간섭/업무 부담/반복·집요/사적 영역/감시/시간 외/무고·신고 위협/단체 동원/신체 위협/성적·평가 침해 등 세부)"
3. **risk_score**: 0.0(정당) ~ 1.0(악성 매우 위험)
4. **reasoning**: 분류 근거 (한국어 비공식 표현 해석 + 진본 패턴 참조)
5. **similar_ids**: 가장 유사한 가상 사례 id 3개 (리스트)

⚠️ 한국어 비공식 표현 해석 — 매우 중요:
- "기를 죽인다 / 차갑게 대한다 / 차별한다 / 째려본다 / 혼낸다 / 야단친다" 류:
  → **정당한 교육활동에 대한 학부모 부정적 해석 = 진본 2024 실태조사 보호자 가해 1위 패턴 '정당 교육활동 부당간섭 24.4%'**
  → 구체 사실이 부족해도 **최소 위험도 0.5 + "주의 (부당간섭 의심)" 또는 "악성 위험 (부당 간섭)" 분류**
  → "학교폭력예방법" 인용 절대 금지 (학폭과 다른 영역)
  → 답변: "구체 사실 확인 + 담임 면담 1차" + "유사 표현은 교권보호위 사례 다수, 신중한 표현 권장"

- "사진 매끼 보내라 / 매일 통화 / 정보공개 청구 / 화장실 횟수":
  → 명백한 업무 부담·사적 영역 침해. risk 0.7+.

- "재시험 / 출결 정정 / 생기부 수정":
  → 평가 자율성 침해. risk 0.6+.

- "선생님 책상에 꽃 / 감사 표현 선물":
  → 청탁금지법 안내, risk 0.1~0.2 (정당 안내 케이스).

- "체험학습 / 공개수업 / 학사일정 / 급식 안내" 정보 요청:
  → 정당, risk 0.0~0.2.

답변 원칙:
- 교사의 정당 교육활동·생활지도·평가 존중
- 학부모 권리도 존중 — 정보 요청·안전 신고 등은 적극 안내
- 즉시 처벌·해임·신고 권유 금지
- 가상 사례에 없어도 일반 지식으로 답변

⚠️ 출력 형식 — 반드시 JSON 외 다른 텍스트 없이:
{"answer": "...", "category": "...", "risk_score": 0.X, "reasoning": "...", "similar_ids": [N, N, N]}
"""


def _build_user_prompt(query: str) -> str:
    samples = _load_samples()
    parts = [f"학부모 입력:\n\"{query}\"\n\n=== 라벨링된 가상 사례 {len(samples)}건 ==="]
    for s in samples:
        parts.append(
            f"\n[id={s['id']}] [{s['category']}]\n"
            f"  사례: \"{s['text']}\"\n"
            f"  판정: {s['verdict']}\n"
            f"  근거: {s['rationale']}"
        )
    parts.append("\n\n위 사례 참조 + 비공식 표현 해석 가이드 적용해 JSON으로 출력하세요.")
    return "\n".join(parts)


def smart_rag_answer(query: str, model: str = "claude-haiku-4-5-20251001",
                     max_tokens: int = 1000) -> dict:
    """Full-context LLM: 가상 사례 60건 전체 + 학부모 입력 → JSON 출력."""
    if not _KEY:
        return {"error": "ANTHROPIC_API_KEY 미설정", "mode": "fail"}

    try:
        from anthropic import Anthropic
    except ImportError:
        return {"error": "anthropic 미설치", "mode": "fail"}

    samples = _load_samples()
    sample_by_id = {s["id"]: s for s in samples}

    client = Anthropic(api_key=_KEY)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=PROMPT_SYS,
        messages=[{"role": "user", "content": _build_user_prompt(query)}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()

    # JSON 파싱 (마크다운 코드블록도 처리)
    json_text = raw
    if "```" in raw:
        json_text = raw.split("```")[1].lstrip("json").strip()
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return {
            "error": f"JSON 파싱 실패",
            "mode": "fail",
            "raw": raw[:500],
        }

    # similar_ids → 사례 객체 후처리
    similar_ids = parsed.get("similar_ids", []) or []
    top_cases = []
    for sid in similar_ids[:5]:
        s = sample_by_id.get(int(sid)) if str(sid).isdigit() else None
        if s:
            top_cases.append({
                "id": s["id"],
                "category": s["category"],
                "urgency": s["urgency"],
                "text": s["text"],
                "verdict": s["verdict"],
                "rationale": s["rationale"],
                "similarity": None,  # LLM 선택이라 점수 없음
            })

    return {
        "mode": "rag",
        "answer": parsed.get("answer", ""),
        "category": parsed.get("category", "분류 실패"),
        "risk_score": float(parsed.get("risk_score", 0)),
        "reasoning": parsed.get("reasoning", ""),
        "top_cases": top_cases,
        "model": model,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }


if __name__ == "__main__":
    tests = [
        "선생님이 우리 아이 기를 죽여요",
        "선생님이 우리 아이만 안 시키는 것 같아요 차별이에요",
        "통학로 신호등 없어서 위험합니다",
        "점심 식판 사진 매끼 찍어주세요",
        "운동회는 언제예요",
        "선생님 결혼하셨어요 자녀는 몇 살이세요",
        "아이가 더워해서 에어컨 옆자리로 옮겨주세요",
        "이번 학기에만 12번째 민원입니다",
        "선생님 책상에 꽃 한 송이 놓아도 될까요",
    ]
    import time
    for t in tests:
        t0 = time.time()
        r = smart_rag_answer(t)
        dt = time.time() - t0
        if r.get("error"):
            print(f"❌ {t} → {r['error']}")
            continue
        print(f"[{dt:.1f}s] risk={r['risk_score']:.2f} | {r['category'][:30]:<30} | {t}")
