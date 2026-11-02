"""Read a pasted crossing bulletin into dated numbers."""

import re
from dataclasses import dataclass, field
from datetime import date

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
MONTHS = ["", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
NAMES = {
    "كرم ابو سالم": "كرم أبو سالم",
    "كرم ابوسالم": "كرم أبو سالم",
    "كيسوفيم": "كيسوفيم",
    "زيكيم": "زيكيم",
    "زكيم": "زيكيم",
    "سولار": "سولار",
    "بنزين": "بنزين",
    "غاز": "غاز",
    "الفارس الشهم": "الفارس الشهم",
    "منظمه الغذاء العالمي": "منظمة الغذاء العالمي",
}
FUELS = {"سولار": "diesel", "بنزين": "petrol", "غاز": "gas"}
FUEL_LABEL = {"diesel": "سولار", "petrol": "بنزين", "gas": "غاز"}
PARTY_LABEL = {"commercial": "تجاري", "institution": "مؤسسات"}


@dataclass
class Issue:
    message: str
    kind: str = "line"
    key: str = ""

    def as_dict(self):
        return {"message": self.message, "kind": self.kind, "key": self.key}


@dataclass
class Parsed:
    movement_date: date | None = None
    weekday: str = ""
    gates: list = field(default_factory=list)
    fuels: list = field(default_factory=list)
    loads: list = field(default_factory=list)
    aid_lines: list = field(default_factory=list)
    stated: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)

    @property
    def ready(self):
        return self.movement_date is not None and not self.issues


