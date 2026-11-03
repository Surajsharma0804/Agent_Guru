# One week of daily use

A checklist for using Agent Guru every day for a week and writing down what goes wrong.
Commands are run from the repository folder with the virtual environment active
(`.venv\Scripts\activate`).

## Start it

1. Make sure Ollama is running. If it is not, the assistant now says "My language model is
   not running. Start Ollama and try again." Start it from the Start menu or with `ollama serve`.
2. Turn on the local API once, so the typed commands below can reach the running assistant:
   `python -m Agent_Guru config set AGENT_GURU_API true`
3. Start the assistant in one of two ways:
   - `python -m Agent_Guru service start` runs it in the background and writes a log file.
     Use this for the week. `python -m Agent_Guru service stop` stops it cleanly.
   - `python main.py` runs it in this console. Its log goes only to the console, so
     `logs` (below) has nothing to read. Stop it with Ctrl+C.

## Five things to try each day

Say "Hey Guru" or "Hey Maya" first, or type them with `python -m Agent_Guru ask "..."`.

| Say | What should happen |
|:--|:--|
| "Good morning" | The briefing: time, weather, news, today's reminders |
| "What's the weather in <your city>?" | The weather, spoken without the source link |
| "Remind me to drink water in 20 minutes" | A reminder, spoken when it is due |
| "How do you say thank you in Hindi?" | An answer, not the briefing |
| "What time is it?" | The time and date from this computer |

## Mute and unmute

- `python -m Agent_Guru mic mute` stops it listening; the microphone is closed.
- `python -m Agent_Guru mic unmute` starts it listening again.
- `python -m Agent_Guru mic` says which it is.

## Rate the answers

Ratings feed `python -m Agent_Guru learn tune`, which only keeps a prompt change that
measures better.

- Right after an answer, say or type the whole sentence "that was right" or "that was
  wrong" ("sahi tha" and "galat tha" work too). A sentence that goes on, such as "that's
  wrong, the capital is Delhi", is treated as a correction, not a rating.
- At the end of the day, `python -m Agent_Guru learn rate` goes through the recent unrated
  turns and asks right or wrong for each (`--limit N` to choose how many).

## Logs

- `python -m Agent_Guru logs` prints the last 20 warnings and errors on one screen
  (`--limit N` for more).
- The files are `%LOCALAPPDATA%\agent_guru\service.log` (background runs) and
  `%LOCALAPPDATA%\agent_guru\logs\errors.log`.
- `python -m Agent_Guru doctor` checks the machine: Ollama, the model, the microphone.

## Problems

Write one row per problem, as soon as it happens. "What happened" is what you saw or heard,
not a guess at the cause. Run `python -m Agent_Guru logs` right after and note anything
from that minute.

| Date and time | What I said or typed | What happened | Log lines from that minute |
|:--|:--|:--|:--|
| | | | |
| | | | |
| | | | |
| | | | |
| | | | |
