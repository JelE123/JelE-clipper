# JelE Clipper: one profile per game.
# The clipper finds out which game a stream is (see clipper.py, detect_game) and then uses the profile
# for everything that depends on the game: words for the speech recognition, what counts as a
# highlight, titles, stickers, hashtags and which tools the editor shows.

GAMES = {
    'valorant': {
        'name': 'Valorant', 'color': '#ff4655', 'icon': 'V',
        'exe': ['valorant-win64-shipping.exe', 'valorant.exe'], 'window': ['valorant'], 'twitch': ['valorant'],
        'killfeed': True, 'killfeed_name': 'Killfeed', 'matchdata': True,
        'hashtags': '#valorant #valorantclips #valorantmoments #twitch #gaming #fyp',
        'platform_tags': {'tiktok': '#fyp #valorant #gaming', 'shorts': '#shorts #valorant', 'reels': '#reels #valorant #gamingclips'},
        'word_tags': {'vandal': '#vandal', 'phantom': '#phantom', 'operator': '#operator', 'op': '#operator', 'sheriff': '#sheriff', 'ghost': '#ghost',
                      'odin': '#odin', 'jett': '#jett', 'reyna': '#reyna', 'raze': '#raze', 'sova': '#sova', 'omen': '#omen', 'sage': '#sage',
                      'phoenix': '#phoenix', 'clove': '#clove', 'iso': '#iso', 'neon': '#neon', 'yoru': '#yoru', 'chamber': '#chamber',
                      'killjoy': '#killjoy', 'cypher': '#cypher', 'viper': '#viper', 'gekko': '#gekko', 'tejo': '#tejo', 'waylay': '#waylay',
                      'miks': '#miks', 'hush': '#hush', 'veto': '#veto', 'ace': '#ace', 'clutch': '#clutch', 'one tap': '#onetap',
                      'headshot': '#headshot', 'ranked': '#ranked', 'immortal': '#immortal', 'radiant': '#radiant'},
        'hype': r"ace|clutch|one tap|onetap|1v[2-5]|one v (two|three|four|five)|four k|4k|team ace|flawless|thrifty|spike'?s down|ninja defuse|got him|headshot",
        'strong': r"ace|clutch|1v[3-5]|one v (three|four|five)|ninja defuse|team ace",
        'hooks': ['THEY NEVER STOOD A CHANCE', 'ONE MORE AND IT WAS AN ACE', 'HOW DID I WIN THIS', 'THE VANDAL DOES NOT MISS'],
        'stickers': ['ACE', 'CLUTCH', 'ONE TAP', '1V5', '4K', 'NINJA DEFUSE', 'NO WAY'],
        'teaser': 'WAIT FOR IT...', 'fallback': 'Valorant moment',
        'placeholders': {'hook': 'e.g. NO WAY THAT WORKED', 'file': 'e.g. ace on haven', 'find': 'jet', 'replace': 'Jett'},
        'zoom_on': 'on "no way", kills and the Clip button',
        'wizard_hint': 'Real multikills, aces and clutches come from your Valorant matches.',
    },
    'cs2': {
        'name': 'Counter-Strike 2', 'color': '#de9b35', 'icon': 'CS',
        'exe': ['cs2.exe', 'csgo.exe'], 'window': ['counter-strike', 'cs2'], 'twitch': ['counter-strike'],
        'killfeed': True, 'killfeed_name': 'Killfeed', 'matchdata': False,
        'hashtags': '#cs2 #counterstrike #cs2clips #csgo #twitch #gaming #fyp',
        'platform_tags': {'tiktok': '#fyp #cs2 #gaming', 'shorts': '#shorts #cs2', 'reels': '#reels #cs2 #gamingclips'},
        'word_tags': {'awp': '#awp', 'deagle': '#deagle', 'ak': '#ak47', 'ak-47': '#ak47', 'm4': '#m4a4', 'ace': '#ace', 'clutch': '#clutch',
                      'mirage': '#mirage', 'inferno': '#inferno', 'dust 2': '#dust2', 'nuke': '#nuke', 'ancient': '#ancient', 'anubis': '#anubis',
                      'faceit': '#faceit', 'premier': '#premier', 'noscope': '#noscope', 'one deag': '#onedeag', 'headshot': '#headshot'},
        'hype': r"ace|clutch|one deag|one tap|onetap|noscope|no scope|1v[2-5]|one v (two|three|four|five)|four k|4k|ninja defuse|wallbang|jumpshot|headshot|awp",
        'strong': r"ace|clutch|1v[3-5]|one v (three|four|five)|ninja defuse|noscope|no scope|one deag",
        'hooks': ['THE AWP DOES NOT MISS', 'ONE DEAG', 'HOW DID I WIN THIS', 'NINJA DEFUSE INCOMING'],
        'stickers': ['ACE', 'CLUTCH', 'ONE DEAG', 'NOSCOPE', '1V5', 'NINJA DEFUSE', 'NO WAY'],
        'teaser': 'WAIT FOR IT...', 'fallback': 'CS2 moment',
        'placeholders': {'hook': 'e.g. ONE DEAG ON MIRAGE', 'file': 'e.g. clutch on mirage', 'find': 'a w p', 'replace': 'AWP'},
        'zoom_on': 'on "no way", kills and the Clip button',
    },
    'fortnite': {
        'name': 'Fortnite', 'color': '#9d4dbb', 'icon': 'F',
        'exe': ['fortniteclient-win64-shipping.exe', 'fortnitelauncher.exe'], 'window': ['fortnite'], 'twitch': ['fortnite'],
        'killfeed': False, 'killfeed_name': 'Elim feed', 'matchdata': False,
        'hashtags': '#fortnite #fortniteclips #fortnitemoments #victoryroyale #twitch #gaming #fyp',
        'platform_tags': {'tiktok': '#fyp #fortnite #gaming', 'shorts': '#shorts #fortnite', 'reels': '#reels #fortnite #gamingclips'},
        'word_tags': {'victory royale': '#victoryroyale', 'zero build': '#zerobuild', 'ranked': '#fortniteranked', 'unreal': '#unreal',
                      'box fight': '#boxfight', 'zone wars': '#zonewars', 'reload': '#fortnitereload', 'creative': '#fortnitecreative', 'og': '#fortniteog'},
        'hype': r"victory royale|crowned|one pump|double pump|cranked|cranking|boxed|beamed|laser|knocked|eliminated|elimmed|w key|end game|last one|top (two|three|five)|squad wipe|team wipe",
        'strong': r"victory royale|crowned|one pump|squad wipe|team wipe|last one",
        'hooks': ['VICTORY ROYALE', 'ONE PUMP', 'HE NEVER SAW IT COMING', 'BOXED LIKE A FISH'],
        'stickers': ['VICTORY ROYALE', 'ONE PUMP', 'BOXED', 'CRANKED', 'SQUAD WIPE', 'CROWNED', 'NO WAY'],
        'teaser': 'WAIT FOR IT...', 'fallback': 'Fortnite moment',
        'placeholders': {'hook': 'e.g. ONE PUMP IN END GAME', 'file': 'e.g. victory royale', 'find': 'victory royal', 'replace': 'Victory Royale'},
        'zoom_on': 'on "no way", eliminations and the Clip button',
    },
    'minecraft': {
        'name': 'Minecraft', 'color': '#62b047', 'icon': 'M',
        'exe': ['minecraft.windows.exe', 'minecraftlauncher.exe'], 'window': ['minecraft'], 'twitch': ['minecraft'],
        'killfeed': False, 'killfeed_name': 'Killfeed', 'matchdata': False,
        'hashtags': '#minecraft #minecraftclips #minecraftfunny #twitch #gaming #fyp',
        'platform_tags': {'tiktok': '#fyp #minecraft #gaming', 'shorts': '#shorts #minecraft', 'reels': '#reels #minecraft #gamingclips'},
        'word_tags': {'diamond': '#diamonds', 'diamonds': '#diamonds', 'creeper': '#creeper', 'hardcore': '#minecrafthardcore', 'speedrun': '#speedrun',
                      'nether': '#nether', 'ender dragon': '#enderdragon', 'warden': '#warden', 'bedwars': '#bedwars', 'hypixel': '#hypixel',
                      'smp': '#minecraftsmp', 'redstone': '#redstone', 'mlg': '#mlg'},
        'hype': r"diamonds?|netherite|mlg|water bucket|creeper|aw man|totem|ender dragon|wither|warden|elytra|i'?m dead|my stuff|my items|lava|fell|blew up|exploded|herobrine",
        'strong': r"diamonds|mlg|totem|ender dragon|creeper|aw man|my stuff|blew up",
        'hooks': ['I FOUND DIAMONDS', 'CREEPER... AW MAN', 'MLG WATER BUCKET', 'NOT MY DIAMONDS'],
        'stickers': ['DIAMONDS!', 'MLG', 'AW MAN', 'TOTEM POP', 'RIP MY STUFF', 'SSSSS...', 'NO WAY'],
        'teaser': 'WAIT FOR IT...', 'fallback': 'Minecraft moment',
        'placeholders': {'hook': 'e.g. I FOUND DIAMONDS', 'file': 'e.g. creeper blew up my house', 'find': 'nether right', 'replace': 'netherite'},
        'zoom_on': 'on "no way", big moments and the Clip button',
    },
    'other': {
        'name': 'Other / Just Chatting', 'color': '#60a5fa', 'icon': '?',
        'exe': [], 'window': [], 'twitch': ['just chatting', 'irl', 'talk shows'],
        'killfeed': False, 'killfeed_name': 'Killfeed', 'matchdata': False,
        'hashtags': '#twitch #streamer #funny #gaming #fyp',
        'platform_tags': {'tiktok': '#fyp #twitch #funny', 'shorts': '#shorts #twitch', 'reels': '#reels #twitch #funny'},
        'word_tags': {},
        'hype': r"chat|no way|bro|oh my god",
        'strong': r"no way|oh my god",
        'hooks': ['CHAT WAS NOT READY', 'I CAN\'T BELIEVE I SAID THAT', 'WAIT FOR IT...'],
        'stickers': ['NO WAY', 'BRO', 'CHAT?!', 'LOL', 'WAIT...'],
        'teaser': 'WAIT FOR IT...', 'fallback': 'Stream moment',
        'placeholders': {'hook': 'e.g. CHAT WAS NOT READY', 'file': 'e.g. funniest moment', 'find': 'shat', 'replace': 'chat'},
        'zoom_on': 'on "no way", laughing and the Clip button',
    },
}
ORDER = ['valorant', 'cs2', 'fortnite', 'minecraft', 'other']