def squash(value):
    text = str(value or "").translate(DIGITS)
    for source, target in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه"), ("ـ", "")):
        text = text.replace(source, target)
    text = re.sub(r"[\u064b-\u0652]", "", text)
    text = re.sub(r"[^\w\s/]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def canonical(value):
    key = squash(value)
    tight = key.replace(" ", "")
    for alias, pretty in NAMES.items():
        if key == alias or tight == alias.replace(" ", ""):
            return pretty
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", str(value), flags=re.UNICODE)).strip()


def _numbers(line):
    return [int(item) for item in re.findall(r"\d+", squash(line))]


def _words(line):
    text = str(line or "").translate(DIGITS)
    text = re.sub(r"[\u064b-\u0652]", "", text)
    text = re.sub(r"\d+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    for noise in ("شاحنة", "شاحنات"):
        text = text.replace(noise, " ")
    return re.sub(r"\s+", " ", text).strip()


def _crossing(folded):
    tight = folded.replace(" ", "")
    for alias, pretty in NAMES.items():
        if pretty in {"سولار", "بنزين", "غاز", "الفارس الشهم", "منظمة الغذاء العالمي"}:
            continue
        if alias in folded or alias.replace(" ", "") in tight:
            return pretty
    return ""


_WEEKDAY_KEYS = (
    ("الاثنين", "الاثنين"),
    ("الثلاثاء", "الثلاثاء"),
    ("الاربعاء", "الأربعاء"),
    ("الخميس", "الخميس"),
    ("الجمعه", "الجمعة"),
    ("السبت", "السبت"),
    ("الاحد", "الأحد"),
)


def _written_weekday(text):
    folded = squash(text)
    found = []
    for key, pretty in _WEEKDAY_KEYS:
        start = 0
        while True:
            index = folded.find(key, start)
            if index < 0:
                break
            found.append((index, pretty))
            start = index + len(key)
    if not found:
        return ""
    found.sort()
    return found[-1][1]


def _replace_weekday(text, pretty):
    pattern = r"الأحد|الاحد|الإثنين|الاثنين|الأثنين|الثلاثاء|الأربعاء|الاربعاء|الإربعاء|الخميس|الجمعة|الجمعه|السبت"
    if re.search(pattern, text):
        return re.sub(pattern, pretty, text, count=1)
    return f"{text.rstrip()}\n{pretty}"


def _section(line):
    folded = squash(line)
    if "اجمالي" in folded:
        return "totals"
    if "شاحن" in folded and "صنف" in folded:
        return "goods"
    if "مساعد" in folded and ("مؤسس" in folded or "جه" in folded):
        return "aid"
    if folded in {"المعابر", "المعابر:"} or folded.startswith("المعابر"):
        return "gates"
    return ""


def parse_crossing(text):
    parsed = Parsed()
    raw = str(text or "")
    found = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})", raw.translate(DIGITS))
    if found:
        day, month, year = (int(found.group(index)) for index in (1, 2, 3))
        try:
            parsed.movement_date = date(year, month, day)
        except ValueError:
            parsed.issues.append(Issue("التاريخ المكتوب غير صالح.", "date"))
    else:
        parsed.issues.append(Issue("لم أجد التاريخ. أرسل السطر الذي فيه اليوم بهذا الشكل: 01/11/2026.", "date"))
    written = _written_weekday(raw)
    if parsed.movement_date:
        actual = WEEKDAYS[parsed.movement_date.weekday()]
        parsed.weekday = actual
        if written and squash(written) != squash(actual):
            label = parsed.movement_date.strftime("%d/%m/%Y")
            parsed.issues.insert(0, Issue(
                f"التاريخ {label} يوافق {actual}، والنص يقول {written}. أرسل اسم اليوم أو التاريخ الصحيح.",
                "date",
            ))
    else:
        parsed.weekday = written

    mode = "gates"
    gate = None
    fuel = False
    party = "commercial"
    organization = ""
    for line in raw.splitlines():
        folded = squash(line)
        if not folded:
            continue
        section = _section(line)
        if section:
            mode = section
            fuel = False
            organization = ""
            continue
        if mode == "gates":
            named = _crossing(folded)
            if named:
                gate = {"name": named, "commercial": 0, "aid": 0}
                parsed.gates.append(gate)
                fuel = False
                party = "commercial"
                continue
            if "محروق" in folded:
                fuel = True
                continue
            if fuel and folded in {"تجاري", "تجاري:"}:
                party = "commercial"
                continue
            if fuel and "مؤسس" in folded:
                party = "institution"
                continue
            if gate is None:
                continue
            count = _numbers(line)
            if not count:
                continue
            if fuel:
                for label, kind in FUELS.items():
                    if label in folded:
                        parsed.fuels.append({"gate": gate["name"], "party": party, "kind": kind, "count": count[0]})
                        break
                continue
            if "تجاري" in folded:
                gate["commercial"] = count[0]
            elif "مساعد" in folded:
                gate["aid"] = count[0]
        elif mode == "totals":
            count = _numbers(line)
            if not count:
                continue
            if "تجاري" in folded:
                parsed.stated["commercial"] = count[0]
            elif "مساعد" in folded:
                parsed.stated["aid"] = count[0]
            elif "محروق" in folded:
                parsed.stated["fuel"] = count[0]
        elif mode == "goods":
            count = _numbers(line)
            name = canonical(_words(line))
            if name and count:
                parsed.loads.append({"name": name, "count": count[0]})
            elif name:
                parsed.issues.append(Issue(f"البند غير واضح: «{line.strip()}». أرسل الاسم والعدد.", "line", line.strip()))
        elif mode == "aid":
            if any(word in folded for word in ("اقتصاد", "اداره", "اعلام", "تجاره والمعابر")):
                continue
            count = _numbers(line)
            name = canonical(_words(line))
            if name and not count:
                organization = name
                continue
            if organization and name and count:
                parsed.aid_lines.append({"organization": organization, "item": name, "count": count[0]})
            elif name and not organization:
                parsed.issues.append(Issue(f"البند غير واضح: «{line.strip()}». أرسل الجهة ثم الصنف والعدد.", "line", line.strip()))
    _check_totals(parsed)
    return parsed


def _check_totals(parsed):
    commercial = sum(gate["commercial"] for gate in parsed.gates)
    aid = sum(gate["aid"] for gate in parsed.gates)
    fuel = sum(item["count"] for item in parsed.fuels)
    goods = sum(item["count"] for item in parsed.loads)
    aid_items = sum(item["count"] for item in parsed.aid_lines)
    checks = (
        ("commercial", "الإجمالي التجاري", commercial),
        ("aid", "الإجمالي للمساعدات", aid),
        ("fuel", "إجمالي المحروقات", fuel),
    )
    for key, label, actual in checks:
        stated = parsed.stated.get(key)
        if stated is None or stated == actual:
            continue
        parsed.issues.append(Issue(
            f"بند {label}: النص يقول {stated}، والمجموع {actual}. أرسل العدد الصحيح لهذا البند.",
            "stated",
            key,
        ))
    if parsed.loads and parsed.stated.get("commercial") not in (None, goods):
        parsed.issues.append(Issue(
            f"بند الأصناف التجارية: مجموعها {goods}، والإجمالي التجاري {parsed.stated['commercial']}. أرسل البند الناقص أو العدد الصحيح.",
            "goods",
        ))
    if parsed.aid_lines and parsed.stated.get("aid") not in (None, aid_items):
        parsed.issues.append(Issue(
            f"بند المساعدات: مجموع الأصناف {aid_items}، والإجمالي {parsed.stated['aid']}. أرسل البند الناقص أو العدد الصحيح.",
            "aid",
        ))


