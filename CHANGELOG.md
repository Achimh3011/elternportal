# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-11-26

### Added
- Automatic retries for transient portal errors (disconnects, timeouts, "Server
  disconnected") with up to three attempts via
  [stamina](https://github.com/hynek/stamina); HTTP status errors are not
  retried.
- CI via GitHub Actions: ruff, ty and pytest run on every push and pull
  request, on Linux and macOS.
- This changelog, project URLs, trove classifiers and a `py.typed` marker.

### Changed
- Relicensed under Apache License 2.0 (previously GPL-3.0-or-later).

### Fixed
- The per-portal `state.json` is only written when something actually
  changed, so a run without news can no longer clobber a state file in a
  directory shared between machines.

## [0.2.1] - 2026-11-26

### Added
- The state file now lives per portal as `state.json` inside its `output_dir`,
  so the directory can be shared between machines (e.g. via Syncthing or
  Nextcloud). The legacy global state is migrated automatically on the first
  run per portal; dry-runs never write.

### Changed
- A per-portal `output_dir` is now used as-is; only a value inherited from
  DEFAULT gets the portal slug appended, so shared directories stay
  separated.

## [0.2.0] - 2026-11-25

### Added
- Mail delivery of new messages with `--mail`: one mail per message with
  attachments as MIME parts. Global `[SMTP]` section with separate `benutzer`
  (SMTP login) and `absender` (From address), `empfaenger` per portal,
  credentials from pass or the system keyring, `Date` header set to the
  message timestamp and a unique `Message-ID`. With `--mail` active the mail
  replaces the terminal output for mailed messages.
- Optional `alt` extra with alternative keyring backends for headless
  environments.

## [0.1.0] - 2026-11-24

### Added
- Initial release: fetch new messages from eltern-portal.org portals as
  Markdown, with saved attachments and extracted text from PDFs and Word
  documents. Counting mode by default, fetching with `--neu`, `--letzte n`
  for the most recent messages, terminal display, read confirmation of
  Elternbriefe, per-portal `bereiche` and `output_dir` overrides, and
  credentials from pass or the system keyring.
