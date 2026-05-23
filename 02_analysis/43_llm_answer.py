"""AI 모델 5 — Claude로 학부모 질문 자연어 답변 생성.

흐름:
  1. FAQ 매처 (42)로 우선 매칭 시도
  2. 강한 매칭 있으면 그대로 사용 (LLM 호출 X, 비용·지연 절감)
  3. 약하거나 없으면 Claude API로 답변 생성 (FAQ Top 3을 컨텍스트로 제공)

비용 통제:
  - haiku-4-5 사용 (가장 저렴 + 빠름)
  - max_tokens 600
  - streamlit cache 활용
"""
from pathlib import Path
import os
import json
import importlib.util
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

# 42 매처 동적 import
_spec = importlib.util.spec_from_file_location("faq", Path(__file__).parent / "42_faq_matcher.py")
_faq_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_faq_mod)

SYSTEM = """당신은 한국 초중고 학부모를 돕는 친절한 학교 안내 도우미입니다.

원칙:
1. 학부모 질문에 학교 운영 매뉴얼·법령·표준 절차 기반으로 답변
2. 교사의 정당한 교육활동·생활지도·평가는 존중 — 무리한 요구는 정중히 안내
3. 답변은 3~5문장으로 간결하게, 다음 행동을 명확히 (누구에게 어떻게 신청)
4. 근거 법령·매뉴얼이 있으면 한 줄로 인용
5. 학교의 결정 권한과 학부모의 권리 모두 존중
6. 모르면 모른다고 정직하게 (담임/행정실/교육청 안내)

피해야 할 것:
- 교사 개인 비난이나 평가
- 즉시 처벌·해임 등 강요성 표현
- 과장된 약속

답변 형식 (자유):
- 핵심 답변 한 단락 + 다음 행동 (어디로 신청/문의)
"""


def _build_user_prompt(question: str, faqs: list[dict]) -> str:
    parts = [f"학부모 질문:\n{question}\n"]
    if faqs:
        parts.append("\n참고할 학교 표준 FAQ (관련도 순):")
        for i, f in enumerate(faqs, 1):
            parts.append(f"\n{i}. [{f['category']}] {f['question']}")
            parts.append(f"   답변: {f['answer']}")
            if f.get("link"):
                parts.append(f"   안내: {f['link']}")
    parts.append("\n\n위 FAQ가 직접 일치하지 않으면 학부모 질문에 맞춰 새로운 답변을 작성하세요. "
                 "FAQ가 일치하면 그 내용을 자연스럽게 정리해도 됩니다.")
    return "\n".join(parts)


def llm_answer(question: str, faqs: list[dict] | None = None,
               model: str = "claude-haiku-4-5-20251001",
               max_tokens: int = 600) -> dict:
    """Claude로 답변 생성. 반환: {answer, model, used_faqs}."""
    if not _KEY:
        return {"answer": None, "error": "ANTHROPIC_API_KEY 미설정",
                "model": None, "used_faqs": []}
    try:
        from anthropic import Anthropic
    except ImportError:
        return {"answer": None, "error": "anthropic 패키지 미설치",
                "model": None, "used_faqs": []}

    if faqs is None:
        faqs = _faq_mod.find_faqs(question, top_k=3, min_similarity=0.10)

    client = Anthropic(api_key=_KEY)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM,
        messages=[{"role": "user", "content": _build_user_prompt(question, faqs)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return {
        "answer": text,
        "model": model,
        "used_faqs": [f["id"] for f in faqs],
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }


def smart_answer(question: str, strong_threshold: float = 0.30) -> dict:
    """FAQ 매칭 강하면 그대로, 약/없으면 Claude 호출.

    반환:
      {mode: 'faq' | 'llm' | 'llm_with_faq',
       faqs: [...],
       llm: {answer, ...} or None}
    """
    faqs_all = _faq_mod.find_faqs(question, top_k=3, min_similarity=0.10)
    strong = [f for f in faqs_all if f["similarity"] >= strong_threshold]

    if strong:
        return {"mode": "faq", "faqs": strong, "llm": None}

    # 약한 매칭 또는 무매칭 → LLM 호출
    llm = llm_answer(question, faqs=faqs_all)
    mode = "llm_with_faq" if faqs_all else "llm"
    return {"mode": mode, "faqs": faqs_all, "llm": llm}


if __name__ == "__main__":
    tests = [
        "통학로에 신호등이 없어서 매일 위험합니다",  # FAQ 강매칭
        "아이가 학교에서 멍해 보입니다 무슨 일이 있는지 알고 싶어요",  # FAQ 약
        "선생님 책상 위에 꽃 한 송이 놓고 싶은데 괜찮나요",  # FAQ 무
    ]
    for t in tests:
        print("=" * 70)
        print("Q:", t)
        r = smart_answer(t)
        print(f"  mode: {r['mode']}, FAQ {len(r['faqs'])}건")
        if r["llm"]:
            print(f"  [LLM 답변]\n  {r['llm']['answer'][:300]}")
            print(f"  (tokens in={r['llm'].get('input_tokens')}, out={r['llm'].get('output_tokens')})")
        elif r["faqs"]:
            print(f"  [FAQ 답변] {r['faqs'][0]['question']}")
