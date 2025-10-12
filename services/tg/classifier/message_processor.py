import re
from typing import Dict, Any

from models import TelegramMessage

class FeatureExtractor:
    def __init__(self):
        self._offer_verbs = [
            r"сдаю", r"сдам", r"сдаётся", r"сдается",
            r"здаю", r"здам", r"здається",
            r"vermiete", r"zu vermieten",
            r"rent out", r"for rent", r"i am renting"
        ]
        self._apartment_words = [
            r"квартира", r"апартаменты", r"комната", r"жиль[оё]",
            r"кімната", r"житло",
            r"wohnung", r"zimmer",
            r"apartment", r"flat", r"house"
        ]
        self._search_words = [
            r"ищу", r"нужн[аяе]", r"шукаю", r"потрібн[аий]",
            r"кто сдаёт", r"кто здає",
            r"looking for", r"suche", r"gesucht"
        ]

        # компиляция regex
        self._offer_verbs_re = [re.compile(p, re.I) for p in self._offer_verbs]
        self._apartment_words_re = [re.compile(p, re.I) for p in self._apartment_words]
        self._search_words_re = [re.compile(p, re.I) for p in self._search_words]
        self._price_re = re.compile(r"(\d{2,6}\s?(грн|uah|€|eur|\$|usd)?(\s*/?(месяц|мес|місяць|monat|month))?)", re.I)
        self._phone_re = re.compile(r"(\+?\d[\d\-\s\(\)]{6,}\d)")
        self._question_re = re.compile(r"\?")

    def extract(self, message: TelegramMessage) -> Dict[str, Any]:
        text = message.text
        features = {
            "offer_verb": int(any(p.search(text) for p in self._offer_verbs_re)),
            "apart_word": int(any(p.search(text) for p in self._apartment_words_re)),
            "price": int(bool(self._price_re.search(text))),
            "phone": int(bool(self._phone_re.search(text))),
            "search_word": int(any(p.search(text) for p in self._search_words_re)),
            "question": int(bool(self._question_re.search(text))),
            "length": len(text)
        }
        return features