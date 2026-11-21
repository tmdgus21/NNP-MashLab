"""Account display-name generator: adjective + food + 3-digit number."""
from __future__ import annotations

import secrets

ADJECTIVES: tuple[str, ...] = (
    "행복한",
    "졸린",
    "용감한",
    "신나는",
    "귀여운",
    "차분한",
    "씩씩한",
    "포근한",
    "반짝이는",
    "상큼한",
    "든든한",
    "느긋한",
    "재빠른",
    "따뜻한",
    "시원한",
    "고소한",
    "달콤한",
    "싱싱한",
    "꼼꼼한",
    "유쾌한",
    "다정한",
    "현명한",
    "명랑한",
    "성실한",
    "활기찬",
    "고요한",
    "튼튼한",
    "산뜻한",
    "향긋한",
    "정직한",
    "친절한",
    "겸손한",
    "솔직한",
    "야무진",
    "반가운",
    "소중한",
    "즐거운",
    "평화로운",
    "호기심많은",
    "겸손한",
    "맑은",
    "밝은",
    "고운",
    "단단한",
    "가벼운",
    "느린",
    "빠른",
    "깊은",
    "넓은",
    "작은",
    "큰",
)

FOODS: tuple[str, ...] = (
    "감자",
    "고구마",
    "만두",
    "푸딩",
    "김밥",
    "떡볶이",
    "라면",
    "비빔밥",
    "호빵",
    "붕어빵",
    "찐빵",
    "호떡",
    "팥죽",
    "식혜",
    "수정과",
    "두부",
    "순두부",
    "된장찌개",
    "김치찌개",
    "계란말이",
    "계란밥",
    "주먹밥",
    "유부초밥",
    "초밥",
    "우동",
    "소바",
    "칼국수",
    "수제비",
    "잔치국수",
    "냉면",
    "쫄면",
    "만두국",
    "떡국",
    "미역국",
    "콩나물국",
    "어묵",
    "오뎅",
    "핫도그",
    "토스트",
    "샌드위치",
    "샐러드",
    "요거트",
    "치즈",
    "버터",
    "크루아상",
    "베이글",
    "도넛",
    "마카롱",
    "케이크",
    "쿠키",
    "젤리",
    "아이스크림",
)

assert len(ADJECTIVES) >= 50
assert len(FOODS) >= 50


def generate_nickname() -> str:
    """Return adjective+food+100..999, always ≤30 UTF-8 characters."""
    for _ in range(32):
        adjective = secrets.choice(ADJECTIVES)
        food = secrets.choice(FOODS)
        number = secrets.randbelow(900) + 100
        name = f"{adjective}{food}{number}"
        if len(name) <= 30:
            return name
    # Extremely unlikely fallback within length limit.
    return f"감자{secrets.randbelow(900) + 100}"
