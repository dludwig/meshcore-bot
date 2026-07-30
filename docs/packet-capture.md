# Packet Capture Service

Captures packets from the MeshCore network and publishes them to MQTT brokers.

---

## Quick Start

1. **Configure Bot** - Edit `config.ini`:

```ini
[PacketCapture]
enabled = true

# Owner info for JWT auth -- these are optional
owner_public_key = YOUR_COMPANION_PUBLIC_KEY_HERE
owner_email = your.email@example.com

# IATA code for topic routing (XYZ is invalid set it to a real IATA)
iata = XYZ

# MQTT Broker (Let's Mesh Analyzer)
mqtt1_enabled = true
mqtt1_server = mqtt-us-v1.letsmesh.net
mqtt1_port = 443
mqtt1_transport = websockets
mqtt1_use_tls = true
mqtt1_use_auth_token = true
mqtt1_token_audience = mqtt-us-v1.letsmesh.net
mqtt1_topic_status = meshcore/{IATA}/{PUBLIC_KEY}/status
mqtt1_topic_packets = meshcore/{IATA}/{PUBLIC_KEY}/packets
```

2. **Restart Bot** - The service starts automatically

---

## Configuration

### Basic Settings

```ini
[PacketCapture]
enabled = true                    # Enable packet capture
output_file = packets.json        # Optional: save to file
verbose = false                   # Detailed packet logging
debug = false                     # Debug mode
mqtt_skip_unparseable_packets = true   # Skip MQTT when content hash is all zeros (strict path reject / short buffer)

# Optional: skip MQTT for ADVERT packets whose Ed25519 signature does not verify (damaged or spoofed mesh payload).
# Does not affect file/JSONL capture.
advert_require_valid_signature = false
```

### Authentication

#### Option 1: On-Device Signing (Recommended)
```ini
auth_token_method = device        # Use device's built-in signing
# No private key file needed
```

#### Option 2: Python Signing
```ini
auth_token_method = python        # Use Python signing
private_key_path = /path/to/key.txt  # Path to private key file
```

### MQTT Brokers

Configure multiple brokers using `mqttN_*` pattern:

```ini
# Broker 1
mqtt1_enabled = true
mqtt1_server = mqtt-us-v1.letsmesh.net
mqtt1_port = 443
mqtt1_transport = websockets      # tcp or websockets
mqtt1_use_tls = true
mqtt1_use_auth_token = true
mqtt1_topic_status = meshcore/{IATA}/{PUBLIC_KEY}/status
mqtt1_topic_packets = meshcore/{IATA}/{PUBLIC_KEY}/packets

# Broker 2
mqtt2_enabled = true
mqtt2_server = your.broker.com
mqtt2_port = 1883
mqtt2_transport = tcp
mqtt2_username = user
mqtt2_password = pass
```

#### Filtering by packet type

You can limit which packet types are uploaded to each broker with `mqttN_upload_packet_types`. Use a comma-separated list of type numbers; if unset or empty, all packet types are uploaded.

```ini
# Only upload text messages and adverts to this broker
mqtt1_upload_packet_types = 2, 4

# Broker 2 gets everything (default)
# mqtt2_upload_packet_types =
```

**Packet type reference:**

| Type | Name       | Description        |
|------|------------|--------------------|
| 0    | REQ        | Request            |
| 1    | RESPONSE   | Response           |
| 2    | TXT_MSG    | Text message       |
| 3    | ACK        | Acknowledgment     |
| 4    | ADVERT     | Advertisement      |
| 5    | GRP_TXT    | Group text         |
| 6    | GRP_DATA   | Group data         |
| 7    | ANON_REQ   | Anonymous request  |
| 8    | PATH       | Path               |
| 9    | TRACE      | Trace              |
| 10   | MULTIPART  | Multipart          |
| 11–15| Type11–RAW_CUSTOM | Other types |

Packets that are excluded by this filter are still written to the output file (if configured) and still counted; they are only skipped for MQTT upload to that broker. Debug logs will show "Skipping" for those packets.

