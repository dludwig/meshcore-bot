# Changelog

All notable changes to this project are documented here. The format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
semantic versioning.

## [Unreleased]

### Added

- Rebuilt web-viewer dashboard, served from a background snapshot instead of
  recomputing statistics on every request. A refresher thread in the viewer
  process writes `daily_rollup` (one row per local date) and
  `dashboard_snapshot` (a single JSON row), so a page load reads one row rather
  than running ~50 aggregate queries five times over.
- Daily trends that outlive retention: `message_stats` and friends are pruned at
  7 days and `packet_stream` at 3, so a 30-day chart had nothing to draw from
  until now. Signal metrics are stored as sums and counts, never means, so any
  window re-aggregates correctly.
- New `/api/dashboard/{summary,series,top,windows,refresh}` endpoints. `summary`
  sends a strong `ETag`, so the page's 30-second poll is normally a bodyless
  `304`, and polling stops entirely while the tab is hidden.
- New dashboard tiles and charts: routing mix (flood vs direct), hop-count and
  path-length histograms, a 30-day multibyte adoption trend, busiest repeaters,
  and a role mix.
- Direct-neighbour signal panel: the nodes heard with no repeater in between,
  their SNR distribution, and the weakest links named. Scoped to `hop_count = 0`
  because that is the only population where SNR means anything — a relayed
  packet's SNR measures the last hop into this radio, not the link to whoever
  sent it, so a network-wide average describes nothing in particular.
  `complete_contact_tracking` records signal for exactly the zero-hop contacts,
  so this is a complete census of the neighbours rather than a sample.
- New `[Web_Viewer]` settings: `dashboard_snapshot_enabled`,
  `dashboard_snapshot_interval_seconds`, `dashboard_snapshot_history_days`, and
  `dashboard_packet_backfill_rows`.
- Partial index `idx_packet_stream_undimensioned` as the backfill worklist.
  Probing for remaining un-dimensioned rows was otherwise a full table scan,
  and it cost the same 4.6 seconds *after* the backfill finished as during it,
  because finding nothing still meant reading everything.

### Changed

- Time-window selectors are now built from each source's configured retention.
  The dashboard previously offered "30d" and "All" against tables pruned at 7
  days, so three of the four choices returned the same number under a label
  that claimed otherwise.
- The incoming-packet chart no longer claims to show 7 days. `packet_stream` is
  pruned at 3 days, so the covered window is now measured and labelled from the
  data — and shown beside a genuinely 7-day contacts chart it can be compared
  to.
- `packet_stream` gained denormalized `route_type_name`, `payload_type_name`,
  `path_len`, and `bytes_per_hop` columns, written at capture time. Aggregating
  these via `json_extract` cost 3–6 seconds per query on a large database.
  Existing rows are converted a bounded batch per refresh rather than in one
  table-rewriting migration.
- Dashboard JavaScript and CSS moved to static files, removing the CSP nonce
  requirement for the bulk of the page's code.
- `cleanup_old_stats` now also deletes rows dated implausibly far in the future.
  Such rows are never older than the retention cutoff, so they were immortal —
  observed in the wild dated 2103.

### Removed

- The orphaned `/stats` page, which was unreachable from the navigation and
  rendered stub charts that never populated.

### Deprecated

- `GET /api/stats`. Every key name is preserved and the response now carries
  `Deprecation` and `Sunset` headers; use `/api/dashboard/*` instead. It will be
  removed at the next major version.

### Notes for downgrades

All schema changes are additive — two new tables, four new nullable columns, and
new indexes — so the data itself is safe to read with older code. However,
`MigrationRunner` fails startup on encountering an applied migration version it
does not know about, so downgrading below this release requires deleting the
corresponding `schema_version` rows.

## [1.0.0] — 2026-07-28

v1.0.0 marks the first stable release. It adds transport recovery, location and rain
improvements, World Cup support, safer feed and outbound HTTP handling, command-prefix
enhancements, and substantial web-viewer performance and security work.

The configuration format, command syntax, service layout, and web-viewer API are now
considered stable; breaking changes to them will come with a major version bump.

### Added

- Automatic serial, BLE, and TCP transport reconnect handling, including service
  plugin re-subscription after reconnect.
- Minute-level rain and precipitation nowcasts with optional proactive notifications.
- World Cup command and live event announcement service.
- Opt-in sender-language detection for localized greeting replies, with
  keyword-first detection and an optional `langdetect` extra for longer text.
