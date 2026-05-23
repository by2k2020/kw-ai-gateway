"""AI 모델 1+2: 민원 분류기 + 유사 사례 검색 (RAG).

방식: 한국어 친화 TF-IDF (char n-gram 2~4) + cosine similarity.
   학습 데이터: 01_data/complaint_samples.json (30건)
   사용:
       result = classify("우리 아이가 ...")
       → category, top3 (유사 사례·점수)
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "01_data" / "complaint_samples.json"


def _load_samples():
    with open(SAMPLES, encoding="utf-8") as f:
        return json.load(f)


# Char n-gram 2~4: 한국어는 형태소 분석기 없이도 의외로 잘 작동
_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
_samples = _load_samples()
_texts = [s["text"] for s in _samples]
_X = _vectorizer.fit_transform(_texts)


def classify(text: str, top_k: int = 3):
    """입력 민원 → 카테고리 예측 + Top-k 유사 사례."""
    q = _vectorizer.transform([text])
    sims = cosine_similarity(q, _X)[0]
    top_idx = sims.argsort()[::-1][:top_k]

    # 카테고리 다수결 (가중치=유사도)
    cat_scores = {}
    for i in top_idx:
        c = _samples[i]["category"]
        cat_scores[c] = cat_scores.get(c, 0) + sims[i]
    predicted = max(cat_scores, key=cat_scores.get)

    # 위험도 계산 — 최고 매칭 신뢰도까지 고려해 false positive 방지
    top_sim = float(sims[top_idx[0]])
    top_cat = _samples[top_idx[0]]["category"]
    raw_risk = sum(s for c, s in cat_scores.items() if "악성" in c) / max(sum(cat_scores.values()), 1e-9)

    # 1) 최고 매칭이 약함 (< 0.30): 신뢰도 부족 → 위험도 깎음
    if top_sim < 0.30:
        risk = raw_risk * 0.4
    # 2) 최고 매칭이 정당 카테고리이고 강함 (>= 0.35): 위험도 거의 0
    elif "악성" not in top_cat and top_sim >= 0.35:
        risk = raw_risk * 0.2
    else:
        risk = raw_risk

    top_cases = [
        {
            "id": _samples[i]["id"],
            "similarity": float(sims[i]),
            "category": _samples[i]["category"],
            "urgency": _samples[i]["urgency"],
            "text": _samples[i]["text"][:200] + ("…" if len(_samples[i]["text"]) > 200 else ""),
            "verdict": _samples[i]["verdict"],
            "rationale": _samples[i]["rationale"],
        }
        for i in top_idx
    ]
    return {
        "predicted_category": predicted,
        "risk_score": float(risk),
        "top_cases": top_cases,
    }


def risk_to_label(risk: float) -> tuple[str, str]:
    """위험도 점수 → 라벨 + 권고."""
    if risk >= 0.65:
        return "🚫 악성 위험 — 교권침해 사례 매우 유사", "민원 제출 전 자가 점검을 강력 권장합니다."
    if risk >= 0.45:
        return "⚠️ 주의 — 표현·내용 검토 필요", "사실 확인·표현 다듬기 권장."
    return "✅ 정당한 민원으로 분류", "특별한 위험 신호 없음. 학교에 정식 제출 가능합니다."


if __name__ == "__main__":
    tests = [
        "선생님이 우리 아이한테 숙제 안 했다고 야단쳤다는데 사과 받고 싶어요",
        "통학로 횡단보도에 신호등이 없어서 매일 위험합니다 시청 요청 부탁드려요",
        "수학 선생님이 한 달째 결근 중인데 보충수업 계획이 어떻게 되나요",
        "선생님 인스타 보니 주말에 술 마시던데 우리 아이 가르치는 사람이 적절한가요",
    ]
    for t in tests:
        print("=" * 70)
        print("입력:", t)
        r = classify(t)
        label, recommend = risk_to_label(r["risk_score"])
        print(f"예측: {r['predicted_category']} | 위험도: {r['risk_score']:.2f}")
        print(f"  {label}\n  → {recommend}")
        print("유사 사례:")
        for c in r["top_cases"]:
            print(f"  [{c['similarity']:.2f}] {c['category']} | {c['verdict']}")
