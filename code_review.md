# Revisão Detalhada do Projeto — Gestão Amicando

Revisão completa do código-fonte, organizada por severidade.

---

## 🔴 Erros / Bugs (Severidade Alta)

### 1. Vazamento de Conexões em 4 Páginas
**Arquivos:** [3_Financeiro.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/pages/3_Financeiro.py), [4_Queimas.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/pages/4_Queimas.py), [1_Insumos.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/pages/1_Insumos.py), [11_Producao.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/pages/11_Producao.py)

Estas 4 páginas ainda usam `conn = database.get_connection()` **sem** `try/finally/conn.close()` nem `with database.db_session()`. Se ocorrer exceção, a conexão SQLite nunca fecha, podendo causar lock do banco.

```diff
-conn = database.get_connection()
-cursor = conn.cursor()
-# ... todo o código da página ...
+with database.db_session() as conn:
+    cursor = conn.cursor()
+    # ... todo o código da página ...
```

### 2. `9_Encomendas.py` — 10 Chamadas `get_connection()` Internas
**Arquivo:** [9_Encomendas.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/pages/9_Encomendas.py)

Apesar de usar `db_session()` no nível de leitura, cria **10 conexões adicionais** via `database.get_connection()` para operações de escrita, cada uma com `try/finally/close()`. Isso é funcional, porém cria risco de inconsistência e complexidade desnecessária.

> [!TIP]
> Considerar passar a conexão existente como argumento ou usar um padrão de "write connection" mais limpo.

### 3. `Dashboard.py` — Padrão Misto de Conexão
**Arquivo:** [Dashboard.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/Dashboard.py)

Usa `db_session()` para criar o admin, mas depois usa `get_connection()` para o restante da página (linha 39). Deveria usar `db_session()` para tudo.

