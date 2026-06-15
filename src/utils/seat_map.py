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
    
    html = []
    html.append('<div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 15px; margin: 10px 0; font-family: sans-serif; max-width: 480px;">')
    
    # Legend
    html.append('  <div style="display: flex; gap: 15px; justify-content: center; margin-bottom: 15px; font-size: 0.8rem; color: #94a3b8;">')
    html.append('    <div style="display: flex; align-items: center; gap: 5px;"><div style="background-color: #28a745; width: 12px; height: 12px; border-radius: 3px;"></div><span>Available</span></div>')
    html.append('    <div style="display: flex; align-items: center; gap: 5px;"><div style="background-color: #dc3545; width: 12px; height: 12px; border-radius: 3px;"></div><span>Booked</span></div>')
    if selected_seats:
        html.append('    <div style="display: flex; align-items: center; gap: 5px;"><div style="background-color: #ffc107; width: 12px; height: 12px; border-radius: 3px;"></div><span>Selected</span></div>')
    html.append('  </div>')
    
    # Screen indicator
    html.append('  <div style="text-align: center; margin-bottom: 20px;">')
    html.append('    <div style="border-bottom: 3px solid #64748b; width: 80%; margin: 0 auto; height: 10px; border-radius: 50%;"></div>')
    html.append('    <span style="font-size: 0.7rem; color: #64748b; letter-spacing: 2px;">SCREEN THIS WAY</span>')
    html.append('  </div>')
    
    # Rows
    for row in sorted(seats_by_row.keys()):
        row_type = seat_types.get(row, "standard").title()
        html.append(f'  <div style="display: flex; align-items: center; margin-bottom: 8px; gap: 8px;">')
        # Row label
        html.append(f'    <div style="width: 20px; font-weight: bold; color: #e2e8f0; font-size: 0.85rem; text-align: center;">{row}</div>')
        # Seats container
        html.append(f'    <div style="display: flex; flex-wrap: wrap; gap: 6px; flex-grow: 1;">')
        
        for seat_id in seats_by_row[row]:
            status = seats_dict[seat_id]
            
            # Determine color
            if seat_id in selected_set:
                bg_color = '#ffc107' # gold/yellow
                text_color = '#000000'
                title_attr = "Selected Seat"
            elif status == "available":
                bg_color = '#28a745' # green
                text_color = '#ffffff'
                title_attr = f"{row_type} - Available"
            else:
                bg_color = '#dc3545' # red
                text_color = '#ffffff'
                title_attr = f"{row_type} - Booked"
                
            html.append(f'      <div title="{title_attr}" style="background-color: {bg_color}; color: {text_color}; min-width: 26px; height: 26px; text-align: center; line-height: 26px; border-radius: 4px; font-weight: bold; font-size: 0.75rem; user-select: none;">{seat_id[1:]}</div>')
            
        html.append('    </div>')
        # Row Type Label
        html.append(f'    <div style="font-size: 0.65rem; color: #64748b; width: 50px; text-align: right;">{row_type[:4]}</div>')
        html.append('  </div>')
        
    html.append('</div>')
    return "\n".join(html)
