# JelE Clipper: changelog

Everything that changed per version. The newest version is at the top.

## 6.53 · 12 November 2026

- **No more moments from just talking.** Saying "oh my god", "what", "no way" or talking fast is no longer enough on its own. A moment now needs something real around it: a kill, a death, a scream, a laugh, chat, a marker or a clip. Only when the AI is very sure (7 out of 10 or more) does a talk-only moment stay.
- **Stories.** The app now links moments that belong together, like "watch me clutch this" and what happened next, a toxic message and your answer later, or a joke that comes back. You see them above the moments under **Stories**.
- **Make story short.** One click makes one short out of the linked pieces, with a "LATER..." or "FAMOUS LAST WORDS..." card between them.
- When you say you will do something and then die, the app now sees that as a story too (a fail can be gold).

## 6.52 · 12 November 2026

### I find what you react to
- Around every good moment I now read all the text that appears on screen in the 45 seconds before it: messages in the game chat, the killfeed, banners. It goes on the timeline of the moment
- When you read a message out loud ("he said jele is the worst player..."), I find that message on screen. The clip starts just before the message appeared, not when you start reading it, and the message is shown big in the middle for 3 seconds, even when the layout cuts the chat off
- The cause of a reaction (the kill, the death, the weird angle, the message) is worked out for every moment. The clip always starts before it, and the opening teaser now shows that cause instead of you reacting
- The local AI knows this too: it is told that reacting to trash talk, a toxic or funny message, a weird angle or a lucky shot is good content, and that the cause is when something shows up, not when you talk about it
- A moment with clear facts (a message you read out loud, or a real cause plus your scream or laugh) is never thrown out by the AI

### Fewer replays
- The slow-motion replay at the end now only comes after a real play: a kill from the match data, or a clutch or skill moment. Never for talking, a reaction or a chat message

### "Oh my god" is not a moment
- What you say counts much less on its own. "Oh my god", "no way" and the like only count fully when something else happens close by: the game, gunshots, laughing or screaming, chat going off or a marker. Talking loudly is not a reason by itself
- A scream is now measured against how loud you normally talk, not against silence, so talking after a quiet bit no longer counts as screaming
- Two different things 15 seconds apart are now two moments (before, the second one was often lost)

## 6.51 · 12 November 2026

### Captions learn from your edits, without asking
- No more "Always fix?" pop-up when you change a word. I simply remember it, with the words around it
- Next time: a word you changed twice or more is always changed. A word you changed once is only changed when the words around it match the last time (so "yellow car" stays yellow, "yellow what is up" becomes "yo what is up")
- The words you taught me also go to the speech model, so it leans towards them when it is not sure what it heard
- Settings > Captions > words: "Learned from your edits" shows what I learned, with × to forget one. "Always fix" still works for words that must change every time

### Game names
- Names that sound almost the same now become the right name: "piper" becomes "Viper", also "viber" or "vyper", when it is used like a name (written as a name, or next to words like ult, their, killed, playing, smoke)
- Works for all agents, weapons and maps, and for the names in the other games

## 6.50 · 12 November 2026

### The AI decides which moments stay
- With the local AI installed, the AI now really decides: a moment it gives a 4 or lower is thrown out, not just moved down. A 10 counts almost double. It now looks at the 30 best candidates, and a moment it did not look at can never beat one it liked
- The AI got strict rules: mumbling, talking to yourself, the end screen, menus, the lobby, waiting and buy phase small talk are a 1 to 3. A 7 or more only when a stranger on TikTok would laugh, be amazed or feel the hype
- Tested with the real models: mumbling at the end screen got a 1 or 2 (out), an ace with a big reaction an 8

### The end screen
- I recognise the end screen after a match (scoreboard, Play again, Return to lobby, match summary) in Valorant, CS2 and Fortnite. A moment on the end screen drops far down, also without the AI
- Mumbling (lots of unclear words) while nothing happens in the game drops far down too

## 6.49 · 12 November 2026

### I understand what a moment is about
- For every good moment I now make a timeline of everything that happens, second by second: what you say, gunshots, laughing and screaming, what is on screen (dead, spectating, round won) and chat
- From that I work out the story: where it starts making sense, the payoff (the kill, the joke, the fail) and where your reaction is over. The clip is cut to that story, never starting or stopping in the middle of a sentence
- The edit follows the story: the zoom lands on the payoff, the teaser shows the second before it, a replay only when the play is worth seeing twice, cam + game when your reaction matters and game only when the play matters
- With the local AI it also says in words what happens ("sneaks behind a camper but gets shot") and what kind of moment it is (clutch, funny, fail...). You see this at the top of every moment and in the editor under Done for you
- Music that fits: the story says hype, funny, tension or chill. Put songs with that word in their name in your music folder, and auto shorts get a fitting song (in the editor you add it with one click)
- Tested with the real AI models on a made-up stream: the smart model found the story ("tried to sneak and got shot"), the timing rules fix what a model gets wrong

## 6.48 · 12 November 2026

### The AI judges every moment
- With the local AI installed, after every stream the AI reads what you said and what happened in the 20 best moments, and gives each one a mark from 1 to 10 with a short reason ("AI: knife kill at one hp, huge reaction")
- Good marks push a moment up, "just buy phase talk" pushes it far down. The AI also writes the title when it has a better one
- Tested with the real models: a clip with an ace and a big reaction got an 8, buy phase talk got a 2