def date_label(movement, weekday=None):
    return {
        "weekday": WEEKDAYS[movement.weekday()],
        "year": str(movement.year),
        "month": f"{MONTHS[movement.month]} / {movement.month}",
        "day": str(movement.day),
    }


def fuel_caption(item):
    kind = FUEL_LABEL[item["kind"]]
    party = "المؤسسات" if item["party"] == "institution" else "تجاري"
    return f"{kind} {party}"


def present(parsed):
    fuel_gates = {item["gate"] for item in parsed.fuels}
    gates = []
    quiet = []
    quiet_fuels = []
    for gate in parsed.gates:
        lines = []
        if gate["commercial"]:
            lines.append(("التجاري", gate["commercial"]))
        else:
            quiet.append((f"{gate['name']}، تجاري", 0))
        if gate["aid"]:
            lines.append(("المساعدات", gate["aid"]))
        else:
            quiet.append((f"{gate['name']}، مساعدات", 0))
        for item in parsed.fuels:
            if item["gate"] != gate["name"]:
                continue
            label = fuel_caption(item)
            if len(fuel_gates) > 1:
                label = f"{gate['name']}، {label}"
            if item["count"]:
                lines.append((label, item["count"]))
            else:
                quiet_fuels.append((label, 0))
        if lines:
            gates.append({"name": gate["name"], "lines": lines})
    quiet.extend(quiet_fuels)
    aid = []
    for line in parsed.aid_lines:
        if not line["count"]:
            quiet.append((f"{line['organization']}، {line['item']}", 0))
            continue
        if not aid or aid[-1]["name"] != line["organization"]:
            aid.append({"name": line["organization"], "lines": []})
        aid[-1]["lines"].append((line["item"], line["count"]))
    loads = []
    for item in parsed.loads:
        if item["count"]:
            loads.append((item["name"], item["count"]))
        else:
            quiet.append((item["name"], 0))
    commercial = parsed.stated.get("commercial", sum(gate["commercial"] for gate in parsed.gates))
    aid_total = parsed.stated.get("aid", sum(gate["aid"] for gate in parsed.gates))
    fuel_total = parsed.stated.get("fuel", sum(item["count"] for item in parsed.fuels))
    return {
        "gates": gates,
        "totals": [("التجاري", commercial), ("المساعدات", aid_total), ("المحروقات", fuel_total)],
        "aid": aid,
        "loads": loads,
        "quiet": quiet,
    }


def _replace_date(text, cleaned):
    found = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})", cleaned.translate(DIGITS))
    if not found:
        return text
    day, month, year = found.groups()
    replacement = f"{int(day):02d}/{int(month):02d}/{year}"
    if re.search(r"\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{4}", text):
        return re.sub(r"\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{4}", replacement, text, count=1)
    return f"{text.rstrip()}\n{replacement}"


def apply_correction(text, issue, reply):
    kind = issue.get("kind") if isinstance(issue, dict) else issue.kind
    key = issue.get("key") if isinstance(issue, dict) else issue.key
    cleaned = str(reply or "").strip()
    if kind == "date":
        updated = _replace_date(text, cleaned)
        written = _written_weekday(cleaned)
        if written:
            updated = _replace_weekday(updated, written)
        if updated != text:
            return updated
    digits = cleaned.translate(DIGITS)
    if kind == "stated" and re.fullmatch(r"\d+", digits):
        return _replace_total(text, key, int(digits))
    if kind == "line" and re.fullmatch(r"\d+", digits) and key and key in text:
        return text.replace(key, f"{key} {cleaned}", 1)
    if kind in {"goods", "aid"} and re.fullmatch(r"\d+", digits):
        return _replace_total(text, "commercial" if kind == "goods" else "aid", int(digits))
    return f"{text.rstrip()}\n{cleaned}"


def _replace_total(text, key, number):
    label = {"commercial": "تجاري", "aid": "مساعد", "fuel": "محروق"}[key]
    lines = text.splitlines()
    mode = ""
    for index, line in enumerate(lines):
        section = _section(line)
        if section:
            mode = section
            continue
        if mode == "totals" and label in squash(line) and _numbers(line):
            lines[index] = re.sub(r"\d+", str(number), line, count=1)
            return "\n".join(lines)
    return text
