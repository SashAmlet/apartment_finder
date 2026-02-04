import re
from typing import Dict

class FeatureExtractor:
    def __init__(self):
        # ==========================================
        # 1. ГЛАГОЛЫ СДАЧИ (OFFER)
        # ==========================================
        # Логика: Корни слов, покрывающие: сдаю, сдам, сдается, освобождается, заезд, предлагаю...
        self._offer_verbs = [
            # RU: сдам, сдаю, сдает(ся), сдаст, освободилась, заезд, сдача, предлагаю, доступна
            r"сда[мютш]|сда[её]т|освобожд|освободи|заезд|сдач|предлаг|доступн|свободн",
            # UA: здам, здаю, здається, звільнилась, заїзд, пропоную, вільна
            r"зда[мю]|зда[еє]т|звільн|заїзд|пропон|доступн|вільн",
            # DE: vermiete, zu vermieten, frei, verfügbar, bezug, einzug, biete, anbieten
            r"vermiet|frei|verfügbar|bezug|einzug|biet|anbiet|nachmieter",
            # EN: rent, lease, available, move in, offer, sublet
            r"rent|leas|avail|move|offer|sublet|vacan"
        ]

        # ==========================================
        # 2. ОБЪЕКТ ЖИЛЬЯ (APARTMENT)
        # ==========================================
        # Логика: Квартиры, комнаты, дома, этажи, апартаменты...
        self._apartment_words = [
            # RU: квартир, комнат, жиль(е/ё), апартамент, дом, студи, этаж, двушк, однушк, трешк, помещени
            r"квартир|комнат|жиль|апартамент|дом|студи|этаж|однушк|двушк|трешк|помещени|кв\.|м2",
            # UA: квартир, кімнат, житл, апартамент, будин, осел, помешкан, поверх
            r"квартир|кімнат|житл|апартамент|будин|осел|помешкан|поверх|хат",
            # DE: wohnung, zimmer, haus, apartment, wg, unterkunft, raum, dachgeschoss, erdgeschoss
            r"wohnung|zimmer|app?art|haus|unterkunft|wg|raum|geschoss|heim",
            # EN: apartment, flat, room, house, studio, accommodation, floor
            r"apart|flat|room|hous|studio|accom|floor|residen"
        ]

        # ==========================================
        # 3. ПОИСК (SEARCH) - Negative Feature
        # ==========================================
        # Логика: Ищу, сниму, нужно, требуется...
        self._search_words = [
            # RU: ищу, ищем, сниму, нужен, нужна, поиск, найти, кто сдает, интересует, семья из
            r"ищ[уем]|сним[уа]|нуж[ен]|поиск|найт|кто\s*сда[её]|интересу|семья\s*из|пар[ае]\s*из",
            # UA: шукаю, винайму, орендую, потрібно, хто здає, цікавить
            r"шука|винайм|оренд|потріб|хто\s*зда[єе]|цікав|сім.?я\s*з|знайт",
            # DE: suche, gesucht, brauche, wer vermietet, interesse
            r"such|gesucht|brauch|benötig|wer\s*vermietet|interess",
            # EN: looking for, search, need, want, seek
            r"look|search|need|want|seek|find"
        ]

        # ==========================================
        # 4. ВРЕМЕННО / ПОСУТОЧНО (TEMPORARY) - Negative Feature
        # ==========================================
        self._temporary_patterns = [
            # RU: посуточно, на сутки, временно, короткий срок, на месяц, на неделю, до (даты), пока
            r"посуточн|на\s*сутк|временн|коротк|на\s*месяц|на\s*недел|ноч|свободна\s*до|даты|пока",
            # UA: подобово, на добу, тимчасово, короткий термін, на місяць
            r"подобов|на\s*доб|тимчасов|коротк|на\s*місяц|тижд|ніч",
            # DE: zwischenmiete, untermiete, befristet, kurzzeit, bis (datum), monat, woche
            r"zwischen|untermiet|befrist|kurz|bis\s*\d|zeitraum|monat|woche",
            # EN: short term, temporary, daily, until, sublet
            r"short|temp|daily|until|sublet|month|week|night"
        ]

        # ==========================================
        # 5. БЕСПЛАТНО / ХОСТЫ / ПОМОЩЬ (HOST/FREE) - Negative Feature
        # ==========================================
        self._host_family_patterns = [
            # RU: бесплатно, помощь, приму, подселение, койка, диван, беженцы
            r"бесплатн|помощ|прим[уе]|подселен|койк|диван|спасн|мест[оа]|бежен",
            # UA: безкоштовно, допомога, прийму, підселення, ліжко, біжен
            r"безкоштов|дарма|допомог|прийм|підселен|ліжк|диван|місц|біжен",
            # DE: kostenlos, gratis, hilfe, gastfamilie, couch, schlafplatz, ukraine
            r"kostenlos|gratis|hilfe|gast|couch|schlafplatz|spende|ukraine",
            # EN: free, help, host, couch, refugee, donate, bed
            r"free|help|host|couch|refuge|donat|bed"
        ]

        # ==========================================
        # 6. КОММЕРЦИЯ / ОФИСЫ / ИВЕНТЫ (COMMERCIAL) - Negative Feature
        # ==========================================
        self._commercial_patterns = [
            # RU: офис, гараж, склад, бизнес, семинар, маникюр, курс, вебинар
            r"офис|гараж|склад|бизнес|семинар|маникюр|курс|вебинар|урок|мастер",
            # UA: офіс, гараж, склад, бізнес, семінар, манікюр, подія
            r"офіс|гараж|склад|бізнес|семінар|манікюр|поді",
            # DE: büro, garage, lager, gewerbe, praxis, laden, workshop
            r"büro|garage|lager|gewerbe|praxis|laden|workshop|nagel|event",
            # EN: office, garage, warehouse, business, nail, course, workshop
            r"office|garage|warehous|business|nail|course|workshop|service"
        ]

        # ==========================================
        # 7. ОБЩЕЖИТИЯ / ЛАГЕРЯ (DORMS) - Negative Feature
        # ==========================================
        self._dorm_patterns = [
            # RU: общежитие, лагерь, хайм, центр прибытия, тегель
            r"общежит|лагер|центр|хайм|тегель|пункт",
            # UA: гуртожиток, табір, центр, шелтер
            r"гуртожит|табір|центр|шелтер",
            # DE: heim, lager, ankerzentrum, wohnheim, notunterkunft
            r"heim|lager|anker|tegel|notunterkunft|container",
            # EN: dorm, camp, shelter, center
            r"dorm|camp|shelter|center"
        ]

        # ==========================================
        # 8. ОБМЕН (SWAP) - Negative Feature
        # ==========================================
        self._swap_patterns = [
            r"обмен|мен[яя]|взамен", # RU
            r"обмін|міня|взамін",    # UA
            r"tausch",               # DE
            r"swap|exchange"         # EN
        ]

        # ==========================================
        # 9. РАБОТА (JOB) - Negative Feature
        # ==========================================
        self._job_patterns = [
            # RU: работа, вакансия, требуется, зарплата, сотрудник
            r"работ|ваканс|требу|зарплат|сотрудник|уборк|водитель|няня|сиделк",
            # UA: робота, вакансія, потрібні, платня
            r"робот|ваканс|потріб|платн|водій|прибиран",
            # DE: arbeit, job, stelle, mitarbeiter, reinigung, firma
            r"arbeit|job|stell|mitarbeiter|reinigung|firma|gesucht",
            # EN: work, job, vacancy, hiring, salary
            r"work|job|vacanc|hir|employ|clean|salary"
        ]

        # ==========================================
        # 10. JOBCENTER (POSITIVE BOOSTER)
        # ==========================================
        self._jobcenter_patterns = [
            # RU: джобцентр (и опечатки), социал, оплата городом
            r"джо[бп]|джо[бп]центр|социал|оплат.*город|город.*платит|документ",
            # UA: джобцентр, соціал
            r"джо[бп]|джо[бп]центр|соціал|оплат.*міст",
            # DE: jobcenter, amt, wbs, kostenübernahme, hartz, bürgergeld
            r"job|jobcenter|amt|wbs|kosten|übernahme|sozial|bürgergeld",
            # EN: jobcenter, social office
            r"job|jobcenter|social"
        ]

        # Компиляция REGEX
        # Мы объединяем 4 строки каждого языка в одну большую группу через join('|')
        # Это создает паттерн вида: (RU_patt)|(UA_patt)|(DE_patt)|(EN_patt)
        self._re_groups = {
            "offer_verb": [re.compile("|".join(self._offer_verbs), re.I)],
            "apart_word": [re.compile("|".join(self._apartment_words), re.I)],
            "search_word": [re.compile("|".join(self._search_words), re.I)],
            "is_temporary": [re.compile("|".join(self._temporary_patterns), re.I)],
            "is_host_family": [re.compile("|".join(self._host_family_patterns), re.I)],
            "is_commercial": [re.compile("|".join(self._commercial_patterns), re.I)],
            "is_dorm": [re.compile("|".join(self._dorm_patterns), re.I)],
            "is_swap": [re.compile("|".join(self._swap_patterns), re.I)],
            "is_job_ad": [re.compile("|".join(self._job_patterns), re.I)],
            "has_jobcenter": [re.compile("|".join(self._jobcenter_patterns), re.I)],
        }

        self._price_re = re.compile(r"(\d{2,6}\s?(грн|uah|€|eur|\$|usd)?)", re.I)
        self._phone_re = re.compile(r"(\+?\d[\d\-\s\(\)]{7,}\d)")
        self._question_re = re.compile(r"\?")

    def extract(self, message) -> Dict[str, int]: # Упростил typing
        text = message.text if hasattr(message, 'text') else str(message)
        
        features = {key: 0 for key in self._re_groups.keys()}
        
        for feature_name, patterns in self._re_groups.items():
            if any(p.search(text) for p in patterns):
                features[feature_name] = 1

        features["price"] = int(bool(self._price_re.search(text)))
        features["phone"] = int(bool(self._phone_re.search(text)))
        features["question"] = int(bool(self._question_re.search(text)))
        
        length = len(text)
        features["len_short"] = 1 if length < 50 else 0
        features["len_long"] = 1 if length > 1000 else 0
        features["length_val"] = length

        return features