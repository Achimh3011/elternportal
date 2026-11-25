# fetch-elternportal

Holt neue Nachrichten aus Eltern-Portalen (eltern-portal.org) und speichert sie
als Markdown – inklusive Anhänge und extrahiertem Text aus PDFs und Word-Dokumenten.

## Installation

```console
    uv sync --all-extras
    prek install
```

## Konfiguration

Die Konfiguration liegt unter `~/.config/elternportal/fetch-elternportal.conf`:

```ini
[DEFAULT]
bereiche = elternbriefe, fachlehrer, klassenleitung, brett
output_dir = ~/elternportal-nachrichten

[gym-a]
pass_eintrag = familie/eltern@gym-a

[gym-b]
pass_eintrag = familie/eltern@gym-b
```

Jede Sektion entspricht einem Portal (Slug der Subdomain von `eltern-portal.org`).
Die Zugangsdaten werden aus `pass` gelesen: erste Zeile = Passwort, `user:`-Zeile = Benutzername.

`bereiche` und `output_dir` können pro Portal überschrieben werden (der
`DEFAULT`-Wert gilt nur, solange ein Portal selbst nichts angibt) – z. B. für
Portale ohne Klassenleitung oder mit eigenem Ablageverzeichnis:

```ini
[gym-b]
pass_eintrag = familie/eltern@gym-b
bereiche = elternbriefe, fachlehrer, brett
output_dir = ~/nachrichten-gym-b
```

Nicht konfigurierte Bereiche werden gar nicht erst abgefragt; die Warnung
„Bereich … nicht verfügbar" erscheint dann nicht mehr. Ohne eigenes
`output_dir` landen die Nachrichten eines Portals unter
`<output_dir>/<portal-slug>/<bereich>/`.

## Nutzung

```console
    # Status: Anzahl neuer und bekannter Meldungen je Portal/Bereich
    fetch-elternportal

    # Neue Meldungen abholen (speichern, anzeigen, bestätigen)
    fetch-elternportal --neu

    # Nur ein Portal
    fetch-elternportal --neu --portal gym-a

    # Nur anzeigen was neu wäre (ohne zu speichern)
    fetch-elternportal --neu --dry-run

    # Ohne Lesebestätigung (z. B. zum stillen Archivieren)
    fetch-elternportal --neu --keine-bestaetigung

    # Ohne Terminal-Ausgabe und ohne Öffnen von Anhängen (z. B. Cron)
    fetch-elternportal --neu --keine-ausgabe

    # Die 5 neuesten Meldungen eines Portals erneut holen (unabhängig vom Lesestatus)
    fetch-elternportal --letzte 5
```

Neue Nachrichten landen unter `output_dir/<portal>/<bereich>/<datum>-<nummer>.md`
(mit pro Portal überschreibbarem `output_dir`), Anhänge im selben Verzeichnis.
Bereiche, die ein Portal nicht anbietet, werden mit Warnung übersprungen.

Neue Meldungen werden im Terminal ausgegeben (Text als Markdown); vorhandene
Anhänge werden mit `xdg-open` geöffnet. Hat eine Meldung keinen Textkörper, wird
stattdessen der extrahierte Anhang-Text ausgegeben, sofern er lesbar ist –
sonst wird der Anhang geöffnet.

Elternbriefe werden nach dem Abrufen **als gelesen bestätigt** (inklusive des
Bestands vom Erstlauf); mit `--keine-bestaetigung` wird darauf verzichtet.

Mit `--letzte n` werden die n neuesten Meldungen pro Portal abgeholt – über alle
Bereiche hinweg nach Datum sortiert, unabhängig davon, ob sie schon bekannt sind.
Nützlich, um sich die letzten Meldungen erneut anzeigen zu lassen; Kombinierbar
mit `--keine-bestaetigung` und `--keine-ausgabe`.
