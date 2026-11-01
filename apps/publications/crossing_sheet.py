"""Official crossing sheet: the approved Kufi layout, as one image."""

import io
from pathlib import Path

import arabic_reshaper
import segno
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

from apps.publications.crossing_text import date_label, present

ASSETS = Path(__file__).resolve().parent / "assets"
S = 2
WIDTH = 720 * S
PAD = 20 * S
INK = (26, 24, 20)
PAPER = (251, 249, 244)
MUTED = (63, 59, 52)
HAIR = (228, 223, 212)
FOOTER = "وزارة الاقتصاد الوطني — الإعلام الرقمي - نسخة الكترونية"

_FONTS = {}


def _font(weight, size):
    key = (weight, size)
    if key not in _FONTS:
        font = ImageFont.truetype(str(ASSETS / "NotoKufiArabic-Variable.ttf"), size)
        font.set_variation_by_axes([weight])
        _FONTS[key] = font
    return _FONTS[key]


def _shape(text):
    text = str(text)
    if text.isascii():
        return text
    return get_display(arabic_reshaper.reshape(text))


def _width(font, shown):
    box = font.getbbox(shown)
    return box[2] - box[0]


def _draw_rtl(draw, text, right, top, font, fill):
    shown = _shape(text)
    draw.text((right - _width(font, shown), top), shown, font=font, fill=fill)


def _draw_center(draw, text, left, right, top, bottom, font, fill):
    shown = _shape(text)
    box = font.getbbox(shown)
    width = box[2] - box[0]
    height = box[3] - box[1]
    x = left + (right - left - width) / 2 - box[0]
    y = top + (bottom - top - height) / 2 - box[1]
    draw.text((x, y), shown, font=font, fill=fill)


def _pair(draw, name, number, left, right, top, font, fill):
    numeral = str(number)
    box = font.getbbox(numeral)
    gap = 8 * S
    number_width = box[2] - box[0]
    draw.text((left - box[0], top), numeral, font=font, fill=fill)
    room = right - left - number_width - gap
    used = font
    shown = _shape(name)
    if _width(used, shown) > room:
        used = _font(500, 9 * S)
        shown = _shape(name)
    draw.text((right - _width(used, shown), top), shown, font=used, fill=fill)
    return top + int(11 * S * 1.45) + 4 * S


