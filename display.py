"""Responsiv terminalvæg med fiktive sessions, buffers og overførsler."""

from functools import lru_cache
import hashlib
import math

MODES = ("overview", "extract", "transfer", "recon", "matrix")
LABELS = {"overview": "CPR-REGISTER / ACCESS", "extract": "CPR-NUMRE / DUMP",
          "transfer": "CPR-DATA / TRANSFER", "recon": "CPR-REGISTER / RECON",
          "matrix": "CPR-DATA / SIGNAL STREAM"}
PALETTE = {"green": "32", "bright": "92", "white": "97", "dim": "2;32", "yellow": "93"}
ASCII = str.maketrans({"█": "#", "░": ".", "─": "-", "│": "|", "┌": "+",
                      "┐": "+", "└": "+", "┘": "+", "▁": ".", "▂": "_",
                      "▃": "-", "▄": "=", "▅": "+", "▆": "*", "▇": "#"})
TOTAL_RECORDS = 8_800_000
FILES = (("cpr_register.enc", 1650.0), ("cpr_numre.csv", 110.0), ("cpr_navne.log", 440.0))


def record_count(value):
    return f"{value:,}".replace(",", ".")


def demo_cpr(index):
    """CPR-lignende demoværdi. Dag 00 er ugyldig og kan ikke være et rigtigt CPR."""
    # 7.919 er indbyrdes primisk med 12.000.000: ingen gentagelser i udtrækket.
    # De 12 måneder, 100 årstal og 10.000 løbenumre har alle ugyldig dag 00.
    value = (index * 7919 + 400001) % 12_000_000
    month = 1 + value // 1_000_000
    year = value // 10_000 % 100
    serial = value % 10_000
    return f"00{month:02d}{year:02d}-{serial:04d}"


def fit(text, width):
    return text[:width].ljust(width)


def bar(value, width):
    width = max(1, width)
    count = int(max(0, min(1, value)) * width)
    return "█" * count + "░" * (width - count)


@lru_cache(maxsize=2048)
def packet(index):
    # Rent visuelle bytes, ikke kryptering eller indhold fra en netværksforbindelse.
    return hashlib.sha256(f"OPEN-HOUSE-FICTION-{index}".encode()).hexdigest()


