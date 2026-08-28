import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
from render_template import build_ass
class TemplateRulesTests(unittest.TestCase):
    def test_rules_are_distinct(self):
        social = json.loads((ROOT / 'rules/social.json').read_text())
        iqiyi = json.loads((ROOT / 'rules/iqiyi.json').read_text())
        self.assertIsNone(social['title'])
        self.assertEqual(iqiyi['title']['line_mode'], 'one_or_two')
        self.assertEqual(social['subtitle']['font_size'], 36)
        self.assertEqual(social['subtitle']['outline'], 1.5)
        self.assertEqual(social['subtitle']['position'], {'x': 248, 'y': 629})
        self.assertEqual(social['subtitle']['render_font'], 'Microsoft YaHei')
        self.assertEqual(iqiyi['subtitle']['font_size'], 35)
        self.assertEqual(iqiyi['subtitle']['outline'], 1.5)
        self.assertEqual(iqiyi['subtitle']['position'], {'x': 248, 'y': 629})
        self.assertEqual(iqiyi['title']['line_1']['outline'], 3)
        self.assertEqual(iqiyi['title']['line_2']['outline'], 3)
        self.assertEqual(iqiyi['subtitle']['font'], '思源黑体')
        self.assertEqual(iqiyi['title']['font'], 'HYZongYiJ')
        self.assertEqual(iqiyi['subtitle']['render_font'], 'SourceHanSansCN-Heavy')
        self.assertEqual(iqiyi['title']['position']['line_gap'], iqiyi['title']['font_size'] / 4)
        self.assertEqual(iqiyi['title']['position']['y'] + iqiyi['title']['font_size'] + iqiyi['title']['position']['line_gap'], 120)

    def test_iqiyi_title_modes(self):
        iqiyi = json.loads((ROOT / 'rules/iqiyi.json').read_text())
        captions = [(0, 1, '测试字幕')]
        two = build_ass(iqiyi, '黄字内容 白字内容', captions, 'two')
        one = build_ass(iqiyi, '黄字内容 白字内容', captions, 'one')
        self.assertIn(r'\pos(248,120)', two)
        self.assertIn('TitleSub', two)
        self.assertEqual(one.count('Dialogue: 1'), 1)
        self.assertIn(r'\c&H00FFFFFF', one)
