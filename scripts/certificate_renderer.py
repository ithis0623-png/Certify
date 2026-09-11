"""Fixed HOF geometry. Preview paths and exports share this renderer.

Coordinates are PDF points measured from the supplied completed reference.
The master PDF-compatible AI is opened read-only and never modified.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / 'HOF_Certificate_Blank.ai'
CONFIG_PATH = ROOT / 'resources/hof-template.json'
FONT_DIR = ROOT / 'resources/fonts'
Image.MAX_IMAGE_PIXELS = 25_000_000


def font_path(role):
    if role == 'body':
        return FONT_DIR / 'NotoSans-Regular.ttf'
    filename = 'Butler-Free-XBd.otf' if role == 'name' else 'Butler-Free-Bd.otf'
    return FONT_DIR / filename


def build():
    """Generate the locked preview from the original document, without redaction."""
    with fitz.open(MASTER) as doc:
        page = doc[0]
        page.get_pixmap(dpi=144, alpha=False).save(ROOT / 'resources/hof-background.png')
        body = fitz.Font(fontfile=str(font_path('body')))
        name_font = fitz.Font(fontfile=str(font_path('name')))
        date_font = fitz.Font(fontfile=str(font_path('date')))
        # Match the reference's Frutiger line width at its original font size.
        body_scale = 56.903015 / body.text_length('Digital Artist', fontsize=10.346)
        config = {
            'id': 'hof-appreciation-v1', 'version': 1,
            'title': 'Certificate of Appreciation',
            'width': page.rect.width, 'height': page.rect.height,
            'masterSha256': hashlib.sha256(MASTER.read_bytes()).hexdigest(),
            'image': {'x': 247.9955, 'y': 370.764, 'width': 98.5118, 'height': 98.4875},
            'fields': {
                'recipientName': {'x': 160, 'width': 275.2756, 'baseline': 500.3833,
                                  'font': 'name', 'fontSize': 20, 'minFontSize': 14,
                                  'scaleX': 139.46878 / name_font.text_length('HERNÁN SIMÓ', fontsize=20),
                                  'color': '#323a41', 'uppercase': True},
                'designation': {'x': 160, 'width': 275.2756, 'baseline': 527.5143,
                                'font': 'body', 'fontSize': 10.346, 'minFontSize': 10.346,
                                'scaleX': body_scale, 'color': '#1c1b17'},
                'identityLine': {'x': 130, 'width': 335.2756, 'baseline': 539.0468,
                                 'font': 'body', 'fontSize': 10.346, 'minFontSize': 10.346,
                                 'scaleX': 108.07425 / body.text_length('Hernán Simó Digital Art', fontsize=10.346),
                                 'color': '#1c1b17'},
                'issueDate': {'x': 220, 'width': 155.2756, 'baseline': 624.0101,
                              'font': 'date', 'fontSize': 9.5, 'minFontSize': 9.5,
                              'scaleX': 60.457916 / date_font.text_length('5th May, 2026', fontsize=9.5),
                              'color': '#2b2a29'},
            },
            'defaults': {'recipientName': '', 'designation': '', 'identityLine': '',
                         'issueDate': date.today().isoformat(), 'profileImage': ''},
            'fonts': {'name': 'Butler ExtraBold (2026 free edition)',
                      'body': 'Noto Sans, width-adjusted fallback for Frutiger',
                      'date': 'Butler Bold (2026 free edition)'},
        }
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding='utf-8')
    return {'built': True, 'masterSha256': config['masterSha256']}


class InvalidCertificate(Exception):
    def __init__(self, errors):
        self.errors = errors


def date_label(raw):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
        raise ValueError('Invalid date')
    value = date.fromisoformat(raw)
    day = value.day
    suffix = 'th' if 11 <= day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return f'{day}{suffix} {value.strftime("%b")}, {value.year}'



def text_overlay(data, config):
    errors, fitted = {}, {}
    doc = fitz.open()
    page = doc.new_page(width=config['width'], height=config['height'])
    for key, region in config['fields'].items():
        text = data.get(key, '')
        if not isinstance(text, str) or not text.strip():
            errors[key] = 'This field is required.'
            continue
        text = text.strip()
        if len(text) > 160 or any(ord(c) < 32 for c in text):
            errors[key] = 'Use a single line of up to 160 characters.'
            continue
        if key == 'issueDate':
            try:
                text = date_label(text)
            except ValueError:
                errors[key] = 'Choose a valid date.'
                continue
        if region.get('uppercase'):
            text = text.upper()
        font = fitz.Font(fontfile=str(font_path(region['font'])))
        if any(not font.has_glyph(ord(c)) for c in text):
            errors[key] = 'This font does not support one or more characters.'
            continue
        size = region['fontSize']
        width = font.text_length(text, fontsize=size) * region['scaleX']
        if width > region['width'] and key == 'recipientName':
            size *= region['width'] / width
        if size < region['minFontSize'] or (width > region['width'] and key != 'recipientName'):
            errors[key] = 'Text is too long for the fixed area. Please shorten it.'
            continue
        width = font.text_length(text, fontsize=size) * region['scaleX']
        point = fitz.Point(region['x'] + (region['width'] - width) / 2, region['baseline'])
        color = tuple(int(region['color'][i:i+2], 16) / 255 for i in (1, 3, 5))
        page.insert_text(point, text, fontname=key, fontfile=str(font_path(region['font'])),
                         fontsize=size, color=color,
                         morph=(point, fitz.Matrix(region['scaleX'], 1)))
        fitted[key] = {'fontSize': size, 'width': width, 'text': text}
    return doc, errors, fitted


def portrait(data):
    raw = data.get('profileImage', '')
    if not isinstance(raw, str) or len(raw) > 14_000_000:
        raise InvalidCertificate({'profileImage': 'Photo exceeds the upload limit.'})
    match = re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\r\n]+)', raw)
    if not match:
        raise InvalidCertificate({'profileImage': 'Upload a JPG, PNG or WEBP photo.'})
    try:
        binary = base64.b64decode(match[2], validate=True)
        if len(binary) > 10_000_000:
            raise ValueError('Photo is too large')
        image = Image.open(io.BytesIO(binary))
        if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 25_000_000:
            raise ValueError('Unsupported image')
        image = ImageOps.exif_transpose(image).convert('RGBA')
        crop = data.get('crop', {})
        zoom, x, y = (float(crop.get(k, default)) for k, default in [('zoom', 1), ('x', 0), ('y', 0)])
        if not all(math.isfinite(v) for v in (zoom, x, y)) or not 1 <= zoom <= 4 or not -1 <= x <= 1 or not -1 <= y <= 1:
            raise ValueError('Invalid crop')
        side = min(image.size) / zoom
        left, top = (image.width-side)*(x+1)/2, (image.height-side)*(y+1)/2
        image = image.resize((1000, 1000), Image.Resampling.LANCZOS, box=(left, top, left+side, top+side))
        mask = Image.new('L', (2000, 2000))
        ImageDraw.Draw(mask).ellipse((0, 0, 1999, 1999), fill=255)
        mask = mask.resize(image.size, Image.Resampling.LANCZOS)
        # Retain source transparency inside the circular mask.
        from PIL import ImageChops
        image.putalpha(ImageChops.multiply(image.getchannel('A'), mask))
        result = io.BytesIO()
        image.save(result, format='PNG')
        return result.getvalue()
    except (ValueError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidCertificate({'profileImage': 'Invalid photo or crop settings.'}) from exc


def run(payload):
    config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    if hashlib.sha256(MASTER.read_bytes()).hexdigest() != config['masterSha256']:
        raise RuntimeError('The approved master changed; rebuild and review the template.')
    overlay, errors, fitted = text_overlay(payload.get('data', {}), config)
    if payload.get('action') == 'preview':
        return {'svg': overlay[0].get_svg_image(text_as_path=True), 'errors': errors, 'fitted': fitted}
    if payload.get('action') != 'export' or payload.get('format') not in ('pdf', 'png', 'jpeg'):
        raise InvalidCertificate({'format': 'Choose PDF, PNG or JPEG.'})
    data = payload.get('data', {})
    photo = None
    try:
        photo = portrait(data)
    except InvalidCertificate as exc:
        errors.update(exc.errors)
    if errors:
        raise InvalidCertificate(errors)
    # Open the master itself: original vector artwork, fonts, colors and dimensions survive.
    document = fitz.open(MASTER)
    page = document[0]
    page.show_pdf_page(page.rect, overlay, 0)
    region = config['image']
    page.insert_image(fitz.Rect(region['x'], region['y'], region['x']+region['width'], region['y']+region['height']), stream=photo)
    if payload['format'] == 'pdf':
        binary = document.tobytes(garbage=3, deflate=True)
    else:
        pixmap = page.get_pixmap(dpi=300, alpha=False)
        binary = pixmap.tobytes('png' if payload['format'] == 'png' else 'jpeg', jpg_quality=95)
    return {'content': base64.b64encode(binary).decode('ascii')}


if __name__ == '__main__':
    try:
        result = build() if '--build' in sys.argv else run(json.load(sys.stdin))
        print(json.dumps(result, ensure_ascii=True))
    except InvalidCertificate as exc:
        print(json.dumps({'errors': exc.errors}))
        sys.exit(2)
    except Exception as exc:
        print(json.dumps({'error': str(exc)}))
        sys.exit(1)
