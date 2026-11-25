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

Alternativ zum `pass`-Store kann der System-Keyring verwendet werden: Ohne
`pass_eintrag` (oder mit dem Flag `--keyring`) werden die Zugangsdaten aus dem
Keyring gelesen – ein Eintrag pro Portal, der Login-Benutzername ist der
Schlüssel des Eintrags, das Passwort das Geheimnis:

```console
    python -m keyring set elternportal/gym-a <benutzer>
```

Für Umgebungen ohne Secret-Service (z. B. Headless-Server, Cron) liefert das
optionale Extra `alt` alternative Keyring-Backends; es ist bei der Installation
mit `uv sync --all-extras` automatisch enthalten.

```ini
[gym-b]
bereiche = elternbriefe, fachlehrer, brett
```

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

### Mailversand

Neu gespeicherte Meldungen können mit `--mail` als E-Mail versendet werden –
eine Mail pro Meldung, Anhänge als echte MIME-Anhänge. Der Mailserver wird
global in der reservierten `[SMTP]`-Sektion konfiguriert, die Empfänger pro
Portal:

```ini
[DEFAULT]
bereiche = elternbriefe, fachlehrer, klassenleitung, brett
output_dir = ~/elternportal-nachrichten

[gym-a]
pass_eintrag = familie/eltern@gym-a
empfaenger = eltern@example.com

[gym-b]
pass_eintrag = familie/eltern@gym-b
empfaenger = eltern@example.com, oma@example.com

[SMTP]
server = mail.example.com
port = 587
starttls = yes
absender = elternportal@example.com
pass_eintrag = mail/elternportal@example.com
```

In `[SMTP]` sind `server` erforderlich sowie `port` (Standard 587),
`starttls` (Standard yes) und `absender` (Standard: SMTP-Benutzer) optional.
Das SMTP-Passwort kommt wie bei den Portalen aus `pass` (`pass_eintrag`,
erste Zeile = Passwort, `user:`-Zeile = Benutzername) oder – ohne `pass_eintrag`
bzw. mit `--keyring` – aus dem System-Keyring:

```console
    python -m keyring set elternportal/smtp <benutzer>
```

Portale ohne `empfaenger` werden beim Mailversand mit einer Warnung
übersprungen; `--mail` ohne `[SMTP]`-Sektion bricht mit einer Fehlermeldung ab.
Einzelne Mailfehler brechen den Lauf nicht ab – die Meldung bleibt gespeichert.

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

    # Zugangsdaten aus dem System-Keyring lesen (statt aus pass)
    fetch-elternportal --keyring

    # Neue Meldungen zusätzlich als E-Mail versenden
    fetch-elternportal --neu --mail
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