### A smart AI model
- Settings > Captions > Local AI: choose Smart (4.7 GB, for a real graphics card like yours) or Small (1 GB, any pc). "Best for this pc" picks Smart when you have an AMD Radeon RX, NVIDIA RTX/GTX or Intel Arc card
- Smart writes clearly better titles and understands harder editor commands. Already have the small one? Click Install to get the smart one, the small one keeps working until then

### Editor
- "The ending feels flat" now ends the short earlier. When I only understand part of a sentence, the AI model takes the whole sentence

## 6.47 · 12 November 2026

### Editor
- "Trim it a bit, like 4 seconds": the number now belongs to the change, also when it comes later in the sentence

## 6.46 · 12 November 2026

### The editor understands you much better
- Type what you want in normal English or Dutch, also several things at once: "make it 5 seconds shorter and no music", "start at the kill", "it drags at the end", "captions bigger and higher", "cut out where I say sorry", "game only", "make it 20 seconds", "no teaser", "title: ONE TAP"
- About 45 kinds of changes: start and end, length, zoom (also "zoom here"), music on, off, quieter or louder, caption size, height, style and animation, layout, teaser, replay, stickers, killfeed, sound effects, swearing bleeps, loop, cutting out a word, undo, preview and export
- You always see what was done, or why not ("I did not find sorry in this short"). Quick buttons with examples sit under the field

### Clips with a better rhythm
- The build-up is about 10 seconds before the big moment (longer when you say "watch this" or "wait for it"), instead of always as long as possible
- No dead air at the start or the end: the clip starts when something happens and stops when the reaction is over (the game itself stays as build-up)

### Tell me what was wrong, I learn from it
- When you remove a short or a moment, you can tick what was wrong: boring, wrong moment, starts too early or too late, reaction cut off, goes on too long, bad title, captions wrong
- New clips start and end better with every "too early" or "cut off", and boring kinds of moments rank lower
- System > Analysis report: a small zip with what I found in your last 6 streams and your feedback (no videos, no passwords or keys). Send it to get the AI tuned to your streams

## 6.45 · 12 November 2026

### Picture understanding installs itself
- After the update, the app installs picture understanding (reading the text on screen, the cam following your face) by itself, once, when your pc is quiet: never during your stream or while shorts are being made
- Not with the Light setup. You can still install or turn it off yourself in Settings > Captions

## 6.44 · 12 November 2026

### Speech model shows the right status
- Fixed: after "Get it now", small.en kept showing as not downloaded. The app looked for the wrong folder name (small-en instead of small.en), so it never saw the model, even when it was there
- A model now only counts as ready when its model file is really in place, and large-v3 is no longer mixed up with large-v3-turbo

## 6.43 · 12 November 2026

### Local AI
- The AI engine is now online for "Install local AI" (tested with the real model before it was published)
- Better AI titles: the model gets an example first, and answers like "Game: ..." are never used as a title

## 6.42 · 12 November 2026

### I see what happens on screen (plan F2.4)
- I read the text in the picture around every moment: menus, "Killed by", "Spectating", "Buy phase", round and match results (Valorant, CS2, Fortnite and more)
- A moment that is mostly a menu drops far down the list. A moment no longer ends with a long stretch of spectating. "You won the round" and "you won the match" are reasons, and they count extra
- Works offline. Comes with the Full setup, or install it in Settings > Captions > Picture understanding (about 100 MB)

### The cam follows your face (plan F4.3)
- In the Cam + game layout the cam zooms in a bit and moves smoothly with your face, so you are always fully in view. Sit still and it simply stays centred on you

### Your friends in the captions (plan F2.3 and F3.5)
- Is Discord on its own OBS track? Pick it in Settings > Captions > Friends (Discord). Then I also write down what your friends say around each moment, and it shows in the captions in blue
- In the editor (step Text) you turn their captions on or off per short

### Check this frame (plan F3.2)
- Under the result preview: "Check this frame" makes the real export and shows exactly the moment you are at, so you can see the preview matches

### Local AI (plan F4.7, optional)
- Install a small AI model on your own pc in Settings > Captions > Local AI (about 1 GB, works without internet, never during your stream)
- It writes extra titles ("More titles (AI)" in step Text)
- New in the editor: type a change, for example "5 seconds shorter", "start 2 s later", "no zoom", "no music", "captions purple" or "title: ONE TAP". Simple sentences in English and Dutch also work without the AI model. Ctrl+Z undoes it

## 6.41 · 12 November 2026

### I hear what happens without words (plan F2.5)
- Laughing, screaming, cheering and fights (gunshots close together) now count as reasons for a moment, also when you say nothing. You see them as "you laughed", "you screamed", "a fight (5 shots)"
- Long music (a menu, a break, a song) counts a bit less, so those parts are less often a moment
- No AI model needed: it listens to the rhythm and pitch of the sound itself

### During the stream (plan F2.1)
- On the Live page you now see "Found so far": moments I already heard while you stream, like "you said no way" or "you laughed"

### Best 5 (plan F2.7)
- On the Moments page, "Best 5" shows only the 5 best moments of a stream. #1 to #5 get an orange badge

