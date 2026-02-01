
import os

file_path = r"d:\GitHub\Gestao-Amicando\pages\9_Encomendas.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
# Lines 0 to 100 (index 0 to 100 inclusive, i.e. lines 1-101 in 1-based) are fine.
# Line 101 (index 100) is empty?
# Let's check the view_file output.
# Line 98: if search_orders...
# Line 99:     mask ...
# Line 100:    orders = orders[mask]
# Line 101:    (newline)
# Line 102:    st.caption... (Indented 4 spaces)
# We want to dedent from line 102 to the end.

start_dedent_line_idx = 101 # Line 102 1-indexed

for i, line in enumerate(lines):
    if i >= start_dedent_line_idx:
        # Check if line starts with 4 spaces
        if line.startswith("    "):
            new_lines.append(line[4:])
        else:
            # Check if it's an empty line (just newline)
            if line.strip() == "":
                new_lines.append(line)
            else:
                # If it doesn't have 4 spaces, maybe it was already at top level?
                # Or maybe it's a multiline string continuation?
                # Safest is to Dedent 4 spaces if possible.
                new_lines.append(line)
    else:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Indentation fixed.")