# words that give a game away when you say them (for streams where nothing else tells which game it is)
SIGNS = {
    'valorant': r"jett|reyna|raze|sova|omen|killjoy|cypher|brimstone|phoenix|chamber|clove|gekko|fade|breach|skye|astra|viper|harbor|deadlock|vyse|tejo|waylay|miks|hush|kay ?o|vandal|phantom|spectre|odin|spike|radianite|ascent|haven|icebox|lotus|sunset|abyss|ult orb",
    'cs2': r"awp|deagle|ak[- ]?47|m4a[14]|glock|usp|tec[- ]?9|mirage|inferno|dust (2|two)|nuke|anubis|overpass|vertigo|terrorists?|counter[- ]terrorists?|faceit|the bomb|bomb ?site|kevlar|defuse kit",
    'fortnite': r"victory royale|storm|zone|box(ed)?|piece control|crank|ninety|90s|mats|chug jug|slurp|shield pot|big pot|minis|pump|reboot|battle bus|v[- ]bucks|zero build|llama|loot|chest",
    'minecraft': r"creeper|enderman|ender (dragon|pearl)|nether|netherite|diamonds?|redstone|villager|piglin|ghast|elytra|totem|obsidian|crafting table|furnace|spawn ?point|hypixel|bedwars|skywars|smp|warden|wither|zombie|skeleton|pickaxe",
}

