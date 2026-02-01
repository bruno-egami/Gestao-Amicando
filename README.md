# 🏺 Amicando - Sistema de Gestão para Atelier de Cerâmica

Sistema completo de gestão para ateliês de cerâmica artesanal, desenvolvido em **Streamlit** com banco de dados **SQLite**.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)
![License](https://img.shields.io/badge/License-Proprietary-gray.svg)

---

## 📋 Funcionalidades

### 📦 Gestão de Produtos
- Cadastro de produtos com preço, categoria e estoque
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
- **Encomendas**: Produtos sob demanda com:
  - Prazo de entrega personalizável (padrão: 30 dias)
  - Sinal/depósito antecipado
  - Acompanhamento de produção
- Geração de **recibos em PDF**
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
│   ├── 1_Insumos.py      # Gestão de matérias-primas
│   ├── 2_Produtos.py     # Cadastro de produtos
│   ├── 3_Financeiro.py   # Despesas e relatórios
│   ├── 4_Queimas.py      # Registro de queimas
│   ├── 5_Clientes.py     # Gestão de clientes
│   ├── 6_Vendas.py       # PDV e histórico
│   ├── 9_Encomendas.py   # Gestão de encomendas
│   └── 99_Administracao.py # Painel administrativo
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
