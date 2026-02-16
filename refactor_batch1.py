import os

def refactor_file(path, start_line_idx, end_line_idx):
    # start_line_idx is the index of 'conn = ...' which becomes 'with ...'
    # end_line_idx is the index of 'conn.close()' which is removed
    # Lines between are indented
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        new_lines = []
        for i, line in enumerate(lines):
            if i < start_line_idx:
                new_lines.append(line)
            elif i == start_line_idx:
                new_lines.append("with database.db_session() as conn:\n")
            elif i > start_line_idx and i < end_line_idx:
                if line.strip():
                    new_lines.append("    " + line)
                else:
                    new_lines.append(line)
            elif i == end_line_idx:
                pass
            else:
                new_lines.append(line)
                
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"Refactored {path}")
    except Exception as e:
        print(f"Error refactoring {path}: {e}")

base = r"c:\Users\Bruno Egami\Documents\GitHub\Gestao-Amicando\pages"
refactor_file(os.path.join(base, "1_Insumos.py"), 16, 464) # 1-based: 17, 465
refactor_file(os.path.join(base, "3_Financeiro.py"), 20, 775) # 1-based: 21, 776
refactor_file(os.path.join(base, "4_Queimas.py"), 17, 334) # 1-based: 18, 335
