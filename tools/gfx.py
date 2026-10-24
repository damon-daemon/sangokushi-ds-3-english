"""Graphic text edits applied at build time.

Each entry redraws labels in a 4bpp linear sheet (NCBR, 256 px wide) with
gfxtext. Boxes are (x, y, w, h) in sheet pixels; find them with
nitrogfx.Cells (OBJ tile t sits at x = t % 32 * 8, y = t // 32 * 8).
"""
import os, sys
import ndspy.lz10
sys.path.insert(0, os.path.dirname(__file__))
import nitrogfx, gfxtext, bgtext

GOLD = dict(kind='emboss', fill=[11, 11, 10, 10, 9, 8, 7, 6, 5], inner=1, outer=3)

def plate(wood):
    """Wooden command buttons: 72x32 cells on a 3-column grid; text plate repainted
    with wood from a clean strip (x, y, w) of the original sheet."""
    return dict(kind='plate', fill=[15, 15, 14, 14, 13], outline=1, wood=wood)

def green(wood):
    """Green confirm bar (bold caps, white gradient); wood = clean strip (x, y, w)."""
    return dict(kind='plate', fill=[15, 15, 14, 13, 12], outline=1, wood=wood, bold=True)

def bars(n, w, h, cols, strip_x, fill=(15, 15, 14, 14, 13), outline=2, outline2=1, x=0, y=0):
    """Lattice menu bars stacked vertically (n cells of w x h at (x, y + i*h)). Text is
    erased using art from bars whose text doesn't cover a column; the bar's bottom
    strip (rows >= 15) falls back to texture from column strip_x."""
    return dict(kind='bars', origins=[(x, y + i * h) for i in range(n)], size=(w, h), cols=cols,
                strip_x=strip_x, fill=list(fill), outline=outline, outline2=outline2)

def buttons(full, fill=(15, 15, 14, 13, 12), outline=1, text_vals=(12, 13, 14, 15), cols=range(6, 82), bold=True):
    """Framed buttons sharing one texture. Cells as wide as full=(w, h) give a clean
    background (per-column from a cell whose text doesn't cover it); narrower cells use
    its left and right halves. Labels are (x, y, w, h), text; text is drawn in bold caps."""
    return dict(kind='buttons', full=full, fill=list(fill), outline=outline, text_vals=set(text_vals), cols=cols, bold=bold)

def scenarios(text_x=(20, 41, 63), ornament=10, clear=(14, 161), row1=39):
    """Scenario-select style bars: NCER cells drawn as 192x24 strips (some split over odd
    OAM layouts). Labels are (cell, parts) with parts drawn at text_x (or centred in
    clear when text_x is None). Rows 2-14 of clear=(x0, x1) are erased (row 1 too from
    x = row1); from x1 on, rows 2-14 come from the ornament cell."""
    return dict(kind='scenario', text_x=text_x, ornament=ornament, clear=clear, row1=row1, fill=[15, 15, 15, 14], outline=2)

def cell_map(cells, i):
    """{(x, y) in cell space: (x, y) in the linear sheet} for NCER cell i."""
    m = {}
    for o in cells.cells[i]:
        tx, ty = o['tile'] % 32 * 8, o['tile'] // 32 * 8
        for dy in range(o['h']):
            for dx in range(o['w']):
                m[(o['x'] + dx, o['y'] + dy)] = (tx + dx, ty + dy)
    return m

