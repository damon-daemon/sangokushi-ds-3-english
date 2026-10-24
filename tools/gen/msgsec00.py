"""English for msgsec00: speech-style substitution table.

Each entry is a list of variants chosen by conditions on the speaker; dialogue
inserts an entry with {01}C<id>{00}. Pronouns/terms of address/insults get
English words; Japanese verb endings and particles (17-58) become empty because
the English dialogue lines carry the meaning themselves.
"""
I = 'I'
EPITHETS = """Yide of Yan|Kongming|Sleeping Dragon|Zhao Zilong|Guan Yunchang|Splendid Ma|
Ma Mengqi|Huang Hansheng|Sun Bofu|Sun Zhongmou|Liu Xuande|Cao Mengde|Gan Xingba|Handsome Zhou|Zhou Gongjin|
Sun Wentai|Xu Zhongkang|Zhang Wenyuan|Lingming|Flying General|Lu Fengxian|Xu Gongming|Evil Comer|
Miaocai|Yuanrang|Ling Gongxu|Yellow Beard|Cao Ziwen|Jiang Boyue|Cao Zixiao|Cao Zidan|
Cao Wenlie|Cao Zihuan|Zhongquan|Wen Zhongye|Chen Xuanbo|Wang Ziquan|Wen Zhongruo|Wen Shu|Gongxiu|
Sima Anshi|Sima Zhongda|Wang Shizhi|Du Yuankai|Ma Shoucheng|White Horse|Bogui|Guan Anguo|
Young Phoenix|Zhang Boqi|Wang Zijun|Wei Wenchang|Wu Ziyuan|Zhang Bogong|Sun Shubi|Huang Gongfu|Sun Shuwu|
Sun Zitong|Cheng Demou|Han Yigong|Zhou Youping|Taishi Ziyi|Ding Chengyuan|Lu Ziming|Lu Boyan|Zhu Yifeng|
Zhu Xiumu|Liu Jingsheng|Nanman King|Yuchi Jingde|First Emperor|Qing Bu|Yue Pengju|Guan Zhong|
Hegemon-King|Xiang Yu|Lanling|Qin Shubao|Qin Zhensu|Zhang Zifang|Chen Ziyun|Koxinga|
Taigong Wang|Prodigal|Twin Snake|Scorpion|Little Li Guang|Great Blade|Short-Lived|
Taisui|Living Yama|Cloud Dragon|Yiqing|Twin Whips|Ten-Foot Blue|Wise Star|
Scholar Wu|Cai Yuanzhang|Reckless|Little Whirlwind|Vanguard|Nine Dragons|Fine Beard|
Golden Spear|Thunderbolt|Timely Rain|Defender|Song Gongming|Swift Runner|Tiger Den|Boat Fire|
Pagoda Bearer|White Streak|Swift Arrow|Twin Spears|Pilgrim|Unstoppable|Blue Beast|
Sickly Guan|Winged Tiger|Iron Staff|Sky Eagle|Iron Ox|Black Whirlwind|River Dragon|
Red Demon|Panther|Jade Unicorn|Tattooed Monk|""".replace('\n', '')
EN = {
    0: [I], 1: [I], 2: [I],
    3: EPITHETS.split('|')[:-1] + [None],          # last variant: officer's own name
    4: ['we'],
    5: ['Your Majesty', 'you', 'you'],
    6: ['my lord', 'you'],
    7: ['you'],
    8: ['Strategist', 'General', 'you', 'you', 'you'],
    9: ['Master Zhang', 'Great Teacher', 'General of Heaven', 'Great King', None, 'brother'],
    10: ['my liege', 'my lord'],
    11: ['you'],
    12: ['that man', 'that dog'],
    13: ['sister', 'brother'],
    14: ['sister', 'brother', 'big brother', 'big sister'],
    15: ['woman', 'you', 'old fool', 'girl', 'brat', 'greenhorn', 'lout', 'brute', 'coward',
         'pedant', 'wretch'],
    16: ['traitor', 'villain', 'scum', 'rebel', 'cur'],
    **{i: [''] for i in range(17, 59)},
    59: ['easily'], 60: ['at all'], 61: ['gladly'], 62: ['firmly'], 63: ['well'],
    64: [''],
    65: ['Ohoho', 'Hehe', 'Heh', 'Hahaha', 'Haha', 'Hahaha'],
}

def apply(path):
    """Write EN into script/msgsec00.json: each variant keeps its condition header
    (tl.header) and gets the English text; None keeps the Japanese variant."""
    import json, os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import tl
    rows = json.load(open(path, encoding='utf-8'))
    for i, words in EN.items():
        if not any(words):
            # All-empty entry: a bare return. Keeping the conditions would leave
            # "{05}{05}{04}<cond>{05}{05}{05}": the if-handler (0x02038470) eats a
            # token after the condition, so on the false branch the first return is
            # swallowed and the expander runs on into the next entries (the
            # blanked particles printed entry 59 "easily").
            rows[i]['en'] = tl.END
            continue
        jv = rows[i]['jp'].split(tl.END)
        out = []
        for k, v in enumerate(jv[:-1]):           # last split part is the empty tail
            w = words[k] if k < len(words) else words[-1]
            # jump-only variants ({01}J..) carry no text
            out.append(v if w is None or tl.invisible(v) else tl.header(v) + w)
        rows[i]['en'] = tl.END.join(out + [jv[-1]])
    json.dump(rows, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    import os
    apply(os.path.join(os.path.dirname(__file__), '..', '..', 'script', 'msgsec00.json'))