### Topic Templates

Placeholders:
- `{IATA}` - Your IATA code (e.g., SEA)
- `{iata}` - Lowercase IATA code
- `{PUBLIC_KEY}` - Device public key (uppercase)
- `{public_key}` - Device public key (lowercase)

### Status Publishing and MQTT auth (JWT)

Two separate settings:

- **`jwt_ttl_seconds`** (global) / **`mqttN_jwt_ttl_seconds`** (per broker): lifetime of the JWT in the `exp` claim (`exp = iat + ttl`). Use this when the broker enforces a maximum token lifetime (e.g. 60 minutes → `3600`).
- **`jwt_renewal_interval`** (global) / **`mqttN_jwt_renewal_interval`** (per broker): how often the bot refreshes the MQTT password for that broker. Set **less than** the TTL (e.g. TTL 3600s and renewal every 1800s) so the connection does not outlive the token.

Per-broker keys override the global values for that broker only. Omit them to inherit globals.

```ini
stats_in_status_enabled = true    # Include device stats in status
stats_refresh_interval = 300      # Publish status every 5 minutes

jwt_ttl_seconds = 86400           # Default JWT exp − iat (24 hours) for all brokers unless overridden
jwt_renewal_interval = 43200      # Default proactive refresh cadence (12 hours); 0 = no renewal task

# Example on a broker that requires 60-minute tokens and refresh halfway through:
# mqtt1_jwt_ttl_seconds = 3600
# mqtt1_jwt_renewal_interval = 1800
```

---

## Packet Format

### Packet Message
```json
{
  "origin": "MyBot",
  "origin_id": "ABCD1234...",
  "timestamp": "2026-01-04T12:34:56",
  "type": "PACKET",
  "direction": "rx",
  "len": "42",
  "packet_type": "2",
  "route": "D",
  "payload_len": "32",
  "raw": "DEADBEEF...",
  "SNR": "8.5",
  "RSSI": "-42",
  "hash": "ABC123..."
}
```

### Decoded Payloads

When `decode_payloads = true`, each packet gains a nested `decoded` object with plain-text /
structured fields, in addition to the unchanged raw fields above. This makes dumps easy to
process with tools like `jq` (e.g. `jq 'select(.decoded.kind=="GRP_TXT") | .decoded.text'`).

```json
{
  "type": "PACKET",
  "packet_type": "5",
  "route": "F",
  "raw": "1540CAB3...",
  "decoded": {
    "kind": "GRP_TXT",
    "channel_hash": "ca",
    "channel": "#bot",
    "sender": "Alice",
    "text": "hello mesh",
    "msg_timestamp": "2026-07-08T21:22:31Z",
    "decrypted": true,
    "path": ["A1", "B2"]
  }
}
```

The `decoded` object holds only payload-specific content — it does not restate header fields
(`packet_type`, `route`) that already exist at the top level.

What can be decoded:

- **GRP_TXT** (channel messages) are decrypted when a matching channel key is available.
  Keys come from the bot's own configured radio channels automatically, plus
  `decode_hashtag_channels` (keys derived from the `#name`), `decode_channel_keys`
  (`name=hexOrBase64` pairs), and the built-in default **Public** channel key
  (`decode_include_public = true`).
- **ADVERT** packets are parsed into `name`, `mode` (role), `lat`/`lon`, and `public_key`.
- The decoded **path** hop list is included in `decoded.path` when it isn't already present at the
  top level (the top-level `path` is only added for `route=D`), so flood-route paths are captured
  without duplication.
- **Direct messages (TXT_MSG)** are ECDH-encrypted between two nodes and **cannot** be decrypted
  by a passive observer — they appear as `{"kind": "TXT_MSG", "encrypted": true}`.

Publishing of the `decoded` object to MQTT is **off by default** (`include_decoded = false`) — opt
in per broker with `mqttN_include_decoded = true`, or set `include_decoded = true` to publish it to
all brokers. This lets you, e.g., send decoded text to a private broker while public brokers receive
only raw packets. The log file always includes the `decoded` object when `decode_payloads = true`,
independent of this setting.

