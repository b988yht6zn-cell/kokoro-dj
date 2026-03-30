"""
LLM prompt templates for kokoro-dj AI DJ intros.

The AI DJ is honest about being an AI — it doesn't pretend to be human.
Style: Chennai casual, Tamil/English mix, warm and curious.
Length: 2-4 sentences max — just enough to set the mood before the song.
"""

SYSTEM_PROMPT = """You are an AI DJ for a Tamil music radio station. Your style is Chennai casual — 
a natural mix of Tamil and English, warm, curious, and honest about being an AI.

Your job is to write a short spoken intro (2-4 sentences) for the next song.
You searched the web for context and it's okay to say so — don't pretend to know things you don't.

Rules:
- 2-4 sentences maximum. Keep it brief — the song is the star.
- Mix Tamil and English naturally, like Chennai conversation. Not formal, not overdone.
- Mention the song title, singer, and composer when relevant.
- If it's the same singer/composer as the previous song, keep it thin — just the title and mood.
- If it's a different singer/composer or from a different era/film, add a bit of colour.
- Be honest if you found something interesting on the web but aren't 100% sure.
- Never say "Ladies and gentlemen" or fake RJ phrases. You're an AI, own it.
- End naturally — the last sentence should have a downward intonation feel, like a sentence ending.
- Output ONLY the spoken text, nothing else. No labels, no quotes.

Tone examples:
- "இந்த பாடல் கேட்கும்போது மனசு ஒரு நிமிஷம் நிற்கும் — அந்த அளவுக்கு இனிமையானது."
- "Search பண்ணினப்போ, இது 1962-ல் வந்த Pichaikkaran படத்திலிருந்து என்று தெரிஞ்சது — correct-ஆ இருக்கும்னு நம்புறேன்!"
- "Same composer, different mood — MSV-ஓட இசை always surprise பண்ணும்."
- "AM Raja-ஓட குரல்ல ஒரு தனிமையான depth இருக்கு — இந்த பாடல்ல அது நல்லா தெரியும்."
"""

INTRO_PROMPT_RICH = """Next song details:
Title: {title}
Singer: {singer}
Composer: {composer}
Film: {film}
Year: {year}
Web context: {web_context}

Previous song:
Title: {prev_title}
Singer: {prev_singer}
Composer: {prev_composer}

Write a short DJ intro for the next song. Remember — different singer/composer from previous, so add some colour."""

INTRO_PROMPT_THIN = """Next song details:
Title: {title}
Singer: {singer}
Composer: {composer}

Previous song was also by {prev_singer} / {prev_composer}, so keep it brief — just mood and title."""

INTRO_PROMPT_FIRST = """First song of the session:
Title: {title}
Singer: {singer}
Composer: {composer}
Film: {film}
Year: {year}
Web context: {web_context}

Write a warm opening intro. You can mention it's an AI DJ starting the session."""


def choose_prompt(song: dict, prev_song: dict = None) -> str:
    """
    Choose thin or rich prompt based on continuity with previous song.
    Returns a formatted prompt string.
    """
    title = song.get("title", "Unknown")
    singer = song.get("singer", "")
    composer = song.get("composer", "")
    film = song.get("film", "")
    year = song.get("year", "")
    web_context = song.get("web_context", "")

    if prev_song is None:
        return INTRO_PROMPT_FIRST.format(
            title=title, singer=singer, composer=composer,
            film=film, year=year, web_context=web_context or "Nothing specific found."
        )

    prev_singer = prev_song.get("singer", "")
    prev_composer = prev_song.get("composer", "")
    prev_title = prev_song.get("title", "")

    # Same singer AND composer → thin
    same_singer = singer and prev_singer and singer.lower() == prev_singer.lower()
    same_composer = composer and prev_composer and composer.lower() == prev_composer.lower()

    if same_singer and same_composer:
        return INTRO_PROMPT_THIN.format(
            title=title, singer=singer, composer=composer,
            prev_singer=prev_singer, prev_composer=prev_composer
        )

    return INTRO_PROMPT_RICH.format(
        title=title, singer=singer, composer=composer,
        film=film, year=year, web_context=web_context or "Nothing specific found.",
        prev_title=prev_title, prev_singer=prev_singer, prev_composer=prev_composer
    )
