"""AI 모델 3 — 학교용 분석 리포트 생성기.

입력: 학부모 민원 텍스트
출력: 학교(교사·교감·교장)용 구조화된 마크다운 리포트
방식: 분류 결과 + 유사 사례 + 규칙 기반 템플릿
"""
from pathlib import Path
import sys
from datetime import datetime
import importlib.util

# 40_classifier_rag.py 동적 import (파일명이 숫자 시작이라)
_spec = importlib.util.spec_from_file_location(
    "clf", Path(__file__).parent / "40_classifier_rag.py")
_clf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_clf)


URGENCY_PRIORITY = {"긴급": 0, "보통": 1, "낮음": 2}


def generate_report(complaint_text: str, parent_name: str = "익명",
                    student_grade: str = "미입력") -> dict:
    result = _clf.classify(complaint_text, top_k=3)
    risk = result["risk_score"]
    label, recommend = _clf.risk_to_label(risk)

    urgencies = [c["urgency"] for c in result["top_cases"]]
    urgency = min(urgencies, key=lambda u: URGENCY_PRIORITY.get(u, 9))

    if risk >= 0.6:
        proc = [
            "학교장·교감 우선 검토 (즉시 처리 X)",
            "교권보호위원회 회부 여부 사전 협의",
            "교사 단독 응대 금지, 복수 입회 권장",
            "응대 기록·녹취 (학부모에게 사전 고지)",
        ]
    elif risk >= 0.3:
        proc = [
            "1차 담임 + 보호자 면담 (학교 내 공식 공간)",
            "면담 기록 작성·보존",
            "필요 시 상담교사 동석",
        ]
    else:
        proc = [
            "관할 담당자(담임/보건/시설 등) 정상 처리",
            "처리 결과를 학부모에게 회신",
            "유사 민원 누적 시 매뉴얼 업데이트",
        ]

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "parent": parent_name,
        "student_grade": student_grade,
        "complaint_text": complaint_text,
        "predicted_category": result["predicted_category"],
        "risk_score": risk,
        "risk_label": label,
        "urgency": urgency,
        "recommend_self_check": recommend,
        "similar_cases": result["top_cases"],
        "school_procedure": proc,
    }


def report_to_markdown(report: dict) -> str:
    md = []
    md.append("# 📋 민원 분석 리포트")
    md.append(f"- **생성일시**: {report['generated_at']}")
    md.append(f"- **민원인**: {report['parent']}  (자녀 학년: {report['student_grade']})")
    md.append("")
    md.append("## 🔎 AI 분류 결과")
    md.append(f"- **카테고리**: {report['predicted_category']}")
    md.append(f"- **위험도 점수**: `{report['risk_score']:.2f}` / 1.00")
    md.append(f"- **판정**: {report['risk_label']}")
    md.append(f"- **긴급도**: {report['urgency']}")
    md.append("")
    md.append("## 📜 민원 원문")
    md.append("> " + report["complaint_text"].replace("\n", "\n> "))
    md.append("")
    md.append("## 📚 유사 과거 사례 (Top 3)")
    for i, c in enumerate(report["similar_cases"], 1):
        md.append(f"### {i}. {c['category']} (유사도 {c['similarity']:.2f})")
        md.append(f"- 사례: {c['text']}")
        md.append(f"- 판정: {c['verdict']}")
        md.append(f"- 근거: {c['rationale']}")
        md.append("")
    md.append("## ✅ 권장 대응 절차")
    for i, p in enumerate(report["school_procedure"], 1):
        md.append(f"{i}. {p}")
    md.append("")
    md.append("---")
    md.append("*본 리포트는 AI 분석 결과로, 최종 대응 판단은 학교의 권한입니다.*")
    return "\n".join(md)


if __name__ == "__main__":
    samples = [
        "선생님이 우리 아이한테 숙제 안 했다고 야단쳤다는데 사과 받고 싶어요.",
        "통학로에 신호등이 없어서 매일 위험합니다.",
    ]
    for s in samples:
        r = generate_report(s, parent_name="홍길동", student_grade="초3")
        print(report_to_markdown(r))
        print("\n" + "=" * 70 + "\n")
