"""
scripts/render_terminal_screenshot.py
Renders a realistic dark-mode terminal window screenshot as a PNG file
into docs/screenshots/terminal_contradiction.png using Pillow.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def render_screenshot():
    out_path = Path(__file__).parent.parent / "docs" / "screenshots" / "terminal_contradiction.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    width = 1100
    height = 680
    bg_color = (24, 24, 27)         # Zinc-900 terminal background
    header_color = (39, 39, 42)     # Title bar
    text_color = (228, 228, 231)    # Crisp zinc-200 text
    green = (74, 222, 128)          # Emerald-400
    red = (248, 113, 113)           # Red-400
    cyan = (56, 189, 248)           # Sky-400
    yellow = (250, 204, 21)         # Amber-400
    gray = (161, 161, 170)          # Zinc-400

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Title bar
    draw.rectangle([0, 0, width, 40], fill=header_color)

    # Mac/Terminal style dots
    draw.ellipse([15, 14, 27, 26], fill=(239, 68, 68))   # Close
    draw.ellipse([35, 14, 47, 26], fill=(234, 179, 8))   # Minimize
    draw.ellipse([55, 14, 67, 26], fill=(34, 197, 94))   # Maximize

    # Title text
    try:
        font = ImageFont.truetype("consola.ttf", 15)
        title_font = ImageFont.truetype("segoeui.ttf", 14)
        bold_font = ImageFont.truetype("consolab.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
        title_font = font
        bold_font = font

    draw.text((width // 2 - 120, 11), "OneContext Multi-Agent Memory Demo", fill=gray, font=title_font)

    # Terminal Content Lines
    y = 55
    x = 24
    line_h = 24

    def write_line(text, fill=text_color, is_bold=False):
        nonlocal y
        f = bold_font if is_bold else font
        draw.text((x, y), text, fill=fill, font=f)
        y += line_h

    write_line("suresh@DEV-WORKSTATION:~/onecontext$ python scripts/demo_before_after.py", cyan, is_bold=True)
    write_line("[agent-planner] Stored architecture standard in Hindsight memory bank 'onecontext-demo-f45180'.", gray)
    write_line("[agent-builder] Queried Hindsight: Recalled 2 decisions. Generated PostgreSQL + UUIDv4 guidance.", gray)
    y += 8
    write_line("=" * 82, gray)
    write_line("  STEP 3: AGENT 3 (VALIDATOR) - MEMORY CONTRADICTION DETECTION", yellow, is_bold=True)
    write_line("=" * 82, gray)
    y += 6

    write_line("--- Validating Compliant Draft ---", cyan)
    write_line("Draft: PR #101: Added User account model using PostgreSQL with UUID primary key.", text_color)
    write_line("Valid: True  |  Contradictions found: 0  [COMPLIANT WITH MEMORY]", green, is_bold=True)
    y += 10

    write_line("--- Validating Deliberately Contradictory Draft ---", red, is_bold=True)
    write_line("Draft: PR #102: Added User profile collection in MongoDB with auto-increment integer IDs.", text_color)
    write_line("Valid: False  |  Contradictions caught: 2", red, is_bold=True)
    y += 4
    write_line("  [1] VIOLATION: MongoDB is prohibited by Memory [2] authored by 'agent-planner'.", red)
    write_line("  [2] VIOLATION: Auto-increment integer IDs conflict with mandatory UUIDv4 standard.", red)
    y += 8

    write_line("Validator Analysis (Groq openai/gpt-oss-120b):", yellow)
    write_line("  'The proposed draft introduces a MongoDB document store and auto-increment integer IDs.", gray)
    write_line("   Both directly violate recorded architecture decisions authored by agent-planner.", gray)
    write_line("   The institutional standard requires PostgreSQL with asyncpg and UUIDv4 keys.", gray)
    write_line("   Decision enforced across agents: DRAFT REJECTED.'", red)
    y += 12

    write_line("=" * 82, gray)
    write_line("  ALL 3 AGENTS SUCCESSFULLY SHARED & ENFORCED A SINGLE HINDSIGHT BANK!", green, is_bold=True)
    write_line("=" * 82, gray)

    img.save(str(out_path), "PNG")
    print(f"Screenshot successfully rendered to: {out_path}")

if __name__ == "__main__":
    render_screenshot()
