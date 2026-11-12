# JelE Clipper: game words for the speech recognition.
# Two jobs:
#  1. prompt(): a short list of the most important words, given to the speech model so it
#     expects them (the model only reads about 220 word pieces, so this list stays short).
#  2. fix(words): after recognition, every word in this file is put in its right spelling,
#     and common mishearings are corrected ("kill joy" -> "Killjoy", "diffuse" -> "defuse").
# You can add your own words in the app: Settings > Captions > Words I should know.

import re

# ---------------------------------------------------------------- Valorant agents and their abilities (ultimate last)
AGENTS = {
    'Astra': ['Gravity Well', 'Nova Pulse', 'Nebula', 'Dissipate', 'Astral Form', 'Cosmic Divide'],
    'Breach': ['Aftershock', 'Flashpoint', 'Fault Line', 'Rolling Thunder'],
    'Brimstone': ['Stim Beacon', 'Incendiary', 'Sky Smoke', 'Orbital Strike'],
    'Chamber': ['Trademark', 'Headhunter', 'Rendezvous', 'Tour De Force'],
    'Clove': ['Pick-Me-Up', 'Meddle', 'Ruse', 'Not Dead Yet'],
    'Cypher': ['Trapwire', 'Cyber Cage', 'Spycam', 'Neural Theft'],
    'Deadlock': ['GravNet', 'Sonic Sensor', 'Barrier Mesh', 'Annihilation'],
    'Fade': ['Prowler', 'Seize', 'Haunt', 'Nightfall'],
    'Gekko': ['Mosh Pit', 'Wingman', 'Dizzy', 'Thrash'],
    'Harbor': ['Cascade', 'Storm Surge', 'Cove', 'High Tide', 'Reckoning'],
    'Hush': ['Telekinesis', 'Displacement', 'Flashbulb', 'Flow', 'Suspension'],
    'Iso': ['Contingency', 'Undercut', 'Double Tap', 'Kill Contract'],
    'Jett': ['Drift', 'Cloudburst', 'Updraft', 'Tailwind', 'Blade Storm'],
    'KAY/O': ['FRAG/ment', 'FLASH/drive', 'ZERO/point', 'NULL/cmd'],
    'Killjoy': ['Nanoswarm', 'Alarmbot', 'Turret', 'Lockdown'],
    'Miks': ['Harmonize', 'M-Pulse', 'Waveform', 'Bassquake'],
    'Neon': ['Fast Lane', 'Relay Bolt', 'High Gear', 'Overdrive'],
    'Omen': ['Shrouded Step', 'Paranoia', 'Dark Cover', 'From the Shadows'],
    'Phoenix': ['Blaze', 'Curveball', 'Hot Hands', 'Run It Back'],
    'Raze': ['Boom Bot', 'Blast Pack', 'Paint Shells', 'Showstopper'],
    'Reyna': ['Leer', 'Devour', 'Dismiss', 'Empress'],
    'Sage': ['Barrier Orb', 'Slow Orb', 'Healing Orb', 'Resurrection'],
    'Skye': ['Regrowth', 'Trailblazer', 'Guiding Light', 'Seekers'],
    'Sova': ['Owl Drone', 'Shock Bolt', 'Recon Bolt', "Hunter's Fury"],
    'Tejo': ['Stealth Drone', 'Special Delivery', 'Guided Salvo', 'Armageddon'],
    'Veto': ['Crosscut', 'Chokehold', 'Interceptor', 'Evolution'],
    'Viper': ['Snake Bite', 'Poison Cloud', 'Toxic Screen', "Viper's Pit"],
    'Vyse': ['Razorvine', 'Shear', 'Arc Rose', 'Steel Garden'],
    'Waylay': ['Saturate', 'Lightspeed', 'Refract', 'Convergent Paths'],
    'Yoru': ['Fakeout', 'Blindside', 'Gatecrash', 'Dimensional Drift'],
}
ULTS = [a[-1] for a in AGENTS.values()]

WEAPONS = ['Classic', 'Shorty', 'Frenzy', 'Ghost', 'Sheriff', 'Bandit', 'Stinger', 'Spectre', 'Bucky', 'Judge', 'Bulldog',
           'Guardian', 'Phantom', 'Vandal', 'Marshal', 'Outlaw', 'Operator', 'Ares', 'Odin', 'Warden', 'Golden Gun', 'Melee']
MAPS = ['Ascent', 'Bind', 'Haven', 'Split', 'Icebox', 'Breeze', 'Fracture', 'Pearl', 'Lotus', 'Sunset', 'Abyss', 'Corrode',
        'District', 'Kasbah', 'Drift', 'Piazza', 'Glitch', 'The Range']
