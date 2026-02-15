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
- Backup Automático Agendado e Restauração
- Importação em massa via Excel

### 📊 Relatórios (18 tipos)

#### Estoque e Inventário
- **Estoque Atual** - Visão geral do estoque de produtos e insumos
- **Valuation WIP** - Valor investido em peças em andamento (Work in Process)
- **Itens sem Movimentação** - Produtos/insumos parados (dead stock)
- **Previsão de Estoque** - Estimativa de quando itens vão acabar

#### Vendas e Faturamento
- **Vendas por Período** - Detalhamento de vendas com filtros
- **Top Produtos Vendidos** - Ranking de produtos
- **Análise de Vendas Anual** - Pivot table mensal
- **Lucratividade por Produto** - Margem de lucro por item
- **Análise de Sazonalidade** - Comparação anual

#### Produção e Qualidade
- **Gargalos de Produção** - Lead time (tempo de permanência) por estágio
- **Controle de Qualidade** - Análise de perdas por motivo e estágio
- **Histórico de Produção** - Registro detalhado de itens produzidos
- **Tendência de Produtividade** - Gráficos de evolução da produção mensal
- **Consumo de Insumos** - Matérias-primas utilizadas
- **Custo de Produção** - Estimativa de custo teórico

#### Clientes e Encomendas
- **Clientes - Histórico** - Histórico de compras por cliente
- **Encomendas Pendentes** - Status de pedidos em aberto

#### Financeiro
- **Despesas por Categoria** - Gastos agrupados
- **Fluxo de Caixa** - Entradas vs saídas
- **Fornecedores - Compras** - Histórico de pagamentos

#### Recursos dos Relatórios
- 📈 Gráficos interativos (Plotly)
- 📄 Exportação para PDF (com gráficos)
- 📊 Exportação para Excel
- 🔍 Filtros dinâmicos
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

## 🧪 Testes Automatizados

O projeto utiliza **pytest** para garantir a integridade da lógica de negócio na camada de serviços.

### Como Rodar os Testes

1. Certifique-se de que as dependências de teste estão instaladas:
```bash
pip install pytest pytest-mock
```

2. Execute todos os testes a partir da raiz do projeto:
```bash
pytest tests/
```

Os testes utilizam um banco de dados SQLite **em memória**, garantindo que as execuções sejam rápidas e não alterem seus dados reais de produção.

---

*Desenvolvido com ❤️ e ☕ por Bruno Egami*
