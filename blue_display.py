"""Blue-team-visninger. Ingen red-team-visninger eller skift mellem hold."""

from display import ASCII, bar, fit, packet, traffic

MODES = ("overview", "alerts", "traffic", "response", "evidence")
LABELS = {"overview": "SOC OVERVIEW", "alerts": "ALERT TRIAGE", "traffic": "NETWORK TELEMETRY",
          "response": "INCIDENT RESPONSE", "evidence": "FORENSIC EVIDENCE"}
PALETTE = {"cyan": "36", "bright": "96", "white": "97", "dim": "2;36", "yellow": "93", "red": "91", "green": "92"}
TITLES = {"status": "SOC / INCIDENT STATUS", "alerts": "DETECTION RULES / ALERT QUEUE",
          "traffic": "NETWORK / FLOW MONITOR", "response": "CONTAINMENT / RESPONSE",
          "evidence": "EVIDENCE BUFFER / HEX", "logs": "ANALYST CONSOLE / LIVE EVENTS"}
PANELS = {"overview": ("status", "alerts", "traffic", "response", "evidence", "logs"),
          "alerts": ("alerts", "evidence", "status", "logs", "traffic", "response"),
          "traffic": ("traffic", "alerts", "evidence", "logs", "status", "response"),
          "response": ("response", "status", "alerts", "logs", "traffic", "evidence"),
          "evidence": ("evidence", "alerts", "traffic", "logs", "response", "status")}
RULES = (("DB-104", "Query volume anomaly", 0.20),
         ("NET-208", "Outbound traffic spike", 0.34),
         ("DLP-301", "Sensitive record pattern", 0.44),
         ("AUTH-402", "Unusual session token", 0.56),
         ("NET-509", "Untrusted egress route", 0.68))