RANKS = ['Iron', 'Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Ascendant', 'Immortal', 'Radiant']
MODES = ['Competitive', 'Unrated', 'Swiftplay', 'Spike Rush', 'Deathmatch', 'Team Deathmatch', 'Escalation', 'Premier', 'Replication', 'Snowball Fight', 'All Random One Site']
SKINS = ['Prime', 'Reaver', 'Elderflame', 'Glitchpop', 'Oni', 'RGX', 'Kuronami', 'Araxys', 'Magepunk', 'Chronovoid', 'Mystbloom', 'Xenohunter',
         'Prelude to Chaos', "Gaia's Vengeance", 'Spectrum', 'Sovereign', 'Ion', 'Champions', 'Forsaken', 'Neptune', 'Overdrive',
         'Sentinels of Light', 'Ruination', 'Radiant Entertainment System', 'BlastX', 'Evori Dreamwings', 'Primordium', 'Kingdom', 'Battle Pass', 'Night Market']
TEAMS = ['Sentinels', 'Fnatic', 'LOUD', 'Paper Rex', 'G2', 'NRG', 'Team Heretics', 'EDward Gaming', 'Team Liquid', '100 Thieves', 'DRX', 'T1', 'Gen.G',
         'Karmine Corp', 'Team Vitality', 'Leviatan', 'MIBR', 'FUT', 'Natus Vincere', 'Rex Regum Qeon', 'Talon', 'Bilibili Gaming', 'Trace Esports',
         'Xi Lai Gaming', 'Cloud9', 'Evil Geniuses', 'FaZe', 'VCT', 'Masters', 'Champions Tour', 'Game Changers', 'Riot', 'Riot Games']
PEOPLE = ['TenZ', 'Demon1', 'Aspas', 'Derke', 'Boaster', 'Chronicle', 'Alfajer', 'something', 'f0rsakeN', 'Jinggg', 'Sacy', 'ScreaM', 'Zekken',
          'Zellsis', 'Johnqt', 'Saadhak', 'Less', 'Cauanzin', 'Kaajak', 'MiniBoo', 'Tarik', 'Shroud', 'Kyedae', 'Hiko', 'iiTzTimmy', 'QuarterJade',
          'Sinatraa', 'Subroza', 'Grim', 'Sick', 'Asuna', 'Yay', 'Sayf', 'Leo', 'Cned', 'nAts', 'Mistic', 'Crashies', 'Victor', 'FNS', 'Marved']
CALLOUTS = ['A site', 'B site', 'C site', 'A main', 'B main', 'C main', 'A long', 'A short', 'B long', 'mid', 'heaven', 'hell', 'hookah', 'showers',
            'garage', 'market', 'tree', 'CT', 'spawn', 'link', 'lobby', 'elbow', 'catwalk', 'rafters', 'ropes', 'vents', 'mail', 'boathouse', 'kitchen',
            'pipes', 'window', 'connector', 'courtyard', 'top mid', 'bottom mid', 'tunnel', 'yellow', 'tube', 'snowman', 'nest', 'hall', 'arcade',
            'dish', 'canteen', 'generator', 'lamps', 'screens', 'sewer', 'back site', 'default', 'triple', 'stairs', 'cubby', 'pillar', 'box', 'truck',
            'switch', 'site', 'rotate', 'door', 'doors', 'mound', 'rubble', 'waterfall', 'fountain', 'pizza', 'bridge', 'rope', 'ramp', 'B halls',
            'A link', 'B link', 'U hall', 'stack', 'ledge']
TERMS = ['spike', 'plant', 'planted', 'defuse', 'defusing', 'defused', 'half defuse', 'fake defuse', 'tap defuse', 'stick', 'ninja defuse', 'post-plant', 'retake',
         'rotate', 'lurk', 'lurker', 'anchor', 'flank', 'entry', 'entry frag', 'trade', 'refrag', 'peek', 'jiggle peek', 'wide swing', 'off-angle', 'prefire',
         'crosshair', 'crosshair placement', 'flick', 'spray', 'spray transfer', 'tap', 'burst', 'one tap', 'headshot', 'head shot', 'wallbang', 'lineup',
         'eco', 'save', 'half buy', 'force buy', 'full buy', 'bonus', 'thrifty', 'flawless', 'ace', 'team ace', 'clutch', 'ninja', '1v1', '1v2', '1v3', '1v4', '1v5',
         'overtime', 'match point', 'pistol round', 'ult', 'ult orb', 'orb', 'utility', 'util', 'smoke', 'flash', 'molly', 'stun', 'concuss', 'suppress',
         'nearsight', 'drone', 'dart', 'recon', 'wall', 'trip', 'tripwire', 'turret', 'cam', 'heal', 'res', 'rez', 'revive', 'Radianite', 'credits',
         'Valorant Points', 'VP', 'RR', 'rank up', 'derank', 'demote', 'placement', 'smurf', 'boosted', 'hardstuck', 'MMR', 'ELO', 'IGL', 'duelist',
         'initiator', 'controller', 'sentinel', 'agent', 'loadout', 'shield', 'light shield', 'heavy shield', 'regen shield', 'armor', 'kill feed',
         'scoreboard', 'K/D', 'ACS', 'ADR', 'KAST', 'first blood', 'MVP', 'match MVP', 'team MVP', 'surrender', 'remake', 'AFK', 'dodge', 'queue',
         'lobby', 'party', 'five stack', 'duo', 'solo queue', 'tracker', 'Tracker.gg', 'VOD', 'VOD review', 'aim lab', 'Aim Lab', 'Kovaak', 'deathmatch',
         'warm up', 'GG', 'GGs', 'gg ez', 'nice try', 'NT', 'nice shot', 'NS', 'WP', 'nice one']
