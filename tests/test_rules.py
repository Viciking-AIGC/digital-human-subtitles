import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
from render_template import build_ass, info_feed_ad_keyword_events, redfruit_caption_events, redfruit_keyword_events, split_redfruit_text
class TemplateRulesTests(unittest.TestCase):
    def test_rules_are_distinct(self):
        social = json.loads((ROOT / 'rules/social.json').read_text())
        redfruit = json.loads((ROOT / 'rules/redfruit.json').read_text())
        iqiyi = json.loads((ROOT / 'rules/iqiyi.json').read_text())
        self.assertIsNone(social['title'])
        self.assertIsNone(redfruit['title'])
        self.assertEqual(iqiyi['title']['line_mode'], 'one_or_two')
        self.assertEqual(social['subtitle']['font_size'], 36)
        self.assertEqual(social['subtitle']['outline'], 1.5)
        self.assertEqual(social['subtitle']['position'], {'x': 248, 'y': 629})
        self.assertEqual(social['subtitle']['render_font'], 'Microsoft YaHei')
        self.assertTrue(social['subtitle']['punctuation_split'])
        self.assertEqual(social['subtitle']['max_chars_per_line'], 10)
        self.assertEqual(redfruit['subtitle']['font_size'], social['subtitle']['font_size'])
        self.assertEqual(redfruit['subtitle']['outline'], social['subtitle']['outline'])
        self.assertEqual(redfruit['subtitle']['shadow'], social['subtitle']['shadow'])
        self.assertEqual(redfruit['subtitle']['position'], social['subtitle']['position'])
        self.assertEqual(redfruit['subtitle']['font'], '抖音美好体')
        self.assertEqual(redfruit['subtitle']['render_font'], 'DouyinSans')
        self.assertEqual(iqiyi['subtitle']['font_size'], 35)
        self.assertEqual(iqiyi['subtitle']['outline'], 1.5)
        self.assertEqual(iqiyi['subtitle']['position'], {'x': 248, 'y': 629})
        self.assertEqual(iqiyi['title']['line_1']['outline'], 3)
        self.assertEqual(iqiyi['title']['line_2']['outline'], 3)
        self.assertEqual(iqiyi['subtitle']['font'], '思源黑体')
        self.assertTrue(iqiyi['subtitle']['punctuation_split'])
        self.assertEqual(iqiyi['subtitle']['max_chars_per_line'], 10)
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

    def test_social_cta_is_opt_in(self):
        social = json.loads((ROOT / 'rules/social.json').read_text())
        captions = [(0, 1, '测试字幕')]
        without_cta = build_ass(social, '', captions)
        with_cta = build_ass(social, '', captions, show_social_cta=True)
        self.assertNotIn('SocialCTA', without_cta)
        self.assertIn('SocialCTA', with_cta)
        self.assertEqual(
            social['cta']['eligible_products'],
            ['爱聊唯西', '爱聊新远方', '会会新远方'],
        )
        self.assertEqual(
            social['cta']['applicable_video_types'],
            ['digital_human', 'empty_shot'],
        )

    def test_redfruit_uses_social_geometry_with_douyin_font(self):
        social = json.loads((ROOT / 'rules/social.json').read_text())
        redfruit = json.loads((ROOT / 'rules/redfruit.json').read_text())
        self.assertEqual(redfruit['template'], 'redfruit')
        self.assertEqual(redfruit['subtitle']['font_size'], social['subtitle']['font_size'])
        self.assertEqual(redfruit['subtitle']['scale_x'], social['subtitle']['scale_x'])
        self.assertEqual(redfruit['subtitle']['scale_y'], social['subtitle']['scale_y'])
        self.assertEqual(redfruit['subtitle']['color'], social['subtitle']['color'])
        self.assertEqual(redfruit['subtitle']['outline_color'], social['subtitle']['outline_color'])
        self.assertEqual(redfruit['subtitle']['outline'], social['subtitle']['outline'])
        self.assertEqual(redfruit['subtitle']['shadow'], social['subtitle']['shadow'])
        self.assertEqual(redfruit['subtitle']['alignment'], social['subtitle']['alignment'])
        self.assertEqual(redfruit['subtitle']['position'], social['subtitle']['position'])
        self.assertEqual(redfruit['subtitle']['render_font'], 'DouyinSans')

    def test_redfruit_removes_punctuation_and_limits_chunks(self):
        self.assertEqual(split_redfruit_text('红果短剧，好看！这是超过十个字的文案内容', 10),
                         ['红果短剧', '好看', '这是超过十个字的', '文案内容'])
        self.assertEqual(split_redfruit_text('你认错人了我根本不是王总', 10),
                         ['你认错人了', '我根本不是王总'])
        self.assertEqual(split_redfruit_text('快来红果短剧看看后续内容', 10),
                         ['快来红果短剧', '看看后续内容'])
        cfg = json.loads((ROOT / 'rules/redfruit.json').read_text())
        events = redfruit_caption_events([(0, 4, '红果短剧，好看！')], cfg['subtitle'])
        self.assertEqual([event[2] for event in events], ['红果短剧', '好看'])
        self.assertLessEqual(max(len(event[2]) for event in events), 10)
        self.assertEqual(events[0][0], 0)
        self.assertEqual(events[-1][1], 4)

    def test_redfruit_keyword_has_red_outline_only(self):
        cfg = json.loads((ROOT / 'rules/redfruit.json').read_text())
        ass = build_ass(cfg, '', [(0, 1, '欢迎来到红果短剧平台！')])
        self.assertNotIn('！', ass)
        self.assertIn(r'{\1c&H00FFFFFF&\3c&H002E1CED&}红果短剧{\1c&H00FFFFFF&\3c&H00101010&}', ass)
        self.assertEqual(ass.count('Dialogue: 0'), 1)

    def test_redfruit_logo_events_follow_keyword_chunks(self):
        cfg = json.loads((ROOT / 'rules/redfruit.json').read_text())
        events = redfruit_keyword_events([(0, 5, '快来红果短剧看看后续内容')], cfg['subtitle'])
        self.assertEqual([event[2] for event in events], ['快来红果短剧'])
        self.assertEqual(events[0][0], 0)
        self.assertLess(events[0][1], 5)
        self.assertEqual(cfg['subtitle']['logo']['position'], {'x': 248, 'y': 500})

    def test_redfruit_logo_only_uses_first_keyword_occurrence(self):
        cfg = json.loads((ROOT / 'rules/redfruit.json').read_text())
        captions = [
            (0, 2, '红果短剧第一处'),
            (2, 4, '第二处红果短剧'),
            (4, 6, '再次出现红果短剧'),
        ]
        events = redfruit_keyword_events(captions, cfg['subtitle'])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][2], '红果短剧第一处')

    def test_info_feed_ad_is_the_canonical_fixed_line(self):
        info = json.loads((ROOT / 'rules/info_feed_ad.json').read_text())
        social = json.loads((ROOT / 'rules/social.json').read_text())
        self.assertEqual(info['template'], 'info_feed_ad')
        self.assertEqual(info['subtitle']['font'], '抖音美好体')
        self.assertEqual(info['subtitle']['render_font'], 'DouyinSans')
        self.assertEqual(info['subtitle']['font_size'], social['subtitle']['font_size'])
        self.assertEqual(info['subtitle']['position'], social['subtitle']['position'])
        self.assertTrue(info['subtitle']['punctuation_split'])
        self.assertEqual(info['subtitle']['max_chars_per_line'], 10)
        self.assertEqual(info['subtitle']['keyword'], '红果短剧')
        self.assertIsNone(info['title'])
        self.assertEqual(info['subtitle']['logo']['position'], {'x': 248, 'y': 500})
        self.assertEqual(info['subtitle']['logo']['width'], 80)
        ass = build_ass(info, '', [(0, 1, '第一段，红果短剧看看后续内容。')])
        self.assertNotIn('，', ass)
        self.assertIn('DouyinSans,36', ass)
        self.assertEqual(len(info_feed_ad_keyword_events([(0, 1, '红果短剧再次出现')], info['subtitle'])), 1)