def draw_scenarios(rom, name, style, labels, px, orig, w):
    from collections import Counter
    cells = nitrogfx.Cells(rom.getFileByName(name.rsplit('.', 1)[0] + '.NCER'))
    maps = [cell_map(cells, i) for i, _ in labels]
    keys = sorted(maps[0])
    clean = {}
    for k in keys:
        clean[k] = Counter(orig[m[k][1] * w + m[k][0]] for m in maps).most_common(1)[0][0]
    x0, x1 = style['clear']
    if style['ornament'] is not None:
        src = maps[[i for i, _ in labels].index(style['ornament'])]
        for (x, y) in keys:                # right ornament: from a bar whose title stops short of it
            if x >= x1 and 2 <= y <= 14:
                sx, sy = src[(x, y)]
                clean[(x, y)] = orig[sy * w + sx]
    for (x, y) in keys:                    # text area: transparent (row 1 keeps the left frame line)
        if x0 <= x < x1 and (2 <= y <= 14 or (y <= 1 and x >= style['row1'])):
            clean[(x, y)] = 0
    for y in range(15, 18):                # bottom band: replace outline/fill bits with band texture
        last = None
        for x in range(x0, x1):
            if clean[(x, y)] in (1, 2, 3, 4, 5, 14, 15):
                clean[(x, y)] = last if last is not None else clean[(x0 - 1, y)]
            else:
                last = clean[(x, y)]
    for m, (_, parts) in zip(maps, labels):
        img = dict(clean)
        for k, t in enumerate(parts):
            mask = gfxtext.pad(gfxtext.render_plain(t), 1)
            tx = style['text_x'][k] if style['text_x'] else (x0 + x1 - len(mask[0])) // 2 + 1
            ring = gfxtext.dilate(mask)
            for y in range(len(mask)):
                for x in range(len(mask[0])):
                    k = (tx - 1 + x, 2 + y)
                    if mask[y][x]:
                        f = style['fill']
                        img[k] = f[min(len(f) - 1, (y - 1) * len(f) // 11)]
                    elif ring[y][x] and k in img:
                        img[k] = style['outline']
            if tx - 1 + len(mask[0]) > x1:
                raise ValueError('%r too wide' % t)
        for k, (sx, sy) in m.items():
            px[sy * w + sx] = img[k]

def rowfill(text_vals, fill=(15, 15, 14, 12), outline=1, outline2=None, grow=0, bold=False):
    """Text on a horizontally banded background: text pixels (text_vals) are refilled
    from the same row (gfxtext.rowfill), then text is drawn centred in the box."""
    return dict(kind='rowfill', text_vals=set(text_vals), fill=list(fill), outline=outline, outline2=outline2,
                grow=grow, bold=bold)

def headers(word_pal, fill=(1, 1, 2, 3), outline=15, widen=None):
    """List column headers: each NCER cell = plate OAMs + word OAMs (palette word_pal).
    Labels are (cell, text); the word OAMs are cleared and the text drawn across them.
    widen = {cell: (dx, w, sheet_x, sheet_y)} first resizes a cell's single word OAM to
    w x 16 at free sheet space, moved dx px."""
    return dict(kind='headers', word_pal=word_pal, fill=list(fill), outline=outline, widen=widen or {})

def draw_headers(rom, name, style, labels, px, w):
    fid = rom.filenames.idOf(name.rsplit('.', 1)[0] + '.ncer')
    raw = bytes(rom.files[fid])
    cells = nitrogfx.Cells(raw)
    for i, (dx, ww, sx, sy) in style['widen'].items():
        o, = [o for o in cells.cells[i] if o['pal'] == style['word_pal']]
        nitrogfx.set_oam(cells, o, x=o['x'] + dx, w=ww, h=16, tile=sy // 8 * 32 + sx // 8)
    for i, text in labels:
        ws = [o for o in cells.cells[i] if o['pal'] == style['word_pal']]
        x0 = min(o['x'] for o in ws)
        W = max(o['x'] + o['w'] for o in ws) - x0
        img = [[0] * W for _ in range(16)]
        gfxtext.draw_cell(img, text, style['fill'], style['outline'], clip=True)
        for o in ws:
            tx, ty = o['tile'] % 32 * 8, o['tile'] // 32 * 8
            for y in range(16):
                for x in range(o['w']):
                    px[(ty + y) * w + tx + x] = img[y][o['x'] - x0 + x]
    rom.files[fid] = ndspy.lz10.compress(bytes(cells.file)) if raw[:1] == b'\x10' else bytes(cells.file)

def grid(labels, cols=3, cw=72, ch=32):
    return [((i % cols * cw + 6, i // cols * ch + 4, 56, 21), t) for i, t in enumerate(labels) if t]


EDITS = [
    # Strategy main menu scroll labels (palette bank 7)
    ('Stg/OBJ_stg_down_main_parts00.ncbr', GOLD, [
        ((128, 0, 40, 22), 'CIVIL'),     # 内政
        ((168, 0, 40, 22), 'ARMY'),      # 軍事
        ((128, 24, 40, 22), 'STAFF'),    # 人事
        ((168, 24, 40, 22), 'PLOTS'),    # 計略
        ((128, 48, 40, 22), 'INTEL'),    # 情報
        ((168, 48, 40, 22), 'ENVOY'),    # 外交
    ]),
    ('Stg/OBJ_stg_down_main_parts.ncbr', GOLD, [
        ((128, 0, 40, 22), 'CIVIL'), ((168, 0, 40, 22), 'ARMY'), ((128, 32, 40, 22), 'STAFF'),
        ((168, 32, 40, 22), 'PLOTS'), ((160, 160, 40, 22), 'INTEL'), ((200, 160, 40, 22), 'ENVOY')]),
    # Season banner (64x64 calligraphy, per-cell palettes with the same white->colour ramp)
    ('Stg/MainMap/OBJ_stg_down_mainmap_kisetumoji.ncbr',
     dict(kind='emboss', fill=[15, 15, 14, 13, 12, 12, 11, 11], inner=1, outer=1, stretch=(1, 2, 3, 5, 7, 8, 9)), [
        ((0, 0, 64, 64), 'SPRING'), ((64, 0, 64, 64), 'AUTUMN'),     # 春 秋
        ((128, 0, 64, 64), 'SUMMER'), ((192, 0, 64, 64), 'WINTER')]),  # 夏 冬
    # 進行 tab (light green, dark outline, green glow)
    ('Stg/OBJ_stg_down_main_parts.ncbr', rowfill((1, 9, 10, 11, 12, 13, 14, 15), outline2=10),
     [((108, 163, 49, 19), 'Advance')]),
    # START機能 / LR地図: keep the START and LR glyphs, replace the kanji plates
    ('Stg/OBJ_stg_down_main_parts.ncbr', rowfill((1, 14), fill=[14]), [
        ((183, 195, 22, 13), 'Menu'), ((225, 195, 28, 13), 'Map')]),
    # Y訪問 (dark text, light outline on yellow)
    ('Stg/OBJ_stg_down_main_parts00.ncbr', rowfill((1, 11, 12, 13), fill=[1], outline=13), [((216, 106, 34, 15), 'Visit')]),
    # X進行
    ('Stg/OBJ_stg_down_main_parts03.ncbr', rowfill((1, 4, 8, 11, 12, 14, 15)), [((203, 3, 46, 19), 'Advance')]),
    # Unit selection: X確定 bar, 武将一括 tag
    ('Stg/SelUnit/OBJ_stg_down_butai1_parts.ncbr', green((10, 4, 30)), [((40, 4, 90, 16), 'X  Confirm')]),
    ('Stg/SelUnit/OBJ_stg_down_butai1_parts.ncbr', rowfill((1, 12, 13, 14, 15), fill=[15, 15, 15, 14]),
     [((1, 25, 62, 13), 'Select All')]),
    # List column headers (cells 15-67; 金 米 widened into free sheet space)
    ('Common/Select/OBJ_hanyou_list_parts.ncbr', headers(9, widen={20: (-8, 32, 0, 176), 21: (-8, 32, 32, 176)}), list(enumerate([
        'Ruler', 'Fame', 'Officer', 'City', 'Troops', 'Gold', 'Rice', 'Hostile',     # 君主 名声 武将 都市 兵士 金 米 敵対
        'Ally', 'Near', 'Name', 'Force', 'Gov.', 'Spare', 'Order', 'Pop.',           # 同盟 隣接 名前 所属 太守 予備 民忠 人口
        'Farm', 'Levee', 'Trade', 'Def.', 'Free', 'Peril', 'Trader', 'Name',         # 農業 治水 商業 防御 在野 災害 商人 名前
        'Age', 'War', 'Int', 'Pol', 'Cha', 'Place', 'Rank', 'Exp',                   # 年齢 武力 知力 政治 魅力 所在 身分 経験
        'Valor', 'Items', 'Task', 'Loyalty', 'Troops', 'Drill', 'Morale', 'Gen. Rank',  # 勇名 アイテム 担当 忠誠 兵士 訓練 士気 将軍位
        'Vigor', 'Joined', 'Moves', 'Name', 'Type', 'Owner', 'Max Troops', 'Serving',  # 気力 参戦 行動 名前 種別 所有者 兵士上限 現任武将
        'Cost', 'Period', 'Date', 'Event Name', 'Cost'], 15))),                       # 費用 期間 年月 イベント名 コスト
    ('Common/Select/OBJ_hanyou_list_parts.ncbr', green((98, 116, 30)), [((128, 116, 90, 16), 'X  Confirm')]),
    # Number entry: Y消去 後退, L最小 R最大, X確定
    ('Common/InpCalc/OBJ_hanyou_down_namber_parts.ncbr', buttons((64, 24), cols=range(6, 58)), [
        ((184, 0, 64, 24), 'Y Clear'), ((184, 24, 64, 24), 'Back')]),
    ('Common/InpCalc/OBJ_hanyou_down_namber_parts.ncbr', rowfill((1, 12, 13, 14, 15), fill=[15], bold=True), [
        ((130, 52, 38, 13), 'L Min'), ((184, 52, 41, 13), 'R Max')]),
    ('Common/InpCalc/OBJ_hanyou_down_namber_parts.ncbr', rowfill((1, 12, 13, 14, 15), bold=True), [
        ((6, 80, 52, 22), 'X  OK')]),
    # Officer editor
    ('EditBushou/EditMenu/OBJ_shoki_down_makemenu_parts.NCBR', buttons((80, 32), cols=range(6, 74)), [
        ((x * 80, y * 32, 80, 32), t) for y, row in enumerate([
            ('Face', 'Name', 'Stats'), ('Formation', 'Skills', 'Age'), ('Kin', 'Affinity', 'Other')])  # 顔 名前 能力値 / 陣形 特殊能力 年齢 / 血縁 相性 その他
        for x, t in enumerate(row)]),
    ('EditBushou/EditMenu/OBJ_shoki_down_makemenu_parts.NCBR', green((10, 100, 30)), [((40, 100, 90, 16), 'X  Confirm')]),
    ('EditBushou/Formation/OBJ_shoki_down_jinkei_parts.NCBR', buttons((38, 28), cols=range(4, 34), bold=False), [
        ((x * 40, y * 32, 38, 28), t) for y, row in enumerate([
            ('Awl', 'Hook', 'Fan', 'Crane', 'Scales', 'Moon'),          # 錐行 鈎行 箕形 鶴翼 魚鱗 偃月
            ('Arrow', 'Yoke', 'Snake', 'Circle', 'Geese', 'Water')])          # 鋒矢 衡軛 長蛇 方円 雁行 水陣
        for x, t in enumerate(row)]),
    ('EditBushou/Formation/OBJ_shoki_down_jinkei_parts.NCBR', green((10, 68, 30)), [((40, 68, 90, 16), 'X  Confirm')]),
    ('EditBushou/GoodEvil/OBJ_shoki_down_zenaku_parts.NCBR', buttons((56, 24), cols=range(5, 51), bold=False), [
        ((0, 0, 48, 24), 'V.Good'), ((48, 0, 48, 24), 'Good'), ((96, 0, 48, 24), 'Evil'), ((144, 0, 48, 24), 'V.Evil'),  # 極善 善人 悪人 極悪
        ((0, 24, 56, 24), 'Short'), ((56, 24, 56, 24), 'Normal'), ((112, 24, 56, 24), 'Long')]),                        # 短い 普通 長い
    ('EditBushou/GoodEvil/OBJ_shoki_down_zenaku_parts.NCBR', green((10, 52, 30)), [((40, 52, 90, 16), 'X  Confirm')]),
    ('EditBushou/SpAbility/OBJ_shoki_down_tokushu1_parts.NCBR', buttons((38, 28), cols=range(4, 34), bold=False), [
        ((x * 40, y * 32, 38, 28), t) for y, row in enumerate([
            ('Fire', 'Panic', 'Feud', 'Order', 'Mystic', 'Rouse'),        # 火計 混乱 同討 収拾 仙術 鼓舞
            ('Heal', 'Rain', 'Skies', 'Douse', 'Rocks', 'Divine'),            # 治療 雨乞 天変 消火 落石 占卜
            ('Lurk', 'Mirage', 'Hex', 'Cheer', 'Flood', 'Flame'),        # 伏兵 幻術 妖術 激励 水計 火矢
            ('Fury', 'Spray', 'Rush', 'Vines', 'Mighty', 'Snipe'),        # 奮迅 乱射 速攻 藤甲 無双 遠矢
            ('March', 'Calm', 'Shift', 'W.God', 'Foil', 'Slide'),          # 強行 沈着 陣立 水神 反計 土砂
            ('Reply', 'M.Bow', 'Sneak', 'Pitfall', 'Taunt', 'Infilt.')])  # 応射 騎射 隠密 落穴 挑発 潜入
        for x, t in enumerate(row)]),
    ('EditBushou/SpAbility/OBJ_shoki_down_tokushu1_parts.NCBR', green((10, 196, 30)), [((40, 196, 90, 16), 'X  Confirm')]),
    ('EditBushou/SpAbility/OBJ_shoki_down_tokushu2_parts.NCBR', buttons((38, 28), cols=range(4, 34), bold=False), [
        ((x * 40, y * 32, 38, 28), t) for y, row in enumerate([
            ('Sway', 'Wall', 'Blitz', 'Beast', 'Charm', 'Awe'),     # 心攻 鉄壁 特攻 猛獣 傾国 威風
            ('F.God', 'Scout', 'Sense', 'Grit', 'Hold', 'Luck')])     # 火神 斥候 探知 逆境 籠城 幸運
        for x, t in enumerate(row)]),
    ('EditBushou/SpAbility/OBJ_shoki_down_tokushu2_parts.NCBR', green((10, 68, 30)), [((40, 68, 90, 16), 'X  Confirm')]),
    ('EditBushou/InpName/OBJ_shoki_down_nameinput_parts.NCBR', green((58, 4, 30)), [((88, 4, 90, 16), 'X  Confirm')]),
    ('EditBushou/InpName/OBJ_shoki_down_nameread_parts.NCBR', green((58, 4, 30)), [((88, 4, 90, 16), 'X  Confirm')]),
    ('EditBushou/InpName/OBJ_shoki_down_nameset_parts.NCBR', green((26, 4, 30)), [((56, 4, 90, 16), 'X  Confirm')]),
    ('EditBushou/Ability/OBJ_shoki_down_nouryoku_parts.NCBR', green((10, 4, 30)), [((40, 4, 90, 16), 'X  Confirm')]),
    ('EditBushou/Charactor/OBJ_shoki_down_setetc_parts.NCBR', green((10, 4, 30)), [((40, 4, 90, 16), 'X  Confirm')]),
    # Gallery menu: 武将カード SP武将カード アイテム 歴史イベント データ消去, コンプリート
    ('Gallery/Menu/OBJ_shoki_down_gallery_parts.NCBR', scenarios(None, 2, (35, 103), 35), [
        (0, ('Officer Cards',)), (1, ('SP Cards',)), (2, ('Items',)), (3, ('Events',)), (4, ('Erase Data',))]),
    ('Gallery/Menu/OBJ_shoki_down_gallery_parts.NCBR', dict(kind='emboss', fill=[14, 14, 13, 12, 11], inner=1, outer=1),
     [((144, 0, 72, 24), 'COMPLETE')]),
    # Hero Battle Road
    ('Challenge/Start/OBJ_eiyuu_down_start_parts.NCBR', scenarios(None, None, (58, 137), 58),
     [(0, ('Suspended Game',)), (2, ('Continue',)), (1, ('New Game',))]),          # 中断データ 続きから 初めから
    ('Challenge/Main/OBJ_eiyuu_down_main_parts.NCBR', buttons((72, 32), cols=range(5, 66)), [
        ((0, 0, 72, 32), 'Advance'), ((0, 32, 72, 32), 'Recruit')]),              # 進軍 登用
    ('Challenge/Growup/OBJ_eiyuu_down_ikusei_parts.NCBR', green((10, 4, 30)), [((40, 4, 90, 16), 'X  Confirm')]),
    ('Challenge/Hensei/OBJ_eiyuu_down_butaihensei_parts.NCBR', green((10, 4, 30)), [((40, 4, 90, 16), 'X  Confirm')]),
    ('Challenge/Hensei/OBJ_eiyuu_down_butaihensei_parts.NCBR', rowfill((1, 12, 13, 14, 15), fill=[15, 15, 15, 14]),
     [((1, 25, 62, 13), 'Select All')]),                                           # 武将一括
    ('Challenge/Score/OBJ_eiyuu_down_score_parts.NCBR', green((10, 20, 30)), [((40, 20, 90, 16), 'X  Confirm')]),  # X確認
    # Officer registry: 新規登録 内容変更 削除
    ('EditBushou/TopMenu/OBJ_shoki_down_newbushoutouroku_parts.NCBR', scenarios(None, None, (58, 118), 58),
     [(0, ('New',)), (1, ('Edit',)), (2, ('Delete',))]),
    # Tutorial chapter buttons: 第N章 / title
    ('Tutorial/OBJ_tut_down_menu_parts.ncbr', buttons((80, 48), cols=range(6, 74), bold=False), [
        ((i % 3 * 80, i // 3 * 48, 80, 48), 'Chapter %d\n%s' % (i + 1, t)) for i, t in enumerate([
            'Prologue', 'The Basics', 'Talent', 'Wealth', 'Army', 'Diplomacy', 'Marching', 'War', 'Epilogue'])]),
    # Function menu (START): 104x32 buttons, ???? cell left alone
    ('Common/Func/OBJ_hanyou_down_kinoumenu_parts.ncbr', buttons((104, 32), cols=range(6, 98)), [
        ((x * 104, y * 32, 104, 32), t) for y, row in enumerate([
            ('Save', 'Load'), ('Options', 'SP Officers'), ('BGM', 'Art of War'),   # セーブ ロード 環境設定 SP武将 BGM変更 兵法教書
            ('Demo Play', 'Quit Game'), ('Suspend', 'Check Goal')])                # デモプレイ ゲーム終了 中断 目標確認
        for x, t in enumerate(row)]),
    # Art of War topics: 基本 内政 軍事 / 人事 計略 外交 / 戦争 陣形 特殊能力
    ('Common/Func/OBJ_hanyou_down_heihoumenu_parts.ncbr', buttons((80, 32), cols=range(6, 74)), [
        ((x * 80, y * 32, 80, 32), t) for y, row in enumerate([
            ('Basics', 'Civil', 'Army'), ('Staff', 'Plots', 'Envoy'), ('War', 'Formation', 'Skills')])
        for x, t in enumerate(row)]),
    # In-game options: 標準 停止, confirm bar
    ('Common/Func/OBJ_hanyou_down_option_parts.ncbr', buttons((88, 24)), [
        ((0, 0, 88, 24), 'Normal'), ((88, 0, 88, 24), 'Wait')]),
    ('Common/Func/OBJ_hanyou_down_option_parts.ncbr', green((10, 36, 30)), [((40, 36, 90, 16), 'X  Confirm')]),
    ('Common/Func/OBJ_hanyou_down_BGM_parts.ncbr', green((82, 4, 30)), [((112, 4, 90, 16), 'X  Confirm')]),
    # Strategy officer commands (green 40x24 buttons; interior x+3..x+36, y+2..y+20)
    ('Stg/OBJ_stg_down_main_parts.ncbr', rowfill((1, 2, 3, 4, 11, 12, 13, 14, 15)), [
        ((x * 40 + 3, 160 + y * 24 + 2, 34, 19), t) for y, row in enumerate([
            ('Search', 'Recruit'), ('Reward', 'Appoint'), ('Items', 'Assign'), ('Feast', 'Train')])  # 捜索 登用 褒美 任命 アイテム 担当 酒宴 修行
        for x, t in enumerate(row)]),
    # Strategy sub-command buttons
    ('Stg/SubCom/OBJ_stg_third_cmd_button00.ncbr', plate((6, 4, 10)), grid([
        'Sell Rice', 'Buy Rice', 'Advisor',      # 米売 米買 参謀
        'Governor', 'General', 'Banish',         # 太守 将軍 追放
        'Bestow', 'Seize', 'Domestic',           # 授与 没収 内政
        'Military', 'Personnel', 'Scheme'])),    # 軍事 人事 計略
    ('Stg/SubCom/OBJ_stg_third_cmd_button01.ncbr', plate((78, 4, 14)), grid([
        'Diplomacy', 'Gold', 'Rice',             # 外交 金 米
        'Items', 'Diplomacy', 'Territory',       # アイテム 外交 領地
        'Retainers', 'Target', 'Officers',       # 配下 目標 武将
        'Battlefield'])),                        # 戦場
    # Start menu and new-game setup menus (lattice bars)
    ('Startup/StartMenu/OBJ_shoki_down_SM_parts.NCBR', bars(6, 192, 24, range(40, 152), 160),
     ['Continue', 'New Game', 'Battle Road', 'New Officer', 'Tutorial', 'Gallery']),
    ('Startup/NewLord/OBJ_shoki_down_newkunshumenu_parts.NCBR', bars(4, 176, 24, range(36, 140), 150),
     ['Add New Rulers', 'Set Cities', 'Reset', 'X  Confirm']),
    ('Startup/EditBushou/OBJ_shoki_down_newbushoumenu_parts.NCBR', bars(5, 176, 24, range(36, 140), 150),
     ['Add New Officers', 'Change Home & Status', 'Set All Ages', 'Reset', 'X  Confirm']),
    ('Startup/SpecialBushou/OBJ_shoki_down_SPbushoumenu_parts.NCBR', bars(4, 176, 24, range(36, 140), 150),
     ['Add SP Officers', 'Set Home & Status', 'Reset', 'X  Confirm']),
    # Options: gold toggle buttons and confirm bar
    ('Startup/Config/OBJ_shoki_down_option_parts.NCBR', buttons((88, 24)), [
        ((0, 0, 88, 24), 'Historical'), ((88, 0, 88, 24), 'Fictional'),     # 史実 仮想
        ((0, 24, 56, 24), 'Easy'), ((56, 24, 56, 24), 'Normal'), ((112, 24, 56, 24), 'Hard'),  # 初級 中級 上級
        ((0, 48, 88, 24), 'Normal'), ((88, 48, 88, 24), 'Wait'),           # 標準 停止
        ((0, 72, 88, 24), 'On'), ((88, 72, 88, 24), 'Off'),                # あり なし
    ]),
    # Scenario select bars (cells 0-10 in order, 11 = Heroes Unite, 12 = locked)
    ('Startup/Scenario/OBJ_shoki_down_sinario_parts.NCBR', scenarios(), [
        (0, ('184', 'Jan', 'Yellow Turbans')), (1, ('189', 'Dec', 'Luoyang Burns')),
        (2, ('196', 'Sep', 'Cao Cao Rises')), (3, ('201', 'Oct', 'Storm in Hebei')),
        (4, ('208', 'Nov', 'Dragon Rises')), (5, ('219', 'Jul', 'Three Kingdoms')),
        (6, ('234', 'Sep', 'Star Falls')), (7, ('184', 'May', 'Wandering Sage')),
        (8, ('187', 'Aug', 'Turbans/Hanzhong')), (9, ('200', 'Jan', 'Guandu')),
        (10, ('213', 'May', 'Liu Bei in Shu')), (11, ('184', 'May', 'Heroes Unite')),
        (12, ('???', '???', '???')),
    ]),
    ('Startup/ConfigCheck/OBJ_shoki_down_settei_parts.NCBR', scenarios(None, None, (42, 151), 0), [
        (1, ('Y  Change Ruler',)), (0, ('X  Start Game',))]),          # 君主武将変更 ゲーム開始
    # Title prompt (blue glow): ボタンを押すか / 下の画面をタッチしてください
    ('Startup/Title/OBJ_shoki_down_title_parts.NCBR',
     dict(kind='plate', fill=[1, 1, 2], outline=4, outline2=10, wood=lambda x, y: 0), [
        ((0, 16, 96, 16), 'Press a button or'), ((0, 0, 192, 16), 'touch the lower screen')]),
    # Save slot tag 最新
    ('Startup/SaveLoad/OBJ_shoki_down_saveload_parts.NCBR', dict(GOLD, fill=[15], inner=1, outer=0, stretch=()),
     [((0, 48, 32, 16), 'NEW')]),
    ('Startup/Config/OBJ_shoki_down_option_parts.NCBR', green((10, 100, 40)), [((40, 100, 96, 16), 'X  Confirm')]),
]

# Text in 1D-mapped character OBJ graphics (NCGR + NCER): (base, style, [(cell, text)])
# style: fill, outline, optional outer/bold/stretch/clip (see gfxtext.draw_cell)
OBJ_CELL_EDITS = [
    # Strategy top screen date glyphs: 年 -> '/', 月 -> blank, seasons
    ('Stg/OBJ_stg_up_main00', dict(fill=[15], outline=1, clip=True), [
        (11, '/'), (12, ' '), (13, 'Spr'), (14, 'Sum'), (15, 'Aut'), (16, 'Win')]),     # 年 月 春 夏 秋 冬
    # Unit selection tags: 攻撃側 守備側 (blue, pink), 共同軍 援軍
    ('Stg/SelUnit/OBJ_stg_up_butai1', dict(fill=[15, 15, 14], outline=1, bold=True, stretch=(1, 3, 5, 7, 9)), [
        (4, 'Attacker'), (5, 'Defender'), (6, 'Attacker'), (7, 'Defender')]),
    ('Stg/SelUnit/OBJ_stg_up_butai1', dict(fill=[15, 15, 14], outline=1), [
        (8, 'Allies'), (9, 'Aid'), (10, 'Allies'), (11, 'Aid')]),
]

def apply_obj_cells(rom, edits):
    low = {n.lower(): n for n in (rom.filenames.filenameOf(i) for i in range(len(rom.files))) if n}
    for base, style, labels in edits:
        cf = rom.filenames.idOf(low[base.lower() + '.ncgr'])
        raw = bytes(rom.files[cf])
        t = nitrogfx.Tiles(raw)
        cells = nitrogfx.Cells(rom.getFileByName(low[base.lower() + '.ncer']))
        for i, text in labels:
            oams = cells.cells[i]
            if 'oams' in style:
                oams = [oams[k] for k in style['oams']]
            x0, y0 = min(o['x'] for o in oams), min(o['y'] for o in oams)
            W = max(o['x'] + o['w'] for o in oams) - x0
            H = max(o['y'] + o['h'] for o in oams) - y0
            img = [[0] * W for _ in range(H)]
            if 'ops' in style or 'box' in style:   # keep the art
                for o in oams:
                    tw = o['w'] // 8
                    for k, ti in enumerate(nitrogfx.oam_tiles(cells, t, o)):
                        tp = t.tile(ti)
                        for yy in range(8):
                            for xx in range(8):
                                img[o['y'] - y0 + k // tw * 8 + yy][o['x'] - x0 + k % tw * 8 + xx] = tp[yy * 8 + xx]
            if 'ops' in style:                     # bgtext ops (inpaint / text) on the cell bitmap
                pal = nitrogfx.Palette(rom.getFileByName(low[base.lower() + '.nclr'])).colors
                bg = bgtext.BG.from_pixels([v for r in img for v in r], W, H, pal, t.bpp, oams[0]['pal'])
                for op in style['ops'](text):
                    getattr(bg, op[0])(*op[1:])
                img = [bg.px[y * W:(y + 1) * W] for y in range(H)]
            elif 'box' in style:                   # refill text pixels in box from the same row
                for o in oams:
                    tw = o['w'] // 8
                    for k, ti in enumerate(nitrogfx.oam_tiles(cells, t, o)):
                        tp = t.tile(ti)
                        for yy in range(8):
                            for xx in range(8):
                                img[o['y'] - y0 + k // tw * 8 + yy][o['x'] - x0 + k % tw * 8 + xx] = tp[yy * 8 + xx]
                flat = [v for r in img for v in r]
                bg = gfxtext.rowfill(flat, W, style['box'], style['text_vals'])
                gfxtext.draw_plate(flat, W, style['box'], text, style['fill'], style['outline'], bg, flat,
                                   bold=style.get('bold', False))
                img = [flat[y * W:(y + 1) * W] for y in range(H)]
            else:
                gfxtext.draw_cell(img, text, style['fill'], style['outline'], style.get('bold', False),
                                  style.get('stretch', ()), style.get('outer'), style.get('clip', False))
            for o in oams:
                tw = o['w'] // 8
                for k, ti in enumerate(nitrogfx.oam_tiles(cells, t, o)):
                    bx, by = o['x'] - x0 + k % tw * 8, o['y'] - y0 + k // tw * 8
                    t.set_tile(ti, [img[by + yy][bx + xx] for yy in range(8) for xx in range(8)])
        out = t.save()
        rom.files[cf] = ndspy.lz10.compress(out) if raw[:1] == b'\x10' else out
    return len(edits)

# VTA sheets: animation frames streamed into VRAM; every NCER cell uses the same OAM
# layout and frame f's OAM data sits at (f * per + tile * 4) * 32 bytes as a linear
# bitmap per OAM. (base, box, style, labels): labels are frame texts in order,
# drawn with rowfill cleaning inside box (x, y, w, h).
def banner(fill, outline, xscale=2, yscale=3):
    return dict(kind='banner', fill=fill, outline=outline, xscale=xscale, yscale=yscale)

HEXTEXT = dict(rowfill((1, 12, 13, 14, 15), fill=[15, 15, 14]), modebg=True)

VTA_EDITS = [
    ('Stg/SubCom/VTA_stg_sub_cmd', (3, 4, 34, 15), rowfill((3, 4, 12, 13, 14, 15), fill=[15], outline=12), [
        'Develop', 'Patrol', 'Trade', 'Enlist', 'Draft', 'Drill', 'Plunder', 'Move', 'Form', 'War', 'Search',
        'Recruit', 'Reward', 'Items', 'Appoint', 'Feast', 'Train', 'Assign', 'Rumor', 'Defect', 'Tigers', 'Incite',
        'Plot', 'Plant', 'Gift', 'Alliance', 'Study', 'Joint', 'Aid', 'Threat', 'Ruler', 'City', 'Officer',
        'Target', 'Vassals', 'Field']),
    # Button guide plates: [button glyph][label]; box from after the glyph to x = W - 3
    ('Common/Guide/VTA_stg_button_guide', (0, 3, 3, 14), dict(rowfill((1, 11, 12, 13, 14), fill=[1], outline=13), rowbg=(26, 40)), [
        (t, {'o': 14, 'L': 16, 'S': 24}[k]) for k, t in [
            ('o', 'Back'), ('o', 'Cancel'), ('o', 'None'), ('o', 'Ruler'), ('S', 'Rice'), ('o', 'OK'),  # B戻る B中止 B目標なし Y君主 SELECT米 X確定
            ('o', 'Cut In'), ('o', 'Items'), ('L', 'Map'), ('L', 'Sort'), ('S', 'All'), ('S', 'Open'),      # X割込 Xアイテム LR地図 LRソート SELECT一括 総展
            ('S', 'Even'), ('S', 'Init'), ('S', 'Opts'), ('S', 'Flip'), ('S', 'List'), ('o', 'Close'),      # 総配 初期 START機能 切替 一覧 B閉じる
            ('o', 'Clear'), ('o', 'All Off.'), ('o', 'Info'), ('o', 'Raise'), ('o', 'Flee'), ('S', 'Clr'),  # Y消去 Y全武将 Y情報 X育成 X退却 SELECTクリア
            ('o', 'Log'), ('S', 'Stop'), ('o', 'Next'), ('o', 'Back'), ('o', 'Done'), ('o', 'End Turn'),  # Xログ START中止 +進む +戻る Bログ終了 B命令終了
            ('o', 'Visit'), ('o', 'Prev.'), ('o', 'Next'), ('o', 'Listen'), ('o', 'Unset')]]),             # Y訪問 L前武将 R次武将 Y試聴 Y解除
    # Battle result banners 勝利 敗北 (8bpp)
    ('Hex/Effect/VTA_eiyuu_down_font_win', None, banner(
        [(246, 246, 172), (246, 238, 189), (238, 213, 90), (222, 189, 82), (197, 164, 74), (172, 148, 65),
         (139, 115, 57), (115, 90, 49)], (65, 49, 8), 2), ['Victory']),
    ('Hex/Effect/VTA_eiyuu_down_font_lose', None, banner(
        [(189, 115, 106), (180, 106, 98), (164, 90, 82), (148, 82, 74), (139, 65, 65), (123, 65, 57),
         (106, 49, 49), (98, 49, 41)], (32, 16, 16), 2), ['Defeat']),
    # Battle: weather / tactic plates (晴れ 曇り 雨 豪雨 大蛇火 火壁 雷光 隕石)
    ('Hex/Command/VTA_hex_down_parts_3kaisou', (3, 3, 50, 15), HEXTEXT, [
        'Clear', 'Cloudy', 'Rain', 'Downpour', 'Snake Fire', 'Fire Wall', 'Lightning', 'Meteor']),
    # Battle commands: 移動 攻撃 計略 特殊 陣形 方向
    ('Hex/Command/VTA_hex_down_parts_maincmd', (5, 3, 46, 17), HEXTEXT, [
        'Move', 'Attack', 'Scheme', 'Special', 'Formation', 'Facing']),
    # Battle tactics
    ('Hex/Command/VTA_hex_down_parts_subcmd', (3, 3, 50, 15), HEXTEXT, [
        'Normal', 'Assault', 'Joint', 'Arrows', 'Flame', 'Fire', 'Panic', 'Feud',      # 通常 突撃 一斉 弓矢 火矢 火計 混乱 同討
        'Order', 'Mystic', 'Rouse', 'Heal', 'Rain', 'Skies', 'Douse', 'Rocks',      # 収拾 仙術 鼓舞 治療 雨乞 天変 消火 落石
        'Divine', 'Lurk', 'Mirage', 'Hex', 'Cheer', 'Flood', 'Slide', 'Sneak',   # 占卜 伏兵 幻術 妖術 激励 水計 土砂 隠密
        'Pitfall', 'Taunt', 'Infiltrate', 'Sway', 'Incite', 'Turncoat', 'Fury', 'Spray',     # 落穴 挑発 潜入 心攻 扇動 寝返 奮迅 乱射
        'Rush', 'Wall', 'Blitz', 'Beast', 'Weapon', 'Duel']),                                   # 速攻 鉄壁 特攻 猛獣 兵器 一騎
    # Retreat: 単独部隊退却 全軍退却 待機武将退却
    ('Hex/Command/VTA_hex_down_parts_taikyakucmd', (6, 3, 100, 17), HEXTEXT, [
        'Retreat Unit', 'Retreat All', 'Retreat Reserves']),
    # Battle button guide (same plates as Common/Guide)
    ('Hex/Command/VTA_hex_down_parts_gaid', (0, 3, 3, 14), dict(rowfill((1, 11, 12, 13, 14), fill=[1], outline=13), rowbg=(26, 40)), [
        (t, {'o': 14, 'S': 24}[k]) for k, t in [
            ('o', 'Flee'), ('o', 'Info'), ('o', 'End Turn'), ('S', 'Opts'), ('o', 'Back'), ('S', 'Stop'), ('o', 'Go')]]),
    # X退却 Y情報 B命令終了 START機能 B戻る START中止 A実行
    # 開発 巡察 取引 募兵 徴兵 訓練 略奪 移動 編成 戦争 捜索 / 登用 褒美 アイテム 任命 酒宴 修行 担当 流言 作敵 駆虎 扇動
    # 工作 埋伏 進物 同盟 研究 共同 援助 脅迫 君主 都市 武将 / 目標 配下 戦場
]

def vta_frames(t, cells):
    """Frame f uses NCER cell f's OAM layout; frames are packed back to back, each OAM
    a linear bitmap starting at its tile number * 128 bytes. Returns [(W, H, read, write)]."""
    frames, base = [], 0                   # base in bytes
    bits = 8 if t.bpp == 8 else 4
    for oams in cells.cells:
        size = max(o['tile'] * 128 + -(-o['w'] * o['h'] * bits // 8 // 128) * 128 for o in oams)
        x0 = min(o['x'] for o in oams); y0 = min(o['y'] for o in oams)
        W = max(o['x'] + o['w'] for o in oams) - x0; H = max(o['y'] + o['h'] for o in oams) - y0
        def pos(o, i, x0=x0, y0=y0):
            return o['y'] - y0 + i // o['w'], o['x'] - x0 + i % o['w']
        def read(oams=oams, W=W, H=H, base=base, pos=pos):
            img = [[0] * W for _ in range(H)]
            for o in oams:
                for i in range(o['w'] * o['h']):
                    y, x = pos(o, i)
                    if bits == 8:
                        img[y][x] = t.data[base + o['tile'] * 128 + i]
                    else:
                        a = (base + o['tile'] * 128) * 2 + i
                        img[y][x] = t.data[a >> 1] >> 4 * (a & 1) & 15
            return img
        def write(img, oams=oams, base=base, pos=pos):
            for o in oams:
                for i in range(o['w'] * o['h']):
                    y, x = pos(o, i)
                    v = img[y][x]
                    if bits == 8:
                        t.data[base + o['tile'] * 128 + i] = v
                    else:
                        a = (base + o['tile'] * 128) * 2 + i
                        t.data[a >> 1] = t.data[a >> 1] & (0xF0 if a & 1 == 0 else 0x0F) | v << 4 * (a & 1)
        frames.append((W, H, read, write))
        base += size
    return frames

def apply_vta(rom, edits):
    low = {n.lower(): n for n in (rom.filenames.filenameOf(i) for i in range(len(rom.files))) if n}
    for base, box, style, labels in edits:
        fid = rom.filenames.idOf(low[base.lower() + '.ncbr'])
        raw = bytes(rom.files[fid])
        t = nitrogfx.Tiles(raw)
        cells = nitrogfx.Cells(rom.getFileByName(low[base.lower() + '.ncer']))
        frames = vta_frames(t, cells)
        rowbg = None
        if style.get('rowbg'):                     # one background value per row, voted over all frames
            from collections import Counter
            x0, x1 = style['rowbg']
            imgs = [fr[2]() for fr in frames]
            rowbg = [Counter(im[y][x] for im in imgs for x in range(x0, min(x1, len(im[0])))
                             if im[y][x] not in style['text_vals']).most_common(1)[0][0]
                     for y in range(max(len(im) for im in imgs))]
        modebg = {}
        if style.get('modebg'):                    # per-pixel vote over same-sized frames, ignoring text pixels
            from collections import Counter
            groups = {}
            for fr in frames:
                groups.setdefault((fr[0], fr[1]), []).append(fr[2]())
            tv = style['text_vals']
            near = lambda im, x, y: any(im[yy][xx] in tv for yy in range(max(0, y - 1), min(len(im), y + 2))
                                        for xx in range(max(0, x - 1), min(len(im[0]), x + 2)))
            for (gw, gh), imgs in groups.items():
                rowmode = [(Counter(im[y][x] for im in imgs for x in range(gw) if im[y][x] not in tv).most_common(1)
                            or [(0, 0)])[0][0] for y in range(gh)]
                modebg[(gw, gh)] = [[(Counter(im[y][x] for im in imgs if not near(im, x, y)).most_common(1) or
                                      [(rowmode[y], 0)])[0][0] for x in range(gw)] for y in range(gh)]
        if style.get('kind') == 'banner':          # big bold caps over a cleared frame, RGB -> nearest palette
            pal = nitrogfx.Palette(rom.getFileByName(low[base.lower() + '.nclr'])).colors
            near = lambda rgb: min(range(1, len(pal)), key=lambda k: sum((a - b) ** 2 for a, b in zip(pal[k], rgb)))
            for f, text in enumerate(labels):
                W, H, read, write = frames[f]
                m = gfxtext.render(text.upper(), stretch=())
                m = [[v for v in r for _ in range(style['xscale'])] for r in m for _ in range(style['yscale'])]
                m = gfxtext.pad(m, 2)
                r1 = gfxtext.dilate(m); r2 = gfxtext.dilate(r1)
                mh, mw = len(m), len(m[0])
                if mw > W or mh > H:
                    raise ValueError('%r is %dx%d, frame %dx%d' % (text, mw, mh, W, H))
                img = [[0] * W for _ in range(H)]
                ox, oy = (W - mw) // 2, (H - mh) // 2
                fill = [near(c) for c in style['fill']]; out = near(style['outline'])
                for y in range(mh):
                    for x in range(mw):
                        if m[y][x]:
                            img[oy + y][ox + x] = fill[min(len(fill) - 1, (y - 2) * len(fill) // max(1, mh - 4))]
                        elif r2[y][x]:
                            img[oy + y][ox + x] = out
                write(img)
            labels = []
        for f, text in enumerate(labels):
            if text is None:
                continue
            W, H, read, write = frames[f]
            fbox = box
            if isinstance(text, tuple):            # (text, x0): box runs from x0 to the frame's right border
                text, x0 = text
                fbox = (x0, box[1], W - box[2] - x0, box[3])
            img = read()
            flat = [v for r in img for v in r]
            if rowbg:
                bg = lambda x, y, y0=fbox[1]: rowbg[y0 + y]
            elif modebg:
                m = modebg[(W, H)]
                rf = gfxtext.rowfill(flat, W, fbox, style['text_vals'])
                bg = lambda x, y, m=m, b=fbox, rf=rf: m[b[1] + y][b[0] + x] if m[b[1] + y][b[0] + x] is not None else rf(x, y)
            else:
                bg = gfxtext.rowfill(flat, W, fbox, style['text_vals'], style['grow'])
            gfxtext.draw_plate(flat, W, fbox, text, style['fill'], style['outline'], bg, flat,
                               outline2=style['outline2'], bold=style['bold'])
            write([flat[y * W:(y + 1) * W] for y in range(H)])
        out = t.save()
        rom.files[fid] = ndspy.lz10.compress(out) if raw[:1] == b'\x10' else out
    return len(edits)

OBJ_CELL_EDITS += [
    # Officer info: アイテム overlay (text-only OAM over a plate)
    ('Common/Info/OBJ_hanyou_up_bushouinfo_parts', dict(fill=[15], outline=0, oams=[0]), [(14, 'Items')]),
    # City info: 商人 (merchant present) tag
    ('Common/Info/OBJ_hanyou_up_tosiinfo_parts', dict(fill=[1], outline=11, box=(3, 2, 25, 11), text_vals={1, 11, 12}),
     [(9, 'Shop')]),
]

SEAL = lambda text: [('fill', (0, 0, 48, 48)), ('fill', (4, 6, 40, 36), (82, 57, 24)), ('rect', (4, 6, 40, 36), (230, 213, 156), 2),
                     ('text', (4, 6, 40, 36), text, dict(font='bold', fill=[(255, 238, 172), (246, 222, 115), (222, 189, 65)],
                                                          outline=(49, 24, 0)), 'center')]

SCENARIOS = [('184', 'Jan', 'Yellow Turbans'), ('189', 'Dec', 'Luoyang Burns'), ('196', 'Sep', 'Cao Cao Rises'),
             ('201', 'Oct', 'Storm in Hebei'), ('208', 'Nov', 'Dragon Rises'), ('219', 'Jul', 'Three Kingdoms'),
             ('234', 'Sep', 'Star Falls'), ('184', 'May', 'Wandering Sage'), ('187', 'Aug', 'Turbans/Hanzhong'),
             ('200', 'Jan', 'Guandu'), ('213', 'May', 'Liu Bei in Shu'), ('184', 'May', 'Heroes Unite'), ('???', '???', '???')]

OBJ_CELL_EDITS += [
    # Settings confirmation: scenario title strip on the top screen
    ('Startup/ConfigCheck/OBJ_shoki_up_settei_parts', dict(fill=[15, 15, 14], outline=1),
     [(i, '%s  %s   %s' % sc) for i, sc in enumerate(SCENARIOS)]),
    # ...the game actually loads this copy (also used on the save/load screens)
    ('Startup/SaveLoad/OBJ_shoki_up_saveload_parts', dict(fill=[15, 15, 14], outline=1),
     [(i, '%s  %s   %s' % sc) for i, sc in enumerate(SCENARIOS)]),
    ('Startup/SaveLoad/OBJ_shoki_up_saveload_parts',                                   # 戦争中 tag
     dict(ops=lambda text: [('inpaint', (3, 3, 56, 22), 'light', 1),
                            ('text', (3, 3, 56, 22), text, dict(font='plain', fill=[(246, 246, 238)], outline=(74, 16, 8)), 'center')]),
     [(13, 'At War')]),
    # Gallery officer cards: faction tabs (8bpp, dark text on a light plate)
    ('Gallery/Bushou/OBJ_shoki_up_bshouC_parts256',
     dict(ops=lambda text: [('inpaint', (3, 2, 74, 19), 'notlight', 1),
                            ('text', (3, 3, 74, 17), text, dict(font='plain', fill=[(16, 16, 16)], outline=(205, 213, 189)), 'center')]),
     list(enumerate(['Cao Cao', 'Liu Bei', 'Sun Quan', 'Dong Zhuo', 'Yuan Shao', 'Liu Yan', 'Liu Biao', 'Zhang Jiao',
                     'He Jin', 'Gongsun Zan', 'Ma Teng', 'Others', 'Ancients', 'Water Margin']))),
    # 曹操軍 劉備軍 孫権軍 董卓軍 袁紹軍 劉焉軍 劉表軍 張角軍 何進軍 公孫瓚軍 馬騰軍 その他 いにしえ 水滸伝
    # Hero Battle Road: stat tags, result brush text, special-award seal
    ('Challenge/Growup/OBJ_eiyuu_up_ikusei_parts', dict(fill=[1, 1, 2], outline=15, outer=14, clip=True), [
        (0, 'War'), (1, 'Int'), (2, 'Pol'), (3, 'Cha')]),                                   # 武力 知力 政治 魅力
    ('Challenge/Score/OBJ_eiyuu_up_score_parts', dict(fill=[1, 2, 3, 5, 7], outline=15, outer=12, bold=True), [
        (5, 'Win!'), (6, 'Record!')]),                                                      # 勝利! 更新!
    ('Challenge/Score/OBJ_eiyuu_up_score_parts', dict(ops=SEAL), [(7, 'Bonus')]),          # 特別褒賞
    ('Challenge/Main/OBJ_eiyuu_up_main_parts', dict(ops=SEAL), [(5, 'Bonus')]),
    # Officer editor tab titles (8bpp overlays on the tab bar): 新武将作成 内容変更 削除
    ('EditBushou/EditMenu/OBJ_shoki_up_makemenu_parts256',
     dict(ops=lambda text: [('inpaint', (0, 0, 96, 22), 'dark', 3), ('text', (2, 1, 94, 20), text, TAB)]),
     [(0, 'New Officer'), (1, 'Edit Officer'), (2, 'Delete')]),
    # Battle top screen: 攻撃側 守備側, status tags 混乱 ぬかるみ 挑発 怪我, 兵器 marks
    ('Hex/Info/OBJ_hex_up_parts', dict(fill=[15, 15, 14], outline=1, bold=True), [
        (0, 'Attacker'), (1, 'Attacker'), (2, 'Defender'), (3, 'Defender')]),
    ('Hex/Info/OBJ_hex_up_parts', dict(fill=[15], outline=1, clip=True), [
        (31, 'Panic'), (32, 'Mud'), (33, 'Taunt'), (34, 'Hurt')]),
    ('Hex/Info/OBJ_hex_up_butai_parts', dict(fill=[15], outline=1, clip=True), [
        (14, 'Panic'), (15, 'Mud'), (16, 'Taunt'), (17, 'Hurt')]),
    ('Hex/Info/OBJ_hex_up_parts', dict(fill=[15], outline=1, box=(3, 2, 26, 11), text_vals={1, 15}), [
        (38, 'Siege'), (39, 'Siege')]),
]

# 8bpp NCBR cells (linear sheet t.w*8 px wide, OAM tile units of 2 tiles): (base, cell, ops)
NCBR8_EDITS = [
    # Battle Road start: "<army>軍 配下武将" header -> "<army> Army  Officers"
    ('Challenge/Start/OBJ_eiyuu_down_start_parts256', 0, [
        ('inpaint', (80, 0, 90, 16), 'light', 1),
        ('text', (82, 1, 24, 14), 'Army', dict(font='plain', fill=[(246, 246, 238)], outline=(24, 16, 8))),
        ('text', (110, 1, 60, 14), 'Officers', dict(font='plain', fill=[(255, 222, 115)], outline=(24, 16, 8)))]),
]

def apply_ncbr8(rom, edits):
    low = {n.lower(): n for n in (rom.filenames.filenameOf(i) for i in range(len(rom.files))) if n}
    for base, i, ops in edits:
        fid = rom.filenames.idOf(low[base.lower() + '.ncbr'])
        raw = bytes(rom.files[fid])
        t = nitrogfx.Tiles(raw)
        cells = nitrogfx.Cells(rom.getFileByName(low[base.lower() + '.ncer']))
        pal = nitrogfx.Palette(rom.getFileByName(low[base.lower() + '.nclr'])).colors
        sw = t.w * 8
        oams = cells.cells[i]
        x0 = min(o['x'] for o in oams); y0 = min(o['y'] for o in oams)
        W = max(o['x'] + o['w'] for o in oams) - x0; H = max(o['y'] + o['h'] for o in oams) - y0
        where = {}
        for o in oams:
            k = o['tile'] // 2
            tx, ty = k % t.w * 8, k // t.w * 8
            for y in range(o['h']):
                for x in range(o['w']):
                    where[(o['y'] - y0 + y) * W + o['x'] - x0 + x] = (ty + y) * sw + tx + x
        px = [t.data[where[k]] if k in where else 0 for k in range(W * H)]
        bg = bgtext.BG.from_pixels(px, W, H, pal, 8)
        for op in ops:
            getattr(bg, op[0])(*op[1:])
        for k, a in where.items():
            t.data[a] = bg.px[k]
        out = t.save()
        rom.files[fid] = ndspy.lz10.compress(out) if raw[:1] == b'\x10' else out
    return len(edits)

# Text baked into BG screens (see bgtext for the ops)
TAB = dict(font='bold', fill=[(255, 255, 238), (230, 230, 213), (213, 222, 197), (172, 180, 156), (139, 139, 123)],
           outline=(24, 24, 8), stretch=(1, 4, 7))
WHITE = dict(font='plain', fill=[(246, 246, 238), (246, 246, 238), (189, 197, 197)], outline=(24, 49, 74))
BLUE = dict(font='plain', fill=[(189, 222, 255)], outline=(16, 24, 49))
PINK = dict(font='plain', fill=[(255, 205, 205)], outline=(49, 16, 16))
YELLOW = dict(font='plain', fill=[(255, 222, 115), (238, 205, 106)], outline=(41, 41, 0))

def tab(title):
    """Upper-screen title tab (top-left, dark-outlined bold text on the light bar)."""
    return [('inpaint', (2, 0, 150, 21), 'dark', 3), ('text', (4, 2, 150, 19), title, TAB)]

def labels(x, y, step, texts, style, w=84, pred='yellow', grow=2):
    """Left-aligned labels at (x, y + i * step), each 12px tall."""
    ops = []
    for i, t in enumerate(texts):
        ops += [('inpaint', (x - 3, y + i * step - 2, w, 15), pred, grow), ('text', (x - 1, y + i * step - 2, w, 16), t, style)]
    return ops

S = 'Startup/'
BG_EDITS = [
    (S + 'Config/BG_shoki_up_option', tab('Options')),
    (S + 'Config/BG_shoki_down_option', labels(15, 31, 28, ['Mode', 'Difficulty', 'Msg. Speed', 'Carry Over'],
                                               WHITE, w=100, pred='bright', grow=3)),
    (S + 'ConfigCheck/BG_shoki_up_settei', tab('Confirm Settings') +
     labels(89, 69, 18, ['Cities', 'Officers', 'Mode', 'Difficulty', 'Msg. Speed', 'Carry Over'], YELLOW, w=82)),
    (S + 'EditBushou/BG_shoki_up_newbushoumenu', tab('New Officers')),
    (S + 'NewLord/BG_shoki_up_newkunshumenu', tab('New Rulers')),
    (S + 'SaveLoad/BG_shoki_up_load', tab('Load') + labels(89, 81, 18, ['Cities', 'Mode', 'Difficulty'], YELLOW, w=82)),
    (S + 'SaveLoad/BG_shoki_up_save', tab('Save') + labels(89, 81, 18, ['Cities', 'Mode', 'Difficulty'], YELLOW, w=82)),
    (S + 'Scenario/BG_shoki_up_sinario', tab('Select Scenario') +
     [('inpaint', (171, 31, 60, 18), 'yellow', 2), ('text', (172, 31, 60, 18), 'Rulers', YELLOW)]),
    (S + 'SpecialBushou/BG_shoki_up_SPbushoumenu', tab('SP Officers')),
    (S + 'StartMenu/BG_shoki_up_SM', tab('Start Menu')),
    (S + 'UserLord/BG_shoki_up_kunshusentaku', tab('Select Ruler')),
    # Strategy: ruler status (名声 金 米 兵士)
    ('Stg/BG_stg_up_main00', [('inpaint', (57, 17, 32, 18), 'bright', 1), ('text', (60, 18, 40, 16), 'Fame', WHITE)] +
     [op for y in (20, 37, 54) for op in [('inpaint', (165, y, 34, 17), 'bright', 1)]] +
     [('text', (160, 20, 37, 16), 'Gold', WHITE, 'right'), ('text', (160, 37, 37, 16), 'Rice', WHITE, 'right'),
      ('text', (160, 54, 37, 16), 'Troops', WHITE, 'right')]),
    ('Stg/BG_stg_up_tantou', [('inpaint', (3, 80, 120, 18), 'yellow', 2), ('text', (5, 81, 120, 16), 'Total Assignments', YELLOW)]),
    # Unit selection (陣形 兵士/参戦日数; 自軍兵力 敵軍兵力)
    ('Stg/SelUnit/BG_stg_down_butai1', [('inpaint', (90, 38, 135, 17), 'yellow', 2),
                                        ('text', (90, 39, 46, 16), 'Formation', YELLOW), ('text', (140, 39, 85, 16), 'Troops/Days', YELLOW)]),
    ('Stg/SelUnit/BG_stg_down_butai2', [('inpaint', (99, 29, 135, 17), 'yellow', 2),
                                        ('text', (99, 30, 46, 16), 'Formation', YELLOW), ('text', (149, 30, 85, 16), 'Troops/Days', YELLOW)]),
    # Common: in-game BGM / options / tabs
    ('Common/Func/BG_hanyou_down_BGM', labels(15, 27, 24, ['Spring', 'Summer', 'Autumn', 'Winter', 'War'], WHITE,
                                              w=80, pred='bright', grow=3)),       # 戦略・春 夏 秋 冬 / 戦争
    ('Common/Func/BG_hanyou_down_option', labels(15, 47, 28, ['Msg. Speed', 'BGM', 'Sound FX'], WHITE, w=80,
                                                 pred='bright', grow=3)),          # 表示時間 (BGM) 効果音
    ('Common/Func/BG_hanyou_up_BGM', tab('BGM')),
    ('Common/Func/BG_hanyou_up_heihou', tab('Art of War')),
    # Info screens
    ('Common/Info/BG_hanyou_up_bushouinfo',
     [op for x, t in zip((6, 60, 114, 168), ('War', 'Int', 'Pol', 'Cha'))
      for op in [('inpaint', (x - 1, 85, 25, 13), 'yellow', 1), ('text', (x - 1, 85, 30, 13), t, YELLOW)]] +
     labels(5, 177, 0, ['Skills'], YELLOW, w=70)),                                 # 武力 知力 政治 魅力 特殊能力
    ('Common/Info/BG_hanyou_up_item', labels(4, 98, 0, ['Effect'], YELLOW, w=70)),  # 特殊効果
    ('Common/Info/BG_hanyou_up_kunshuinfo1', labels(4, 130, 31, ['Weapons Dev.', 'Joint Ops'], YELLOW, w=70)),  # 兵器開発 共同作戦
    # Duel: 対 -> VS
    ('Hex/Ikki/00_BG/BG_ikki_up_main', [
        ('inpaint', (100, 52, 58, 56), 'gold', 2),
        ('text', (100, 52, 58, 56), 'VS', dict(font='bold', xscale=2, yscale=2,
                                               fill=[(255, 246, 205), (238, 230, 172), (238, 222, 123), (205, 180, 90)],
                                               outline=(49, 41, 49)), 'center')]),
    # Officer editor
    ('EditBushou/Ability/BG_shoki_down_nouryoku', labels(15, 32, 28, ['War', 'Int', 'Pol', 'Cha'], WHITE, w=34,
                                                       pred='bright', grow=2)),                 # 武力 知力 政治 魅力
    ('EditBushou/Charactor/BG_shoki_down_setetc', labels(15, 31, 28, ['Duty', 'Ambit.', 'Calm', 'Brave'], WHITE, w=34,
                                                       pred='bright', grow=2)),                 # 義理 野望 冷静 勇猛
    ('EditBushou/GoodEvil/BG_shoki_down_zenaku', labels(15, 59, 28, ['Morality', 'Life'], WHITE, w=60,
                                                       pred='bright', grow=2)),                 # 善悪 寿命
    ('EditBushou/EditMenu/BG_shoki_up_makemenu',
     [op for x, t in zip((6, 60, 114, 168), ('War', 'Int', 'Pol', 'Cha'))
      for op in [('inpaint', (x - 1, 89, 25, 13), 'yellow', 1), ('text', (x - 1, 89, 30, 13), t, YELLOW)]] +
     labels(5, 106, 48, ['Formations', 'Skills'], YELLOW, w=86)),                              # 使用可能陣形 特殊能力
    ('EditBushou/Formation/BG_shoki_down_jinkei', [('inpaint', (79, 26, 98, 16), 'bright', 1),
                                                    ('text', (79, 26, 98, 16), 'Formations', WHITE, 'center')]),
    ('EditBushou/SpAbility/BG_shoki_down_tokushu', [('inpaint', (83, 26, 64, 16), 'bright', 1),
                                                     ('text', (86, 26, 82, 16), 'Skills', WHITE, 'center')]),
    ('EditBushou/InpName/BG_shoki_down_nameinput', [('inpaint', (79, 26, 17, 15), 'bright', 1),
                                                     ('text', (75, 26, 24, 15), 'Name', WHITE, 'center')]),
    ('EditBushou/InpName/BG_shoki_down_nameset', [('inpaint', (79, 26, 17, 15), 'bright', 1),
                                                   ('text', (75, 26, 24, 15), 'Name', WHITE, 'center')]),
    ('EditBushou/InpName/BG_shoki_down_nameread', [('inpaint', (41, 26, 17, 15), 'bright', 1),
                                                    ('text', (37, 26, 24, 15), 'Name', WHITE, 'center')]),
    ('EditBushou/TopMenu/BG_shoki_up_newbushoutouroku', tab('Officer Registry')),          # 新武将登録
    # Hero Battle Road
    ('Challenge/Growup/BG_eiyuu_up_ikusei', tab('Train Officer') +
     labels(32, 108, 21, ['War', 'Int', 'Pol', 'Cha'], YELLOW, w=30)),                     # 武将育成 / 武力 知力 政治 魅力
    ('Challenge/Growup/BG_eiyuu_up_ikuseiseitaku', tab('Train Officer') + labels(6, 121, 51, ['Formations', 'Skills'], YELLOW, w=70)),
    ('Challenge/Hensei/BG_eiyuu_up_bushousentaku', tab('Select Officers') + labels(6, 121, 51, ['Formations', 'Skills'], YELLOW, w=70)),
    ('Challenge/Hensei/BG_eiyuu_up_jinkei', tab('Select Formation') + labels(6, 121, 51, ['Formations', 'Skills'], YELLOW, w=70)),
    ('Challenge/Touyou/BG_eiyuu_up_touyou_bushouinfo', tab('Recruit Officer') + labels(6, 121, 51, ['Formations', 'Skills'], YELLOW, w=70)),
    ('Challenge/Touyou/BG_eiyuu_up_touyou', tab('Recruit Officer') + labels(3, 108, 46, ['Need', 'Have'], YELLOW, w=34)),  # 必要 所持
    ('Challenge/Hensei/BG_eiyuu_up_butaihensei', tab('Form Units') + [('inpaint', (46, 112, 30, 14), 'bright', 1),
                                                                     ('text', (40, 112, 42, 14), 'Rating', WHITE, 'center')]),  # 部隊編成 評価
    ('Challenge/Main/BG_eiyuu_up_main', tab('Select Stage') + [('inpaint', (46, 112, 30, 14), 'bright', 1),
                                                              ('text', (40, 112, 42, 14), 'Rating', WHITE, 'center')]),
    ('Challenge/Score/BG_eiyuu_up_score', tab('Record') + [('inpaint', (46, 112, 30, 14), 'bright', 1),
                                                          ('text', (40, 112, 42, 14), 'Rating', WHITE, 'center')]),      # 戦績
    ('Challenge/Start/BG_eiyuu_up_nameinput', tab('Enter Army Name')),
    ('Challenge/Score/BG_eiyuu_down_score', [('inpaint', (8, 21, 52, 18), 'light', 2), ('text', (9, 23, 60, 16), 'Spoils', YELLOW)]),                          # 軍団名入力
    ('Challenge/Start/BG_eiyuu_down_nameinput', [('inpaint', (79, 26, 17, 15), 'bright', 1),
                                                 ('text', (75, 26, 24, 15), 'Name', WHITE, 'center')]),
    ('Challenge/Start/BG_eiyuu_down_nameset', [('inpaint', (79, 26, 17, 15), 'bright', 1),
                                               ('text', (75, 26, 24, 15), 'Name', WHITE, 'center')]),
    # Gallery / tutorial
    ('Gallery/Bushou/BG_shoki_up_bshouC',
     [op for (x, y, w), t in [((128, 65, 15), 'War'), ((92, 102, 14), 'Int'), ((182, 102, 15), 'Pol'), ((128, 154, 15), 'Cha')]
      for op in [('inpaint', (x - 2, y - 1, w + 4, 16), 'bright', 1),
                 ('text', (x + w // 2 - 15, y - 1, 30, 16), t, WHITE, 'center')]] +                # 武 知 政 魅
     [op for y, t in zip((115, 130, 145, 160), ('Duty', 'Ambit.', 'Calm', 'Brave'))
      for op in [('inpaint', (24, y, 28, 13), 'yellow', 2),
                 ('text', (20, y, 34, 13), t, dict(YELLOW, outline=(0, 0, 0)), 'center')]]),        # 義理 野望 冷静 勇猛
    ('Gallery/Item/BG_shoki_up_item', tab('Items') + labels(3, 127, 0, ['Effect'], YELLOW, w=60)),  # アイテム 特殊効果
    ('Gallery/Menu/BG_shoki_up_gallery', tab('Gallery')),
    ('Tutorial/BG_tut_up_menu', tab('Tutorial')),
    # Battle (Hex) top screens
    ('Hex/Info/BG_eiyuu_up_mokuhyou', tab('Check Goal')),                          # 目標確認
    ('Hex/Info/BG_hex_up_butai', [op for (x, y, w), t in [((49, 84, 15), 'War'), ((13, 121, 14), 'Int'),
                                                          ((103, 121, 15), 'Pol'), ((49, 173, 15), 'Cha')]
                                  for op in [('inpaint', (x - 2, y - 1, w + 4, 16), 'bright', 1),
                                             ('text', (x + w // 2 - 15, y - 1, 30, 16), t, WHITE, 'center')]]),  # 武 知 政 魅
    ('Hex/Info/BG_Hex_up_main',
     [op for x in (18, 186) for y, t in ((57, 'Unit'), (74, 'Men'), (90, 'Rice'))                 # 部隊 兵 米
      for op in [('inpaint', (x - 2, y - 1, 28, 14), 'yellow', 1), ('text', (x - 1, y - 1, 34, 14), t, YELLOW)]] +
     [op for (x, y, w, bw), t in [((56, 126, 11, 30), 'Men'), ((56, 143, 23, 48), 'War'), ((109, 143, 54, 56), 'Atk/Def'),
                                  ((56, 160, 23, 48), 'Drill'), ((109, 160, 54, 56), 'Bow A/D'),
                                  ((56, 177, 23, 48), 'Morale'), ((109, 177, 23, 50), 'Mobility'), ((164, 177, 23, 30), 'Range')]
      for op in [('inpaint', (x - 1, y - 1, w + 2, 13), 'bright', 0), ('text', (x - 1, y - 2, bw, 15), t, WHITE)]]),
     # 兵 武力 攻撃/防御 訓練 弓攻/弓防 士気 機動 射程
] + [('Stg/SelUnit/BG_stg_up_butai%d' % i, [
        ('inpaint', (3, 119, 64, 18), 'blue', 2), ('text', (5, 120, 80, 16), 'Our Forces', BLUE),
        ('inpaint', (189, 119, 64, 18), 'pink', 2), ('text', (170, 120, 80, 16), 'Enemy Forces', PINK, 'right')])
     for i in (1, 2)]

def apply(rom):
    n = bgtext.apply(rom, BG_EDITS) + apply_obj_cells(rom, OBJ_CELL_EDITS) + apply_vta(rom, VTA_EDITS) + apply_ncbr8(rom, NCBR8_EDITS)
    for name, style, labels in EDITS:
        fid = rom.filenames.idOf(name)
        if fid is None:
            raise KeyError(name)
        raw = bytes(rom.files[fid])
        t = nitrogfx.Tiles(raw)
        px = []
        for b in t.data:
            px += [b & 15, b >> 4]
        w = t.w * 8
        orig = list(px)
        if style['kind'] == 'bars':
            bw, bh = style['size']
            sx = style['strip_x']
            fb = lambda x, y, o=style['origins'][0]: 0 if y < 15 else orig[(o[1] + y) * w + o[0] + sx + x % 8]
            clean, (x0, _, x1, _) = gfxtext.clean_by_extent(orig, w, style['origins'], bw, bh, {14, 15},
                                                            range(2, 13), fallback=fb, cols=style['cols'])
            for (ox, oy), text in zip(style['origins'], labels):
                if text:
                    gfxtext.draw_plate(px, w, (ox + x0, oy, x1 - x0, bh), text, style['fill'], style['outline'],
                                       lambda x, y, c=clean, a=x0: c[y][x + a], orig, outline2=style['outline2'])
            labels = []
        if style['kind'] == 'scenario':
            draw_scenarios(rom, name, style, labels, px, orig, w)
            labels = []
        if style['kind'] == 'headers':
            draw_headers(rom, name, style, labels, px, w)
            labels = []
        if style['kind'] == 'rowfill':
            for box, text in labels:
                bg = gfxtext.rowfill(orig, w, box, style['text_vals'], style['grow'])
                gfxtext.draw_plate(px, w, box, text, style['fill'], style['outline'], bg, orig,
                                   outline2=style['outline2'], bold=style['bold'])
            labels = []
        if style['kind'] == 'buttons':
            fw, fh = style['full']
            origins = [b[:2] for b, _ in labels if b[2:] == (fw, fh)]
            clean, _ = gfxtext.clean_by_extent(orig, w, origins, fw, fh, style['text_vals'], range(4, fh - 4),
                                               fallback=lambda x, y: None, cols=style['cols'], mirror=False)
            gfxtext.fill_gaps(clean, style['cols'][0], style['cols'][-1])
            for (bx, by, bw, bh), text in labels:
                half = bw // 2
                lines = text.split('\n')
                for k, line in enumerate(lines):     # two-line labels: rows at y+3 and y+19, 15px tall
                    box = (bx, by, bw, bh) if len(lines) == 1 else (bx, by + 3 + k * 16, bw, 15)
                    oy = box[1] - by
                    bg = lambda x, y, h=half, bw=bw, oy=oy: clean[y + oy][x if x < h else fw - bw + x]
                    gfxtext.draw_plate(px, w, box, line, style['fill'], style['outline'], bg, orig,
                                       bold=style['bold'])
            labels = []
        for box, text in labels:
            if style['kind'] == 'emboss':
                gfxtext.draw(px, w, box, text, style['fill'], style['inner'], style['outer'],
                             stretch=style.get('stretch', (1, 4, 7)))
            else:
                gfxtext.draw_plate(px, w, box, text, style['fill'], style['outline'], style['wood'], orig,
                                   bold=style.get('bold', False), outline2=style.get('outline2'))
        t.data[:] = bytes(px[k] | px[k + 1] << 4 for k in range(0, len(px), 2))
        out = t.save()
        rom.files[fid] = ndspy.lz10.compress(out) if raw[:1] == b'\x10' else out
        n += 1
    return n