### Done for you (plan F3.3 and F4.4)
- In the editor (step Effects) a list shows what the app did by itself: zoom, killfeed, sticker, teaser, replay and cut boring bits, each with why. Take one out with ×

### Captions (plan F3.4)
- Select words in "What is said" and choose "New line here" or "One line" to decide yourself where a caption line breaks
- Drag a caption block on the timeline to move it a bit earlier or later

### Sound (plan F4.2)
- With your mic on its own track, your voice is put on top and the rest goes a bit quieter while you talk. A limiter keeps the loudest bits from clipping

### Posting (plan F4.5)
- "Text to post" is now a post card per platform: TikTok, YouTube Shorts and Instagram Reels each get the right title length and hashtags, and one button marks it as posted there
- "Fill in views" on the Shorts page: the views of all your posted shorts in one screen

## 6.40 · 12 November 2026

### Everything neat and in line, in the whole app
- Text in drop-down lists and search fields is now always in the middle. It used to be cut off at the bottom ("All tags", "Newest first", "No safe zones")
- Editor: a landscape short now shows your source and the result side by side, the source no longer disappears. The play buttons stay neat on a narrow screen, the "Clip" button text is in the middle, and story parts that are too small no longer show cut-off text
- Editor: the 5 caption animations sit on one line ("Typewriter" is now "Type")
- Shorts: every card is the same height, with the buttons at the bottom on one line. "Posted on" has 3 equal buttons, the status list is no longer squashed
- Today: the 5 numbers are evenly spread, Weekly montage sits next to the tip. In the to-do list only the first task has an orange button
- Moments: the "Search everything you ever said" box has its own spacing again and no longer sticks to the box above
- Settings: a menu click shows the group from the top, the Save button stays in the column of your settings, and the status next to a key ("empty") no longer makes the field narrower
- Long page titles and subtitles get "..." instead of pushing the buttons away

## 6.39 · 12 November 2026

### Captions no longer repeat the same sentence
- Fixed: with the graphics card engine the captions could get stuck and repeat one sentence over and over. The engine now starts fresh for every part, and repeated loops are cleaned up
- Old transcripts with such a loop are cleaned up when they are loaded. Click "Search again" on a stream to also get new titles and moments

### Better titles
- A title must have at least two real words: no more titles like "NO", "YO" or "4". Half sentences ("I CAN'T BELIEVE THE") are cut cleanly

### Your mic track
- The setup wizard and Settings no longer pretend the tracks in your file are OBS track numbers. When I don't know which OBS tracks were recorded, you pick your OBS track (1 to 6) yourself, and the list shows "In file: 1, 2, 3..." to listen to
- When OBS connects later, the real track numbers are picked up right away

### A cleaner editor
- Source and result side by side, with the play buttons right under your video, then the timeline and what is said
- The result preview now has the same height as your video, the step bar no longer covers the step title, and the editor uses the full width of big screens
- Tiny caption blocks on the timeline show as a slim bar instead of cut-off text

### Moments page
- The reason chips ("chat went off", "Clip button") were broken, they are readable again
- #1, #2 and #3 are now small orange badges, the same size as the rest, and the numbers follow the score

## 6.38 · 12 November 2026

### A clearer Settings page
- Settings now has a menu on the left: Finding clips, Captions, Video and look, Posting and phone, Connections and app, and System. You see one group at a time, in one readable column, instead of 20 cards in two columns
- Every group starts with what is in it. The most used settings come first
- Advanced settings are folded away per group ("Show 2 advanced settings")
- Search finds settings in every group, and shows which group each one is in
- In the OBS dock the Shorts filters no longer run off the screen

## 6.37 · 12 November 2026

### OBS dock (plan F4.6, first part)
- While you record, the dock now also shows which game it sees and how many minutes are already heard
- The Clip button in the dock has the same clean look as the rest of the app

## 6.36 · 12 November 2026

### The reaction stays in (plan F2.6, first part)
- A moment no longer stops in the middle of a reaction without words: when you scream, laugh or cheer right after the play, the moment runs until it is over (up to 4 seconds longer)

## 6.35 · 12 November 2026

### Shorts board (plan F4.5, first part)
- New: in Shorts you can switch between Grid and Board. The board has 4 columns: To review, Ready to post, Scheduled and Posted
- Drag a short to another column to change where it is (posted, scheduled, back to review)
- Every card has edit, post text, schedule and watch at hand. The app remembers whether you like the grid or the board

## 6.34 · 12 November 2026

### Your mic on track 6 (or any track)
- Fixed: the Clipper counted the audio tracks in the recording file, not the OBS track numbers. When OBS records for example tracks 1, 2 and 6, the file has 3 tracks and your track 6 showed up as "Track 3", and "Track 6" in Settings pointed at nothing
- The Clipper now remembers which OBS tracks every recording has, so Track 6 in Settings and in the setup is really your OBS track 6
- Is the track you picked not in a recording? Then the Clipper finds your mic itself instead of giving no captions
- "Set up OBS for me" now keeps the track you already use for your mic (for example 6), instead of moving it to track 2

## 6.33 · 12 November 2026

### OBS without a password
- Fixed: there was no clear way to connect OBS without a password. The setup now has a button "My OBS has no password", and Settings > Keys has "OBS without password". Both remove a saved password and test the connection right away
- When OBS has no password, the Keys list now says "not needed, connected" instead of "empty"
- Clearer messages when OBS does not connect: OBS asks for a password, the password is wrong, or OBS does not answer at all (with where to turn on the WebSocket server)

