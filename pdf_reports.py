from __future__ import annotations

from io import BytesIO
from decimal import Decimal
from typing import Iterable

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .utils import brl, qty

PAGE_W, PAGE_H = A4
MARGIN_X = 7 * mm
MARGIN_Y = 6 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X


def _txt(value) -> str:
    return '' if value is None else str(value)


def _fit_font(c: canvas.Canvas, text: str, font: str, size: float, max_width: float, min_size: float = 11) -> float:
    s = size
    while s > min_size and c.stringWidth(text, font, s) > max_width:
        s -= 0.5
    return s


def _draw_logo(c: canvas.Canvas, company, x: float, y_top: float, w: float = 13 * mm, h: float = 11 * mm):
    data = getattr(company, 'logo_data', None) if company else None
    if not data:
        return
    try:
        img = ImageReader(BytesIO(data))
        c.drawImage(img, x, y_top - h, width=w, height=h, preserveAspectRatio=True, anchor='c', mask='auto')
    except Exception:
        pass


def _draw_copy(c: canvas.Canvas, order, company, *, x: float, y_top: float, width: float, height: float, label: str, items=None, continuation: bool = False):
    items = list(order.items if items is None else items)
    bottom = y_top - height

    # Moldura externa da via.
    c.setStrokeColorRGB(0.45, 0.45, 0.45)
    c.setLineWidth(0.55)
    c.rect(x, bottom, width, height, stroke=1, fill=0)

    pad = 4 * mm
    left = x + pad
    right = x + width - pad
    top = y_top - 3 * mm

    # Cabeçalho: mantido compacto, como no layout aprovado.
    _draw_logo(c, company, left, top, 13 * mm, 11 * mm)
    c.setFillColorRGB(0, 0, 0)
    c.setFont('Helvetica-Bold', 10.5)
    company_name = _txt(getattr(company, 'trade_name', None) or getattr(company, 'legal_name', None) or 'HORTA').upper()
    c.drawCentredString(x + width / 2, top - 1 * mm, company_name)
    c.setFont('Helvetica-Bold', 9.5)
    title = f"ROMANEIO {order.number}"
    if continuation:
        title += ' - CONTINUAÇÃO'
    c.drawCentredString(x + width / 2, top - 6 * mm, title)
    c.setFont('Helvetica-Bold', 8.8)
    c.drawRightString(right, top - 1 * mm, label)
    c.setFont('Helvetica', 8.2)
    c.drawRightString(right, top - 6 * mm, f"Entrega: {order.delivery_date.strftime('%d/%m/%Y')}")

    rule_y = top - 10 * mm
    c.setLineWidth(0.8)
    c.line(left, rule_y, right, rule_y)

    client = order.client
    y = rule_y - 5 * mm
    c.setFont('Helvetica-Bold', 11.5)
    fantasy = _txt(client.trade_name or client.company_name)
    c.drawString(left, y, fantasy)
    y -= 4.6 * mm
    c.setFont('Helvetica', 7.6)
    legal = _txt(client.company_name if client.trade_name else '')
    if legal:
        c.drawString(left, y, legal)
        y -= 3.8 * mm
    address = ' '.join(part for part in [_txt(client.address), (_txt(client.city) + ('/' + _txt(client.state) if client.state else ''))] if part).strip()
    if address:
        c.drawString(left, y, address)
        y -= 3.8 * mm
    contact = f"Contato: {_txt(client.contact_name or '-')} · {_txt(client.phone or client.whatsapp or '-')}"
    c.drawString(left, y, contact)
    y -= 5.0 * mm

    # Grade: QTDE | UNIDADE | DESCRIÇÃO | PREÇO UNITÁRIO | TOTAL PRODUTO
    table_x = left
    table_w = right - left
    col_fracs = (0.10, 0.12, 0.43, 0.17, 0.18)
    cols = [table_x]
    for f in col_fracs:
        cols.append(cols[-1] + table_w * f)

    header_h = 8 * mm
    row_h = 8.0 * mm  # ~22.7 pt: comporta fonte 18 com folga.
    total_h = 8 * mm

    headers = ('QTDE', 'UNIDADE', 'DESCRIÇÃO', 'PREÇO\nUNITÁRIO', 'TOTAL\nPRODUTO')
    c.setLineWidth(0.45)
    c.setStrokeColorRGB(0.55, 0.55, 0.55)

    # Header.
    top_table = y
    c.rect(table_x, top_table - header_h, table_w, header_h, stroke=1, fill=0)
    for xx in cols[1:-1]:
        c.line(xx, top_table, xx, top_table - header_h)
    c.setFont('Helvetica-Bold', 8.0)
    for idx, htxt in enumerate(headers):
        cx0, cx1 = cols[idx], cols[idx + 1]
        if '\n' in htxt:
            a, b = htxt.split('\n', 1)
            c.drawCentredString((cx0 + cx1) / 2, top_table - 3.0 * mm, a)
            c.drawCentredString((cx0 + cx1) / 2, top_table - 6.0 * mm, b)
        elif idx == 2:
            c.drawString(cx0 + 1.5 * mm, top_table - 5.2 * mm, htxt)
        else:
            c.drawCentredString((cx0 + cx1) / 2, top_table - 5.2 * mm, htxt)

    current_y = top_table - header_h
    c.setFont('Helvetica', 18)
    for item in items:
        next_y = current_y - row_h
        c.rect(table_x, next_y, table_w, row_h, stroke=1, fill=0)
        for xx in cols[1:-1]:
            c.line(xx, current_y, xx, next_y)

        baseline = next_y + 2.15 * mm
        values = [qty(item.quantity), _txt(item.product.unit), _txt(item.product.name), brl(item.unit_price), brl(item.total)]

        # Quantidade e unidade centralizadas.
        c.setFont('Helvetica', 18)
        c.drawCentredString((cols[0] + cols[1]) / 2, baseline, values[0])
        c.drawCentredString((cols[1] + cols[2]) / 2, baseline, values[1])

        # Descrição em 18pt; reduz apenas se um nome excepcionalmente longo não couber.
        desc_max = (cols[3] - cols[2]) - 3 * mm
        desc_size = _fit_font(c, values[2], 'Helvetica', 18, desc_max, 13)
        c.setFont('Helvetica', desc_size)
        c.drawString(cols[2] + 1.5 * mm, baseline, values[2])

        # Preços alinhados à direita.
        c.setFont('Helvetica', 18)
        c.drawRightString(cols[4] - 1.5 * mm, baseline, values[3])
        c.drawRightString(cols[5] - 1.5 * mm, baseline, values[4])
        current_y = next_y

    # Total em negrito.
    next_y = current_y - total_h
    c.rect(table_x, next_y, table_w, total_h, stroke=1, fill=0)
    c.line(cols[4], current_y, cols[4], next_y)
    c.setFont('Helvetica-Bold', 10.5)
    c.drawString(table_x + 1.5 * mm, next_y + 2.45 * mm, 'TOTAL DO ROMANEIO')
    c.setFont('Helvetica-Bold', 11.5)
    c.drawRightString(cols[5] - 1.5 * mm, next_y + 2.25 * mm, brl(order.total))
    current_y = next_y

    # Observação e conferência.
    if getattr(order, 'notes', None):
        c.setFont('Helvetica', 7.5)
        note = 'Obs.: ' + _txt(order.notes)
        fs = _fit_font(c, note, 'Helvetica', 7.5, table_w, 6)
        c.setFont('Helvetica', fs)
        c.drawString(table_x, current_y - 4.2 * mm, note)
        current_y -= 4.2 * mm
    c.setFont('Helvetica', 7.5)
    c.drawString(table_x, max(bottom + 5.5 * mm, current_y - 5.0 * mm), 'Conferência/Recebimento: ________________________________________')