def progress_line(label, value, width):
    label = label[:min(17, max(7, width // 3))]
    return f"{label} [{bar(value, width - len(label) - 11)}] {value:5.1%}"


def trace(index, scene, width):
    messages = (
        "CPR session token renewed", "CPR buffer page mapped", "CPR channel handshake OK",
        "CPR query advancing", "CPR checksum OK", "CPR archive segment indexed",
        "CPR route refreshed", "CPR cipher buffer rotated", "CPR cache block committed",
        "CPR uplink heartbeat OK", "CPR packet window expanded", "CPR + navn serialized",
    )
    digest = packet(index)
    prefix = f"[{index:06x}] "
    message = f"{messages[index % len(messages)]} / {digest[:12]}"
    if width >= 70:
        message += f"  seq={index:08x} len={256 + index % 4096:04d} ACK"
    return prefix + message


def traffic(scene, width):
    glyphs = "▁▂▃▄▅▆▇█"
    return "".join(glyphs[min(7, int((0.35 + 0.65 * abs(math.sin(scene.elapsed * 1.9 - i * 0.61))) * 7))]
                   for i in range(width))


def content(kind, scene, records, width, height):
    """Leverer præcis det antal indholdsrækker, panelet har plads til."""
    rows = []
    tick = int(scene.elapsed * 9)
    total_mb = sum(size for _, size in FILES)

    def add(text, shade="green", bold=False):
        rows.append((text, shade, bold))

    if kind == "session":
        add("TARGET: cpr-register.demo.invalid", "yellow", True)
        add(f"SESSION {packet(int(scene.elapsed // 10))[:16]}  UID=0", "white")
        stages = (("RECON", min(1, scene.progress / 0.10)),
                  ("SESSION", min(1, scene.progress / 0.14)),
                  ("CPR DUMP", scene.extracted / scene.total),
                  ("CPR ARCHIVE", scene.archive), ("CPR UPLINK", scene.transfer))
        for label, value in stages:
            add(progress_line(label, value, width), "bright" if value == 1 else "green")
        add("CPR-REGISTER: ADGANG OPNÅET" if scene.progress >= 0.14 else "CPR-REGISTER: HANDSHAKE", "bright", True)
        add(f"CPR {record_count(scene.extracted)}/{record_count(scene.total)} POSTER")
        add(traffic(scene, width), "bright")

    elif kind == "records":
        add(progress_line("CPR DUMP", scene.extracted / scene.total, width), "bright", True)
        add(f"{record_count(scene.extracted)}/{record_count(scene.total)} CPR-POSTER / DEMO", "white")
        name_width = max(9, min(38, width - 13))
        add(f"{'CPR-NUMMER':<12} NAVN", "yellow", True)
        count = max(0, height - len(rows))
        end = scene.extracted
        for i in range(count):
            position = end - count + i
            if position < 0:
                add(f"[ALLOC {i:04x}] buffer={packet(tick + i)[:max(8, width - 22)]}", "dim")
            else:
                record = records[position % len(records)]
                text = f"{demo_cpr(position):<12} {record['fuldt_navn'][:name_width]:<{name_width}}"
                if width >= 84:
                    text += f"  {record['demo_id']} crc={packet(position)[:8]} OK"
                add(text, "bright" if i == count - 1 else "green")

    elif kind == "transfer":
        add(f"CPR TX {scene.transfer * total_mb:05.1f}/{total_mb:.1f} MB  {scene.rate:04.1f} MB/s", "bright", True)
        add("DEST uplink.demo.invalid // TUNNEL-08", "dim")
        consumed = 0.0
        for name, size in FILES:
            progress = max(0, min(1, (scene.transfer * total_mb - consumed) / size))
            add(progress_line(name, progress, width), "bright" if progress == 1 else "green")
            consumed += size
        add(traffic(scene, width), "bright")
        add("CPR TRANSFER COMPLETE" if scene.transfer == 1 else "SENDING CPR-NUMRE + NAVNE" if scene.transfer > 0 else "CPR UPLINK QUEUED", "white", True)
        channel = 0
        while len(rows) < height:
            value = (math.sin(scene.elapsed * 0.9 + channel) + 1) / 2
            add(progress_line(f"CH-{channel + 1:02d} {packet(tick + channel)[:4]}", value, width))
            channel += 1

    elif kind == "recon":
        add(progress_line("CPR HOST MAP", min(1, scene.progress / 0.10), width), "bright", True)
        add("ROUTE / NODE / PORT / SERVICE / STATUS", "dim")
        ports = ((22, "SSH"), (443, "TLS"), (5432, "DB"), (8080, "API"), (6379, "CACHE"))
        for i in range(max(0, height - 2)):
            node = (i + tick // 5) % 250 + 1
            port, service = ports[i % len(ports)]
            text = f"192.0.2.{node:<3} {port:>4} {service:<5} OPEN  {packet(node)[:8]}"
            if width >= 52:
                text += f"  cpr-{node:03d}.demo.invalid"
            if width >= 88:
                text += f"  session={packet(node)[:12]}"
            add(text, "bright" if i % 5 == tick % 5 else "green")

    elif kind == "hex":
        add("CPR-REGISTER / CIPHER BUFFER / LIVE HEX", "dim")
        for i in range(max(0, height - 1)):
            index = max(0, tick - height + i + 1)
            digest = packet(index)
            prefix = f"{index * 32:08x}: "
            available = width - len(prefix)
            byte_count = max(1, min(32, available // 3))
            data = " ".join(digest[j:j + 2] for j in range(0, byte_count * 2, 2))
            add(prefix + data, "bright" if i == height - 2 else "green")

    elif kind == "wire":
        add("CPR PACKETS // 192.0.2.10 > 203.0.113.20", "white")
        for i in range(max(0, height - 1)):
            index = max(0, tick - height + i + 1)
            text = f"{index:06d} TLS len={1024 + index % 4096:04d} ACK {packet(index)[:12]}"
            if width >= 65:
                text += f" seq={index * 1460:09d} win=65535"
            add(text, "bright" if index % 7 == 0 else "green")

    elif kind == "console":
        for i in range(height):
            index = max(0, tick - height + i + 1)
            add(trace(index, scene, width), "bright" if i == height - 1 else "green")
        events = scene.events()
        if events and rows:
            _, _, message = events[-1]
            rows[-1] = (f"root@ghost:~# {message}", "white", True)

    while len(rows) < height:
        index = max(0, tick - height + len(rows))
        add(trace(index, scene, width))
    return rows[:height]


TITLES = {"session": "CPR-REGISTER / ROOT SESSION", "records": "CPR-NUMRE / NAVNE / UDTRÆK",
          "transfer": "CPR-DATA / FILE TRANSFER", "recon": "CPR-REGISTER / HOST MAP",
          "hex": "CPR BUFFER / LIVE HEX", "console": "CPR CONSOLE / LIVE LOG",
          "wire": "CPR PACKET STREAM / TX"}
PANELS = {"overview": ("session", "transfer", "records", "hex", "recon", "console"),
          "extract": ("records", "hex", "transfer", "console", "session", "recon"),
          "transfer": ("transfer", "wire", "hex", "console", "session", "records"),
          "recon": ("recon", "session", "hex", "console", "wire", "records")}


def render(mode, scene, records, width=100, height=32, station=1, color=True, unicode=True, paused=False, repeat=True):
    # Én kolonne er reserveret, så nederste højre celle ikke scroller terminalen.
    canvas = max(1, width - 1)
    height = max(1, height)

    def paint(text, shade="green", bold=False):
        if not unicode:
            text = text.translate(ASCII)
        if color:
            return f"\033[40;{'1;' if bold else ''}{PALETTE[shade]}m{text}\033[0m"
        return text

    def line(text, shade="green", bold=False):
        return paint(fit(text, canvas), shade, bold)

    if width < 62 or height < 22:
        rows = ["GHOST // TERMINAL / SIMULATION", "Gør terminalen større: mindst 62 x 22.",
                f"{scene.phase[0]}", "Q / Ctrl+C: afslut"]
        rows += [packet(i) * (1 + canvas // 64) for i in range(max(0, height - len(rows)))]
        return [line(text) for text in rows[:height]]

    mode_label = LABELS[mode]
    identity = f"root@ghost-{station:02d}:~# {mode_label}"
    clock = f"{int(scene.elapsed):03d}/{int(scene.duration):03d}s {'PAUSE' if paused else 'LIVE'}"
    gap = max(1, canvas - len(identity) - len(clock))
    title = f"─ CPR-REGISTER // {record_count(scene.total)} POSTER "
    lines = [line("┌" + title.ljust(canvas - 2, "─") + "┐", "yellow", True),
             line(identity + " " * gap + clock, "bright", True),
             line(f"{scene.phase[0]} / POSTER {record_count(scene.extracted)} / TX {scene.transfer:5.1%}", "white"),
             line(progress_line("CYCLE", scene.progress, canvas), "green")]
    body_height = height - 6

    def panel(kind, panel_width, panel_height):
        title = f"─ {TITLES[kind]} "[:panel_width - 2]
        rows = [paint("┌" + title.ljust(panel_width - 2, "─") + "┐", "dim")]
        for text, shade, bold in content(kind, scene, records, panel_width - 4, panel_height - 2):
            padded = fit(text, panel_width - 4)
            if kind == "records" and text.startswith("00") and text[6:7] == "-":
                body = paint(padded[:11], "yellow", True) + paint(padded[11:], shade, bold)
            else:
                body = paint(padded, shade, bold)
            rows.append(paint("│ ", "dim") + body + paint(" │", "dim"))
        rows.append(paint("└" + "─" * (panel_width - 2) + "┘", "dim"))
        return rows

    if mode == "matrix":
        inner_height = body_height - 2
        inner_width = canvas - 2
        tick = int(scene.elapsed * 13)
        chars = "0123456789ABCDEF<>:./[]"
        lines.append(line("┌" + "─ SIGNAL STREAM ".ljust(canvas - 2, "─") + "┐", "dim"))
        for row in range(inner_height):
            text = []
            for col in range(inner_width):
                head = (col * 17 + tick * (1 + col % 3)) % inner_height
                distance = (head - row) % inner_height
                visible = distance < max(7, int(inner_height * 0.72))
                text.append(chars[(row * 19 + col * 31 + tick) % len(chars)] if visible else " ")
            lines.append(paint("│", "dim") + paint("".join(text), "bright" if row % 5 == tick % 5 else "green") + paint("│", "dim"))
        lines.append(line("└" + "─" * (canvas - 2) + "┘", "dim"))
    else:
        columns = 3 if width >= 150 else 2 if width >= 94 else 1
        base, extra = divmod(canvas - (columns - 1), columns)
        widths = [base + (i < extra) for i in range(columns)]
        top_height = body_height * 3 // 5
        heights = (top_height, body_height - top_height)
        kinds = PANELS[mode]
        if columns == 1:
            kinds = (kinds[0], "console")
        for band, band_height in enumerate(heights):
            group = [panel(kinds[band * columns + col], widths[col], band_height)
                     for col in range(columns)]
            for row in range(band_height):
                lines.append(paint(" ", "dim").join(p[row] for p in group))
    lines.append(line("SIMULATION / FIKTIVE DATA | 1 OPS  2 DATA  3 TX  4 RECON  5 MATRIX", "dim"))
    lines.append(line(f"P PAUSE  R RESTART  Q AFSLUT  |  {'AUTO LOOP' if repeat else 'ET ENKELT FORLØB'}  |  STATION {station:02d}", "dim"))
    return lines
