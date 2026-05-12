"""生成 Pix Web 主页范例素材图。

该脚本使用项目内的 pix.pixelize 管线把程序化草图压成真实像素 PNG，
输出到 apps/web/public/homepage-examples，并同步生成前端 manifest。
"""

from __future__ import annotations

import colorsys
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from pix.pixelize.core import PixelizeParams, pixelize

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "apps" / "web" / "public" / "homepage-examples"
ITEM_DIR = PUBLIC_DIR / "items"
UI_DIR = PUBLIC_DIR / "ui"
MANIFEST_TS = ROOT / "apps" / "web" / "src" / "homepageExamples.ts"

ITEM_SUFFIX = (
    "pixel art, 16-bit style, transparent background, game asset, crisp pixels, "
    "no anti-aliasing, sprite sheet layout, 32x32 per item"
)
UI_SUFFIX = (
    "pixel art UI, game interface, 16-bit RPG style, clean pixel borders, readable icons, "
    "no anti-aliasing, 1920x1080 showcase layout"
)

RAW_TABLE = r"""
| 01 | 东方 | 武侠 | pixel art wuxia items, ink-wash sword, bamboo flute, jade pendant, silk scroll, iron fan, copper coins, tea set, muted ink black red jade green palette | pixel art wuxia UI, rice paper texture, ink brush borders, bamboo frames, red seal icons, calligraphy fonts, jade green accents | 01_wuxia_item.png | 01_wuxia_ui.png |
| 02 | 东方 | 仙侠修真 | pixel art cultivation items, glowing spirit stones, jade pill bottles, flying sword, taoist talismans, bagua mirror, celestial robe, cyan purple gold palette | pixel art xianxia UI, cloud pattern borders, golden immortal frames, bagua symbols, nebula background, jade buttons | 02_xianxia_item.png | 02_xianxia_ui.png |
| 03 | 东方 | 玄幻 | pixel art xuanhuan items, flaming heavenly sword, dragon scale armor, phoenix feather, pill cauldron, soul orb, ancient tome, red gold black palette | pixel art xuanhuan UI, dragon-carved frames, fire lightning borders, gold ancient script, crimson panels, beast totem icons | 03_xuanhuan_item.png | 03_xuanhuan_ui.png |
| 04 | 东方 | 古风宫廷 | pixel art palace items, phoenix hairpin, jade seal, silk fan, porcelain vase, incense burner, embroidered robe, crimson gold ivory palette | pixel art palace UI, ornate gold dragon phoenix borders, red lacquer panels, pearl ornaments, silk curtain frames, imperial yellow | 04_palace_item.png | 04_palace_ui.png |
| 05 | 东方 | 神话志怪 | pixel art Shan Hai Jing items, nine-tailed fox charm, jade rabbit, bronze mask, mystic gourd, peach of immortality, ghost lantern, teal gold palette | pixel art mythology UI, bronze oracle bone borders, mountain silhouette, star constellation icons, mystic fog, jade copper accents | 05_myth_item.png | 05_myth_ui.png |
| 06 | 东方 | 三国演义 | pixel art Three Kingdoms items, guandao halberd, general helmet, war drum, strategy scroll, command seal, wine jug, earth red black bronze palette | pixel art war UI, wooden camp borders, leather map panels, bronze seal icons, crimson banners, ink strategy script | 06_sanguo_item.png | 06_sanguo_ui.png |
| 07 | 东方 | 日式和风 | pixel art wafu items, katana, oni mask, paper lantern, folding fan, sake bottle, tatami, sakura branch, red black white sakura pink palette | pixel art Japanese UI, shoji paper frames, torii gate borders, sakura petals, ink brush headers, red seal buttons, washi texture | 07_wafu_item.png | 07_wafu_ui.png |
| 08 | 东方 | 现代修仙 | pixel art urban cultivation items, smartphone with taoist app, glowing jade bracelet, talisman card, briefcase sword, neon jade city grey palette | pixel art modern xianxia UI, holographic taoist symbols, neon jade frames, city skyline, modern app icons with ancient patterns | 08_urbanxian_item.png | 08_urbanxian_ui.png |
| 09 | 西幻 | 高魔奇幻 | pixel art high fantasy items, enchanted longsword, spellbook, mana potion, crystal staff, elven bow, dwarven hammer, dragon shield, blue gold emerald palette | pixel art high fantasy UI, ornate gold filigree borders, parchment panels, gem buttons, mythical creature icons, tavern warm colors | 09_highfantasy_item.png | 09_highfantasy_ui.png |
| 10 | 西幻 | 低魔奇幻 | pixel art low fantasy items, worn iron sword, leather journal, rusty dagger, bread cheese, tin cup, crude map, oil lantern, muted brown grey palette | pixel art low fantasy UI, worn leather borders, ink-stained paper, iron rivets, dark wood panels, faded heraldry | 10_lowfantasy_item.png | 10_lowfantasy_ui.png |
| 11 | 西幻 | 剑与魔法 | pixel art sword sorcery items, barbarian broadsword, bone amulet, skull cup, tribal axe, fur cloak, crude idol, blood red bronze bone palette | pixel art barbarian UI, carved bone borders, blood-stained parchment, tribal totem icons, rough stone panels, primitive feel | 11_swordsorcery_item.png | 11_swordsorcery_ui.png |
| 12 | 西幻 | 黑暗奇幻 | pixel art dark fantasy items, cursed greatsword, bloody chalice, rotting tome, tarnished crown, black candle, plague mask, desaturated blood red black palette | pixel art dark fantasy UI, rusted iron borders, blood-splattered panels, gothic cathedral arches, bone ornaments, hollow eye icons | 12_darkfantasy_item.png | 12_darkfantasy_ui.png |
| 13 | 西幻 | 中世纪写实 | pixel art realistic medieval items, arming sword, chainmail, wooden shield, leather boots, iron helm, bread, barrel, realistic earth tone palette | pixel art medieval UI, wooden plank borders, parchment scrolls, heraldic shields, iron buckles, leather straps, historical feel | 13_medieval_item.png | 13_medieval_ui.png |
| 14 | 西幻 | 童话绘本 | pixel art fairytale items, glass slipper, magic beanstalk seed, red riding hood cape, poisoned apple, fairy wand, gingerbread, pastel pink mint gold palette | pixel art storybook UI, pop-up book frames, pastel ribbon borders, flower buttons, fairy icons, whimsical soft colors | 14_fairytale_item.png | 14_fairytale_ui.png |
| 15 | 西幻 | 北欧神话 | pixel art Norse items, Mjolnir hammer, rune stone, drinking horn, viking axe, wolf pelt, gold arm ring, yggdrasil branch, icy blue bronze red palette | pixel art Norse UI, carved wooden rune borders, knotwork patterns, viking shield panels, frost textures, bronze rivets | 15_norse_item.png | 15_norse_ui.png |
| 16 | 西幻 | 凯尔特德鲁伊 | pixel art celtic druid items, twisted wooden staff, mistletoe, celtic knot amulet, wicker basket, ogham stones, cauldron, forest green gold brown palette | pixel art celtic UI, knotwork spiral borders, ivy-covered frames, stone circle panels, oak leaf ornaments, mossy green | 16_celtic_item.png | 16_celtic_ui.png |
| 17 | 西幻 | 希腊罗马神话 | pixel art Greek items, laurel wreath, golden trident, olive branch, marble bust, wine amphora, bronze shield, spartan helmet, marble white gold ocean blue palette | pixel art Greek UI, marble column borders, laurel leaf frames, gold meander pattern, classical statue icons, Mediterranean blue | 17_greek_item.png | 17_greek_ui.png |
| 18 | 西幻 | 埃及神话 | pixel art Egyptian items, ankh key, scarab amulet, canopic jar, golden mask, pharaoh crown, papyrus scroll, was scepter, gold lapis turquoise sand palette | pixel art Egyptian UI, hieroglyph borders, pyramid frames, gold sun disk icons, papyrus texture, obelisk panels | 18_egyptian_item.png | 18_egyptian_ui.png |
| 19 | 科幻 | 硬科幻 | pixel art hard sci-fi items, plasma rifle, magnetic boots, data chip, oxygen tank, EVA helmet, fusion cell, white steel blue palette | pixel art hard sci-fi UI, minimalist HUD, white steel panels, blue holographic borders, scientific readouts, grid background | 19_hardscifi_item.png | 19_hardscifi_ui.png |
| 20 | 科幻 | 太空歌剧 | pixel art space opera items, laser sword, starship key, alien artifact, cosmic gem, commander badge, plasma blaster, deep purple gold chrome palette | pixel art space opera UI, starship bridge borders, galactic map backgrounds, glowing blue panels, alien symbol icons, chrome frames | 20_spaceopera_item.png | 20_spaceopera_ui.png |
| 21 | 科幻 | 赛博朋克 | pixel art cyberpunk items, cyber katana, neural implant chip, holo-phone, energy drink, cyber arm, data shard, neon pink cyan purple black palette | pixel art cyberpunk UI, glitchy neon borders, holographic panels, pink cyan glow, hexagonal tech frames, scrolling code background | 21_cyberpunk_item.png | 21_cyberpunk_ui.png |
| 22 | 科幻 | 蒸汽朋克 | pixel art steampunk items, brass goggles, gear mechanism, pocket watch, steam pistol, pressure gauge, leather top hat, brass copper leather palette | pixel art steampunk UI, brass gear borders, pressure gauge meters, riveted copper panels, victorian filigree, clockwork icons | 22_steampunk_item.png | 22_steampunk_ui.png |
| 23 | 科幻 | 柴油朋克 | pixel art dieselpunk items, tommy gun, gas mask, zeppelin key, leather aviator cap, propaganda poster, fuel canister, military olive rust orange palette | pixel art dieselpunk UI, riveted metal borders, industrial warning stripes, art deco frames, stenciled fonts, oil-stained panels | 23_dieselpunk_item.png | 23_dieselpunk_ui.png |
| 24 | 科幻 | 生物朋克 | pixel art biopunk items, pulsating flesh sword, DNA vial, organic implant, bio-syringe, eyeball jar, sickly green flesh pink purple palette | pixel art biopunk UI, veiny pulsing borders, organic membrane panels, DNA helix icons, flesh-textured frames, sickly glow | 24_biopunk_item.png | 24_biopunk_ui.png |
| 25 | 科幻 | 原子朋克 | pixel art atompunk items, ray gun, vacuum tube radio, atomic soda bottle, 50s lunchbox, geiger counter, chrome robot, retro turquoise red chrome palette | pixel art atompunk UI, chrome rounded borders, atomic symbol icons, retro-futuristic panels, turquoise red accents, 1950s feel | 25_atompunk_item.png | 25_atompunk_ui.png |
| 26 | 科幻 | 太阳朋克 | pixel art solarpunk items, vine-wrapped solar panel, seed pouch, clean water flask, bamboo bicycle, eco-phone, lush green gold sky blue palette | pixel art solarpunk UI, living vine borders, leaf-shaped frames, solar panel icons, clean panels, nature-tech fusion | 26_solarpunk_item.png | 26_solarpunk_ui.png |
| 27 | 科幻 | 废土末日 | pixel art wasteland items, rusty pipe wrench, scrap armor, contaminated water bottle, gas mask, makeshift rifle, radiation pill, rust brown grey toxic green palette | pixel art wasteland UI, rusted metal borders, duct tape patches, cracked screen panels, hazard icons, scavenged feel | 27_wasteland_item.png | 27_wasteland_ui.png |
| 28 | 科幻 | 近未来 | pixel art near-future items, smart glasses, drone, encrypted USB, tactical jacket, hacking laptop, branded coffee cup, muted tech blue grey palette | pixel art near-future UI, minimalist app-like panels, subtle holographic accents, corporate clean frames, smartphone icons | 28_nearfuture_item.png | 28_nearfuture_ui.png |
| 29 | 恐怖 | 克苏鲁 | pixel art cosmic horror items, forbidden tome, tentacle idol, ritual dagger, old revolver, sanity pill, strange artifact, sickly green deep teal black palette | pixel art cosmic horror UI, tentacle borders, forbidden symbol icons, crumbling parchment, sanity meter, non-euclidean shapes | 29_cthulhu_item.png | 29_cthulhu_ui.png |
| 30 | 恐怖 | 哥特恐怖 | pixel art gothic horror items, silver cross, holy water vial, wooden stake, candelabra, bloody chalice, coffin key, deep crimson black silver palette | pixel art gothic UI, stained glass borders, cathedral arch frames, wrought iron panels, bat silhouette icons, candlelit dark red | 30_gothic_item.png | 30_gothic_ui.png |
| 31 | 恐怖 | 丧尸生化 | pixel art zombie horror items, blood-stained shotgun, herb kit, bandage, crowbar, canned food, emergency flare, blood red military green grey palette | pixel art survival horror UI, blood-splattered borders, torn paper panels, broken HUD, warning red, ammo counter icons | 31_zombie_item.png | 31_zombie_ui.png |
| 32 | 恐怖 | 心理恐怖 | pixel art psychological horror items, rusted knife, pill bottle, broken mirror shard, old photograph, flickering flashlight, fog grey sickly yellow palette | pixel art psychological horror UI, distorted glitchy borders, fog-filled panels, static noise background, asymmetric frames | 32_psycho_item.png | 32_psycho_ui.png |
| 33 | 恐怖 | 都市怪谈 | pixel art urban legend items, cursed doll, red envelope, haunted phone, convenience store receipt, ofuda charm, neon pink eerie green grey palette | pixel art urban legend UI, convenience store glow panels, vending machine frames, subway sign borders, eerie neon icons | 33_urbanlegend_item.png | 33_urbanlegend_ui.png |
| 34 | 恐怖 | 民俗恐怖 | pixel art folk horror items, straw doll, ritual knife, old incense, yellowed talisman, clay idol, burial shroud, earthy brown yellow ritual red palette | pixel art folk horror UI, woven bamboo borders, ancient paper talismans, rural village panels, temple bell icons | 34_folkhorror_item.png | 34_folkhorror_ui.png |
| 35 | 恐怖 | Analog复古恐怖 | pixel art analog horror items, VHS tape, CRT remote, broadcast badge, static photo, emergency broadcast card, VHS color bleed red green blue palette | pixel art analog horror UI, VHS static borders, scanline overlays, emergency broadcast panels, distorted text, 1990s TV | 35_analoghorror_item.png | 35_analoghorror_ui.png |
| 36 | 恐怖 | 身体恐怖 | pixel art body horror items, pulsing flesh weapon, bone spike, mutated organ, surgical saw, mutation vial, raw flesh pink bone white bile green palette | pixel art body horror UI, fleshy membrane borders, bone fragment frames, veiny panels, mutation gauge, visceral icons | 36_bodyhorror_item.png | 36_bodyhorror_ui.png |
| 37 | 现代 | 现代都市 | pixel art modern city items, smartphone, coffee cup, car keys, leather wallet, earbuds, energy bar, clean grey white accent palette | pixel art modern UI, flat clean panels, app-style icons, rounded rectangles, smartphone-like interface, minimalist | 37_modern_item.png | 37_modern_ui.png |
| 38 | 现代 | 校园青春 | pixel art school items, textbook, pencil case, bento box, sports whistle, student ID, love letter, cherry blossom pink sky blue navy palette | pixel art school UI, notebook paper borders, sticky note panels, doodle decorations, cute sticker icons, cheerful colors | 38_school_item.png | 38_school_ui.png |
| 39 | 现代 | 黑帮黑道 | pixel art yakuza mafia items, tattoo pen, gold watch, cigar, handgun in case, whiskey bottle, business card, black gold blood red palette | pixel art gangster UI, gold ornate borders, leather panels, smoky background, tattoo art icons, luxurious underworld | 39_gangster_item.png | 39_gangster_ui.png |
| 40 | 现代 | 警匪侦探 | pixel art detective items, magnifying glass, revolver, case file, evidence bag, fedora, notepad, noir grey brown file yellow palette | pixel art detective noir UI, evidence board borders, newspaper panels, red string connections, case file frames, noir tone | 40_detective_item.png | 40_detective_ui.png |
| 41 | 现代 | 军事战争 | pixel art military items, assault rifle, dog tags, combat knife, MRE pack, grenade, combat helmet, olive drab desert tan black palette | pixel art military UI, ammo box borders, tactical HUD, camo panels, warning stripe icons, rugged field manual | 41_military_item.png | 41_military_ui.png |
| 42 | 现代 | 谍战特工 | pixel art spy items, silenced pistol, briefcase, hidden camera, fake passport, listening device, martini glass, charcoal grey black silver palette | pixel art spy UI, sleek black borders, surveillance screen panels, red alert icons, classified stamps, 60s spy elegance | 42_spy_item.png | 42_spy_ui.png |
| 43 | 历史 | 古代文明 | pixel art ancient civilization items, golden idol, stone tablet, obsidian blade, feathered headdress, ceremonial mask, clay pot, earthy gold jade palette | pixel art ancient civilization UI, carved stone borders, glyph patterns, temple pyramid panels, tribal icons, dusty relic | 43_ancient_item.png | 43_ancient_ui.png |
| 44 | 历史 | 大航海时代 | pixel art age of sail items, cutlass, treasure map, spyglass, compass, pirate hat, rum bottle, gold doubloon, ocean blue parchment gold palette | pixel art pirate UI, rope borders, weathered parchment panels, compass rose, wooden ship frames, treasure icons | 44_pirate_item.png | 44_pirate_ui.png |
| 45 | 历史 | 工业革命 | pixel art industrial revolution items, coal lump, wrench, pocket watch, factory whistle, soot-stained letter, iron key, soot black coal orange iron grey palette | pixel art industrial UI, iron riveted borders, coal smoke background, factory gauge panels, worn wooden frames | 45_industrial_item.png | 45_industrial_ui.png |
| 46 | 历史 | 二战 | pixel art WW2 items, bolt-action rifle, ration tin, field radio, steel helmet, wartime letter, gas mask, military olive drab earth palette | pixel art WW2 UI, sandbag borders, typewritten document panels, propaganda poster style, field manual icons, sepia tone | 46_ww2_item.png | 46_ww2_ui.png |
| 47 | 历史 | 冷战 | pixel art cold war items, briefcase documents, decoder ring, rotary phone, cigarette pack, spy camera, muted grey olive red star palette | pixel art cold war UI, typewriter panels, classified red stamps, surveillance monitor borders, 60s government office | 47_coldwar_item.png | 47_coldwar_ui.png |
| 48 | 历史 | 西部牛仔 | pixel art wild west items, revolver, cowboy hat, whiskey bottle, sheriff badge, lasso, horseshoe, wanted poster, desert tan brown red palette | pixel art western UI, wooden plank borders, wanted poster panels, leather saddle textures, sheriff badge icons, sepia | 48_western_item.png | 48_western_ui.png |
| 49 | 历史 | 江户幕末 | pixel art Edo period items, katana, ukiyo-e fan, sake cup, ryo coin purse, samurai armor, pipe, indigo crimson cream gold palette | pixel art Edo UI, shoji screen borders, ukiyo-e panels, family crest icons, indigo fabric textures, traditional elegance | 49_edo_item.png | 49_edo_ui.png |
| 50 | 混搭 | 史诗神话英雄 | pixel art epic mythic items, legendary hero sword, hero medallion, titan horn, celestial shield, ambrosia flask, heroic gold bronze sky blue palette | pixel art epic UI, marble gold borders, heroic banner panels, mythic beast icons, sunrise glow, grandiose tone | 50_epichero_item.png | 50_epichero_ui.png |
| 51 | 混搭 | 魔幻现实主义 | pixel art magical realism items, coffee cup with floating steam swirl, book with glowing pages, modern keychain faint glow, realistic palette with magic highlights | pixel art magical realism UI, realistic mundane panels with magic glow accents, everyday icons, life with wonder hints | 51_magicreal_item.png | 51_magicreal_ui.png |
| 52 | 混搭 | 超自然灵异 | pixel art supernatural items, ouija planchette, EMF detector, ghost camera, cursed locket, salt circle kit, spectral blue grey pale palette | pixel art supernatural UI, ghostly translucent borders, EMF reader panels, flickering spirit icons, haunted blue tone | 52_paranormal_item.png | 52_paranormal_ui.png |
| 53 | 混搭 | 卡通搞笑 | pixel art cartoon items, giant cartoon bomb, rubber chicken, whoopee cushion, oversized hammer, pie in face, bright saturated clownish palette | pixel art cartoon UI, bouncy rounded borders, popping colors, silly sticker icons, comic speech bubble panels, wacky fun | 53_cartoon_item.png | 53_cartoon_ui.png |
| 54 | 混搭 | 治愈日常 | pixel art cozy items, warm tea cup, knitted scarf, potted plant, open book, cookie jar, soft pillow, warm cream pastel earth palette | pixel art cozy UI, soft wooden borders, cotton texture panels, cute plant icons, warm cream frames, homey feel | 54_cozy_item.png | 54_cozy_ui.png |
| 55 | 混搭 | 艺术抽象 | pixel art abstract items, geometric shape artifact, floating crystal, paint brush, ink blot orb, color palette stone, gradient rainbow palette | pixel art abstract UI, flowing organic borders, gradient panels, minimalist symbolic icons, gallery aesthetic | 55_abstract_item.png | 55_abstract_ui.png |
| 56 | 混搭 | 怪诞超现实 | pixel art surreal items, melting clock, floating eye, impossible staircase token, talking fish, backwards key, dreamlike purple teal pink palette | pixel art surreal UI, warped dreamlike borders, floating panels, impossible geometry, eye icons, Dali-inspired | 56_surreal_item.png | 56_surreal_ui.png |
| 57 | 混搭 | 宗教神学 | pixel art religious items, golden reliquary, prayer beads, stained glass shard, sacred scripture, angel feather, holy chalice, gold marble divine blue palette | pixel art religious UI, gothic cathedral borders, stained glass panels, gold cross icons, illuminated manuscript frames | 57_religious_item.png | 57_religious_ui.png |
| 58 | 混搭 | 马戏团恐怖 | pixel art circus horror items, bloody clown mask, cursed ticket, haunted music box, balloon, twisted popcorn bucket, circus red white sickly yellow palette | pixel art creepy circus UI, big top tent borders, carousel icons, striped panels, clown face frames, twisted carnival | 58_circushorror_item.png | 58_circushorror_ui.png |
| 59 | 混搭 | 极地生存 | pixel art arctic survival items, fur coat, ice pick, frozen meat, fire starter, snow goggles, emergency flare, ice blue white steel grey palette | pixel art arctic UI, frost-covered borders, ice-cracked panels, snowflake icons, cold blue glow, harsh survival | 59_arctic_item.png | 59_arctic_ui.png |
| 60 | 混搭 | 深海 | pixel art deep sea items, diving helmet, pressurized flask, bioluminescent lantern, coral artifact, harpoon, abyss blue teal cyan palette | pixel art deep sea UI, coral-encrusted borders, pressure gauge panels, bioluminescent icons, abyssal blue tone | 60_deepsea_item.png | 60_deepsea_ui.png |
| 61 | 混搭 | 太空探索 | pixel art space exploration items, helmet with reflection, oxygen tank, star map, alien rock sample, log recorder, cosmic black starry blue palette | pixel art space explorer UI, spaceship window borders, star map panels, constellation icons, lonely cosmic tone | 61_spaceexplore_item.png | 61_spaceexplore_ui.png |
| 62 | 跨文化 | 印度神话 | pixel art Indian mythology items, lotus flower, trishul trident, sacred conch, bindi gem, sari cloth, prayer bell, saffron gold crimson jade palette | pixel art Indian UI, mandala pattern borders, temple arch frames, lotus icons, gold ornament panels, spiritual aesthetic | 62_indian_item.png | 62_indian_ui.png |
| 63 | 跨文化 | 阿拉伯夜谭 | pixel art Arabian Nights items, magic lamp, flying carpet piece, scimitar, genie jewel, spice bag, brass teapot, gold deep blue crimson sand palette | pixel art Arabian UI, arabesque pattern borders, dome-shaped frames, gold filigree panels, crescent moon icons, desert luxury | 63_arabian_item.png | 63_arabian_ui.png |
| 64 | 跨文化 | 非洲神话 | pixel art African mythology items, tribal mask, wooden spear, beaded necklace, drum, ancestor totem, baobab seed, earth red ochre gold palette | pixel art African tribal UI, carved wood borders, tribal pattern panels, animal totem icons, warm savanna tones | 64_african_item.png | 64_african_ui.png |
| 65 | 跨文化 | 南美神话 | pixel art South American mythology items, Incan gold mask, feathered headdress, obsidian mirror, quipu knots, coca leaves, jungle green gold jade palette | pixel art Inca Maya UI, stepped pyramid borders, glyph panels, sun god icons, gold jade ornaments, ancient jungle | 65_southamerican_item.png | 65_southamerican_ui.png |
| 66 | 跨文化 | 斯拉夫神话 | pixel art Slavic mythology items, birch bark charm, wooden idol, cursed doll, iron skull key, embroidered cloth, forest green wood brown red palette | pixel art Slavic UI, embroidered folk pattern borders, birch wood panels, Baba Yaga hut icons, dark fairytale feel | 66_slavic_item.png | 66_slavic_ui.png |
| 67 | 跨文化 | 蒙古草原 | pixel art Mongolian items, curved saber, horse whip, yurt charm, shaman drum, airag flask, composite bow, grassland green sky blue leather palette | pixel art steppe UI, felt tent borders, leather strap panels, shaman symbol icons, wide sky background, nomadic feel | 67_mongol_item.png | 67_mongol_ui.png |
| 68 | 跨文化 | 东南亚神话 | pixel art Southeast Asian mythology items, gold naga amulet, palm leaf scroll, kris dagger, incense cone, wayang puppet, temple gold tropical green crimson palette | pixel art SEA UI, temple carving borders, gold naga decorations, tropical leaf panels, ritual symbol icons, mystical tropical | 68_sea_item.png | 68_sea_ui.png |
| 69 | 主题 | 反乌托邦 | pixel art dystopia items, surveillance camera, citizen ID card, ration ticket, banned book, regime pin, oppressive grey red propaganda palette | pixel art dystopia UI, state propaganda borders, surveillance screen panels, citizen ranking icons, red censorship stamps | 69_dystopia_item.png | 69_dystopia_ui.png |
| 70 | 主题 | 多元宇宙 | pixel art multiverse items, reality shard, portal key, timeline fragment, dimensional compass, parallel coin, prismatic rainbow glitch palette | pixel art multiverse UI, fractured reality borders, parallel dimension panels, portal ring icons, glitch transitions | 70_multiverse_item.png | 70_multiverse_ui.png |
| 71 | 主题 | 时间循环 | pixel art time loop items, broken pocket watch, looping hourglass, memory notebook, paradox coin, sepia cyan split palette | pixel art time loop UI, clock gear borders, timeline panels, repeating pattern frames, hourglass icons, deja vu aesthetic | 71_timeloop_item.png | 71_timeloop_ui.png |
| 72 | 主题 | 怪物收集 | pixel art monster collector items, capture ball, monster candy, evolution stone, trainer badge, creature journal, bright primary color palette | pixel art monster collector UI, capture ball buttons, creature list panels, elemental type icons, badge showcase frames | 72_monster_item.png | 72_monster_ui.png |
| 73 | 主题 | 美食烹饪 | pixel art cooking items, chef knife, frying pan, fresh vegetable, recipe book, spice jar, golden bread, warm kitchen orange red cream palette | pixel art cooking UI, wooden cutting board borders, recipe paper panels, ingredient icons, menu board frames, cozy restaurant | 73_cooking_item.png | 73_cooking_ui.png |
| 74 | 主题 | 体育竞技 | pixel art sports items, trophy, soccer ball, running shoes, stopwatch, team jersey, whistle, bright team color palette | pixel art sports UI, scoreboard borders, stadium panels, medal icons, team flag frames, energetic competitive feel | 74_sports_item.png | 74_sports_ui.png |
| 75 | 主题 | 音乐节奏 | pixel art music items, electric guitar, vinyl record, music note crystal, headphones, drum stick, microphone, neon beat purple pink cyan palette | pixel art rhythm UI, music note borders, sound wave panels, beat timing icons, stage light frames, pulsing feel | 75_music_item.png | 75_music_ui.png |
| 76 | 主题 | 浪漫乙女 | pixel art romance items, love letter, rose bouquet, heart pendant, chocolate box, photo album, diary, soft pink cream gold palette | pixel art otome UI, lace ribbon borders, heart-shaped panels, sparkle icons, pastel rose frames, sweet dreamy feel | 76_otome_item.png | 76_otome_ui.png |
"""