SLANG = ['no way', "let's go", 'W', 'L', 'dub', 'diff', 'gap', 'cracked', 'goated', 'washed', 'throwing', 'griefing', 'baited', 'bot', 'tilted',
         'toxic', 'ratting', 'rat', 'shmoovin', 'sheesh', 'clip it', 'clip that', 'insane', 'crazy', 'nuts', 'filthy', 'disgusting', 'nasty', 'one deag',
         'hold W', 'run it down', 'chat', 'chatters', 'POG', 'Pog', 'PogChamp', 'KEKW', 'LUL', 'OMEGALUL', 'monkaS', 'Sadge', 'Copium', 'Hopium', 'Kappa',
         'pepega', 'catJAM', 'ResidentSleeper', 'gigachad', 'rizz', 'aura', 'cooked', 'locked in', 'lock in', 'skill issue', 'ratio', 'mid', 'bussin',
         'sub', 'subs', 'gifted subs', 'Prime sub', 'bits', 'raid', 'hype train', 'follow', 'follower', 'mod', 'emote', 'clip', 'Twitch', 'stream',
         'streamer', 'TikTok', 'YouTube', 'Shorts', 'Discord', 'OBS', 'Spotify']
OTHER_GAMES = ['Counter-Strike', 'CS2', 'CS:GO', 'Mirage', 'Inferno', 'Dust 2', 'Ancient', 'Anubis', 'Nuke', 'Overpass', 'Vertigo', 'AWP', 'AK-47',
               'M4A4', 'M4A1-S', 'Deagle', 'Desert Eagle', 'Fortnite', 'Apex Legends', 'Overwatch', 'League of Legends', 'Teamfight Tactics', 'TFT',
               'Minecraft', 'Rocket League', 'Call of Duty', 'Warzone', 'GTA', 'GTA 6', 'Rainbow Six Siege', 'Marvel Rivals', 'Elden Ring', 'Roblox',
               'Lethal Company', 'Among Us', 'Fall Guys', 'PUBG', 'Dota 2', 'Hearthstone', 'Arcane', 'Riot Client', 'Vanguard', 'Steam', 'Battle.net']