## 6.32 · 12 November 2026

### Captions on the timeline (plan F3.3, first part)
- New: a captions row above the timeline, with every caption line in its place. Click a line to go there, double-click it to change a word
- It follows your changes right away: fixed words, hidden words and cuts

## 6.31 · 12 November 2026

### The editor in 4 steps (plan F3.1, design C)
- The editor now works in 4 steps: 1 Cut, 2 Text, 3 Effects, 4 Done. Each step shows only what you need there, the rest is under "More options"
- Every step ends with a "Next" button, and "Make short" is always at the top
- Cut: start and end, cutting the boring bits, cutting all silences in one click, and jumping to the build-up, the peak, the reaction or the end
- Text: your captions and the title at the top, with a button that walks you past every unsure word ("Check unsure words, 3 left")
- Effects: layout, zoom, sound effects and music together (picture, extras and voice under More options)
- Done: file name and style, the rest under More options
- New: a story bar above the timeline that shows the build-up, the peak, the reaction and the end of your clip. Click a part to jump there
- New: double-click the captions in the preview to change the word that is said right then

## 6.30 · 12 November 2026

### The speech model on your graphics card, also AMD and Intel (plan F2.2)
- New in Settings > Captions > Runs on: "Install graphics card support". It downloads a graphics card engine (whisper.cpp with Vulkan, about 10 MB) and its speech model (large-v3-turbo, about 550 MB), in the background while you keep working
- After that the captions and the listening are done on your graphics card: AMD, Intel or NVIDIA. Much faster than the processor
- Never during your stream: while you stream the Clipper still listens along with the light model on a few processor cores, so your game keeps all of your graphics card
- If the graphics card engine does not work on your pc, the Clipper notes it and goes on with the processor by itself
- You can pick Automatic, Graphics card or Processor yourself
- The Full setup now also installs this for AMD and Intel Arc graphics cards

### Small fixes
- A Dutch word left in the setup ("Nu") is now English

## 6.29 · 12 November 2026

### Learns your look (plan F3.7)
- The editor now starts with the look of the last short you made yourself for that game: layout, caption style, size, height and animation, cuts, sound effects, progress bar and end card
- What you pick 10 times in a row for a game, the automatic shorts use too. Those shorts get a "learned from you" label (hover to see what was learned). Your own automatic preset always wins
- You can turn this off in Settings > Connections and app > Speed and safety

## 6.28 · 12 November 2026

### Nicer captions (plan F3.5, first part)
- Captions always stay inside the safe zone: never under the buttons and the text of TikTok, Reels and Shorts, also when you drag them very low or high
- Lines are a bit narrower, so they stay clear of the buttons on the right
- A name of two words (like an ability, a map or a name from your own word list) is never split over two caption lines
- Uh, um and ehm are left out of the captions (the sound stays). You can turn this off in Settings > Captions

## 6.27 · 12 November 2026

### Fixing captions is easier (plan F3.4, first part)
- Fixed: double-clicking a word in the editor to change it often did nothing (the first click redrew the list). It now always opens the word
- When you change a word, the Clipper asks "Always fix this in new captions?". One click and that word is fixed in every new short from then on (you find these in Settings > Captions: words)

## 6.26 · 12 November 2026

### Make shorts again (plan F3.6, first part)
- New: "Make again" on every short, and for many shorts at once (Shorts > Select > Make again). Handy after an update: your shorts get everything that got better
- You choose: keep your captions (your own edits, cuts and effects stay exactly as they are), or new captions from your voice, in the language you pick (English, Dutch, German, French, Spanish, or let it find out)
- The old short stays next to the new one, and a short you posted stays posted

## 6.25 · 12 November 2026

### Faster app on Windows
- The speed test found that on Windows every click in the app could wait about 2 seconds: Windows first tries the IPv6 address of "localhost", where the Clipper did not listen. The Clipper now listens there too, so the app answers right away

### Titles that fit the story (plan F2.8, first part)
- A title never claims something the match data says did not happen (no "ACE" when it was a 3K)
- New title from the facts of the play, for example "ACE WITH THE SHERIFF" or "1V3 CLUTCH TO WIN THE ROUND"
- "Clip that" is now a reason for a moment, never its title
- Words the speech model could not understand are never part of a title
- When you hover over a title suggestion, you see where it comes from: what you said, the match data, or why it is a moment

### Your mic track (plan F2.3, first part)
- Every stream now shows which audio track the captions listened to (your mic track or all audio), and why

## 6.24 · 12 November 2026

### Moments right after your stream (plan F2.1)
- New: the Clipper listens along while you stream. Every 5 minutes it turns the newest part of the recording into text, with the light speech model, at low priority and with only a quarter of your cores
- After the stream it only has to do the last few minutes, so the moments of a long stream are there much sooner
- It only does this on a strong pc (NVIDIA graphics card or 8+ cores), never when your pc is already busy, and only when OBS records to MKV (an MP4 cannot be read while it records; "Set up OBS for me" sets MKV for you)
- Next to "Recording" you see how many minutes are already heard
- The captions of your shorts still come from the best speech model, not the light one
- You can turn it off in Settings > Connections and app > Speed and safety