# per game: more words for the speech recognition (Valorant has its own big list in gamewords.py)
WORDS = {
    'cs2': {
        'names': ['Counter-Strike', 'Counter-Strike 2', 'CS2', 'AWP', 'AK-47', 'AK', 'M4A4', 'M4A1-S', 'Deagle', 'Desert Eagle', 'USP-S', 'Glock', 'P250',
                  'Five-SeveN', 'Tec-9', 'CZ75', 'SSG 08', 'Scout', 'Galil', 'FAMAS', 'MP9', 'MAC-10', 'UMP', 'P90', 'Negev', 'Nova', 'XM1014', 'Zeus',
                  'Mirage', 'Inferno', 'Dust 2', 'Nuke', 'Ancient', 'Anubis', 'Overpass', 'Vertigo', 'Train', 'Office', 'Italy', 'Premier', 'Faceit',
                  'CS Rating', 'Major', 'Navi', 'Vitality', 'FaZe', 'G2', 'Spirit', 'MOUZ', 'NiP', 's1mple', 'ZywOo', 'donk', 'm0NESY', 'NiKo', 'ropz'],
        'terms': ['CT', 'T side', 'CT side', 'bomb', 'bomb site', 'plant', 'planted', 'defuse', 'defusing', 'defuse kit', 'kit', 'ninja defuse', 'eco',
                  'force buy', 'full buy', 'save', 'AWPer', 'entry', 'lurk', 'rotate', 'retake', 'clutch', 'ace', '4K', 'one deag', 'noscope',
                  'no scope', 'wallbang', 'jumpshot', 'spray', 'spray transfer', 'tap', 'headshot', 'one tap', 'nade', 'HE', 'flash', 'pop flash',
                  'smoke', 'molly', 'incendiary', 'decoy', 'lineup', 'one-way', 'peek', 'jiggle', 'counter-strafe', 'crosshair', 'connector', 'jungle',
                  'palace', 'apps', 'banana', 'ramp', 'heaven', 'window', 'short', 'long', 'catwalk', 'doors', 'tunnels', 'pit', 'goose', 'xbox',
                  'car', 'mid', 'A site', 'B site', 'cubby', 'default', 'boost', 'kevlar', 'helmet', 'armor'],
        'mishears': {'a w p': 'AWP', 'a.w.p.': 'AWP', 'awe p': 'AWP', 'dee gul': 'Deagle', 'deegle': 'Deagle', 'diegel': 'Deagle', 'one deeg': 'one deag',
                     'face it': 'Faceit', 'c t': 'CT', 'see tea': 'CT', 'diffuse': 'defuse', 'diffusing': 'defusing', 'diffused': 'defused',
                     'diffuse kit': 'defuse kit', 'no-scope': 'noscope', 'wall bang': 'wallbang', 'dust two': 'Dust 2', 'cs 2': 'CS2', 'zywoo': 'ZywOo',
                     'simple': None, 'monesy': 'm0NESY', 'nico': None, 'tech nine': 'Tec-9', 'tec nine': 'Tec-9', 'mac ten': 'MAC-10'},
        'prompt': ['AWP', 'AK-47', 'M4A4', 'M4A1-S', 'Deagle', 'one deag', 'USP', 'Glock', 'Mirage', 'Inferno', 'Dust 2', 'Nuke', 'Ancient', 'Anubis',
                   'CT', 'bomb', 'defuse', 'ninja defuse', 'eco', 'force buy', 'noscope', 'wallbang', 'ace', 'clutch', 'Faceit', 'Premier',
                   "he's one, lit for 90, bomb's down, smoke mid, flash out, he's on site"],
    },
    'fortnite': {
        'names': ['Fortnite', 'Victory Royale', 'Battle Bus', 'Chug Jug', 'Slurp', 'Shield Potion', 'Big Pot', 'Mini', 'Med Kit', 'Reboot Van', 'Zero Build',
                  'Ranked', 'Unreal', 'Champion', 'Elite', 'Diamond', 'Creative', 'Reload', 'Ballistic', 'Lego Fortnite', 'Festival', 'Item Shop',
                  'V-Bucks', 'Battle Pass', 'Peely', 'Jonesy', 'Midas', 'Tilted Towers', 'Pleasant Park', 'Retail Row', 'Salty Springs', 'Lazy Lake',
                  'Mythic', 'Legendary', 'Epic', 'Rare', 'Reaper', 'Ninja', 'Bugha', 'Clix', 'Peterbot', 'SypherPK', 'Lachlan', 'Mongraal', 'FNCS'],
        'terms': ['storm', 'zone', 'circle', 'end game', 'moving zone', 'box', 'boxed', 'box fight', 'zone wars', 'edit', 'piece control', 'crank',
                  'cranking', '90s', 'ramp', 'wall', 'cone', 'floor', 'tarp', 'mats', 'wood', 'brick', 'metal', 'shield', 'minis', 'pump', 'shotgun',
                  'AR', 'SMG', 'sniper', 'heavy', 'elim', 'elims', 'eliminated', 'knocked', 'knock', 'reboot', 'revive', 'third party', 'third partied',
                  'hot drop', 'drop', 'land', 'loot', 'chest', 'ammo box', 'supply drop', 'llama', 'vault', 'gold', 'purple', 'blue', 'grey', 'sweat',
                  'bot', 'default', 'skin', 'emote', 'dance', 'squad', 'duo', 'trio', 'solo', 'squad wipe', 'team wipe', 'one pump', 'double pump',
                  'crowned', 'Crown', 'top 10', 'top 5', 'w key', 'beamed', 'laser'],
        'mishears': {'victory royal': 'Victory Royale', 'victory royals': 'Victory Royale', 'chug jugs': 'Chug Jugs', 'slurp juice': 'Slurp Juice',
                     'v bucks': 'V-Bucks', 'vbucks': 'V-Bucks', 'zero built': 'Zero Build', 'forty nine': None, 'for tonight': None,
                     'cranking nineties': 'cranking 90s', 'nineties': '90s', 'box fights': 'box fights', 'tilted tower': 'Tilted Towers'},
        'prompt': ['Victory Royale', 'storm', 'zone', 'end game', 'box', 'boxed', 'piece control', 'cranking 90s', 'mats', 'pump', 'one pump', 'Chug Jug',
                   'Slurp', 'big pot', 'minis', 'reboot', 'Zero Build', 'Ranked', 'Unreal', 'elim', 'knocked', 'third party', 'squad wipe', 'crowned',
                   "he's one shot, I boxed him, cranking 90s, moving zone, last squad"],
    },
    'minecraft': {
        'names': ['Minecraft', 'Creeper', 'Enderman', 'Ender Dragon', 'Wither', 'Warden', 'Zombie', 'Skeleton', 'Spider', 'Piglin', 'Ghast', 'Blaze',
                  'Villager', 'Iron Golem', 'Nether', 'the End', 'Overworld', 'Stronghold', 'Ancient City', 'Bastion', 'Nether Fortress', 'Trial Chamber',
                  'Ender Pearl', 'Eye of Ender', 'Totem of Undying', 'Elytra', 'Trident', 'Mace', 'Shulker Box', 'Hypixel', 'Bedwars', 'SkyWars',
                  'SMP', 'Optifine', 'Steve', 'Alex', 'Herobrine', 'Dream', 'Technoblade', 'Mojang', 'Bedrock', 'Java Edition'],
        'terms': ['diamonds', 'diamond', 'netherite', 'emerald', 'iron', 'gold', 'redstone', 'obsidian', 'TNT', 'totem', 'enchanting', 'anvil', 'beacon',
                  'crafting table', 'furnace', 'bed', 'spawn', 'respawn', 'hardcore', 'survival', 'creative', 'speedrun', 'seed', 'biome', 'mob',
                  'mob farm', 'XP farm', 'MLG', 'water bucket', 'MLG water bucket', 'clutch', 'bridge', 'bridging', 'pillar up', 'strip mining',
                  'cave', 'ravine', 'portal', 'nether portal', 'pickaxe', 'sword', 'shield', 'bow', 'crossbow', 'armor', 'chestplate', 'helmet',
                  'boots', 'leggings', 'potion', 'golden apple', 'gapple', 'notch apple', 'stack', 'chunk', 'render distance', 'mod', 'shaders'],
        'mishears': {'nether right': 'netherite', 'nether rite': 'netherite', 'netherrite': 'netherite', 'creepers': 'creepers', 'ender man': 'Enderman',
                     'endermen': 'Endermen', 'ender pearl': 'Ender Pearl', 'eye of ender': 'Eye of Ender', 'mlg': 'MLG', 'hi pixel': 'Hypixel',
                     'high pixel': 'Hypixel', 'bed wars': 'Bedwars', 'sky wars': 'SkyWars', 'g apple': 'gapple', 'elitra': 'Elytra', 'alitra': 'Elytra',
                     'pig lin': 'Piglin', 'ghasts': 'Ghasts', 'techno blade': 'Technoblade', 'red stone': 'redstone', 'warden': 'Warden'},
        'prompt': ['Minecraft', 'Creeper', 'Enderman', 'Ender Dragon', 'Nether', 'netherite', 'diamonds', 'redstone', 'Elytra', 'totem', 'TNT',
                   'Warden', 'Piglin', 'Villager', 'Hypixel', 'Bedwars', 'SMP', 'MLG water bucket', 'gapple', 'hardcore', 'speedrun',
                   "I found diamonds, a creeper blew up my house, aw man, MLG water bucket, totem popped"],
    },
    'other': {'names': [], 'terms': [], 'mishears': {}, 'prompt': ['chat', 'stream', 'KEKW', 'Pog', 'LUL', 'emote', 'sub', 'raid', 'mod', 'Discord']},
}


def get(gid):
    return GAMES.get(gid) or GAMES['other']


def public():
    """what the app's screens need, without the regexes"""
    keep = ('name', 'color', 'icon', 'killfeed', 'killfeed_name', 'matchdata', 'hashtags', 'platform_tags', 'hooks', 'stickers', 'teaser',
            'fallback', 'placeholders', 'zoom_on')
    return [dict({k: GAMES[g].get(k) for k in keep}, id=g) for g in ORDER]