- Centralized location resolution and geocoding helpers shared by weather, AQI,
  path, and related commands.
- Web-viewer plugin settings, node settings, multi-byte evidence views, and
  paginated contacts APIs.
- Database restore tooling and hardened service-layout migration for configuration,
  state, logs, and local plugins.
- Flexible command prefixes: single, multiple, or decorative prefixes, with
  permissive and strict matching modes and optional bare commands.
- Per-channel flood scope configuration for more granular message routing.
- Optional packet-capture payload decoding — `GRP_TXT` channel messages are
  decrypted and `ADVERT`s parsed into a nested `decoded` object. Publishing it to
  MQTT is off by default and set per broker via `mqttN_include_decoded`.
  Packet-log rotation (off/size/time) is configurable.
- `{hops}` and `{hops_label}` placeholders for path command replies, and an RSSI
  placeholder for test command responses.
- Configuration is validated on every startup, surfacing misspelled sections and
  keys that previously failed silently. `validate_config.py --strict` checks a
  config before upgrading.
- DARC MOWAS alerts map German region IDs (*Regionalschlüssel*) to MeshCore scopes,
  limiting each alert to the regions it was issued for.
- NWS gridpoint data as the US precipitation-nowcast source.
- A tracked `LICENSE` file (MIT) and matching `pyproject.toml` license metadata, so
  built wheels and packages carry the license the README has always declared.

### Changed

- Feed polling now has bounded response and item limits, duplicate queue protection,
  per-feed serialization, and configurable post limits.
- Direct-message responses are split at MeshCore byte limits without breaking UTF-8.
- Mesh graph and contacts queries scope enrichment work to the requested page or
  visible data.
- Service installs keep executable code root-owned while configuration and runtime
  state remain writable only by the service account.
- The help command now respects its own `channels` override, falling back to the
  global `monitor_channels` only when no help command is loaded.
- The webhook service starts before the radio connection and returns HTTP 503
  until the bot is connected, narrowing the window for connection refusals.
- Weather alerts recognize NWS responses that mean "no coverage here" and stop
  reporting them as errors.

### Fixed

- Closed outbound HTTP SSRF bypasses, including IPv4-mapped IPv6 and redirect/DNS
  rebinding cases.
- Hardened configuration reload rollback, scheduler operation claims, feed queue
  deduplication, and blocking weather-provider calls.
- Escaped user-controlled web-viewer content and neutralized Discord mentions.
- Restored Python 3.10 compatibility and expanded CI coverage through Python 3.13.
- `NEW_CONTACT` adverts are classified as known or new instead of always being
  logged as newly discovered.
- The standalone installer preserves custom alternative commands and symlinks, and
  rolls back a partial executable sync rather than restarting a half-updated tree.
- Startup validation now actually reports unknown and misspelled keys — including
  in `*_Command` sections — with a "did you mean" suggestion, instead of only
  checking section names and a hardcoded `[Connection]` pair.
- `!aqi`, `!rain`, `!snow`, `!aurora`, `!prefix`, `!alert`, and `!gwx` no longer
  block the event loop while geocoding; location resolution runs off-thread like
  the forecast fetch already did. `!prefix` was the worst case, reverse-geocoding
  once per matching repeater with the loop stalled throughout.
- The Nominatim rate limiter reserves its slot before the request instead of
  recording it afterwards, so concurrent geocodes can no longer clear the gate
  together and breach the 1 req/s policy. The geocode caches are locked against
  concurrent eviction.
- The web viewer footer and the `!version` command agree on dev and detached-tag
  checkouts; a detached checkout on a release tag reports that tag rather than
  `HEAD-<sha>`.
- `[Feed_Manager]` numeric limits are clamped to sane minimums. `max_items_per_check`
  below 1 no longer takes Python's negative-slice meaning; `max_posts_per_check` is
  enforced before an item is sent rather than after, while configured values below
  1 are clamped to 1; `feed_request_timeout` below 1 no longer disables the HTTP
  timeout outright; and `max_message_length` below 4 no longer lengthens the message
  it is meant to cap.

### Contributors