# what players say about utility and fights: verbs, nicknames and short callouts
UTIL_TALK = [
    # being hit by utility
    'seized', 'seize', 'naded', 'nade', 'nades', 'nading', 'molly', 'mollies', "molly'd", 'mollied', 'flashed', 'flash', 'pop flash', 'blinded', 'blind',
    'stunned', 'stun', 'dazed', 'concussed', 'concuss', 'suppressed', 'suppress', 'nearsighted', 'nearsight', 'deafened', 'deafen', 'decayed', 'decay',
    'vulnerable', 'vuln', 'vulned', 'slowed', 'slow', 'tethered', 'tether', 'trapped', 'trip', 'tripped', 'tripwire', 'detained', 'hindered',
    'revealed', 'reveal', 'scanned', 'dart', 'darted', 'drone', 'droned', 'tagged', 'marked', 'pinged', 'ping', 'spotted', 'heard', 'footsteps',
    'grabbed', 'pulled', 'pushed', 'displaced', 'levitated', 'lifted', 'knocked up', 'knocked back', 'disarmed', 'ulted', 'ulting', 'ult is up',
    "ult's up", 'ult ready', 'one orb', 'two orbs', 'orbs', 'satchel', 'satchels', 'boom bot', 'nanos', 'alarm bot', 'cam', 'camera',
    'dog', 'dogs', 'eye', 'owl', 'bird', 'birds', 'flower', 'wolf', 'dizzy', 'wingman', 'thrash', 'turret', 'bubble', 'wall', 'walled', 'cage',
    'caged', 'cove', 'tp', 'teleport', 'teleported', 'dash', 'dashed', 'updraft', 'knife', 'knives', 'smoke', 'smokes', 'smoked', 'one way',
    'one-way', 'lineup', 'lineups', 'molly lineup', 'shock dart', 'double shock', 'recon', 'res', 'rez', 'resurrected', 'heal', 'healed', 'healing',
    # positions and situations
    'in the smoke', 'in the cage', 'in the orb', 'in the wall', 'behind the wall', 'through the smoke', 'off the smoke', 'on the spike', 'on site',
    'off site', 'one there', 'two there', 'one left', 'last one', 'last guy', 'he is low', "he's low", "he's one", 'one HP', '1 HP', 'one shot',
    'one-shot', 'lit', 'lit for', 'hit for', 'tagged for', 'dinked', 'dink', 'beamed', 'beaming', 'domed', 'headshotted', 'tapped', 'tapping',
    'sprayed', 'spraying', 'whiffed', 'whiff', 'missed', 'traded', 'refragged', 'swung', 'swinging', 'peeked', 'peeking', 'holding', 'holding an angle',
    'anchoring', 'lurking', 'flanking', 'rotating', 'rotated', 'stacking', 'stacked', 'pushing', 'rushing', 'executing', 'execute', 'default',
    'split push', 'fake', 'faking', 'baiting', 'bait', 'ratting', 'jiggle', 'shoulder peek', 'crouch spray', 'counter-strafe', 'strafe', 'bhop',
    'jump peek', 'dry peek', 'swing', 'wide swing', 'crossfire', 'off angle', 'off-angle', 'pre-aim', 'prefire', 'timing', 'spike down',
    "spike's down", 'spike is down', 'planted', 'planting', 'defusing', 'he is defusing', 'tap it', 'stick it', 'half', 'half defuse', 'anti-eco',
    'save', 'saving', 'drop me', 'drop', 'buy', 'buying', 'full buy', 'bonus round', 'pistol', 'pistol round', 'econ', 'loss bonus', 'ult orb',
    'orb', 'first blood', 'first kill', 'entry', 'opening', 'opening duel', 'man advantage', '4v5', '5v4', '2v1', 'retake', 'retaking',
    'post plant', 'post-plant', 'afterplant', 'clutched', 'clutching', 'aced', 'nice', 'nice try', 'thrown', 'threw', 'choked', 'griefed',
]

