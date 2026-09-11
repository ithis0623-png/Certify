import base64
import hashlib
import io
import json
import unittest
from unittest.mock import patch

import pymupdf as fitz
from PIL import Image, ImageChops, ImageDraw

from scripts import certificate_renderer as renderer


class CertificateRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(renderer.CONFIG_PATH.read_text())
        image = Image.new('RGB', (420, 640), '#284b6b')
        ImageDraw.Draw(image).rectangle((0, 0, 210, 320), fill='#e0b24c')
        buffer = io.BytesIO()
        image.save(buffer, 'PNG')
        cls.photo = 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()

    def data(self):
        return {'recipientName': 'Hernán Simó', 'designation': 'Digital Artist',
                'identityLine': 'Hernán Simó Digital Art', 'issueDate': '2026-05-05',
                'profileImage': self.photo, 'crop': {'zoom': 1, 'x': 0, 'y': 0}}

    def test_date_ordinals_and_validation(self):
        for day, suffix in [(1, 'st'), (2, 'nd'), (3, 'rd'), (11, 'th'), (12, 'th'), (13, 'th'), (21, 'st'), (22, 'nd'), (23, 'rd'), (31, 'st')]:
            self.assertEqual(renderer.date_label(f'2026-05-{day:02}'), f'{day}{suffix} May, 2026')
        self.assertEqual(renderer.date_label('2026-09-11'), '11th Sep, 2026')
        self.assertEqual(renderer.date_label('2026-01-01'), '1st Jan, 2026')
        self.assertEqual(renderer.date_label('2026-08-22'), '22nd Aug, 2026')
        for bad in ['2026-02-29', '2026-13-01', '2026-5-5', '<script>']:
            with self.assertRaises(ValueError):
                renderer.date_label(bad)


    def test_reference_fields_use_shared_preview_geometry(self):
        result = renderer.run({'action': 'preview', 'data': self.data()})
        self.assertFalse(result['errors'])
        self.assertEqual(result['fitted']['recipientName']['text'], 'HERNÁN SIMÓ')
        self.assertEqual(result['fitted']['issueDate']['text'], '5th May, 2026')
        self.assertIn('<svg', result['svg'])
        for name, field in result['fitted'].items():
            self.assertLessEqual(field['width'], self.config['fields'][name]['width'] + .001)

    def test_long_names_shrink_and_overflow_is_blocked(self):
        data = self.data()
        data['recipientName'] = 'Alexandria Montgomery'
        result = renderer.run({'action': 'preview', 'data': data})
        self.assertLess(result['fitted']['recipientName']['fontSize'], 20)
        for field in ['recipientName', 'designation', 'identityLine']:
            data = self.data()
            data[field] = 'W' * 100
            with self.assertRaises(renderer.InvalidCertificate) as error:
                renderer.run({'action': 'export', 'format': 'pdf', 'data': data})
            self.assertIn(field, error.exception.errors)

    def test_missing_fields_and_unsupported_glyphs_block_exports(self):
        for field in ['profileImage', 'recipientName', 'designation', 'identityLine', 'issueDate']:
            data = self.data()
            data[field] = ''
            with self.assertRaises(renderer.InvalidCertificate) as error:
                renderer.run({'action': 'export', 'format': 'pdf', 'data': data})
            self.assertIn(field, error.exception.errors)
        data = self.data()
        data['recipientName'] = 'Name 😀'
        self.assertIn('recipientName', renderer.run({'action': 'preview', 'data': data})['errors'])

    def test_photo_validation_and_crop_bounds(self):
        for photo in ['data:image/svg+xml;base64,PHN2Zz4=', 'data:image/png;base64,YmFk', 'https://example.com/photo.jpg']:
            data = self.data()
            data['profileImage'] = photo
            with self.assertRaises(renderer.InvalidCertificate):
                renderer.portrait(data)
        for crop in [{'zoom': 5}, {'x': 2}, {'y': -2}, {'zoom': float('nan')}]:
            data = self.data()
            data['crop'] = crop
            with self.assertRaises(renderer.InvalidCertificate):
                renderer.portrait(data)
        photo = Image.open(io.BytesIO(renderer.portrait(self.data())))
        self.assertEqual(photo.getpixel((0, 0))[3], 0)
        self.assertEqual(photo.getpixel((500, 500))[3], 255)

    def test_master_hash_protection(self):
        modified = {**self.config, 'masterSha256': 'wrong'}
        with patch.object(renderer.CONFIG_PATH.__class__, 'read_text', return_value=json.dumps(modified)):
            with self.assertRaises(RuntimeError):
                renderer.run({'action': 'preview', 'data': self.data()})

    def test_pdf_preserves_static_artwork_and_preview_ink(self):
        before = hashlib.sha256(renderer.MASTER.read_bytes()).hexdigest()
        exported = renderer.run({'action': 'export', 'format': 'pdf', 'data': self.data()})
        final = fitz.open(stream=base64.b64decode(exported['content']), filetype='pdf')
        master = fitz.open(renderer.MASTER)
        self.assertEqual(final[0].rect, master[0].rect)
        self.assertEqual(len(final), 1)
        self.assertIn('HERNÁN SIMÓ', final[0].get_text())
        self.assertIn('Inclusion in which', final[0].get_text())
        base_pixels = Image.open(io.BytesIO(master[0].get_pixmap(dpi=144).tobytes('png')))
        final_pixels = Image.open(io.BytesIO(final[0].get_pixmap(dpi=144).tobytes('png')))
        delta = ImageChops.difference(base_pixels, final_pixels)
        mask = Image.new('L', delta.size, 255)
        draw = ImageDraw.Draw(mask)
        boxes = [(246, 369, 348, 471), (158, 480, 437, 509), (158, 514, 437, 532), (128, 527, 468, 545), (218, 611, 378, 631)]
        for box in boxes:
            draw.rectangle(tuple(round(n*2) for n in box), fill=0)
        outside = ImageChops.multiply(delta.convert('RGB'), Image.merge('RGB', (mask, mask, mask)))
        self.assertIsNone(outside.getbbox(), 'Static artwork changed outside the approved regions')
        # PDF dynamic layer has the same visible glyph positions as the live preview.
        overlay, _, _ = renderer.text_overlay(self.data(), self.config)
        expected = {s['text']: s['origin'] for b in overlay[0].get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans']}
        actual = {s['text']: s['origin'] for b in final[0].get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans']}
        for text, origin in expected.items():
            self.assertAlmostEqual(actual[text][0], origin[0], places=3)
            self.assertAlmostEqual(actual[text][1], origin[1], places=3)
        self.assertEqual(hashlib.sha256(renderer.MASTER.read_bytes()).hexdigest(), before)

    def test_high_resolution_image_exports(self):
        for output_format in ['png', 'jpeg']:
            result = renderer.run({'action': 'export', 'format': output_format, 'data': self.data()})
            image = Image.open(io.BytesIO(base64.b64decode(result['content'])))
            self.assertEqual(image.size, (2481, 3508))
            self.assertEqual(image.format.lower(), output_format)


if __name__ == '__main__':
    unittest.main()