@dataclass(frozen=True)
class Example:
    number: str
    category: str
    theme: str
    item_prompt: str
    ui_prompt: str
    item_file: str
    ui_file: str

    @property
    def id(self) -> str:
        return self.item_file.removesuffix("_item.png")

    @property
    def item_full_prompt(self) -> str:
        return f"{self.item_prompt}, {ITEM_SUFFIX}"

    @property
    def ui_full_prompt(self) -> str:
        return f"{self.ui_prompt}, {UI_SUFFIX}"


COLOR_KEYWORDS: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("ink black", (22, 23, 26)),
    ("deep teal", (15, 78, 86)),
    ("blood red", (136, 22, 28)),
    ("sickly green", (132, 170, 66)),
    ("jade green", (36, 145, 102)),
    ("jungle green", (29, 120, 72)),
    ("forest green", (34, 110, 58)),
    ("grassland green", (71, 142, 73)),
    ("lush green", (54, 164, 88)),
    ("mint", (125, 218, 171)),
    ("emerald", (33, 168, 115)),
    ("teal", (31, 162, 156)),
    ("cyan", (46, 203, 219)),
    ("turquoise", (52, 190, 181)),
    ("sky blue", (94, 169, 220)),
    ("ocean blue", (42, 108, 175)),
    ("icy blue", (108, 176, 220)),
    ("blue", (55, 107, 204)),
    ("lapis", (38, 62, 153)),
    ("navy", (20, 34, 78)),
    ("purple", (116, 72, 184)),
    ("pink", (225, 101, 166)),
    ("sakura", (236, 141, 180)),
    ("crimson", (175, 38, 56)),
    ("red", (202, 51, 55)),
    ("orange", (221, 120, 42)),
    ("saffron", (224, 143, 45)),
    ("yellow", (232, 201, 80)),
    ("gold", (219, 171, 64)),
    ("bronze", (153, 103, 54)),
    ("copper", (181, 103, 59)),
    ("brass", (185, 132, 61)),
    ("brown", (119, 78, 48)),
    ("earth", (121, 90, 57)),
    ("leather", (111, 72, 45)),
    ("sand", (205, 175, 112)),
    ("cream", (237, 220, 166)),
    ("ivory", (234, 224, 190)),
    ("marble white", (218, 219, 210)),
    ("white", (230, 232, 225)),
    ("silver", (176, 184, 190)),
    ("chrome", (163, 184, 194)),
    ("steel", (121, 137, 153)),
    ("iron grey", (94, 101, 106)),
    ("grey", (102, 107, 111)),
    ("gray", (102, 107, 111)),
    ("charcoal", (46, 49, 55)),
    ("black", (20, 20, 24)),
    ("flesh", (200, 111, 119)),
    ("bone", (220, 207, 171)),
    ("olive", (91, 111, 61)),
    ("rust", (142, 69, 42)),
    ("sepia", (127, 87, 53)),
    ("pastel", (214, 174, 203)),
    ("rainbow", (130, 106, 213)),
)