### Status Message
```json
{
  "status": "online",
  "timestamp": "2026-01-04T12:34:56",
  "origin": "MyBot",
  "origin_id": "ABCD1234...",
  "model": "Heltec V3",
  "firmware_version": "v3.1.2",
  "radio": "915000000,250,9,8",
  "client_version": "meshcore-bot/v1.0.0",
  "stats": {
    "rx_packets": 1234,
    "tx_packets": 567
  }
}
```

---

## Troubleshooting

### Service Not Starting

Check logs:
```bash
tail -f meshcore_bot.log | grep PacketCapture
```

Common issues:
- `enabled = false` in config
- Missing `paho-mqtt` library: `pip install paho-mqtt`

### MQTT Not Connecting

1. **Check broker settings** - Verify hostname and port
2. **Test connection manually**:
   ```bash
   mosquitto_pub -h mqtt-us-v1.letsmesh.net -p 443 -t test -m "test"
   ```
3. **Check authentication** - Verify JWT token generation
4. **Check logs** - Look for connection errors

### No Packets Being Published

1. **Verify MQTT connection** - Check logs for "Connected to MQTT broker"
2. **Check packet count** - Service logs "Captured packet #N" (or "Skipping packet #N" when filtered) for each packet
3. **Verify topics** - Ensure topics match broker expectations
4. **Check upload filter** - If `mqttN_upload_packet_types` is set, only those types are uploaded. DEBUG Logs show "packet type X not in [Y, Z]" when a packet is skipped

---

## Advanced

### Multiple Brokers

Configure up to 10 brokers (mqtt1_* through mqtt10_*). Each broker has independent connection tracking and auto-reconnection.

### Health Monitoring

```ini
health_check_interval = 30        # Check connection every 30s
health_check_grace_period = 2     # Allow 2 failures before warning
```

### Log Rotation

By default `output_file` is a single file that is appended to forever. To keep historical dumps
manageable, enable rotation:

```ini
# Size-based: roll at 50 MB, keep 5 backups (packets.jsonl.1 ... .5)
log_rotation = size
log_max_bytes = 50MB
log_backup_count = 5

# Or time-based: roll daily at midnight, keep 14 days
log_rotation = time
log_rotation_when = midnight
log_backup_count = 14
```

`log_rotation = off` (default) keeps the original single-file behavior. `log_max_bytes` accepts
plain bytes or suffixes like `10M` / `1G`. `log_rotation_when` uses Python's
`TimedRotatingFileHandler` values (`midnight`, `H`, `D`, `W0`–`W6`).

### JWT Authentication

Tokens are valid for 24 hours and auto-renewed. The service tries on-device signing first (if `auth_token_method = device`), then falls back to Python signing.

**Token Format:**
```json
{
  "iat": 1234567890,
  "exp": 1234654290,
  "aud": "mqtt-us-v1.letsmesh.net",
  "publicKey": "DEVICE_PUBLIC_KEY",
  "owner": "OWNER_PUBLIC_KEY",
  "email": "your@email.com",
  "iata": "SEA"
}
```

---

## FAQ

**Q: Do I need to provide a private key?**
A: Not if using on-device signing (`auth_token_method = device`). The service will fetch the key from your device automatically.

**Q: Can I publish to my own MQTT broker?**
A: Yes. Set `mqtt1_use_auth_token = false` and provide `mqtt1_username` and `mqtt1_password`.

**Q: What's the difference between TCP and WebSockets?**
A: WebSockets work through firewalls better (uses HTTPS port 443). TCP is lighter but may be blocked.

**Q: How do I disable packet capture but keep status publishing?**
A: You can't disable just packet capture - it's all or nothing. Consider filtering on the broker side.

**Q: Can I capture TX (outgoing) packets?**
A: Currently only RX (incoming) packets are captured.
