import re

def generate_seat_grid_html(seats_dict: dict, seat_types: dict, selected_seats: list = None) -> str:
    """
    Generates a beautifully styled HTML grid representing the seat layout of the theater.
    Green = Available
    Red = Booked
    Gold/Yellow = Selected/Recommended
    """
    # Sort seats properly using natural sorting
    def seat_sort_key(seat_id):
        match = re.match(r"^([A-Z]+)(\d+)$", seat_id)
        if match:
            row, num = match.groups()
            return (row, int(num))
        return (seat_id, 0)
        
    sorted_seat_ids = sorted(seats_dict.keys(), key=seat_sort_key)
    
    # Group by row
    seats_by_row = {}
    for seat_id in sorted_seat_ids:
        row_letter = seat_id[0]
        seats_by_row.setdefault(row_letter, []).append(seat_id)
        
    selected_set = set(selected_seats) if selected_seats else set()
    
    # --- Color palette ---
    colors = {
        "available":      ("linear-gradient(135deg, #22c55e, #16a34a)", "#ffffff"),
        "booked":         ("linear-gradient(135deg, #ef4444, #dc2626)",  "#ffffff"),
        "selected":       ("linear-gradient(135deg, #facc15, #eab308)", "#1a1a2e"),
    }
    
    html = []

    # ── Outer wrapper: full-width flex to center the card ──
    html.append('<div style="display: flex; justify-content: center; width: 100%; padding: 8px 0;">')

    # ── Main card ──
    html.append('  <div style="'
        'background: linear-gradient(145deg, rgba(15, 23, 42, 0.85), rgba(30, 41, 59, 0.75));'
        'backdrop-filter: blur(16px);'
        '-webkit-backdrop-filter: blur(16px);'
        'border: 1px solid rgba(148, 163, 184, 0.15);'
        'border-radius: 16px;'
        'padding: 24px 28px;'
        'max-width: 520px;'
        'width: 100%;'
        'box-shadow: 0 8px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.05);'
        'font-family: \'Outfit\', \'Inter\', system-ui, sans-serif;'
    '">')

    # ── Title ──
    html.append('  <div style="text-align: center; margin-bottom: 16px;">')
    html.append('    <span style="'
        'font-size: 0.85rem;'
        'font-weight: 600;'
        'letter-spacing: 3px;'
        'text-transform: uppercase;'
        'background: linear-gradient(90deg, #a78bfa, #818cf8, #6366f1);'
        '-webkit-background-clip: text;'
        '-webkit-text-fill-color: transparent;'
        'background-clip: text;'
    '">🎬 Select Your Seats</span>')
    html.append('  </div>')

    # ── Screen indicator ──
    html.append('  <div style="text-align: center; margin-bottom: 22px;">')
    html.append('    <div style="'
        'width: 75%;'
        'margin: 0 auto 6px auto;'
        'height: 6px;'
        'background: linear-gradient(90deg, transparent, rgba(139,92,246,0.5), rgba(99,102,241,0.6), rgba(139,92,246,0.5), transparent);'
        'border-radius: 50%;'
        'box-shadow: 0 0 20px rgba(139,92,246,0.25);'
    '"></div>')
    html.append('    <span style="'
        'font-size: 0.6rem;'
        'color: #64748b;'
        'letter-spacing: 4px;'
        'text-transform: uppercase;'
        'font-weight: 500;'
    '">screen</span>')
    html.append('  </div>')

    # ── Seat rows ──
    html.append('  <div style="display: flex; flex-direction: column; gap: 6px; align-items: center;">')
    
    for row in sorted(seats_by_row.keys()):
        row_type = seat_types.get(row, "standard").lower()
        row_label = row_type[:4].title()

        # Type badge color (uniform gold/yellow theme)
        badge_bg = "rgba(250,204,21,0.15)"
        badge_color = "#facc15"

        html.append(f'    <div style="display: flex; align-items: center; gap: 10px; width: 100%; max-width: 460px;">')
        
        # Row letter
        html.append(f'      <div style="'
            f'min-width: 22px;'
            f'font-weight: 700;'
            f'color: #cbd5e1;'
            f'font-size: 0.8rem;'
            f'text-align: center;'
            f'opacity: 0.7;'
        f'">{row}</div>')
        
        # Seats container – centered via margin auto
        html.append(f'      <div style="'
            f'display: flex;'
            f'flex-wrap: wrap;'
            f'gap: 5px;'
            f'flex: 1;'
            f'justify-content: center;'
        f'">')
        
        for seat_id in seats_by_row[row]:
            status = seats_dict[seat_id]
            seat_num = seat_id[1:]
            
            if seat_id in selected_set:
                bg, fg = colors["selected"]
                title = "✓ Selected"
                border = "2px solid rgba(250,204,21,0.6)"
                shadow = "0 0 8px rgba(250,204,21,0.35)"
                cursor = "default"
            elif status == "available":
                bg, fg = colors["available"]
                title = f"{row_type.title()} – Available"
                border = "2px solid rgba(34,197,94,0.25)"
                shadow = "0 2px 6px rgba(0,0,0,0.2)"
                cursor = "pointer"
            else:
                bg, fg = colors["booked"]
                title = f"{row_type.title()} – Booked"
                border = "2px solid rgba(239,68,68,0.25)"
                shadow = "none"
                cursor = "not-allowed"

            html.append(f'        <div title="{title}" style="'
                f'background: {bg};'
                f'color: {fg};'
                f'min-width: 28px;'
                f'height: 28px;'
                f'text-align: center;'
                f'line-height: 28px;'
                f'border-radius: 6px;'
                f'font-weight: 600;'
                f'font-size: 0.7rem;'
                f'border: {border};'
                f'box-shadow: {shadow};'
                f'cursor: {cursor};'
                f'transition: transform 0.15s ease, box-shadow 0.15s ease;'
                f'user-select: none;'
            f'">{seat_num}</div>')
            
        html.append('      </div>')
        
        # Row type badge
        html.append(f'      <div style="'
            f'min-width: 42px;'
            f'text-align: center;'
            f'font-size: 0.55rem;'
            f'font-weight: 600;'
            f'color: {badge_color};'
            f'background: {badge_bg};'
            f'padding: 2px 6px;'
            f'border-radius: 4px;'
            f'letter-spacing: 0.5px;'
            f'text-transform: uppercase;'
        f'">{row_label}</div>')
        
        html.append('    </div>')

    html.append('  </div>')

    # ── Legend ──
    html.append('  <div style="'
        'display: flex;'
        'gap: 18px;'
        'justify-content: center;'
        'margin-top: 20px;'
        'padding-top: 14px;'
        'border-top: 1px solid rgba(148,163,184,0.1);'
        'font-size: 0.72rem;'
        'color: #94a3b8;'
    '">')
    
    legend_items = [
        ("linear-gradient(135deg, #22c55e, #16a34a)", "Available", "0 0 6px rgba(34,197,94,0.4)"),
        ("linear-gradient(135deg, #ef4444, #dc2626)",  "Booked",    "0 0 6px rgba(239,68,68,0.4)"),
    ]
    if selected_seats:
        legend_items.append(
            ("linear-gradient(135deg, #facc15, #eab308)", "Selected", "0 0 6px rgba(250,204,21,0.4)")
        )
    
    for bg, label, shadow in legend_items:
        html.append(f'    <div style="display: flex; align-items: center; gap: 6px;">')
        html.append(f'      <div style="'
            f'background: {bg};'
            f'width: 14px;'
            f'height: 14px;'
            f'border-radius: 4px;'
            f'box-shadow: {shadow};'
        f'"></div>')
        html.append(f'      <span style="font-weight: 500;">{label}</span>')
        html.append(f'    </div>')
    
    html.append('  </div>')

    # ── Close card + outer wrapper ──
    html.append('  </div>')
    html.append('</div>')
    
    return "\n".join(html)