### "Clip that" works better (plan F2.7, first part)
- The Clipper now also hears "clip dat", "iemand clip dat", "dat moet geclipt worden", "someone clip that", "that's a clip" and more, in English and Dutch
- A moment you called with "clip that" now ends right after you say it, and starts at a pause before, so the play itself is in it
- The reason says when you said it, for example: you said "clip that" at 1:04:12

## 6.23 · 12 November 2026

### Speed test (plan F1.8)
- Every new version is now speed-tested on a clean Windows pc: opening the app, how fast it answers, finding the moments per minute of video and rendering a short with captions. The result is in the release notes on GitHub

### Fixed
- Work that waits (because you stream, your disk is full or your pc is busy) now stays visible in the queue while it waits, instead of looking like nothing is happening

## 6.22 · 12 November 2026

### New look and clearer menu (plan F1.5, F1.6 and F1.7)
- One style for the whole app in the JelE Studio colors: one font (Inter), a few fixed text sizes and roundings, the brand orange on dark blue
- The menu now has 5 items: Today, Moments, Editor, Shorts and Settings. Insights is now a tab inside Shorts, System is a tab inside Settings
- Today is now a to-do list: only what needs you (OBS not connected, a recording that stopped halfway, new shorts to pick, shorts ready to post, a new version), each with the button that does it. When nothing needs you, it says so
- The explanation at the top of Today only shows for new users
- Editor is always in the menu. With nothing open it tells you how to start
- Settings are split into 5 groups (Video and look, Captions, Finding clips, Posting and phone, Connections and app) and have a search field. Search also finds the Advanced settings
- The setup now has 4 steps: OBS, your mic, your cam, and the optional extras together
- New: "Set up OBS for me". One click (only when you click) and the Clipper sets OBS up for good captions: your mic on its own audio track 2, the game, music and Discord off that track, recording with both tracks, as MKV. It tells you exactly what it changed
- Keys 1 to 5 jump to the 5 menu items

## 6.21 · 12 November 2026

### Your own logo
- The JelE Studio logo is now used everywhere: the app icon, the shortcut, the icon next to the clock, the browser tab and the top left of the app (with the JelE wordmark in Syne)

### A nicer setup
- The setup now has a dark look in the JelE Studio colors, with the logo on the side and at the top
- The Light or Full choice is clearer: two choices, each with its size, which PC it fits and what it holds, and "Recommended for this PC" at the one that fits
- A welcome page and an end page that explain in short what the Clipper does and how you start it

## 6.20 · 12 November 2026

### A real setup (plan F1.4)
- New: JelE_Clipper_Setup.exe. It brings its own Python, so a new user does not have to install anything else
- Before installing you pick Light or Full, with an explanation of what each one holds:
  - Light (about 0.5 GB): for laptops and PCs without an NVIDIA graphics card. The speech model downloads the first time you need it
  - Full (about 4 GB): for gaming PCs with an NVIDIA graphics card. Also installs graphics card support for the speech model and downloads the speech models right away
- The setup looks for an NVIDIA graphics card itself and picks the version that fits as the default
- It makes the "JelE Clipper" shortcuts and can start the Clipper right away
- The uninstaller closes the Clipper first and asks before it removes your shorts and settings (default: keep them)
- Every new setup is built and test-installed on a clean Windows machine before it is added to a release
- The speech model now finds the graphics card support from the Full setup by itself
- start.bat, veilig.bat, herstel.bat and the OBS script work with both the setup and the old install

## 6.19 · 12 November 2026

### No more black window (plan F1.3)
- New: a "JelE Clipper" shortcut with the J icon, on your desktop and in the start menu. The Clipper puts it there by itself at the next start
- That shortcut starts the Clipper without the black window and opens it in its own app window, without tabs or an address bar
- The Clipper keeps running in the background as a J icon next to the clock: Open, Clip now, Log, Restart and Quit
- Updates and going back to an older version now restart the Clipper without opening new windows
- If the Clipper ever stops unexpectedly, it starts again by itself. If it keeps stopping, it opens the log so you can see why
- A new version that does not start is still put back to the previous one by itself
- The OBS script now starts the Clipper without a window too (only the icon next to the clock)
- The log of the last run is kept in data/clipper.log (and the run before that in clipper_vorige.log)
- start.bat still works and still shows the black window, handy when something is wrong

## 6.18 · 12 November 2026

### Safer and steadier (plan F1.1 and F1.2)
- The speech model now runs in its own process. If it crashes or runs out of memory, only that process stops: the Clipper keeps running, tries again with a lighter model and tells you what happened
- That speech process stays loaded between jobs, works at low priority, leaves cores free for your game and OBS, and on Windows can never use more than 60% of your memory
- The whole Clipper and all the video work it starts now run below normal priority, so your game, OBS and stream always go first. On an idle PC this costs no speed
- Stopping a job now also stops the speech model right away
- New work waits instead of breaking halfway when your disk has less than 2 GB free, and goes on by itself once there is room
- New heavy work waits a moment when your PC is already at its limit (it never waits for its own work). "Do it now anyway" still works
- The banner and the job card now say why the work waits: your stream, your disk or a busy PC

### Under the hood
- clipper.py is split into parts by topic in the new app folder (recording, analysis, speech, captions, rendering, library, server and more). Everything works the same

## 6.17 · 6 November 2026