# heard wrong -> right. Only mishearings that are almost never meant otherwise on a Valorant stream.
MISHEARS = {

    # utility talk that speech recognition often writes wrong
    'nated': 'naded', 'nayded': 'naded', 'neighed': 'naded', 'naeded': 'naded', 'naid': 'nade', 'nayed': 'naded', 'nades': 'nades', 'nate': None,
    'mollie': 'molly', 'mollyed': "molly'd", 'molly-ed': "molly'd", 'mollie\'d': "molly'd", 'mollied': "molly'd", 'molley': 'molly', 'mali': None,
    'ceased': 'seized', 'seased': 'seized', 'ceazed': 'seized', 'siezed': 'seized', 'sieze': 'seize',
    'satchle': 'satchel', 'satchell': 'satchel',
    'vulnd': 'vulned', 'vulned': 'vulned', 'vuln\'d': 'vulned', 'vol': None,
    'dinked': 'dinked', 'dinged': None, 'bea med': 'beamed', 'one shotted': 'one-shot', 'one shot': 'one shot', 'one hp': '1 HP', '1hp': '1 HP',
    'anti eco': 'anti-eco', 'antieco': 'anti-eco', 'counter strafe': 'counter-strafe', 'counterstrafe': 'counter-strafe', 'b hop': 'bhop',
    'pre aim': 'pre-aim', 'preaim': 'pre-aim', 'after plant': 'afterplant', 'off angle': 'off-angle', 'one way': 'one-way', 'oneway': 'one-way',
    'tee pee': 'TP', 'tea pee': 'TP', 'teepee': 'TP', 'tp\'d': "TP'd", 'tpd': "TP'd", 'ulted': 'ulted', 'alted': None, 'ult\'d': 'ulted',
    'spikes down': "spike's down", 'kayo\'d': "KAY/O'd", 'caged': 'caged',
    'jet': 'Jett', 'jets': "Jett's", 'rayna': 'Reyna', 'raina': 'Reyna', 'reina': 'Reyna', 'rena': 'Reyna', 'raena': 'Reyna',
    'kayo': 'KAY/O', 'k.o.': 'KAY/O', 'k o': 'KAY/O', 'kay o': 'KAY/O', 'kay-o': 'KAY/O', 'k-o': 'KAY/O', 'kaio': 'KAY/O',
    'kill joy': 'Killjoy', 'kill-joy': 'Killjoy', 'brim stone': 'Brimstone', 'fenix': 'Phoenix', 'pheonix': 'Phoenix', 'yoro': 'Yoru', 'yuru': 'Yoru',
    'piper': 'Viper', 'viber': 'Viper', 'vyper': 'Viper', 'vipor': 'Viper', 'bryce': None, 'raise': None, 'raised': None, 'sky': None,
    'gecko': 'Gekko', 'geko': 'Gekko', 'vise': 'Vyse', 'vyce': 'Vyse', 'tayo': 'Tejo', 'teho': 'Tejo', 'tejo': 'Tejo', 'tey ho': 'Tejo',
    'way lay': 'Waylay', 'cipher': 'Cypher', 'sypher': 'Cypher', 'harbour': 'Harbor', 'astro': 'Astra', 'sky': None, 'soba': 'Sova', 'sovah': 'Sova',
    'reyna\'s': "Reyna's", 'miks': 'Miks', 'mix agent': 'Miks agent', 'hush': None, 'veto': None,
    'ice box': 'Icebox', 'icebox': 'Icebox', 'acent': 'Ascent', 'assent': 'Ascent', 'lotis': 'Lotus', 'corode': 'Corrode',
    'spectra': 'Spectre', 'specter': 'Spectre', 'vandle': 'Vandal', 'vandel': 'Vandal', 'fantom': 'Phantom', 'phantum': 'Phantom', 'odyn': 'Odin',
    'the op': 'the Op', 'operater': 'Operator', 'sherif': 'Sheriff', 'sherriff': 'Sheriff', 'bucky': 'Bucky', 'buckey': 'Bucky',
    'diffuse': 'defuse', 'diffusing': 'defusing', 'diffused': 'defused', 'diffuser': 'defuser', 'diffuse kit': 'defuse kit', 'defuze': 'defuse',
    'one-tap': 'one tap', 'onetap': 'one tap', 'one tapped': 'one tapped', 'one-tapped': 'one tapped', 'wall bang': 'wallbang', 'wall-bang': 'wallbang',
    'pre fire': 'prefire', 'pre-fire': 'prefire', 'post plant': 'post-plant', 'postplant': 'post-plant', 're take': 'retake',
    'head shot': 'headshot', 'hooka': 'hookah',
    'blade storm': 'Blade Storm', 'bladestorm': 'Blade Storm', 'blades storm': 'Blade Storm', 'show stopper': 'Showstopper', 'boombot': 'Boom Bot',
    'boom bot': 'Boom Bot', 'nano swarm': 'Nanoswarm', 'alarm bot': 'Alarmbot', 'grav net': 'GravNet', 'gravnet': 'GravNet', 'razor vine': 'Razorvine',
    'bass quake': 'Bassquake', 'base quake': 'Bassquake', 'trap wire': 'Trapwire', 'spy cam': 'Spycam', 'cyber cage': 'Cyber Cage',
    'fake out': 'Fakeout', 'gate crash': 'Gatecrash', 'blind side': 'Blindside', 'fault line': 'Fault Line', 'after shock': 'Aftershock',
    'flash point': 'Flashpoint', 'cloud burst': 'Cloudburst', 'up draft': 'Updraft', 'tail wind': 'Tailwind', 'trail blazer': 'Trailblazer',
    'curve ball': 'Curveball', 'owl drone': 'Owl Drone', 'night fall': 'Nightfall', 'cross cut': 'Crosscut', 'choke hold': 'Chokehold',
    'wave form': 'Waveform', 'm pulse': 'M-Pulse', 'em pulse': 'M-Pulse', 'light speed': 'Lightspeed', 'flash bulb': 'Flashbulb',
    'null command': 'NULL/cmd', 'null cmd': 'NULL/cmd', 'zero point': 'ZERO/point', 'flash drive': 'FLASH/drive', 'frag ment': 'FRAG/ment',
    'orbital': 'Orbital', 'hunters fury': "Hunter's Fury", "hunter's fury": "Hunter's Fury", 'vipers pit': "Viper's Pit", "viper's pit": "Viper's Pit",
    'radiantite': 'Radianite', 'radiannite': 'Radianite', 'aim labs': 'Aim Lab', 'kovaaks': "KovaaK's", 'tracker gg': 'Tracker.gg',
    'poggers': 'POGGERS', 'pog champ': 'PogChamp', 'kek w': 'KEKW', 'omega lul': 'OMEGALUL', 'monka s': 'monkaS', 'copium': 'Copium',
    'cs go': 'CS:GO', 'cs 2': 'CS2', 'c s 2': 'CS2', 'dust two': 'Dust 2', 'a w p': 'AWP', 'ak 47': 'AK-47', 'ak-47': 'AK-47',
    'ten z': 'TenZ', 'tenzie': 'TenZ', 'demon one': 'Demon1', 'demon 1': 'Demon1', 'jingg': 'Jinggg', 'zeckin': 'Zekken', 'zekkin': 'Zekken',
    'paper wrecks': 'Paper Rex', 'paper rex': 'Paper Rex', 'f natic': 'Fnatic', 'fanatic': None,
}

