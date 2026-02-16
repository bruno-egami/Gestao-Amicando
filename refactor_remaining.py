import os

def refactor_file(path, start_line_idx, end_line_idx, has_close=True):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        new_lines = []
        for i, line in enumerate(lines):
            if i < start_line_idx:
                new_lines.append(line)
            elif i == start_line_idx:
                new_lines.append("with database.db_session() as conn:\n")
            elif i > start_line_idx:
                if has_close and i == end_line_idx:
                    pass # Skip conn.close()
                else:
                    should_indent = False
                    if has_close:
                        if i < end_line_idx:
                            should_indent = True
                    else:
                        should_indent = True
                    
                    if should_indent:
                        if line.strip():
                            new_lines.append("    " + line)
                        else:
                            new_lines.append(line)
                    else:
                        # Append lines after close (if any)
                        if has_close and i > end_line_idx:
                             new_lines.append(line)

        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"Refactored {path}")
    except Exception as e:
        print(f"Error refactoring {path}: {e}")

base = r"c:\Users\Bruno Egami\Documents\GitHub\Gestao-Amicando\pages"

# Batch 2
refactor_file(os.path.join(base, "5_Produtos.py"), 23, 1037)
refactor_file(os.path.join(base, "6_Vendas.py"), 17, 94)
refactor_file(os.path.join(base, "7_Fornecedores.py"), 18, 147)

# Batch 3
refactor_file(os.path.join(base, "8_Clientes.py"), 15, 146)
refactor_file(os.path.join(base, "9_Encomendas.py"), 27, 604)
refactor_file(os.path.join(base, "10_Relatorios.py"), 18, 93, has_close=False)

# Batch 4
refactor_file(os.path.join(base, "11_Producao.py"), 21, 500)
refactor_file(os.path.join(base, "13_Gestao_Aulas.py"), 16, 65, has_close=False)
refactor_file(os.path.join(base, "99_Administracao.py"), 19, 443)
