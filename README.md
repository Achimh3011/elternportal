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

## Nutzung

```console
    # Alle konfigurierten Portale abrufen
    fetch-elternportal

    # Nur ein Portal, nur anzeigen was neu wäre
    fetch-elternportal --portal gym-a --dry-run
```

Neue Nachrichten landen unter `output_dir/<portal>/<bereich>/<datum>-<nummer>.md`,
Anhänge im selben Verzeichnis. Bereiche, die ein Portal nicht anbietet, werden mit
Warnung übersprungen. Lesebestätigungen für Elternbriefe werden **nicht** ausgelöst.