CATEGORY_PALETTES: dict[str, list[tuple[int, int, int]]] = {
    "东方": [(22, 23, 26), (171, 41, 47), (218, 173, 74), (52, 144, 103), (230, 220, 185)],
    "西幻": [(35, 33, 40), (86, 70, 52), (210, 161, 67), (61, 121, 177), (216, 205, 174)],
    "科幻": [(13, 19, 34), (39, 93, 159), (73, 206, 220), (204, 72, 175), (188, 198, 205)],
    "恐怖": [(18, 20, 23), (91, 29, 38), (103, 135, 75), (201, 190, 144), (69, 78, 88)],
    "现代": [(27, 31, 36), (87, 104, 124), (220, 207, 174), (177, 54, 54), (225, 225, 218)],
    "历史": [(47, 39, 30), (133, 86, 52), (208, 161, 78), (74, 112, 126), (223, 204, 151)],
    "混搭": [(30, 27, 48), (129, 76, 176), (220, 106, 160), (72, 171, 150), (234, 206, 122)],
    "跨文化": [(36, 34, 29), (183, 96, 54), (217, 170, 64), (38, 136, 100), (64, 101, 170)],
    "主题": [(29, 33, 45), (82, 134, 203), (226, 90, 89), (227, 190, 78), (91, 187, 135)],
}


