"""학교 FAQ 매처 — 학부모 질문 → 학교 표준 답변 Top 3.

핵심 변경: 단순 필터링이 아닌 "답을 주는 도우미" 톤.
방식: 분류기와 동일 (TF-IDF char n-gram 2~4 + cosine).
"""
from pathlib import Path
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent.parent
FAQ_PATH = ROOT / "01_data" / "school_faq.json"
NOTICES_PATH = ROOT / "01_data" / "sample_school_notices.json"


def _load():
    with open(FAQ_PATH, encoding="utf-8") as f:
        faqs = json.load(f)
    items = [{"source": "FAQ", "category": x["category"], "id": x["id"],
              "q": x["q"], "a": x["a"], "link": x.get("link", "")} for x in faqs]
    # 가상 학교 공지·가정통신문·매뉴얼 함께 인덱싱
    if NOTICES_PATH.exists():
        with open(NOTICES_PATH, encoding="utf-8") as f:
            notices = json.load(f)
        for n in notices:
            items.append({"source": n["type"], "category": n["type"],
                          "id": n["id"], "q": n["title"], "a": n["body"],
                          "link": f"시연용 학교 샘플 · {n.get('date','')}"})
    return items


_faqs = _load()
_corpus = [f"{x['q']} {x['a']}" for x in _faqs]
_vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
_X = _vec.fit_transform(_corpus)


def find_faqs(text: str, top_k: int = 3, min_similarity: float = 0.18) -> list[dict]:
    """학부모 입력 → 가장 관련 있는 FAQ Top-k.

    min_similarity 미만은 제외 (관련 없는 매칭 방지).
    """
    q = _vec.transform([text])
    sims = cosine_similarity(q, _X)[0]
    top_idx = sims.argsort()[::-1][:top_k]
    out = []
    for i in top_idx:
        if sims[i] < min_similarity:
            continue
        f = _faqs[i]
        out.append({
            "id": f["id"],
            "source": f.get("source", "FAQ"),
            "category": f["category"],
            "similarity": float(sims[i]),
            "question": f["q"],
            "answer": f["a"],
            "link": f.get("link", ""),
        })
    return out


if __name__ == "__main__":
    tests = [
        "통학로에 신호등이 없어서 매일 위험합니다",
        "우리 아이가 알레르기가 있는데 급식이 걱정됩니다",
        "선생님께 감사 표현하고 싶은데 선물 드려도 되나요",
        "수학 점수가 너무 낮은데 채점이 잘못된 것 같습니다",
        "학원 정보 어디서 볼 수 있나요",
    ]
    for t in tests:
        print("=" * 70)
        print(f"Q: {t}")
        for r in find_faqs(t):
            print(f"  [{r['similarity']:.2f}] {r['category']} | {r['question']}")
            print(f"      → {r['answer'][:80]}…")