# everyday English words: their spelling is only changed when you say them as part of a longer name ("high tide"),
# never on their own, so "split the team" or "a ghost town" stay as they are
COMMON = {w.lower() for w in '''
Classic Frenzy Ghost Sheriff Bandit Stinger Judge Bulldog Guardian Marshal Outlaw Operator Melee Warden
Bind Haven Split Breeze Fracture Pearl Lotus Sunset Abyss District Drift Glitch Iron Bronze Silver Gold Platinum Diamond Immortal Radiant Ascendant
Competitive Unrated Premier Replication Escalation Deathmatch Prime Oni Ion Champions Forsaken Neptune Overdrive Kingdom Spectrum Sovereign Ruination
Nebula Dissipate Aftershock Flashpoint Incendiary Trademark Headhunter Rendezvous Meddle Ruse Prowler Seize Haunt Nightfall Wingman Dizzy Thrash
Cascade Cove Reckoning Telekinesis Displacement Flow Suspension Contingency Undercut Drift Cloudburst Updraft Tailwind Turret Lockdown Harmonize
Waveform Paranoia Blaze Curveball Showstopper Leer Devour Dismiss Empress Resurrection Regrowth Trailblazer Seekers Armageddon Crosscut Chokehold
Interceptor Evolution Shear Saturate Lightspeed Refract Fakeout Blindside Gatecrash Annihilation Masters Riot Talon Less Grim Sick Leo Victor Sentinels
Sage Omen Viper Harbor Neon Fade Breach Chamber Deadlock Iso Clove Phoenix Astra Cypher Skye Veto Hush Waylay Ares Odin Spectre Vandal Phantom
something Yay Asuna zombie skeleton spider villager blaze dream mace trident wither mini epic rare legendary champion elite ranked unreal creative reload festival ninja crown major office train spirit nova scout bedrock steve alex mythic overworld Chronicle Shroud LOUD Boaster Sacy Subroza Mistic Crashies Ancient Nuke Overpass Vertigo Inferno Mirage Arcane Vanguard Steam Masters Flashbulb Orbital Kasbah Piazza
'''.split()}
COMMON_PHRASES = {'run it back', 'not dead yet', 'from the shadows', 'pick-me-up', 'pick me up', 'double tap', 'high tide', 'special delivery',
                  'guiding light', 'high gear', 'fast lane', 'dark cover', 'hot hands', 'rolling thunder', 'kill contract', 'tour de force',
                  'golden gun', 'the range', 'battle pass', 'night market', 'storm surge', 'slow orb', 'healing orb', 'barrier orb', 'shock bolt',
                  'snake bite', 'poison cloud', 'toxic screen', 'gravity well', 'sonic sensor', 'barrier mesh', 'mosh pit', 'paint shells',
                  'blast pack', 'stealth drone', 'guided salvo', 'steel garden', 'arc rose', 'convergent paths', 'dimensional drift', 'sky smoke',
                  'stim beacon', 'relay bolt', 'recon bolt', 'shrouded step', 'astral form', 'cosmic divide', 'nova pulse', 'orbital strike',
                  'neural theft', 'the end', 'big pot', 'iron golem', 'item shop', 'med kit', 'shield potion', 'champions tour', 'game changers', 'team deathmatch', 'spike rush', 'snowball fight', 'evil geniuses'}

