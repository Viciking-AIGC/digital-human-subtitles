import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from render_template import build_ass, split_benxian_text


class SocialBenxianTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / 'rules' / 'social.json').read_text(encoding='utf-8'))

    def test_standard_keyword_list_is_scoped_to_social(self):
        expected = [
            '同城夜聊', '同城约会吧', '爱聊', '爱聊唯西', '爱聊新远方', '会会',
            '会会新远方', '会会宇视', '本地寻友', '他趣', '闪糖', '甜话',
        ]
        self.assertEqual(self.cfg['subtitle']['highlight_keywords'], expected)
        ass = build_ass(self.cfg, '', [(0, 1, '普通字幕 爱聊唯西 和同城夜聊')])
        self.assertIn(r'{\1c&H0000E5FF&\3c&H00101010&}爱聊唯西', ass)
        self.assertIn(r'{\1c&H0000E5FF&\3c&H00101010&}同城夜聊', ass)

    def test_body_is_one_simultaneous_punctuation_stripped_event(self):
        text = '在一起了，她温柔 体贴！真诚'
        self.assertEqual(split_benxian_text(text), ['在一起了', '她温柔 体贴', '真诚'])
        for font in self.cfg['variants']['奔现']['fonts']:
            ass = build_ass(
                self.cfg, '', [(1, 8, text)],
                social_variant='奔现', social_font=font,
            )
            self.assertEqual(ass.count('Dialogue: 0,'), 1)
            self.assertIn(r'\pos(50,700)', ass)
            self.assertIn(r'\N', ass)
            self.assertNotIn('！', ass)
            self.assertNotIn('，', ass)

    def test_multiple_caption_windows_are_preserved(self):
        ass = build_ass(
            self.cfg, '', [(1, 2, '第一段，第二行'), (3, 4, '第三段')],
            social_variant='奔现', social_font='新青年体',
        )
        self.assertIn('Dialogue: 0,0:00:01.00,0:00:02.00', ass)
        self.assertIn('Dialogue: 0,0:00:03.00,0:00:04.00', ass)
        self.assertEqual(ass.count('Dialogue: 0,'), 2)

    def test_fixed_title_contract(self):
        variant = self.cfg['variants']['奔现']
        self.assertEqual(set(variant['fonts']), {
            '标题圆', '抖音体', '新青年体', '美玲体', '江户招牌', '仓耳丰黑',
        })
        self.assertEqual(variant['font_size'], 32)
        self.assertEqual(variant['position'], {'x': 50, 'y': 700})
        title = variant['title']
        self.assertEqual(title['font_size'], 35)
        self.assertEqual(title['position'], {'x': 248, 'y': 50})
        self.assertEqual(set(title['styles']), {'心动时刻', '黄色星星'})
        ass = build_ass(
            self.cfg, '', [(2, 4, '片中文案')],
            social_variant='奔现', social_font='标题圆',
            social_title='温柔相遇 在这里遇见专属偏爱',
            social_title_style='心动时刻',
        )
        self.assertIn('Style: SocialTitle,HYZongYiJ,35', ass)
        self.assertIn(r'{\pos(248,50)}温柔相遇\N在这里遇见专属偏爱', ass)
        self.assertIn('Dialogue: 1,0:00:02.00,0:00:04.00', ass)


if __name__ == '__main__':
    unittest.main()