def parse_examples() -> list[Example]:
    examples: list[Example] = []
    for line in RAW_TABLE.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 7 or not cells[0].isdigit():
            continue
        examples.append(Example(*cells))
    return examples


def seed_for(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def clamp_channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(clamp_channel(x * (1 - t) + y * t) for x, y in zip(a, b))


def shift(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    target = (245, 240, 220) if amount > 0 else (10, 12, 18)
    return mix(color, target, abs(amount))


def extract_palette(example: Example, prompt: str) -> list[tuple[int, int, int]]:
    text = f"{example.category} {prompt}".lower()
    colors: list[tuple[int, int, int]] = []
    for word, color in COLOR_KEYWORDS:
        if word in text and color not in colors:
            colors.append(color)
    for color in CATEGORY_PALETTES.get(example.category, []):
        if color not in colors:
            colors.append(color)
    rng = random.Random(seed_for(prompt))
    while len(colors) < 6:
        h = rng.random()
        s = 0.42 + rng.random() * 0.28
        v = 0.48 + rng.random() * 0.34
        rgb = colorsys.hsv_to_rgb(h, s, v)
        colors.append(tuple(clamp_channel(c * 255) for c in rgb))
    dark = shift(colors[0], -0.58)
    return [dark, *colors[:7], shift(colors[1], 0.42)]


def item_keywords(prompt: str) -> list[str]:
    body = prompt
    if "," in body:
        body = body.split(",", 1)[1]
    for marker in (" palette", " with "):
        if marker in body:
            body = body.split(marker, 1)[0]
    words = [part.strip() for part in body.split(",") if part.strip()]
    return (words + ["mystic token"] * 8)[:8]


def rect(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: tuple[int, int, int], outline: tuple[int, int, int] | None = None, width: int = 1) -> None:
    draw.rectangle(xy, fill=fill, outline=outline, width=width)


def draw_gem(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, dark, main, accent, light) -> None:
    pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    draw.polygon(pts, fill=dark)
    inset = max(2, r // 4)
    pts2 = [(cx, cy - r + inset), (cx + r - inset, cy), (cx, cy + r - inset), (cx - r + inset, cy)]
    draw.polygon(pts2, fill=main)
    draw.polygon([(cx, cy - r + inset), (cx + r - inset, cy), (cx, cy)], fill=accent)
    draw.rectangle((cx - 3, cy - r + inset + 2, cx + 2, cy - r + inset + 6), fill=light)


def draw_item_icon(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], keyword: str, palette: list[tuple[int, int, int]], seed: int) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    dark, main, accent, light = palette[0], palette[2], palette[3], palette[-1]
    alt = palette[4]
    k = keyword.lower()

    if any(w in k for w in ("sword", "katana", "scimitar", "cutlass", "dagger", "knife", "blade", "saber", "guandao")):
        draw.line((x0 + 15, y1 - 13, x1 - 13, y0 + 15), fill=dark, width=8)
        draw.line((x0 + 17, y1 - 15, x1 - 15, y0 + 17), fill=light, width=4)
        draw.line((x0 + 18, y1 - 18, x0 + 33, y1 - 4), fill=accent, width=6)
        draw.rectangle((x0 + 12, y1 - 17, x0 + 27, y1 - 11), fill=dark)
        return
    if any(w in k for w in ("rifle", "gun", "pistol", "revolver", "shotgun", "blaster", "ray", "tommy")):
        draw.rectangle((x0 + 10, cy - 7, x1 - 13, cy + 4), fill=dark)
        draw.rectangle((x0 + 15, cy - 10, x1 - 22, cy - 4), fill=main)
        draw.rectangle((x1 - 14, cy - 5, x1 - 5, cy - 1), fill=accent)
        draw.polygon([(x0 + 24, cy + 4), (x0 + 35, cy + 4), (x0 + 29, y1 - 10)], fill=dark)
        draw.rectangle((x0 + 8, cy - 4, x0 + 15, cy + 10), fill=alt)
        return
    if any(w in k for w in ("bow", "whip", "lasso")):
        draw.arc((x0 + 12, y0 + 10, x1 - 12, y1 - 10), 80, 280, fill=dark, width=5)
        draw.line((cx + 4, y0 + 12, cx + 4, y1 - 12), fill=accent, width=2)
        draw.line((x0 + 14, cy, x1 - 12, cy), fill=light, width=3)
        return
    if any(w in k for w in ("staff", "trident", "hammer", "axe", "halberd", "scepter", "spear", "wand", "mjölnir", "mjolnir")):
        draw.line((cx - 12, y1 - 9, cx + 10, y0 + 11), fill=dark, width=7)
        draw.line((cx - 11, y1 - 11, cx + 8, y0 + 14), fill=main, width=3)
        if any(w in k for w in ("hammer", "mjolnir")):
            draw.rectangle((cx + 2, y0 + 8, cx + 24, y0 + 24), fill=dark)
            draw.rectangle((cx + 5, y0 + 11, cx + 21, y0 + 21), fill=accent)
        elif "trident" in k:
            for dx in (-8, 0, 8):
                draw.line((cx + dx + 7, y0 + 9, cx + dx + 7, y0 + 28), fill=accent, width=4)
        else:
            draw.ellipse((cx + 2, y0 + 7, cx + 22, y0 + 27), fill=dark)
            draw.ellipse((cx + 6, y0 + 11, cx + 18, y0 + 23), fill=accent)
        return
    if any(w in k for w in ("potion", "vial", "bottle", "flask", "jar", "jug", "amphora", "teapot", "cup", "chalice", "horn")):
        draw.rectangle((cx - 8, y0 + 10, cx + 8, y0 + 22), fill=dark)
        draw.rectangle((cx - 5, y0 + 9, cx + 5, y0 + 21), fill=light)
        draw.polygon([(cx - 18, y0 + 22), (cx + 18, y0 + 22), (cx + 23, y1 - 12), (cx - 23, y1 - 12)], fill=dark)
        draw.rectangle((cx - 16, y0 + 25, cx + 16, y1 - 15), fill=main)
        draw.rectangle((cx - 14, cy + 2, cx + 14, y1 - 16), fill=accent)
        draw.rectangle((cx - 9, y0 + 28, cx - 3, y0 + 35), fill=light)
        return
    if any(w in k for w in ("scroll", "book", "tome", "journal", "notebook", "letter", "map", "card", "passport", "ticket", "poster", "receipt", "papyrus", "scripture")):
        draw.rectangle((x0 + 12, y0 + 14, x1 - 12, y1 - 12), fill=dark)
        draw.rectangle((x0 + 16, y0 + 18, x1 - 16, y1 - 16), fill=light)
        for yy in range(y0 + 25, y1 - 20, 8):
            draw.rectangle((x0 + 22, yy, x1 - 24, yy + 2), fill=main)
        draw.rectangle((x0 + 14, y0 + 17, x0 + 23, y1 - 16), fill=accent)
        return
    if any(w in k for w in ("shield", "armor", "helmet", "mask", "crown", "hat", "cap", "coat", "robe", "boots", "goggles", "glasses")):
        draw.polygon([(cx, y0 + 8), (x1 - 12, y0 + 18), (x1 - 17, y1 - 12), (cx, y1 - 5), (x0 + 17, y1 - 12), (x0 + 12, y0 + 18)], fill=dark)
        draw.polygon([(cx, y0 + 13), (x1 - 18, y0 + 22), (x1 - 22, y1 - 15), (cx, y1 - 12), (x0 + 22, y1 - 15), (x0 + 18, y0 + 22)], fill=main)
        draw.rectangle((cx - 4, y0 + 18, cx + 4, y1 - 17), fill=accent)
        draw.rectangle((cx - 15, cy - 5, cx + 15, cy + 1), fill=light)
        return
    if any(w in k for w in ("stone", "gem", "crystal", "orb", "shard", "amulet", "pendant", "ring", "coin", "badge", "medallion", "jewel", "reliquary", "idol", "artifact", "key")):
        draw_gem(draw, cx, cy, 23, dark, main, accent, light)
        if "key" in k:
            draw.line((cx + 8, cy + 8, x1 - 7, y1 - 7), fill=dark, width=5)
            draw.rectangle((x1 - 15, y1 - 11, x1 - 8, y1 - 6), fill=accent)
        return
    if any(w in k for w in ("phone", "chip", "usb", "drone", "laptop", "camera", "detector", "radio", "counter", "remote")):
        draw.rectangle((x0 + 16, y0 + 12, x1 - 16, y1 - 12), fill=dark)
        draw.rectangle((x0 + 20, y0 + 17, x1 - 20, y1 - 20), fill=main)
        for i in range(4):
            draw.rectangle((x0 + 24 + i * 8, y1 - 17, x0 + 28 + i * 8, y1 - 14), fill=accent)
        draw.rectangle((x0 + 25, y0 + 23, x1 - 27, y0 + 28), fill=light)
        return
    if any(w in k for w in ("lantern", "candle", "flashlight", "flare", "lamp")):
        draw.rectangle((cx - 16, y0 + 17, cx + 16, y1 - 11), fill=dark)
        draw.rectangle((cx - 11, y0 + 22, cx + 11, y1 - 16), fill=accent)
        draw.polygon([(cx, y0 + 11), (cx + 9, y0 + 27), (cx - 9, y0 + 27)], fill=light)
        draw.arc((cx - 16, y0 + 5, cx + 16, y0 + 26), 200, 340, fill=dark, width=3)
        return
    if any(w in k for w in ("bread", "cheese", "apple", "gingerbread", "cookie", "food", "candy", "meat", "vegetable", "spice")):
        draw.ellipse((x0 + 13, y0 + 20, x1 - 10, y1 - 14), fill=dark)
        draw.ellipse((x0 + 17, y0 + 18, x1 - 15, y1 - 18), fill=accent)
        draw.rectangle((x0 + 25, y0 + 27, x0 + 32, y0 + 33), fill=light)
        draw.rectangle((x0 + 38, y0 + 34, x0 + 45, y0 + 40), fill=main)
        return
    if any(w in k for w in ("flower", "leaf", "branch", "seed", "plant", "coral", "feather", "mistletoe", "lotus")):
        draw.line((cx - 3, y1 - 10, cx + 2, y0 + 18), fill=dark, width=5)
        for dx, dy in [(-16, -7), (14, -12), (-12, 8), (16, 6)]:
            draw.ellipse((cx + dx - 9, cy + dy - 6, cx + dx + 9, cy + dy + 6), fill=accent, outline=dark, width=2)
        draw.ellipse((cx - 7, y0 + 12, cx + 8, y0 + 27), fill=light, outline=dark, width=2)
        return

    # fallback relic
    draw_gem(draw, cx, cy, 20, dark, main, accent, light)
    draw.rectangle((cx - 6, cy - 5, cx + 6, cy + 6), fill=alt)


def generate_item_sheet(example: Example) -> Image.Image:
    palette = extract_palette(example, example.item_full_prompt)
    source = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(source)
    words = item_keywords(example.item_prompt)
    for idx, word in enumerate(words):
        col = idx % 4
        row = idx // 4
        x = col * 128 + 32
        y = row * 128 + 32
        # 透明图上只绘制非常淡的对齐角标，保持游戏素材可用。
        mark = shift(palette[0], 0.35)
        draw.rectangle((x - 3, y - 3, x + 5, y - 1), fill=mark + (80,))
        draw.rectangle((x - 3, y - 3, x - 1, y + 5), fill=mark + (80,))
        draw_item_icon(draw, (x + 4, y + 4, x + 92, y + 92), word, palette, seed_for(example.id + word))
    pixel, _, _ = pixelize(
        source,
        PixelizeParams(
            output_size=(128, 64),
            colors=32,
            dither="none",
            preview_scale=0,
            edge_enhance=0.05,
            saturation=1.08,
            resample="box",
            snap_to_grid=False,
        ),
    )
    rgba = pixel.convert("RGBA")
    alpha = rgba.getchannel("A").point(lambda a: 255 if a > 8 else 0)
    rgba.putalpha(alpha)
    return rgba


def draw_frame(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], palette: list[tuple[int, int, int]], seed: int, motif: str) -> None:
    dark, main, accent, light = palette[0], palette[2], palette[3], palette[-1]
    x0, y0, x1, y1 = xy
    draw.rectangle(xy, fill=shift(dark, 0.08), outline=dark, width=6)
    draw.rectangle((x0 + 8, y0 + 8, x1 - 8, y1 - 8), outline=main, width=4)
    draw.rectangle((x0 + 16, y0 + 16, x1 - 16, y1 - 16), outline=accent, width=2)
    rng = random.Random(seed)
    step = 34 + (seed % 4) * 6
    for x in range(x0 + 22, x1 - 24, step):
        if motif in {"rune", "glyph", "hieroglyph", "mandala"}:
            draw.rectangle((x, y0 + 5, x + 11, y0 + 14), fill=accent)
            draw.line((x + 2, y0 + 18, x + 13, y0 + 28), fill=light, width=2)
        elif motif in {"leaf", "vine", "sakura"}:
            draw.ellipse((x, y0 + 6, x + 16, y0 + 18), fill=accent)
            draw.line((x + 6, y0 + 16, x + 20, y0 + 28), fill=main, width=2)
        elif motif in {"gear", "tech", "atomic"}:
            draw.rectangle((x, y0 + 7, x + 16, y0 + 23), outline=accent, width=3)
            draw.rectangle((x + 5, y0 + 12, x + 11, y0 + 18), fill=light)
        else:
            size = 6 + rng.randrange(0, 8, 2)
            draw.rectangle((x, y0 + 10, x + size, y0 + 10 + size), fill=accent)
            draw.rectangle((x + size + 4, y0 + 12, x + size + 8, y0 + 16), fill=light)


def motif_for(prompt: str) -> str:
    text = prompt.lower()
    if any(w in text for w in ("rune", "bagua", "oracle", "glyph", "hieroglyph", "symbol", "script")):
        return "rune"
    if any(w in text for w in ("vine", "leaf", "ivy", "sakura", "flower", "lotus")):
        return "leaf"
    if any(w in text for w in ("gear", "clock", "gauge", "tech", "holographic", "hud", "atomic", "chrome")):
        return "tech"
    if any(w in text for w in ("tentacle", "flesh", "bone", "vein")):
        return "organic"
    if any(w in text for w in ("mandala", "arabesque", "knotwork")):
        return "mandala"
    return "square"


def faux_text(draw: ImageDraw.ImageDraw, x: int, y: int, widths: list[int], color: tuple[int, int, int], h: int = 6, gap: int = 12) -> None:
    yy = y
    for width in widths:
        draw.rectangle((x, yy, x + width, yy + h), fill=color)
        yy += gap


def generate_ui_showcase(example: Example) -> Image.Image:
    palette = extract_palette(example, example.ui_full_prompt)
    rng = random.Random(seed_for(example.id + "ui"))
    dark, base, main, accent, light = palette[0], palette[1], palette[2], palette[3], palette[-1]
    bg = mix(dark, base, 0.28)
    source = Image.new("RGB", (960, 540), bg)
    draw = ImageDraw.Draw(source)

    # 低调背景网格/星点，模拟游戏 UI 展示板。
    grid = mix(bg, light, 0.12)
    for x in range(0, 960, 32):
        draw.line((x, 0, x, 540), fill=grid, width=1)
    for y in range(0, 540, 32):
        draw.line((0, y, 960, y), fill=grid, width=1)
    for _ in range(42):
        x = rng.randrange(20, 940, 4)
        y = rng.randrange(20, 520, 4)
        draw.rectangle((x, y, x + 3, y + 3), fill=mix(accent, light, rng.random() * 0.45))

    motif = motif_for(example.ui_prompt)
    draw_frame(draw, (54, 44, 906, 496), palette, seed_for(example.id), motif)

    panel_fill = mix(bg, light, 0.09)
    panel_alt = mix(bg, main, 0.22)
    # 顶栏
    draw.rectangle((92, 78, 868, 124), fill=panel_alt, outline=dark, width=4)
    faux_text(draw, 118, 93, [92, 52, 70], light, h=7, gap=0)
    for i in range(5):
        x = 670 + i * 34
        draw.rectangle((x, 91, x + 20, 111), fill=accent if i == 0 else main, outline=dark, width=2)

    # 左侧栏和物品格
    draw.rectangle((92, 148, 300, 434), fill=panel_fill, outline=dark, width=4)
    faux_text(draw, 116, 166, [112, 78, 136], mix(light, accent, 0.3), h=5, gap=13)
    slot = 34
    for row in range(4):
        for col in range(4):
            x = 118 + col * 42
            y = 226 + row * 42
            draw.rectangle((x, y, x + slot, y + slot), fill=mix(dark, main, 0.18), outline=main, width=2)
            if (row + col + seed_for(example.id)) % 3 != 0:
                cx, cy = x + slot // 2, y + slot // 2
                draw_gem(draw, cx, cy, 10, dark, accent, main, light)

    # 主展示窗
    draw.rectangle((330, 148, 842, 434), fill=panel_fill, outline=dark, width=4)
    draw.rectangle((356, 174, 614, 286), fill=mix(bg, accent, 0.16), outline=main, width=3)
    for i in range(5):
        x = 376 + i * 42
        h = 18 + ((seed_for(example.id) >> i) % 52)
        draw.rectangle((x, 262 - h, x + 22, 262), fill=accent if i % 2 else main)
        draw.rectangle((x, 262 - h, x + 22, 262 - h + 5), fill=light)

    # 右侧状态卡和按钮，不使用真实文字，避免字体锯齿不一致。
    for i in range(3):
        y = 176 + i * 62
        draw.rectangle((646, y, 808, y + 42), fill=mix(bg, base, 0.34), outline=main, width=3)
        draw.rectangle((662, y + 12, 684, y + 30), fill=accent)
        faux_text(draw, 700, y + 12, [68, 92], light, h=5, gap=12)

    draw.rectangle((356, 316, 808, 392), fill=mix(bg, base, 0.26), outline=main, width=3)
    for i in range(7):
        x = 382 + i * 58
        draw.rectangle((x, 338, x + 34, 370), fill=mix(main, accent, i / 9), outline=dark, width=2)
        draw.rectangle((x + 8, 346, x + 26, 352), fill=light)

    # 风格化装饰角标。
    if motif == "organic":
        for i in range(5):
            draw.arc((70 + i * 35, 58 + i * 11, 210 + i * 26, 210 + i * 10), 210, 330, fill=accent, width=4)
    elif motif == "tech":
        for i in range(6):
            x = 704 + i * 22
            draw.line((x, 456, x + 18, 474), fill=accent, width=3)
            draw.rectangle((x + 17, 472, x + 24, 479), fill=light)
    elif motif == "leaf":
        for i in range(8):
            x = 720 + i * 18
            draw.ellipse((x, 456, x + 22, 470), fill=accent, outline=dark, width=2)
    else:
        for i in range(6):
            x = 710 + i * 24
            draw.rectangle((x, 456, x + 14, 470), fill=accent)
            draw.rectangle((x + 6, 462, x + 20, 476), outline=light, width=2)

    pixel, _, _ = pixelize(
        source,
        PixelizeParams(
            output_size=(480, 270),
            colors=48,
            dither="none",
            preview_scale=0,
            edge_enhance=0.08,
            saturation=1.05,
            resample="box",
            snap_to_grid=False,
        ),
    )
    return pixel.convert("RGB").resize((1920, 1080), Image.Resampling.NEAREST)


def write_manifest(examples: list[Example]) -> None:
    payload = []
    for example in examples:
        payload.append(
            {
                "id": example.id,
                "number": example.number,
                "category": example.category,
                "theme": example.theme,
                "itemSrc": f"/homepage-examples/items/{example.item_file}",
                "uiSrc": f"/homepage-examples/ui/{example.ui_file}",
                "itemFile": example.item_file,
                "uiFile": example.ui_file,
                "itemPrompt": example.item_full_prompt,
                "uiPrompt": example.ui_full_prompt,
            }
        )
    categories = []
    for example in examples:
        if example.category not in categories:
            categories.append(example.category)
    body = (
        "export type HomepageExample = {\n"
        "  id: string\n"
        "  number: string\n"
        "  category: string\n"
        "  theme: string\n"
        "  itemSrc: string\n"
        "  uiSrc: string\n"
        "  itemFile: string\n"
        "  uiFile: string\n"
        "  itemPrompt: string\n"
        "  uiPrompt: string\n"
        "}\n\n"
        f"export const homepageExamples: HomepageExample[] = {json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        f"export const homepageExampleCategories = {json.dumps(categories, ensure_ascii=False, indent=2)} as const\n"
    )
    MANIFEST_TS.write_text(body, encoding="utf-8")


def main() -> None:
    examples = parse_examples()
    if len(examples) != 76:
        raise RuntimeError(f"期望 76 条范例，实际解析到 {len(examples)} 条")
    ITEM_DIR.mkdir(parents=True, exist_ok=True)
    UI_DIR.mkdir(parents=True, exist_ok=True)

    for idx, example in enumerate(examples, start=1):
        item_target = ITEM_DIR / example.item_file
        ui_target = UI_DIR / example.ui_file
        generate_item_sheet(example).save(item_target)
        generate_ui_showcase(example).save(ui_target)
        print(f"[{idx:02d}/{len(examples)}] {example.theme}: {item_target.name}, {ui_target.name}")

    write_manifest(examples)
    print(f"manifest: {MANIFEST_TS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