### Changed
- The GitHub repository and the updates now only hold the Clipper app. The mascot, stingers, overlays, sounds and OBS scene collection are no longer in it. The ones on your PC stay exactly where they are: an update does not touch them, and the Clipper works without them

## 6.16 · 6 November 2026

### Privacy
- The team logo is gone from the mascot: the poster in the room backgrounds and the badge on the game frame now show the JelE logo, and the jersey has the JelE logo and colours
- Leftover channel emote names removed from the code

## 6.15 · 6 November 2026

### Changed
- Making a short no longer means it counts as posted. Every short now goes through clear steps: To review (made automatically) → Ready to post (made or kept by you) → Scheduled (when you pick a date) → Posted (only when you mark it)
- Mark per platform where you posted it: TikTok, YouTube or Instagram, right on the short. Click again to undo. The views box only shows up once a short is posted
- Shorts has its own lists for To review, Ready to post, Scheduled and Posted
- Insights and your weekly goal count posted shorts, by the day you posted them. Made but not posted yet is shown next to it, plus how many shorts are in each step
- On your phone: "Mark as posted", and tap again to undo
- Older shorts with views filled in are counted as posted

## 6.14 · 6 November 2026

### Better
- One story per short. The opening glimpse now shows the second just before the payoff (not the payoff itself), and the replay at the end shows that same payoff again. Both only appear when there is a real payoff (a multikill, a big shout or your Clip button) and when the clip does not already open with the action
- The title is there from the first frame: over the opening glimpse and on into the clip, instead of "wait for it" first and then a second text
- Cut boring bits is much more careful. A gap only goes out when you say nothing, the game is quiet AND the picture hardly moves (aiming and fights stay in). The run-up to the payoff, kills, clip presses, the first second and the last part are never cut, and at most a quarter of the clip goes out
- You now see those cuts in the editor: striped yellow on the timeline, and the video skips them while you play. Click a striped part to keep it in. What you see is exactly what gets exported
- Seamless loop really loops: no opening glimpse, replay or end screen any more when it is on, so the end flows straight into the start
- No more little clicks in the sound where pieces are glued together
- Captions: viewers never see a "..." for words that were not understood, and fewer words are given up on
- Settings: the captions are explained in three steps (listen, fix words, you check), with the word list right below them
- Keys are grouped by what they are for (OBS, Twitch, Valorant), with what each one adds and step-by-step how to get the Twitch and HenrikDev keys. Test Twitch now also shows your current category

## 6.13 · 6 November 2026

### New
- The clipper knows which game you play: Valorant, Counter-Strike 2, Fortnite, Minecraft, or "other / Just Chatting". It looks at the game in front on your PC while you record (every 3 minutes, so a switch from Valorant to Minecraft is noted too), then your Twitch category, your OBS capture, the name of the recording and what you say
- The editor follows the game: its own colour, title ideas ("I FOUND DIAMONDS", "VICTORY ROYALE", "ONE DEAG"), sticker texts with one-click picks, example texts, and the Killfeed button only for games that have one
- Finding moments listens for the big moments of that game: "victory royale" and "one pump" in Fortnite, "diamonds" and "MLG" in Minecraft, "one deag" and "noscope" in CS2
- Captions use the words of that game: CS2 weapons and maps, Fortnite items and moves, Minecraft mobs and items, each with its own fixes for common mishearings
- Titles and hashtags per game, also in the export packs per platform. Set your own hashtags per game in Settings > Games
- Valorant match data is only looked up for Valorant streams
- Wrong game? Change it at the top of a stream or the editor. "Find out by itself" lets the clipper decide again

## 6.12 · 6 November 2026

### New
- The speech recognition understands much more of how players talk about utility and fights: seized, naded, molly'd, flashed, stunned, caged, suppressed, nearsighted, tagged, dinked, beamed, one-way, lineup, satchel, TP, "he's in the smoke", "he's one", "lit for 140", "spike's down", anti-eco and about 300 more
- The speech model now gets a short example sentence in streamer speech, so it expects these words in the right way
- More mishearings fixed by themselves: "nated" becomes naded, "mollied" becomes molly'd, "ceased" becomes seized, "spikes down" becomes spike's down

## 6.11 · 6 November 2026

### New
- The speech recognition knows far more game words. Built in now: all Valorant agents (up to Miks and Hush) with every ability and ultimate, all weapons, maps, ranks, modes, callouts, skins, pro teams and players, Twitch emotes and words from other big games like CS2 and Fortnite
- Game words are put in their right spelling by themselves: "kill joy" becomes Killjoy, "kayo" becomes KAY/O, "blade storm" becomes Blade Storm, "diffuse the spike" becomes defuse. Everyday words like "split" or "ghost" are left alone
- Your own word list always fits now: the built-in list makes room for it, so your words are never cut off

## 6.10 · 6 November 2026

### Fixed
- "Phone cannot find the PC?" showed its tips as a squashed strip of text in a strange place. It borrowed the style of the playhead line from the editor; it now has its own neat box under the button

## 6.9 · 6 November 2026

### Fixed
- Updating with one click could fail and put the old version back. The updater replaces start.bat while that file is still running, and Windows then went on reading the new file at the wrong spot. start.bat is now built so this can not happen any more, also when you update from an older version
- The .bat files had the wrong line endings for Windows since 6.6

## 6.8 · 6 November 2026