def generate_romaneios_pdf(orders: Iterable, company) -> bytes:
    orders = list(orders)
    out = BytesIO()
    c = canvas.Canvas(out, pagesize=A4, pageCompression=1)
    c.setTitle('Romaneios')
    c.setAuthor(_txt(getattr(company, 'trade_name', None) or getattr(company, 'legal_name', None) or 'Horta'))

    two_up_limit = 10
    full_page_chunk = 23
    usable_top = PAGE_H - MARGIN_Y
    full_h = PAGE_H - 2 * MARGIN_Y

    for order_index, order in enumerate(orders):
        items = list(order.items)
        if len(items) <= two_up_limit:
            gap = 4.5 * mm
            half_h = (full_h - gap) / 2
            _draw_copy(c, order, company, x=MARGIN_X, y_top=usable_top, width=CONTENT_W, height=half_h, label='1ª VIA')
            # Linha de corte entre vias.
            sep_y = usable_top - half_h - gap / 2
            c.saveState()
            c.setDash(2, 2)
            c.setStrokeColorRGB(0.55, 0.55, 0.55)
            c.line(MARGIN_X, sep_y, PAGE_W - MARGIN_X, sep_y)
            c.restoreState()
            c.setFont('Helvetica', 6.5)
            c.drawCentredString(PAGE_W / 2, sep_y - 2.2 * mm, 'corte / destaque')
            _draw_copy(c, order, company, x=MARGIN_X, y_top=usable_top - half_h - gap, width=CONTENT_W, height=half_h, label='2ª VIA')
            c.showPage()
        else:
            # Pedidos grandes: cada via começa em página própria. Se houver itens demais
            # para uma folha, continua em páginas adicionais sem cortar linhas.
            for label in ('1ª VIA', '2ª VIA'):
                chunks = [items[i:i + full_page_chunk] for i in range(0, len(items), full_page_chunk)] or [[]]
                for idx, chunk in enumerate(chunks):
                    _draw_copy(c, order, company, x=MARGIN_X, y_top=usable_top, width=CONTENT_W, height=full_h, label=label, items=chunk, continuation=(idx > 0))
                    c.showPage()

    c.save()
    return out.getvalue()