def _rule(draw, left, right, top, color):
    draw.line((left, top, right, top), fill=color, width=max(1, S // 2))


def _heading(draw, title, left, right, top):
    _draw_rtl(draw, title, right, top, _font(700, 14 * S), INK)
    top += 14 * S + 4 * S
    draw.line((left, top, right, top), fill=INK, width=S)
    return top + 6 * S


def _rows(draw, pairs, left, right, top, columns, fill):
    if not pairs:
        return top
    gap = 14 * S
    span = right - left
    column_width = (span - gap * (columns - 1)) / columns
    row_height = int(11 * S * 1.45) + 6 * S
    font = _font(500, 11 * S)
    for index, (name, number) in enumerate(pairs):
        column = index % columns
        row = index // columns
        cell_right = right - column * (column_width + gap)
        cell_left = cell_right - column_width
        y = top + row * row_height
        _pair(draw, name, number, cell_left, cell_right, y, font, fill)
        _rule(draw, cell_left, cell_right, y + row_height - 3 * S, HAIR)
    rows = (len(pairs) + columns - 1) // columns
    return top + rows * row_height


def _gate_block(draw, gate, left, right, top):
    _draw_rtl(draw, gate["name"], right, top, _font(600, 12 * S), INK)
    top += 12 * S + 6 * S
    return _rows(draw, gate["lines"], left, right, top, 1, INK)


def _header(image, draw, parsed, url):
    logo_size = 92 * S
    top = 16 * S
    logo = Image.open(ASSETS / "ministry-logo.png").convert("RGBA")
    logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
    logo_x = (WIDTH - logo.width) // 2
    logo_y = top + (logo_size - logo.height) // 2
    image.paste(logo, (logo_x, logo_y), logo)

    lines = ("وزارة الاقتصاد الوطني", "حركة الشاحنات الواردة من المعابر", "الإدارة العامة للتجارة والمعابر")
    font = _font(500, 13 * S)
    line_height = int(13 * S * 1.7)
    text_top = top + (logo_size - line_height * len(lines)) // 2
    for index, line in enumerate(lines):
        _draw_rtl(draw, line, WIDTH - PAD, text_top + index * line_height, font, INK)

    qr_size = 92 * S
    buffer = io.BytesIO()
    segno.make(url, error="m").save(buffer, kind="png", scale=6, border=1, dark="#1a1814", light="#fbf9f4")
    buffer.seek(0)
    qr = Image.open(buffer).convert("RGB").resize((qr_size, qr_size), Image.Resampling.NEAREST)
    image.paste(qr, (PAD, top))

    table_left = PAD + qr_size + 8 * S
    table_right = table_left + 96 * S
    label = date_label(parsed.movement_date, parsed.weekday)
    cells = (label["weekday"], label["year"], label["month"], label["day"])
    heights = (20 * S, 20 * S, 22 * S, 30 * S)
    fonts = (_font(500, 12 * S), _font(500, 12 * S), _font(500, 11 * S), _font(600, 22 * S))
    cursor = top
    for text, height, cell_font in zip(cells, heights, fonts):
        draw.rectangle((table_left, cursor, table_right, cursor + height), outline=INK, width=S)
        _draw_center(draw, text, table_left, table_right, cursor, cursor + height, cell_font, INK)
        cursor += height
    bottom = top + logo_size + 12 * S
    draw.line((PAD, bottom, WIDTH - PAD, bottom), fill=INK, width=S)
    return bottom + 14 * S


def _side(draw, view, side, left, right, top):
    inner_left = left + 16 * S
    inner_right = right - 16 * S
    if side == "gates":
        if view["gates"]:
            top = _heading(draw, "المعابر", inner_left, inner_right, top)
            for gate in view["gates"]:
                top = _gate_block(draw, gate, inner_left, inner_right, top)
                top += 8 * S
        top = _heading(draw, "الإجمالي", inner_left, inner_right, top)
        return _rows(draw, view["totals"], inner_left, inner_right, top, 1, INK)
    if not view["aid"]:
        return top
    top = _heading(draw, "المساعدات حسب الجهة", inner_left, inner_right, top)
    for group in view["aid"]:
        top = _gate_block(draw, group, inner_left, inner_right, top)
        top += 4 * S
    return top


def render_sheet(parsed, url):
    view = present(parsed)
    image = Image.new("RGB", (WIDTH, 4200), PAPER)
    draw = ImageDraw.Draw(image)
    top = _header(image, draw, parsed, url)
    content_right = WIDTH - PAD
    content_left = PAD
    span = content_right - content_left
    gates_width = int(span * 1 / 2.35)
    split = content_right - gates_width
    gates_bottom = _side(draw, view, "gates", split, content_right, top)
    aid_bottom = _side(draw, view, "aid", content_left, split, top)
    if view["gates"] or view["aid"]:
        draw.line((split, top, split, max(gates_bottom, aid_bottom)), fill=INK, width=S)
    top = max(gates_bottom, aid_bottom) + 14 * S
    if view["loads"]:
        top = _heading(draw, "الشاحنات التجارية حسب الصنف", content_left, content_right, top)
        top = _rows(draw, view["loads"], content_left, content_right, top, 4, INK)
        top += 14 * S
    if view["quiet"]:
        top = _heading(draw, "لم يدخل", content_left, content_right, top)
        top = _rows(draw, view["quiet"], content_left, content_right, top, 3, MUTED)
        top += 8 * S
    top += 8 * S
    draw.line((PAD, top, WIDTH - PAD, top), fill=INK, width=S)
    top += 8 * S
    footer_font = _font(400, 11 * S)
    _draw_center(draw, FOOTER, PAD, WIDTH - PAD, top, top + int(11 * S * 1.8), footer_font, MUTED)
    top += int(11 * S * 1.8) + 10 * S
    cropped = image.crop((0, 0, WIDTH, top))
    buffer = io.BytesIO()
    cropped.save(buffer, format="PNG")
    return buffer.getvalue()


def store_crossing(parsed, body, user):
    from django.conf import settings
    from django.core.files.base import ContentFile
    from django.db import IntegrityError, transaction

    from apps.publications.models import CrossingAidLine, CrossingFuel, CrossingGate, CrossingLoad, CrossingReport

    url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/crossings/{parsed.movement_date.isoformat()}/"
    png = render_sheet(parsed, url)
    name = ""
    if user is not None:
        name = user.display_name or user.username
    try:
        with transaction.atomic():
            if CrossingReport.objects.filter(movement_date=parsed.movement_date).exists():
                return None
            report = CrossingReport.objects.create(
                body=body,
                movement_date=parsed.movement_date,
                weekday=parsed.weekday,
                image=ContentFile(png, name=f"{parsed.movement_date.isoformat()}.png"),
                publisher=user,
                publisher_name=name,
            )
            CrossingGate.objects.bulk_create([
                CrossingGate(report=report, name=gate["name"], commercial=gate["commercial"], aid=gate["aid"], position=index)
                for index, gate in enumerate(parsed.gates)
            ])
            CrossingFuel.objects.bulk_create([
                CrossingFuel(report=report, gate=item["gate"], party=item["party"], kind=item["kind"], count=item["count"])
                for item in parsed.fuels
            ])
            CrossingLoad.objects.bulk_create([
                CrossingLoad(report=report, name=item["name"], count=item["count"], position=index)
                for index, item in enumerate(parsed.loads)
            ])
            CrossingAidLine.objects.bulk_create([
                CrossingAidLine(
                    report=report, organization=item["organization"], item=item["item"], count=item["count"], position=index,
                )
                for index, item in enumerate(parsed.aid_lines)
            ])
    except IntegrityError:
        return None
    return report