### Fixed
- Clicking a video could leave you stuck: it opened native controls and full screen, and in the OBS dock you could not always get out again. A video now opens in a small player with a Close button, and Esc or a click outside closes it
- Full screen is turned off for videos in the dock, so you can no longer get trapped in it
- The bottom navigation in a wide dock: the orange line was far too wide, the keyboard hint showed up as a stray "1" under Inbox, and Live sat lower than the other buttons
- Every window (help, changelog, preview and so on) now closes with X, Esc or a click outside it, and the video inside stops playing
- In a small dock the Close button of a long window could fall off the screen; the title bar with the button now stays at the top
- "Look through shorts" in a low dock pushed the video off the top of the screen; it now sits side by side in a wide dock and scrolls in a narrow one

## 6.7 · 6 November 2026

### Fixed
- Live clips showed up between your streams, and the number of shorts per stream also counted test renders and deleted shorts
- "Search again" on a stream made the same automatic shorts a second time
- The bars in the post-ready score stayed at a quarter even at 100
- "Automatic" under Effects in the editor could give an error when an effect was selected
- In the dock, the "Stream done" overview could show up while you were still live, and live clips are now always newest first
- The word list fields and the speech model choice in Settings ran off the screen; the filter buttons above Shorts scroll in the dock
- Shorts this week no longer counts shorts in the recycle bin
- The last Dutch bits in the mascot control panel and the editor are now English

## 6.6 · 6 November 2026

### New
- The whole app is now in English: every screen, button, message, post text, the phone page and the mascot control panel

### Better
- File names still accept the old Dutch fields ({titel}, {datum}, {tijd}, {indeling}), next to the new {title}, {date}, {time} and {layout}

### Fixed
- The OBS scenes Starting soon, BRB, Queue, Agent select and Ending did not load in 6.5

## 6.5 · 6 November 2026

### New
- Get the speech model for captions in advance, with a progress bar (setup wizard and System). Your first short does not have to wait
- The setup wizard checks whether you have a Twitch VOD track without music in OBS, and tells you in a few steps how to set it up
- "Phone cannot find the PC?": the Clipper works out why (for example wifi set to Public, or a guest network) and tells you what to do
- A 4:5 version of every short for the Instagram and Facebook feed
- Fill in your Twitch name and team name under Settings > Keys

### Better
- Your channel, Valorant name and team name are no longer in the app files, only in your own config.js. After the update the Clipper puts them there by itself
- Without a channel name, a short no longer shows an empty label

## 6.4 · 6 November 2026

### New
- Brand profiles: your own colour, logo, font, channel name and end screen text, in one place (Settings, Brand)
- Upload a logo and pick a colour from it in one click
- Watermark: your logo small in a corner, for the whole short or only at the end
- Several profiles, for example for your team or a friend. In the editor you pick a profile per short
- Share profiles: export one as a file and load it at a teammate's
- Two sides: your view and a teammate's view stacked. The Clipper finds the moment by the sound
- More from every short: a Discord version under 10 MB, a GIF, 4 stills for Instagram and a meme version with a text bar
- Team folder: approved shorts go to a shared folder by themselves (or with one click)
- Stream recap: a text with your best moments, ready to paste in Discord or on X

### Better
- Text on your brand colour picks dark or white by itself, so it is always readable
- The preview in the editor shows your brand colour and channel right away

### Fixed
- The Export short button had become very narrow in 6.3
- "Made with JelE Clipper" overlapped your channel name

## 6.3 · 6 November 2026

### New
- Taste model: after 30 choices (keep or remove) the Clipper picks moments on your taste instead of fixed rules
- "Not like this again" in your inbox: moments like that rank much lower from now on
- Story detection: "watch this" followed by a hit within 15 seconds counts as the best kind of clip
- Every moment shows when it is the kind of clip you often keep
- Search everything you ever said, across all your streams, with a button to make a clip right away
- Shorts: search, tags (also automatic: ace, clutch, funny, live), favourites, archive and status (draft, done, scheduled, posted)
- Tag, mark as posted, archive, delete or export several shorts at once
- Recycle bin: deleted shorts can be restored for 7 days
- Insights: shorts and views per week, your best shorts, what works (layout, kind of moment, teaser, length, score, day and hour) and the best hour to post
- Weekly goal with progress, and a weekly report on your phone every Sunday
- Two days after posting, a notification asks for the views
- The Clipper learns from your edits and suggests a better default ("You often remove the teaser...")
- Problems you never fix count less in the post-ready score
- Phone: installable as an app, inbox with keep and remove, edit title and hashtags, tick posted and fill in views
- A notification on your phone opens the right short right away

### Better
- Live clips no longer show up between your streams
- Backups now also contain what the Clipper learned about your taste and edits

## 6.2 · 6 November 2026

### New
- Live clips: press Clip during your stream, OBS saves the last seconds (replay buffer) and the short is in your dock within a minute
- Stream Deck button: a "Website" button to http://localhost:8765/api/clip
- "!clip 30" in chat for a longer clip
- No clips on scenes like Starting soon, BRB, Pause and End
- Same moment clipped several times (you, a mod, !clip)? Then it becomes one clip
- Hype meter in the dock: how busy chat is now compared to normal
- Warning when OBS drops frames during your stream
- Overview after your stream in the dock: live clips, ready and marked
- Your mascot shows "CLIPPED!" when something gets clipped
- Post-ready score: every short is checked on picture, sound and editing, with a score from 0 to 100
- Fix per problem (opens the editor with the improvement) and "Fix everything and make it again"
- Export pack: per platform the video, post text with its own hashtags, cover and captions (SRT) in one folder
- Seamless loop: the end flows into the start
- Safe zones of TikTok, Shorts and Reels in the preview
- Custom file names with {title}, {date}, {time} and {layout}

