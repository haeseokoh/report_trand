from kiwipiepy import Kiwi
from collections import Counter
import re
from typing import List, Tuple, Dict
from db.database import get_unprocessed_reports, save_report_keywords

# Kiwi 싱글톤 인스턴스 초기화
kiwi = Kiwi(num_workers=2)

# 사용자 정의 금융/테크 고유명사 사전 추가 (분석 정확도 향상)
CUSTOM_WORDS = [
    ("온디바이스", "NNP"),
    ("온디바이스AI", "NNP"),
    ("HBM", "SL"),
    ("CXL", "SL"),
    ("생성형AI", "NNP"),
    ("유리기판", "NNG"),
    ("전력망", "NNG"),
    ("변압기", "NNG"),
    ("피크아웃", "NNG"),
    ("턴어라운드", "NNG"),
    ("파운드리", "NNG"),
    ("피어그룹", "NNG"),
    ("밸류에이션", "NNG"),
    ("멀티플", "NNG"),
    ("컨센서스", "NNG"),
    ("가이던스", "NNG"),
    ("모멘텀", "NNG"),
    ("어닝서프라이즈", "NNG"),
    ("레거시", "NNG"),
    ("CAPEX", "SL"),
    ("OPEX", "SL"),
]

for word, tag in CUSTOM_WORDS:
    try:
        kiwi.add_user_word(word, tag)
    except Exception:
        pass

# 금융 리포트 노이즈/불용어 목록 (트렌드 분석 시 의미 없는 빈출어)
STOPWORDS = {
    "리포트", "투자의견", "목표주가", "매수", "매도", "유지", "상향", "하향", "중립",
    "분기", "전년", "동기", "대비", "기록", "전망", "가능", "관련", "기준", "원",
    "증권", "연구원", "애널리스트", "컴퍼니", "투자", "예상", "판단", "실적", "영업이익",
    "매출액", "당기순이익", "증가", "감소", "전년동기", "전분기", "수준", "지속", "확대",
    "부문", "사업", "회사", "시장", "효과", "영향", "상황", "성장", "개선", "부진",
    "억원", "조원", "만원", "달러", "퍼센트", "포인트", "비중", "규모", "이유", "목표",
    "현재", "향후", "최근", "올해", "내년", "상반기", "하반기", "연간", "월", "일", "년",
    "주가", "종목", "기업", "국내", "글로벌", "미국", "중국", "한국", "주요", "가능성",
    "컨센서스", "가이던스", "자료", "출처", "통해", "대한", "따른", "위한", "포함",
    "대비", "상대적", "추정", "반영", "결과", "기대", "우려", "요인", "추이", "흐름",
    "그림", "당사", "리서치", "BUY", "HOLD", "SELL", "표", "도표", "페이지", "센터",
    "개요", "요약", "본문", "참고", "유안타", "하나", "한화", "신한", "키움", "미래에셋",
    "메리츠", "삼성", "KB", "NH", "IBK", "대신", "한국투자", "메리츠증권", "유안타증권",
    "정보", "제공", "확인", "작성", "기준일", "변동", "발생", "진행", "발표", "예정"
}

def extract_keywords_from_text(text: str, top_n: int = 50) -> List[Tuple[str, int]]:
    """본문에서 의미 있는 명사 및 전문용어(SL) 추출 및 빈도 계산"""
    if not text or len(text) < 30:
        return []
        
    tokens = kiwi.tokenize(text)
    keywords = []
    
    for token in tokens:
        # NNG(일반명사), NNP(고유명사), SL(외국어/알파벳 약어)
        if token.tag in ('NNG', 'NNP', 'SL'):
            word = token.form.strip()
            
            # 영문의 경우 대문자로 표준화 (예: hbm -> HBM, ai -> AI)
            if token.tag == 'SL':
                word = word.upper()
                
            # 길이 필터링 (1글자 한글 제외, 단 영문 2글자 이상은 허용)
            if len(word) < 2 and not (token.tag == 'SL' and len(word) >= 2):
                continue
                
            # 숫자만 있는 경우 제외
            if word.isdigit():
                continue
                
            # 불용어 제외
            if word in STOPWORDS:
                continue
                
            keywords.append(word)
            
    counter = Counter(keywords)
    return counter.most_common(top_n)

def extract_nouns_as_token_list(text: str) -> List[str]:
    """TF-IDF 등 벡터화를 위한 토큰 리스트 반환"""
    if not text or len(text) < 30:
        return []
        
    tokens = kiwi.tokenize(text)
    keywords = []
    
    for token in tokens:
        if token.tag in ('NNG', 'NNP', 'SL'):
            word = token.form.strip()
            if token.tag == 'SL':
                word = word.upper()
            if len(word) >= 2 and not word.isdigit() and word not in STOPWORDS:
                keywords.append(word)
                
    return keywords

def update_keywords_for_report(report_id: int, text: str):
    """단일 리포트에 대한 키워드 추출 및 DB 저장"""
    keywords = extract_keywords_from_text(text, top_n=50)
    if keywords:
        save_report_keywords(report_id, keywords)