Thanks to [@rlwilliamson-dev](https://github.com/rlwilliamson-dev) for the rain
nowcast work and the NWS gridpoint source, and to
[@fmoessbauer](https://github.com/fmoessbauer) for the MOWAS region-scope mapping
and code-style fixes.

## [0.9.3] — 2026-05-30

### Changed

- Bridged Discord messages set `allowed_mentions` to an empty list, so `@everyone`,
  `@here`, and role mentions arrive as plain text instead of pinging the channel.

### Documentation

- Expanded the command reference for `cmd`, `version`, `weather`, and `path` with
  usage examples and configuration options, and documented the `RandomLine`
  configurable triggers.
- Marked the global `[Aliases]` section deprecated in favor of per-command
  `aliases =` keys, and clarified the `[Rate_Limits]` and `[Webhook]` sections.
- Emphasized web-viewer security practices in the viewer documentation.

## [0.9.2] — 2026-05-17

### Fixed

- Webhook channel lookup strips a leading `#`, so posts match hashtag channels
  cached from the radio.
- The webhook endpoint returns HTTP 500 when the mesh send fails, instead of
  reporting success.

### Changed

- Packet capture applies log levels from its own verbose/debug settings rather
  than setting the global logger level, and logs a per-packet summary whose level
  follows those flags.
- Clarified how `outgoing_flood_scope_override` and `flood_scopes` interact, with
  more informative scope-resolution logging and RF-correlation eligibility checks.
- Corrected the documentation URL in the systemd unit and the command User-Agent.

## [0.9.1] — 2026-05-16

The theme of this release is flood-scope control: which slice of the mesh a given
outgoing message is flooded to.

### Added

- Optional regional `TC_FLOOD` scope configuration across services (weather,
  earthquake, webhook). `CommandManager` resolves the scope from the incoming
  message, the owning config section, or an explicit parameter.
- Optional flood scope for scheduled channel messages via `channel:#scope:body`
  in `[Scheduled_Messages]`.
- Five-field cron expressions and preset aliases for `[Scheduled_Messages]`. The
  legacy `HHMM` form is still parsed and warns.
- `reply_prefix` and `minimum_path_bytes` settings for the path command.
- `[Test_Command] response_format` supports piped path filters (`pathbytes_min`,
  `prefix_if_nonempty`) and takes priority over `[Keywords]`.
- Global and per-broker MQTT JWT settings: `jwt_ttl_seconds` and
  `jwt_renewal_interval`.
- `send_channel_message` accepts an explicit timestamp, enabling bit-identical
  message replication and chronological display ordering.
- DARC MOWAS retransmits bit-identical messages when a repeater ack is missing,
  so an emergency alert is not lost to a dropped ack.

### Fixed

- Direct-message responses route by `sender_pubkey` rather than `sender_id`,
  preventing misrouting when several nodes share a display name.
- Keyword and `RandomLine` channel replies now carry their configured flood scope.
- Scheduled sends are staggered by a deterministic delay
  (`scheduled_message_max_stagger_seconds`, default 1.5) and skip the global user
  rate limit, so simultaneous jobs are no longer dropped. Per-channel and
  `bot_tx` limits still apply.
- Mesh graph pending-update flushing no longer deadlocks.
- The feed manager checks lock status before acquiring it to prevent coroutine
  pileup, and the scheduler processes messages without blocking its main thread.
- Advert flag parsing uses bitwise operations so invalid flag values degrade to a
  warning instead of failing to parse.
- DARC MOWAS message chunks get ascending timestamps, giving receivers correct
  ordering and deduplication.
- Service names strip leading and trailing underscores, so `<foo>_Service`
  resolves to `<foo>` rather than `<foo>_`.

### Contributors

Thanks to [@fmoessbauer](https://github.com/fmoessbauer) for the MOWAS
reliability work and the service-name fix (#182, #183).

## [0.9.0] — 2026-04-17

v0.9.0 is a large release that focuses on operational reliability, observability, and
deployment ergonomics. The headline additions are the authenticated real-time web
viewer, a full APScheduler rewrite, multi-arch Docker images, `.deb` packaging, a
migration-versioned aiosqlite DB, and numerous message-handling and radio-health
hardening fixes.

### Highlights

- **Real-time web viewer**: auth, contact management, live packet/message/log/mesh
  streaming, admin config editor, maintenance tools, DB backup UI, API Explorer tab,
  and early-start initializing banner.
- **Radio reliability**: zombie-radio detection with health probe and banner alerts,
  radio-offline fail state, send suppression during outages, `asyncio.wait_for`
  guards on `send_advert` / `disconnect_radio` / `reboot_radio`, radio debug mode
  toggle, packet-capture restart-storm prevention, auto-restart and reconnect logic.
- **Scheduler migration**: scheduler slimmed and switched to APScheduler; maintenance
  moved to its own module; signal-driven graceful shutdown and config reload; backup
  scheduler fire-window fix (BUG-024).
- **Database**: aiosqlite `AsyncDBManager`, versioned migrations in `db_manager`,
  safer ALTER-TABLE startup migrations for `channel_operations` and
  `feed_message_queue` (BUG-002), improved connection lifecycle across modules
  (BUG-017).
- **Packaging**: `.deb` build via `scripts/build-deb.sh`, multi-arch Docker images
  with SBOM + provenance, `check-package-data.sh` dist verification, ncurses config
  TUI (`scripts/config_tui.py`), bot admin HTTP server + `reload_config.sh`.
- **Rate limiting & safety**: per-channel rate limiting, per-user cooldown defaults
  tightened, thread-safe rate limiter with LRU SNR/RSSI caches, inbound webhook relay
  with bearer-token auth, SSRF hardening and log-injection sanitization, allow-local
  SMTP flag.
- **Commands**: `!schedule`, `!version`, `!path` geographic scoring toggle, airplanes
  (full list, no truncation), weather (high/low display, Open-Meteo model selection,
  MQTT weather, location fallback, multi-day forecasts), fortune (BSD format),
  RandomLine, configurable command reference URL.

### Added

- Authenticated web viewer with real-time streams (`packet_stream`, `command_stream`,
  `message_stream`, `log_stream`, `mesh_graph`) — see `93f73a1`, `a15827b`,
  `23f652f`, `4685ea7`, `da2e39c`, `ae52be4`, `9be5166`, `6246a81`.
- Web viewer admin config editor with password redaction and CSRF protection
  (`3a9f710`, `8bea10c`); live banner polling and early-start banner (`23f652f`).
- API Explorer tab and actionable error messages in the viewer (`a15827b`, `75be386`).
- Zombie-radio detection, health probe, timeout guards, and alert system (`d0ae737`,
  `8b14c40`); radio-offline fail state with send suppression and auto-restart
  (`51ab5d3`); radio debug logging mode with web UI toggle (`9ce6970`).
- APScheduler-based scheduler, maintenance module, graceful shutdown via Unix
  signals, and config-reload support (`aa2677b`, `07a2db4`, `904303f`).
- `.deb` packaging, multi-arch Docker build pipeline with SBOM + provenance, ncurses
  config TUI (`c7f2bdb`, `5b6f282`, `da1e68f`).
- Bot admin HTTP server + `reload_config.sh` CLI (`773b80f`).
- Inbound webhook relay with bearer-token authentication (`d07cca6`).
- Per-channel rate limiting (`25eb7cc`) and thread-safe rate limiter with LRU SNR
  and RSSI caches (`ea0e25d`).
- `!version` command and web-viewer footer version string (issue #91, `883b67d`,
  `fbf3995`).
- `!schedule` command listing scheduled messages and advert interval (`97e5c59`).
- `!path` geographic scoring toggle (`2a3a787`) and multibyte path chart rendering
  (`fbf3995`, `c6a7355`).
- Fortune command reading BSD fortune files (`13c10fd`) and RandomLine command
  (`a4d5f54`); `cmd_reference_url` option for `Cmd_Command` (`90fdd0c`).
- MQTT weather support, Open-Meteo model selection, location fallback, multi-day
  forecasts, and high/low temperature display (`9d768a3`, `5f6eced`,
  `206753a`, `3735f26`, `d9ea209`).
- Airplanes command sends all aircraft without truncation (`7403c1e`); keeps
  single-message output (`46d3fab`).
- CI log-injection regression check (`ce4fa8e`); lint gates for ruff, mypy, eslint,
  and shellcheck (`e1cf2eb` / `a12797f`).

### Changed

- **Upgraded `meshcore` to `>= 2.3.6`**, which also supplies upstream fixes for:
  - `can't convert negative int to unsigned` on flood contacts (issue #126) — the
    library now converts `out_path_len == -1` to `255` before packing. Commit
    `ba52c3b` adds belt-and-braces defensive wire-field rebuilding in
    `_ensure_contact_meshcore_path_encoding`.
  - `KeyError('msg_hash')` asyncio parser spam (issue #83) — the new
    `meshcore_parser.py` guards with `'msg_hash' in l`.
- `max_response_hops` default in shipped config templates lowered from 10 → 7
  (issue #161).
- `requires-python` raised to `>= 3.10` (Python 3.9 dropped; `meshcore >= 2.3.6`
  requires 3.10+). Ruff target bumped to `py310`, CI matrix now covers 3.11, 3.12,
  and 3.13.
- Web-viewer subscription handlers are silent; the navbar indicator reflects socket
  state (`1ee84f2`).
- Scheduler now uses `add_done_callback` (fire-and-forget) instead of blocking
  `future.result(timeout=X)` to avoid TimeoutError spam and loop stalls (BUG-015).
- Command aliases moved from global `[Aliases]` section to per-command `aliases =`
  keys (`14d3c0c`).
- Channel messages now reserve an extra 10-byte budget for regional flood scope
  (`4ee2079`).
- Web-viewer password is emphasized but no longer strictly required (`8b6ccc9`).
- Configuration docs clarified for monitored channels, `max_response_hops`, and
  public-channel guard (`20c4ea4`, `4bf0929`).
- Discord bridge supports multiple webhooks per channel (`0cd23e8`).

### Fixed

- **#126** (negative `out_path_len`): fixed via `meshcore >= 2.3.6` dep bump plus
  defensive handling in `_ensure_contact_meshcore_path_encoding`.
- **#83** (`KeyError('msg_hash')` asyncio spam): fixed via `meshcore >= 2.3.6` dep
  bump.
- Web-viewer status-ack tests now assert the silent UX instead of the removed
  `emit('status', …)` calls (`tests/test_web_viewer.py`).
- `send_advert()` guarded with `asyncio.wait_for(timeout=30)` to prevent event-loop
  lockup (`22e1b2b`, `329905d`).
- `packetcapture` restart storm during radio reconnect (`f09b214`).
- Scheduler `RuntimeError` on threadsafe `future.result` handled (`7b01242`).
- Web-viewer config-item retrieval no longer triggers interpolation errors
  (`ad09e8b`).
- Path length calculation and hash mode in `MessageHandler` corrected (`ba52c3b`).
- Mention handling, reply-match base function, and command-class inheritance fixes
  (`8bea10c`, `9d4b142`, `56be1e7`, `277491f`).
- Path validation hardened (`6e8204c`); scheduler duplicate run + mypy fallback
  types (`8b68644`).
- Shutdown hardened — single stop, viewer cleanup, MQTT log teardown, scheduler
  drain (`e058da4`).
- Discord-bridge channel-key normalization test alignment (`4178371`, `f971e97`).
- BUG-001 .. BUG-029 — see `BUGS.md` v0.9.0 section for the full list.

### Security

- SSRF hardening in outbound HTTP (`54aeb28`) with explicit CGN-network check in
  `validate_external_url` (`2a80f76`).
- Log-injection sanitization applied to user-supplied log lines (`54aeb28`); CI
  regression check added (`ce4fa8e`).
- `allow_local_smtp` flag for opt-in local SMTP relay usage (`54aeb28`).
- SMTP SSRF guard import restored in `scheduler.py` (`c543cac`).
- CSRF protection in the web viewer (`3a9f710`).

### Infrastructure

- Initial test suite, pytest timeouts, coverage threshold, and tracking files
  (`9de9230`, `ba32acc`, `c95ddf6`).
- Test-coverage expansion for commands, web viewer, and infrastructure (`9be5166`).
- MQTT live-test framework and packet fixtures (`a667e3c`).
- Per-test timeout in `pytest.ini` to prevent CI hangs (`d7cf0d5`).
- Makefile + virtual-environment bootstrap (`c2149bc`).

### Documentation

- README, config example, `docs/configuration.md`, and BUGS.md updated throughout
  v0.9.0.
- Discord integration, kg7qin integration notes (`f2936be`, `de6279c`).

[1.0.0]: https://github.com/agessaman/meshcore-bot/compare/v0.9.3...v1.0.0
[0.9.3]: https://github.com/agessaman/meshcore-bot/compare/v0.9.2...v0.9.3
[0.9.2]: https://github.com/agessaman/meshcore-bot/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/agessaman/meshcore-bot/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/agessaman/meshcore-bot/compare/v0.8.3...v0.9.0