### Better
- Clips during your stream are made with low priority, so your game and stream do not stutter
- An OBS replay is only used once it has been fully written

## 6.1 · 6 November 2026

### New
- Editor with tabs: Layout, Text, Effects, Audio and Export, with the export button always in view
- Preview of the result: a quick, small version with teaser, replay and music before you export
- Cut through the text: shift+click a piece of text and choose Cut out, or Back to restore it
- Cut silences with one button (longer than 0.6, 0.8 or 1.2 seconds)
- Magnet: the edges of your clip snap to the start or end of a word
- Autosave: your edit is back when you return later, undo too
- Drag the ratio between cam and game in the preview itself
- Whole frame: blurred, solid or gradient background, with rounded corners and a border in your colour
- Line between cam and game on or off
- Preview without the phone frame or full screen
- Caption animations: pop, bounce, typewriter, per word or none
- Unsure words with a yellow dotted line; Tab jumps from unsure word to unsure word
- Find and replace in the captions, with "always fix like this"
- Word list for names and emotes, and edit the voiceline list in the app
- Put a piece of text on the voiceline list in one click
- Bleep swearing, with asterisks in the captions
- Caption timing in one slider

### Better
- Never a single lonely word on a caption line again
- Changelog in the app: click the version number at the bottom left
- Updates come from JelE123/JelE-clipper on GitHub by default
- Clear message when there is no release on GitHub yet

## 6.0 · 6 November 2026

### New
- Update with one click through GitHub, and go back to a previous version with one click
- If a new version does not start properly, the Clipper puts the previous one back by itself
- Error report with one click, without passwords or keys
- Self-test on every start: if your graphics card does not work, it switches to your processor by itself
- Warning in the dock when you go live without recording, with a button to start recording
- Warning when your disk is almost full, with how many hours of recording still fit
- MKV recordings become MP4 by themselves after the stream; the MKV goes to the recycle bin
- A backup of your settings, library and taste every day
- Fill in keys (OBS, HenrikDev, Twitch) in the app instead of in Notepad
- Setup wizard: OBS, your mic, cam and killfeed, post text, phone
- Safe mode (veilig.bat): shorts without effects and music
- "What's new" after every update, and this changelog

### Better
- New design: the same buttons, cards and spacing everywhere, soft transitions and loading placeholders
- Light working copy of your recording: the editor jumps through the video much faster
- Make two shorts at the same time, and the queue continues after a crash or restart
- During your stream the heavy work waits, so your stream does not stutter
- Time estimate that learns how long things take on your PC
- Settings in Basic and Advanced, with a question mark and explanation for every part
- Tour the first time, and shortcuts everywhere (press ? for the overview)
- Clear error messages in plain language instead of Python errors
- Phone access only through your own wifi, and it turns off by itself after a week of not using it
- The app can only be opened from your own PC

### Fixed
- If you started the Clipper twice, the second one could mess up the queue of the first
- Passwords with a quote in them were not read correctly from config.js

## 5.0 · 6 November 2026

### New
- Effects as blocks under the timeline: zoom, killfeed, stickers, teaser and replay, all draggable
- Music from your own folder, which gets quieter by itself when you talk
- Saying "clip that" during your stream counts as the Clip button
- Highlights: a landscape YouTube summary with chapters
- Thumbnails, scheduling posts with a notification on your phone, and quick pick (Y keep, X remove)
- Add a video through a link (Twitch, Medal, YouTube), a file, a whole folder or by dragging it into the window
- Storage: see how much space your recordings take and move old ones to the recycle bin
- Set the killfeed box under Where is your cam

## 4.0 · 5 November 2026

### New
- Match data: your 3Ks, 4Ks, aces and clutches from your Valorant matches become clips
- Twitch clips from viewers count too
- Cut boring bits, sound effects, montages per stream and per week, three titles to choose from
- Notification on your phone when your shorts are ready (ntfy)
- Fill in views, so it learns what really scores
- Save styles in the editor
- Undo and redo (Ctrl+Z and Ctrl+Y)

## 3.0 · 5 November 2026

### New
- Looks in the editor: size and height of the captions, position of the game, size of the cam, progress bar and end screen
- Text to post with every short
- Your shorts on your phone through a QR code
- System: a check of everything that can go wrong, a test short and the log

### Better
- The dock in OBS has been redesigned

## 2.0 · 5 November 2026

### New
- Inbox: after every stream the Clipper makes your best shorts by itself, and learns from what you keep
- Zoom in on hype at "no way", "let's go" or the Clip button
- The cam frame is taken from OBS on every recording
- Look through the video yourself and make your own clips

### Better
- Better speech model for the captions; what it does not understand becomes "..."
- Voicelines and music stay out of the captions

### Fixed
- Searching only took the first 20 seconds of a recording
- Errors making shorts and captions with newer ffmpeg versions