# ---------------------------------------------------------------- the prompt for the speech model
def prompt_words(game='valorant'):
    """words for the model to expect, least important first: the model only reads the last ~220 word pieces,
    so the clipper drops words from the front until everything fits (your own words go after these)."""
    parts = [
        ['dinked', 'beamed', 'one-way', 'lineup', 'satchel', 'nanos', 'dog', 'TP', 'anti-eco', 'afterplant'],
        ['flawless', 'thrifty', 'lurk', 'entry', 'trade', 'Radiant', 'Immortal', 'Ascendant', 'RR', 'KEKW', 'Pog'],
        ['spike', 'defuse', 'plant', 'retake', 'rotate', 'eco', 'force buy', 'ult', 'one tap', 'headshot', 'wallbang', 'ace', 'clutch', 'GG'],
        ['Blade Storm', 'Showstopper', "Hunter's Fury", 'Orbital Strike', 'Nightfall', 'NULL/cmd', 'Steel Garden', 'Bassquake', 'Annihilation'],
        ['Vandal', 'Phantom', 'Operator', 'Sheriff', 'Ghost', 'Spectre', 'Judge', 'Odin', 'Marshal', 'Outlaw', 'Bandit'],
        # a short sentence in streamer speech teaches the model how these words are used
        ["he's in the smoke, he's caged, I got seized, naded, molly'd, flashed, stunned, he's one, lit for 140, spike's down, one tap"],
        MAPS[:12],
        list(AGENTS) + ['Valorant', 'chat'],
    ]
    if game and game != 'valorant':
        try:
            import games
            return (games.WORDS.get(game) or games.WORDS['other'])['prompt'] + ['chat']
        except Exception: pass
    return [w for p in parts for w in p]

# ---------------------------------------------------------------- correcting the recognised words
def _norm(t):
    t = t.lower().replace('\u2019', "'")
    return re.sub(r"^[^\w/]+|[^\w/']+$", '', t)

def _key(s):
    """'Pick-Me-Up' / 'pick me up' / 'Pick me-up!' -> 'pick me up'"""
    return ' '.join(x for x in (_norm(w) for w in s.replace('-', ' ').split()) if x)

def _make(names, terms, mishears):
    canon = {}
    def add(key, val, force=False):
        k = _key(key)
        if k and (force or k not in canon): canon[k] = val
    for n in names + terms:
        add(n, n)
        for v in (n.replace('/', ' '), n.replace('/', ''), n.replace(' ', ''), n.replace('-', '')):
            if v != n: add(v, n)
    for k, v in mishears.items():
        if v: add(k, v, force=True)
    return canon

STREAM_NAMES = OTHER_GAMES + ['Twitch', 'TikTok', 'YouTube', 'Discord', 'OBS', 'Spotify']
GENERIC_MISHEARS = {k: MISHEARS[k] for k in ('poggers', 'pog champ', 'kek w', 'omega lul', 'monka s', 'copium', 'cs go', 'cs 2', 'c s 2', 'dust two',
                                             'a w p', 'ak 47', 'ak-47', 'aim labs', 'kovaaks', 'tracker gg') if k in MISHEARS}

def _build():
    names = list(AGENTS) + [a for v in AGENTS.values() for a in v] + WEAPONS + MAPS + RANKS + MODES + SKINS + TEAMS + PEOPLE + STREAM_NAMES + \
            ['Radianite', 'Valorant Points', 'Tracker.gg', 'Aim Lab', "KovaaK's", 'Valorant']
    return _make(names, TERMS + SLANG + CALLOUTS + UTIL_TALK, MISHEARS)

_CANON = {}
def canon(game='valorant'):
    """the word list for one game: Valorant has the big list above, other games get theirs from games.py"""
    game = game or 'valorant'
    if game not in _CANON:
        if game == 'valorant': c = _build()
        else:
            try:
                import games
                W = games.WORDS.get(game) or games.WORDS['other']
            except Exception:
                W = {'names': [], 'terms': [], 'mishears': {}}
            c = _make(W['names'] + STREAM_NAMES, W['terms'] + SLANG, dict(GENERIC_MISHEARS, **{k: v for k, v in W['mishears'].items()}))
        _CANON[game] = (c, min(4, max(len(k.split()) for k in c)))
    return _CANON[game]

CANON = canon('valorant')[0]