### 4. `financial_views.py` — `except Exception: pass` Silencioso
**Arquivo:** [financial_views.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/views/financial_views.py#L141)

Linha 141: exceção engolida silenciosamente. Se houver erro ao processar dados financeiros, o usuário jamais saberá.

---

## 🟠 Problemas de Segurança / Manutenção (Severidade Média)

### 5. `delete_backup()` — Sem Validação de Path Traversal
**Arquivo:** [backup_utils.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/utils/backup_utils.py#L97-L103)

A função `delete_backup(filename)` aceita um filename direto e constrói o path sem validar se está dentro do `BACKUP_FOLDER`. Diferente de `perform_backup()`, que **tem** essa validação.

```python
# Atual (vulnerável):
def delete_backup(filename):
    path = os.path.join(BACKUP_FOLDER, filename)
    # ⚠️ filename = "../../database.db" apagaria o banco!

# Correção:
def delete_backup(filename):
    path = os.path.abspath(os.path.join(BACKUP_FOLDER, filename))
    if not path.startswith(os.path.abspath(BACKUP_FOLDER)):
        raise ValueError("Path fora do diretório de backup")
```

### 6. ~33 Blocos `except Exception:` Silenciosos
**Arquivos:** Espalhados por todo o projeto (principalmente `5_Produtos.py`, `9_Encomendas.py`, `3_Financeiro.py`, `4_Queimas.py`)

Aproximadamente 33 blocos `except Exception:` sem logging. Quando algo falha, não há registro — dificulta debug em produção.

> [!IMPORTANT]
> Considerar substituir por `except Exception as e: logger.debug(...)` para pelo menos registrar o erro em arquivo de log.

### 7. `audit.py` — SQL Dinâmico no Rollback
**Arquivo:** [audit.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/audit.py#L176-L191)

Embora exista whitelist de tabelas e validação de colunas (boa prática!), os nomes de colunas no `SET` clause são inseridos via f-string. Se um `old_data` malicioso vier do banco, ainda há risco residual.

### 8. `audit.py` — Imports Dentro de Funções
**Arquivo:** [audit.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/audit.py)

Linhas 55, 67, 81, 137: `import pandas as pd` repetido dentro de 4 funções. Deveria estar no topo do arquivo (PEP 8).

---

## 🟡 Melhorias de Arquitetura / Qualidade (Severidade Baixa)

### 9. `Dashboard.py` — SQL Inline em vez de Services
**Arquivo:** [Dashboard.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/Dashboard.py#L66-L112)

O Dashboard tem **6 queries SQL inline** (linhas 66-112) em vez de usar service layer. Isso quebra a separação de responsabilidades e dificulta testes.

```python
# Atual:
orders_df = pd.read_sql("SELECT ...", conn)
materials_df = pd.read_sql("SELECT ...", conn)

# Ideal:
orders_df = order_service.get_pending_orders_summary(conn)
materials_df = material_service.get_low_stock_alerts(conn)
```

### 10. Arquivos Órfãos na Raiz do Projeto
| Arquivo | Status | Ação Sugerida |
|---------|--------|---------------|
| `refactor_batch1.py` | Script de refatoração antigo | 🗑️ Excluir |
| `refactor_remaining.py` | Script de refatoração antigo | 🗑️ Excluir |
| `compile_manual.py` | Compilador de manual | ⚠️ Avaliar se ainda é usado |
| `gui_main.py` | Launcher desktop | ✅ Manter, mas documentar |

### 11. Duplicação: `views/reports/` vs `services/reporting/`
**Diretórios:**
- [views/reports/](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/views/reports/) (7 arquivos, 67KB)
- [services/reporting/](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/services/reporting/) (4 arquivos)

Dois diretórios de "reports" em locais diferentes gera confusão. Verificar se `views/reports/` contém lógica duplicada ou se é um módulo de relatórios visuais (Streamlit) que deveria ser renomeado para algo mais claro como `views/report_pages/`.

### 12. `create_default_admin` Chamado em Dois Lugares
**Arquivos:** [Dashboard.py:36](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/Dashboard.py#L36) e [99_Administracao.py:23](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/pages/99_Administracao.py#L23)

`auth.create_default_admin(conn)` é chamado tanto no Dashboard quanto na página de Administração. Deveria ser chamado apenas uma vez, no `Dashboard.py` (que é o entry point).

### 13. `migrations/` — Scripts Avulsos de Migração
**Diretório:** [migrations/](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/migrations/)

3 scripts de migração soltos (`clean_cancellations.py`, `create_cancellations_table.py`, `create_cancellations_table_v2.py`) não parecem integrados ao sistema de migração em `database_schema.py`.

### 14. `scripts/` — 13 Scripts de Debug/Fix
**Diretório:** [scripts/](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/scripts/)

Scripts como `debug_check_quotes.py`, `fix_items_db.py`, `fix_wip_priority.py` são úteis para desenvolvimento, mas não deveriam ser distribuídos em produção.

> [!TIP]
> Mover para uma pasta `scripts/archive/` ou adicionar ao `.gitignore` se forem ferramentas internas.

### 15. `database.py` — `initialize()` Sem WAL Mode
**Arquivo:** [database.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/database.py#L23-L37)

A função `initialize()` abre uma conexão sem `PRAGMA journal_mode=WAL`, diferente de `get_connection()`. Se a inicialização for lenta, pode haver lock.

### 16. `ui_components.py` — Parâmetros Não Utilizados
**Arquivo:** [ui_components.py](file:///c:/Users/Bruno%20Egami/Documents/GitHub/Gestao-Amicando/utils/ui_components.py#L6)

A função `card_metric()` aceita `icon` e `color` como parâmetros mas não os usa. Isso confunde quem usar a função.

---

## ✅ Pontos Positivos

| Aspecto | Avaliação |
|---------|-----------|
| **Logging centralizado** | `utils/logging_config.py` é bem estruturado e usado consistentemente |
| **Auditoria** | `audit.py` com whitelist de tabelas e validação de colunas |
| **Service Layer** | Boa separação com `services/` para lógica de negócio |
| **Backup seguro** | `VACUUM INTO` com validação de path |
| **Autenticação** | RBAC bem implementado com bcrypt e force password change |
| **Senha aleatória** | Admin padrão com senha segura (recém-implementado) |
| **Context manager DB** | `db_session()` disponível e já usado em vários arquivos |

---

## Prioridade Sugerida para Correções

| Prioridade | Item | Esforço |
|:----------:|------|:-------:|
| 🔴 P0 | #1. Conexões sem close em 4 páginas | ~30 min |
| 🔴 P0 | #5. Path traversal em `delete_backup` | ~5 min |
| 🟠 P1 | #3. Dashboard padrão misto de conexão | ~15 min |
| 🟠 P1 | #6. `except Exception:` → adicionar log | ~45 min |
| 🟠 P1 | #8. Imports inline em `audit.py` | ~5 min |
| 🟡 P2 | #9. SQL inline no Dashboard → services | ~1 hora |
| 🟡 P2 | #10. Limpar arquivos órfãos | ~10 min |
| 🟡 P2 | #12. `create_default_admin` duplicado | ~5 min |
| 🟡 P3 | #11. Renomear `views/reports/` | ~15 min |
| 🟡 P3 | #13-14. Organizar scripts e migrations | ~20 min |