def content(kind, scene, width, height):
    rows = []
    tick = int(scene.elapsed * 8)

    def add(text, shade="cyan", bold=False):
        rows.append((text, shade, bold))

    if kind == "status":
        severity, color = scene.severity
        add(f"THREAT {severity} // INCIDENT IR-0042", color, True)
        add(f"EVENTS {12000 + tick * 17:07d}  HOSTS 064  SENSORS 12", "white")
        add(f"ALERTS {scene.alerts:02d}  BLOCKS {int(scene.blocked):02d}  CASES 01")
        add(f"VAULT-01: {'ISOLATED' if scene.blocked else 'MONITORED'}", color)
        for i in range(max(0, height - len(rows))):
            sensor = i % 12 + 1
            value = (tick * 13 + sensor * 17) % 80 + 20
            prefix = f"SENSOR {sensor:02d} "
            add(prefix + bar(value / 100, max(1, width - len(prefix) - 9)) + f" {value:03d} EPS", "bright" if sensor == tick % 12 + 1 else "cyan")

    elif kind == "alerts":
        add(f"QUEUE {scene.alerts:02d} / CORRELATION ENGINE ONLINE", "white", True)
        for i in range(max(0, height - 1)):
            code, text, threshold = RULES[i % len(RULES)]
            state = "CLOSED" if scene.resolved else "ALERT " if scene.progress >= threshold else "WATCH "
            color = "green" if scene.resolved else "red" if state == "ALERT " else "dim"
            row = f"[{state}] {code} {text}"
            if width >= 70:
                row += f" src=192.0.2.{i % 250 + 1:03d} ref={packet(tick + i)[:8]}"
            add(row, color, state == "ALERT ")

    elif kind == "traffic":
        add("FLOW 192.0.2.10 > 203.0.113.20", "white", True)
        add("EGRESS POLICY: DENY" if scene.blocked else "EGRESS POLICY: MONITOR", "red" if scene.blocked else "cyan")
        add(traffic(scene, width), "bright")
        for i in range(max(0, height - len(rows))):
            seq = max(0, tick - height + i)
            state = "DROP" if scene.blocked else "PASS"
            row = f"{seq:06d} TLS 443 {state} len={1024 + seq % 4096:04d} {packet(seq)[:8]}"
            if width >= 70:
                row += f" sensor={i % 12 + 1:02d} flow={seq:08x} ACK"
            add(row, "red" if scene.blocked else "cyan")

    elif kind == "response":
        actions = ((0.20, "DETECT", "Anomaly correlated"), (0.44, "TRIAGE", "Incident opened"),
                   (0.70, "REVIEW", "Egress policy evaluated"), (0.82, "BLOCK", "Egress route denied"),
                   (0.87, "ISOLATE", "Demo host quarantined"), (0.94, "CLOSE", "Incident contained"))
        add("PLAYBOOK IR-0042 // AUTOMATED RESPONSE", "white", True)
        for threshold, action, description in actions:
            done = scene.progress >= threshold
            add(f"[{'DONE' if done else 'WAIT'}] {action:<7} {description}", "green" if done else "dim", done)
        if len(rows) < height:
            add(f"CASE STATE: {scene.phase[0]}", scene.severity[1], True)

    elif kind == "evidence":
        add("SNAPSHOT / SYNTHETIC PACKET BUFFER", "white")
        for i in range(max(0, height - 1)):
            index = max(0, tick - height + i + 1)
            digest = packet(index)
            byte_count = max(1, min(32, (width - 10) // 3))
            add(f"{index * 32:08x}: " + " ".join(digest[j:j + 2] for j in range(0, byte_count * 2, 2)), "bright" if i == height - 2 else "cyan")

    elif kind == "logs":
        messages = ("sensor heartbeat received", "flow metadata indexed", "rule engine pass complete",
                    "event correlation window advanced", "case evidence fingerprinted",
                    "telemetry batch acknowledged", "audit journal appended", "policy snapshot refreshed")
        for i in range(height):
            seq = max(0, tick - height + i)
            add(f"[{seq:06x}] {messages[seq % len(messages)]} / {packet(seq)[:12]}", "bright" if i == height - 1 else "cyan")
        if rows:
            rows[-1] = (f"analyst@sentinel:~# {scene.phase[0]}", scene.severity[1], True)

    while len(rows) < height:
        seq = max(0, tick - height + len(rows))
        add(f"[{seq:06x}] telemetry verified / {packet(seq)[:max(8, width - 32)]}")
    return rows[:height]


def render(mode, scene, width=100, height=32, station=6, color=True, unicode=True, paused=False, repeat=True):
    canvas, height = max(1, width - 1), max(1, height)

    def paint(text, shade="cyan", bold=False):
        if not unicode:
            text = text.translate(ASCII)
        if color:
            return f"\033[40;{'1;' if bold else ''}{PALETTE[shade]}m{text}\033[0m"
        return text

    def line(text, shade="cyan", bold=False):
        return paint(fit(text, canvas), shade, bold)

    if width < 62 or height < 22:
        rows = ["SENTINEL // SOC / SIMULATION", "Gør terminalen større: mindst 62 x 22.",
                scene.phase[0], "Q / Ctrl+C: afslut"]
        rows += [packet(i) * (1 + canvas // 64) for i in range(max(0, height - len(rows)))]
        return [line(text) for text in rows[:height]]

    identity = f"analyst@sentinel-{station:02d}:~# {LABELS[mode]}"
    clock = f"{int(scene.elapsed):03d}/{int(scene.duration):03d}s {'PAUSE' if paused else 'LIVE'}"
    title = "─ S E N T I N E L // S O C "
    severity, severity_color = scene.severity
    progress_width = canvas - 19
    lines = [line("┌" + title.ljust(canvas - 2, "─") + "┐", "bright", True),
             line(identity + " " * max(1, canvas - len(identity) - len(clock)) + clock, "bright", True),
             line(f"{scene.phase[0]} / THREAT {severity} / ALERTS {scene.alerts:02d} / HOSTS 064", severity_color),
             line(f"INCIDENT [{bar(scene.progress, progress_width)}] {scene.progress:5.1%}")]
    body_height = height - 6
    columns = 3 if width >= 150 else 2 if width >= 94 else 1
    base, extra = divmod(canvas - (columns - 1), columns)
    widths = [base + (i < extra) for i in range(columns)]
    top_height = body_height * 3 // 5
    heights = (top_height, body_height - top_height)
    kinds = PANELS[mode] if columns > 1 else (PANELS[mode][0], "logs")

    def panel(kind, panel_width, panel_height):
        title = f"─ {TITLES[kind]} "[:panel_width - 2]
        rows = [paint("┌" + title.ljust(panel_width - 2, "─") + "┐", "dim")]
        for text, shade, bold in content(kind, scene, panel_width - 4, panel_height - 2):
            rows.append(paint("│ ", "dim") + paint(fit(text, panel_width - 4), shade, bold) + paint(" │", "dim"))
        rows.append(paint("└" + "─" * (panel_width - 2) + "┘", "dim"))
        return rows

    for band, band_height in enumerate(heights):
        group = [panel(kinds[band * columns + col], widths[col], band_height) for col in range(columns)]
        for row in range(band_height):
            lines.append(paint(" ", "dim").join(p[row] for p in group))
    lines.append(line("SIMULATION / FIKTIVE DATA | 1 SOC  2 ALERTS  3 TRAFFIC  4 RESPONSE  5 EVIDENCE", "dim"))
    lines.append(line(f"P PAUSE  R RESTART  Q AFSLUT  |  {'AUTO LOOP' if repeat else 'ET ENKELT FORLØB'}  |  STATION {station:02d}", "dim"))
    return lines