def fix(words, unclear='...', game='valorant'):
    """words: list of (start, end, text, ...). Returns the list with game words in their right spelling."""
    if not words: return words
    CANON, MAXN = canon(game)
    out = []; i = 0; n = len(words)
    while i < n:
        w = words[i]
        if w[2] == unclear: out.append(w); i += 1; continue
        done = False
        for k in range(min(MAXN, n - i), 0, -1):
            chunk = words[i:i + k]
            if any(c[2] == unclear for c in chunk): continue
            # also try the words glued together: "kill" "joy" -> "killjoy"
            raw = [c[2] for c in chunk]
            lead = re.match(r'^[^\w/]*', raw[0]).group(0)
            tail = re.search(r"('s|s')?[^\w/]*$", raw[-1].replace('’', "'"))
            tail = tail.group(0) if tail else ''
            body = [_norm(r) for r in raw]
            if tail.startswith("'s") or tail.startswith("s'"): body[-1] = re.sub(r"'s?$", '', body[-1])
            joined = _key(' '.join(body))
            keys = [joined] + ([joined.replace(' ', '')] if k > 1 else [])
            hit = next((CANON[x] for x in keys if x in CANON), None)
            if not hit: continue
            said = ' '.join(re.sub(r"^[^\w/]+|[^\w/']+$", '', r) for r in raw)
            said_core = said[:-2] if tail.startswith("'s") and said.lower().endswith("'s") else said
            if said_core == hit: break                    # already right
            if k == 1 and said_core.lower() == hit.lower() and (hit.lower() in COMMON or hit == hit.lower() or _key(hit) in COMMON_PHRASES):
                break                                      # only a capital differs on an everyday word: leave it
            if k > 1 and said_core.lower() == hit.lower() and hit.lower() in COMMON_PHRASES:
                break
            text = lead + hit + (tail if not (hit.endswith("'s") and tail.startswith("'s")) else tail[2:])
            hw = hit.split(' ')
            if len(hw) == k:   # same number of words: keep the timing of every word
                for j, c in enumerate(chunk):
                    t = (lead if j == 0 else '') + hw[j] + (tail if j == k - 1 else '')
                    out.append((c[0], c[1], t) + tuple(c[3:]))
            else:
                out.append((chunk[0][0], chunk[-1][1], text) + tuple(chunk[0][3:]))
            i += k; done = True; break
        if not done: out.append(w); i += 1
    return out

# ---------------------------------------------------------------- names that sound almost the same ("piper" -> "Viper")
def _snd(t):
    """a sound key: p/b/f/v, c/k/q, s/z, d/t sound alike, all vowels are one sound"""
    t = re.sub(r'[^a-z]', '', t.lower()).replace('ph', 'f').replace('ck', 'k')
    t = re.sub(r'[pbfv]', 'b', t); t = re.sub(r'[ckq]', 'k', t); t = re.sub(r'[sz]', 's', t); t = re.sub(r'[dt]', 't', t)
    t = re.sub(r'[aeiouy]+', 'a', t)
    return re.sub(r'(.)\1+', r'\1', t)
CUES = re.compile(r"^(ult|ulted|ulting|util|utility|smoke|smokes|flash|flashed|molly|wall|walls|their|enemy|enemies|killed|kill|kills|site|push|pushing|lurk|lurking|"
                  r"rotate|rotating|playing|agent|maining|operator|vandal|phantom|sheriff|spike|plant|defuse|nade|darts?|drone|dash|updraft|tp)$", re.I)
def _names(game):
    if game in (None, '', 'valorant'): return list(AGENTS) + WEAPONS + MAPS
    try:
        import games
        return [n for n in (games.WORDS.get(game) or {}).get('names', []) if ' ' not in n]
    except Exception: return []
_SNDIDX = {}
def soundalike(words, unclear='...', game='valorant'):
    """a word that sounds like a game name and is used like one (written as a name, or next to "ult", "their", "killed"...) becomes that name"""
    if not words: return words
    if game not in _SNDIDX:
        idx = {}
        for n in _names(game):
            if len(n) >= 4 and n.isalpha(): idx.setdefault(_snd(n), n)
        _SNDIDX[game] = idx
    idx = _SNDIDX[game]
    out = list(words)
    for i, w in enumerate(words):
        raw = w[2]; core = re.sub(r"^[^\w]+|[^\w']+$", '', raw)
        if raw == unclear or len(core) < 4 or not core.isalpha(): continue
        hit = idx.get(_snd(core))
        if not hit or hit.lower() == core.lower() or core.lower() in COMMON: continue
        near = [re.sub(r"[^\w']", '', x[2]) for x in words[max(0, i - 2):i] + words[i + 1:i + 3]]
        if core[0].isupper() and i > 0 and not re.search(r'[.!?]$', words[i - 1][2]) or any(CUES.match(x) for x in near if x):
            out[i] = (w[0], w[1], raw.replace(core, hit)) + tuple(w[3:])
    return out

def all_words():
    """every word in this file, for the settings page"""
    return len(CANON)

def similar(word, game='valorant', extra=(), n=3):
    """game names (and extra names, for example from the screen) that sound like this word, best first"""
    import difflib
    core = re.sub(r"^[^\w]+|[^\w']+$", '', word or '')
    if len(core) < 3 or not core.replace("'", '').isalpha(): return []
    k = _snd(core); out = []
    for nm in list(_names(game)) + [e for e in extra if e]:
        if nm.lower() == core.lower() or ' ' in nm: continue
        r = difflib.SequenceMatcher(None, core.lower(), nm.lower()).ratio()
        if _snd(nm) == k: r = max(r, 0.9)
        if r >= 0.72: out.append((r, nm))
    out.sort(reverse=True)
    return [nm for r, nm in out[:n]]
