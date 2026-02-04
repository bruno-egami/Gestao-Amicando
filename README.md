# 🏺 Amicando - Sistema de Gestão para Atelier de Cerâmica

Sistema completo de gestão para ateliês de cerâmica artesanal, desenvolvido em **Streamlit** com banco de dados **SQLite**.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)
![License](https://img.shields.io/badge/License-Proprietary-gray.svg)

---

## 📋 Funcionalidades

### 📦 Gestão de Produtos
- Cadastro de produtos com preço, categoria e estoque
- **Variações de Produtos** (ex: diferentes esmaltes/cores com ajuste de preço)
- Sistema de **Kits** (produtos compostos por outros produtos)
- Receitas de produtos vinculando matérias-primas
- Controle automático de estoque

### 🧱 Gestão de Insumos
- Cadastro de matérias-primas (argilas, esmaltes, etc.)
- Controle de estoque com alertas de mínimo
- Histórico de movimentações
- Vinculação com fornecedores

### 💰 Vendas e Encomendas
- **Venda Direta**: Produtos em estoque vendidos imediatamente
- **Orçamentos**: Criação, aprovação e conversão automática em encomenda
- **Encomendas**: Produtos sob demanda com:
  - Prazo de entrega personalizável (padrão: 30 dias)
  - Sinal/depósito antecipado
  - Acompanhamento de produção (Status com cores e alertas)
  - Automação de status "Concluída"
- Geração de **recibos e orçamentos em PDF**
- Histórico completo de vendas

### 📊 Gestão Financeira
- Lançamento de despesas eventuais e recorrentes
- Consolidação automática de custos fixos
- Relatórios de faturamento e lucro
- Exportação para Excel

### 🔥 Queimas
- Registro de queimas (biscoito/esmalte)
- Controle de consumo energético (kWh)
- Cálculo automático de custo
- Histórico de manutenção e queimas por forno

### 👥 Clientes e Fornecedores
- Cadastro completo de clientes
- Histórico de compras por cliente
- Cadastro de fornecedores

### ⚙️ Administração
- Gestão de usuários com controle de acesso
- Auditoria de ações (CRUD)
- Backup e restauração do banco de dados
- Importação em massa via Excel

### 📊 Relatórios (16 tipos)

#### Estoque e Inventário
- **Estoque Atual** - Visão geral do estoque de produtos
- **Itens sem Movimentação** - Produtos/insumos parados (dead stock)
- **Previsão de Estoque** - Estimativa de quando itens vão acabar

#### Vendas e Faturamento
- **Vendas por Período** - Detalhamento de vendas com filtros
- **Top Produtos Vendidos** - Ranking de produtos mais vendidos
- **Análise de Vendas Anual** - Pivot table de vendas mensais por produto
- **Lucratividade por Produto** - Margem de lucro por item
- **Análise de Sazonalidade** - Comparação do mesmo mês em diferentes anos

#### Clientes e Encomendas
- **Clientes - Histórico** - Histórico de compras por cliente
- **Encomendas Pendentes** - Status de pedidos em aberto

#### Financeiro
- **Despesas por Categoria** - Gastos agrupados por categoria
- **Fluxo de Caixa** - Entradas vs saídas com saldo acumulado
- **Fornecedores - Compras** - Valores pagos por fornecedor

#### Produção
- **Histórico de Produção** - Registro de produção por período
- **Consumo de Insumos** - Matérias-primas consumidas
- **Custo de Produção** - Estimativa de custo por produto

#### Recursos dos Relatórios
- 📈 Gráficos interativos (Plotly)
- 📄 Exportação para PDF (com gráficos incluídos)
- 📊 Exportação para Excel
- 🔍 Filtros por período, categoria, etc.
- 📱 Layout responsivo

---

## 🚀 Instalação

### Requisitos
- Python 3.9+
- pip

### Passos

1. Clone o repositório:
```bash
git clone https://github.com/bruno-egami/Gestao-Amicando.git
cd Gestao-Amicando
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Execute o sistema:
```bash
streamlit run Dashboard.py
```

4. Acesse no navegador:
```
http://localhost:8501
```

---

## 📁 Estrutura do Projeto

```
Gestao-Amicando/
├── Dashboard.py          # Página inicial com métricas
├── database.py           # Conexão e migrations do SQLite
├── auth.py               # Autenticação e controle de acesso
├── audit.py              # Sistema de auditoria
├── reports.py            # Geração de PDFs
├── admin_utils.py        # Utilitários administrativos
├── pages/
├── 1_Insumos.py      # Gestão de matérias-primas
├── 2_Produtos.py     # Cadastro de produtos (Variações e Kits)
├── 3_Financeiro.py   # Despesas e relatórios
├── 4_Queimas.py      # Registro de queimas
├── 5_Clientes.py     # Gestão de clientes
├── 6_Vendas.py       # PDV, Orçamentos e Histórico
├── 9_Encomendas.py   # Gestão de encomendas e produção
├── 10_Relatorios.py  # Central de Relatórios (16 tipos)
└── 99_Administracao.py # Painel administrativo
├── assets/               # Imagens e uploads
├── data/                 # Banco de dados SQLite
└── requirements.txt      # Dependências Python
```

---

## 🔐 Credenciais Padrão

| Usuário | Senha | Perfil |
|---------|-------|--------|
| `admin` | `admin` | Administrador |

> ⚠️ **Importante**: Altere a senha padrão após o primeiro acesso!

---

## 📦 Dependências Principais

- `streamlit` - Framework web
- `pandas` - Manipulação de dados
- `fpdf2` - Geração de PDFs
- `bcrypt` - Criptografia de senhas
- `openpyxl` - Exportação Excel
- `plotly` - Gráficos interativos
- `kaleido` - Exportação de gráficos para PDF

---

## 🎨 Sobre o Atelier Amicando

Sistema desenvolvido sob medida para o **Atelier Amicando**, especializado em cerâmica artesanal utilitária e decorativa.

📍 Bento Gonçalves, RS - Brasil  
📱 Instagram: [@amicandoatelier](https://instagram.com/amicandoatelier)

---

## 📄 Licença

Este software é proprietário e de uso exclusivo do Atelier Amicando.

---

*Desenvolvido com ❤️ e ☕ por Bruno Egami*
