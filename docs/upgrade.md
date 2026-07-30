# Upgrade Guide

This document describes changes that may affect users upgrading from previous versions.

## Upgrading from v0.9.3 to v1.0.0

### Service Layout and Ownership

The standalone installer and Debian package now keep executable code root-owned and
separate mutable runtime data:

| Component | Linux | macOS |
|-----------|-------|-------|
| Code and virtual environment | `/opt/meshcore-bot` | `/usr/local/meshcore-bot` |
| Configuration | `/etc/meshcore-bot/config.ini` | `/usr/local/etc/meshcore-bot/config.ini` |
| Database and local plugins | `/var/lib/meshcore-bot` | `/usr/local/var/lib/meshcore-bot` |
| Logs | `/var/log/meshcore-bot` | `/usr/local/var/log/meshcore-bot` |

Run `sudo ./install-service.sh --upgrade` from an updated source checkout. The
installer requires Python 3.10+ and `rsync`. It stops an active service before the
database migration, copies relative-path databases coherently, rewrites the migrated
configuration, builds a fresh virtual environment, and restarts a service that was
active before the upgrade.

Before upgrading, keep a separate backup of your configuration and database. The
installer preserves:

- the active configuration and absolute custom paths;
- relative-path databases, logs, and the `local/` plugin tree;
- installed-only files under `modules/commands/alternatives/`.

Trusted source versions still replace shipped alternative commands. If the upgrade
fails after stopping an active service, the installer attempts one best-effort restart
and retains the original failure exit status. Inspect the reported error before
retrying.

### Configuration Compatibility

v0.9.3 shipped configuration examples pass the v1.0.0 strict validator. Normal startup
warns about unknown sections or keys without refusing to start. You can check a config
before upgrading:

```bash
python3 validate_config.py --config /path/to/config.ini --strict
```

### Outbound HTTP and Feeds

Outbound HTTP now validates every resolved address and redirect. Private feed URLs
remain disabled by default; set `allow_private_urls = true` only for intentional
private-network feeds. Cloud metadata and non-unicast destinations remain blocked.
Feed responses are bounded by `max_response_bytes` and `max_parsed_items`.

`[Feed_Manager]` numeric limits are now clamped to sane minimums instead of being
used as written. **If you set `max_items_per_check = 0` to pause posting, that no
longer works** — it now scans and posts one item per poll. Use
`feed_manager_enabled = false` to stop the feed manager, or `feed disable <id>` for a
single feed.

### Optional Geocoding Data

`pycountry` and `us` remain optional under the `geo` extra. Install them for improved
country and US-state normalization:

```bash
pip install -e ".[geo]"
```

The standalone installer also offers the geocoding extras interactively.

### Optional Sender-Language Detection

Greeting-style commands can reply in the sender's language. The feature is off by
default and changes no behavior until you enable it:

```ini
[Localization]
auto_detect_language = true
```

Detection is keyword-first, so short greetings work with no extra dependency. For
statistical detection of longer messages, install the optional `lang` extra:

```bash
pip install -e ".[lang]"
```

Replies fall back to the configured `language` whenever the message is ambiguous,
the detector is unavailable, or that translation catalog is not installed.

## Upgrading from v0.8 to v0.9

- Python 3.10+ is required.
- The global `[Aliases]` section was replaced by per-command `aliases =` keys.
- Database migrations run automatically at startup.
- Review web-viewer authentication before binding beyond localhost.
- Connection and radio settings still require a process restart after changes.

## Upgrading from v0.7

### Config Compatibility

Previous config files continue to work. The following legacy config formats are supported:

- **`[Jokes]`** with `joke_enabled` / `dadjoke_enabled` — Migrated to `[Joke_Command]` and `[DadJoke_Command]` with `enabled`. Both formats work; consider updating to the new format.
- **`[Stats]` / `stats_enabled`**, **`[Sports]` / `sports_enabled`**, **`[Hacker]` / `hacker_enabled`**, **`[Alert_Command]` / `alert_enabled`** — All support the legacy `*_enabled` key; the new `enabled` key is preferred.

### Banned Users: Prefix Matching

`[Banned_Users]` uses **prefix (starts-with) matching** for `banned_users` entries. A banned entry `"Awful Username"` matches both `"Awful Username"` and `"Awful Username 🍆"`. If you rely on exact matching, ensure your banned entries are specific enough.

### New Optional Sections

- **`[Feed_Manager]`** — If you use RSS/API feeds, add this section. If absent, the feed manager is disabled. New installs and minimal configs include `[Feed_Manager]` with `feed_manager_enabled = false`.
- **`[Path_Command]`** — New options like `path_selection_preset`, `enable_p_shortcut` (default: true), and graph-related settings. Omitted options use sensible defaults.
