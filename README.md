# SnapBot

Discord bot voor een via ADB verbonden Android-telefoon. De enige schermdumpmethode
is een blijvende `uiautomator2`-verbinding. ADB voert de tikken uit.

## Installeren

Gebruik Python 3.11+, ADB in PATH, een ontgrendelde telefoon met USB-debugging,
en Snapchat met een aangemeld account.

```bash
python3 -m venv env
source env/bin/activate
python -m pip install -r requirements.txt
adb devices -l
python3 bot.py
```

Stel `DISCORD_TOKEN` in als omgevingsvariabele, of gebruik `config.ini` met
`[BOT]` en `token=...`. Bij meerdere ADB-apparaten kies je de telefoon met
`ANDROID_SERIAL`. Voor de eerste UI-verbinding start uiautomator2 zo nodig
zijn automatiseringsservice op de telefoon.

Er is geen backendkeuze meer; `SNAPBOT_XML_BACKEND` wordt niet gebruikt.
Alle Python-afhankelijkheden staan in `requirements.txt`.

## Werking

- `!snap`: controleert ADB-aanwezigheid, toestemming en shelltoegang vóór de invoervragen.
- Geef de exacte zichtbare ontvangernaam en het aantal snaps op; `/quit` stopt de invoer.
- Een zichtbare unieke naam wordt direct geselecteerd. Zoeken is de fallback.
- Beide waargenomen Snapchat-schermvarianten worden ondersteund.
- De bevestigingsbalk moet precies de bedoelde ontvanger tonen vóór verzending.
- Verse XML wordt voor de bijbehorende klik hergebruikt; onzekere verzendklikken
  worden niet blind herhaald.
- Na elke 200 afgeronde snaps wordt Snapchat herstart, alleen als nog snaps volgen.
  De teller blijft behouden en de ontvanger wordt opnieuw gecontroleerd.
- Herstel via de terugknop vóór verzending telt niet als een afgeronde snap.

Andere bestaande opdrachten: `!addsnap`, `!status`, `!logs`, `!purge`.
`!status` gebruikt de huidige bestaande botstatus; de teller wordt pas na een
voltooide run bijgewerkt en is geen live voortgangsrapportage.

Direct zonder Discord:

```bash
python3 script.py clo 450
```

Gebruik de telefoon niet handmatig tijdens een run. Houd hem ontgrendeld;
`adb shell svc power stayon true` kan slapen tijdens het laden voorkomen,
maar omzeilt geen pincode. Een voltooide UI-flow is geen bewijs van serverbezorging.
Bij ADB-verlies, onbekende schermen of onzekere selectie/verzending kan de run
nog stoppen; automatisch pauzeren/hervatten is niet toegevoegd.

## Logging en onderhoud

Logs staan standaard in `botlog.log` en roteren dagelijks. Met `BOT_LOG_FILE`
is het pad instelbaar. Klik-, dump- en wachttijden worden gelogd zonder een
persistente timinghistorie. Bestaande `xml/screen_wait_profile.json`-bestanden
worden niet meer gelezen en mogen desgewenst handmatig verwijderd worden.

De oude CLI-dumpbackend, backendbenchmark, aparte snelle requirements,
GUI-prototype en ongebruikte dubbele helpermodules zijn verwijderd.
Snapchat-updates kunnen selectors veranderen; controleer bij fouten de actuele XML.

## Validatie na bijwerken

```bash
python3 -m py_compile bot.py script.py script_adduser.py utils/__init__.py utils/ui_dump.py utils/clicking.py utils/recipient_ui.py
```

Test eerst 3 snaps en daarna 450, inclusief herstarts na 200 en 400.
