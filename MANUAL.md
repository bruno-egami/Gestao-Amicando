# 📖 Manual do Usuário - Sistema Amicando

**Versão:** 2.0  
**Data:** Fevereiro 2026  
**Sistema de Gestão para Atelier de Cerâmica**
**https://github.com/bruno-egami/Gestao-Amicando**

---

## 📑 Índice

1. [Instalação](#1-instalação)
2. [Introdução](#2-introdução)
3. [Primeiros Passos](#3-primeiros-passos)
4. [Dashboard](#4-dashboard)
5. [Insumos](#5-insumos)
6. [Produtos](#6-produtos)
7. [Financeiro](#7-financeiro)
8. [Queimas](#8-queimas)
9. [Clientes e Fornecedores](#9-clientes-e-fornecedores)
10. [Vendas](#10-vendas)
11. [Encomendas](#11-encomendas)
12. [Relatórios](#12-relatórios)
13. [Administração](#13-administração)
14. [Dicas e Melhores Práticas](#14-dicas-e-melhores-práticas)

---

## 1. Instalação

Este guia foi elaborado para usuários sem experiência técnica. Siga os passos exatamente como descritos.

### 1.1 O que você vai precisar

- Um computador com Windows 10 ou 11
- Conexão com a internet
- Cerca de 30 minutos para a instalação

### 1.2 Passo 1: Instalar o Python

O Python é o programa que faz o sistema funcionar. Você precisa instalá-lo uma única vez.

1. Abra seu navegador (Chrome, Edge ou Firefox)
2. Acesse: **https://www.python.org/downloads/**
3. Clique no botão amarelo **"Download Python 3.xx"** (a versão mais recente)
4. Quando o download terminar, abra o arquivo baixado
5. **IMPORTANTE:** Na primeira tela, marque a opção:
   - ☑️ **"Add Python to PATH"** (está na parte de baixo da janela)
6. Clique em **"Install Now"**
7. Aguarde a instalação terminar
8. Clique em **"Close"**

### 1.3 Passo 2: Baixar o Sistema Amicando

1. Acesse: **https://github.com/bruno-egami/Gestao-Amicando**
2. Clique no botão verde **"Code"**
3. Clique em **"Download ZIP"**
4. Quando o download terminar, localize o arquivo (geralmente na pasta "Downloads")
5. Clique com o botão direito no arquivo
6. Escolha **"Extrair tudo..."** ou **"Extrair aqui"**
7. Escolha uma pasta de fácil acesso, como **"C:\Amicando"** ou **"Documentos\Amicando"**
8. Clique em **"Extrair"**

### 1.4 Passo 3: Instalar as Dependências

1. Abra a pasta onde você extraiu o sistema
2. Na barra de endereço do Explorador de Arquivos, clique e digite: `cmd`
3. Pressione **Enter** - isso abrirá uma janela preta (Prompt de Comando)
4. Digite o comando abaixo e pressione **Enter**:

```
pip install -r requirements.txt
```

5. Aguarde a instalação (pode levar alguns minutos)
6. Quando terminar, você verá várias mensagens; a última deve indicar sucesso

> ⚠️ Se aparecer erro, tente: `python -m pip install -r requirements.txt`

### 1.5 Passo 4: Executar o Sistema

1. Na mesma janela preta (ou abra novamente como no passo anterior)
2. Digite o comando abaixo e pressione **Enter**:

```
streamlit run Dashboard.py
```

3. Aguarde alguns segundos
4. Seu navegador abrirá automaticamente com o sistema
5. Se não abrir, acesse manualmente: **http://localhost:8501**

### 1.6 Criar um Atalho (Opcional)

Para não precisar repetir os comandos toda vez:

1. Abra o Bloco de Notas
2. Cole o texto abaixo:

```
cd /d "C:\CAMINHO\PARA\SUA\PASTA\Amicando"
streamlit run Dashboard.py
pause
```

3. Substitua `C:\CAMINHO\PARA\SUA\PASTA\Amicando` pelo caminho real onde você extraiu
4. Salve como **"Iniciar Amicando.bat"** (não .txt)
5. Clique duas vezes neste arquivo sempre que quiser abrir o sistema

### 1.7 Solução de Problemas na Instalação

| Problema | Solução |
|----------|---------|
| "python não é reconhecido" | Reinstale o Python marcando "Add to PATH" |
| "pip não é reconhecido" | Use `python -m pip install` em vez de `pip install` |
| "Porta 8501 em uso" | Feche outras janelas do sistema ou reinicie o computador |
| Página não abre | Acesse manualmente http://localhost:8501 |

---

## 2. Introdução

O **Sistema Amicando** foi desenvolvido para auxiliar na gestão de ateliês de cerâmica artesanal. Ele permite controlar o ciclo de produção, desde a compra de insumos até a venda ao cliente.

### 2.1 Funcionalidades

- Controle de estoque de insumos e produtos
- Registro de despesas e receitas
- Ponto de Venda (PDV)
- Encomendas com acompanhamento
- Registro de queimas (fornos)
- Cadastro de clientes e fornecedores
- 16 tipos de relatórios
- Exportação para PDF e Excel
- Controle de usuários

### 2.2 Requisitos

- Navegador web (Chrome, Firefox, Edge)
- Resolução mínima: 1280x720

---

## 3. Primeiros Passos

### 3.1 Acessando o Sistema

1. Abra o sistema (veja seção Instalação)
2. Na tela de login, insira:
   - **Usuário:** `admin`
   - **Senha:** `admin`

> ⚠️ Altere a senha padrão após o primeiro acesso.

### 3.2 Navegação

O menu lateral contém todas as páginas:

| Ícone | Página | Função |
|-------|--------|--------|
| 🏠 | Dashboard | Resumo e métricas |
| 🧱 | Insumos | Matérias-primas |
| 📦 | Produtos | Catálogo |
| 💰 | Financeiro | Despesas |
| 🔥 | Queimas | Fornos |
| 👥 | Clientes | Cadastros |
| 🛒 | Vendas | PDV |
| 📋 | Encomendas | Pedidos |
| 📊 | Relatórios | Análises |
| ⚙️ | Administração | Configurações |

### 3.3 Níveis de Acesso

| Perfil | Permissões |
|--------|------------|
| Administrador | Acesso a todas as funções |
| Gerente | Tudo, exceto gestão de usuários |
| Vendedor | Vendas, clientes e consultas |

---

## 4. Dashboard

Página inicial com resumo das métricas.

### 4.1 Métricas

- Faturamento do mês
- Despesas do mês
- Lucro estimado
- Produtos em estoque
- Encomendas pendentes

### 4.2 Alertas

- 🔴 Estoque baixo
- 🟡 Prazo de encomenda próximo
- 🟢 Vendas do dia

---

## 5. Insumos

Gerencia matérias-primas (argilas, esmaltes, etc.).

### 5.1 Tipos

- **Material:** Consumíveis (argilas, esmaltes)
- **Ferramenta:** Equipamentos (moldes, extrusoras)

### 5.2 Cadastrar

1. Clique em **"➕ Novo Insumo"**
2. Preencha: nome, categoria, fornecedor, preço, unidade, estoque
3. Salve

### 5.3 Movimentar Estoque

1. Localize o insumo
2. Clique em **"📦 Movimentar"**
3. Escolha: ENTRADA, SAÍDA ou AJUSTE
4. Informe quantidade e confirme

---

## 6. Produtos

Gerencia itens para venda.

### 6.1 Cadastrar

1. Clique em **"➕ Novo Produto"**
2. Preencha: nome, categoria, preço, estoque
3. Adicione foto (opcional)
4. Salve

### 6.2 Kits

Produtos compostos por outros produtos.

1. Cadastre o kit
2. Em "Composição", adicione os itens
3. Ao vender, todos os estoques são baixados

### 6.3 Receitas

Vinculam produtos aos insumos necessários.

1. Acesse o produto
2. Vá em "Receita"
3. Adicione insumos e quantidades

### 6.4 Produção

1. Clique em **"🔨 Produzir"**
2. Informe quantidade
3. Os insumos são baixados automaticamente

---

## 7. Financeiro

Controla despesas e custos.

### 7.1 Categorias de Despesas

- Custo Fixo Mensal
- Compra de Insumo
- Manutenção
- Gasto Eventual
- Marketing

### 7.2 Lançar Despesa

1. Clique em **"➕ Nova Despesa"**
2. Preencha: data, descrição, valor, categoria
3. Salve

### 7.3 Compra com Entrada no Estoque

Ao registrar "Compra de Insumo":
1. Selecione o material
2. O sistema pergunta se deseja dar entrada
3. Informe a quantidade recebida

---

## 8. Queimas

Registra uso dos fornos.

### 8.1 Registrar Queima

1. Clique em **"🔥 Nova Queima"**
2. Selecione: forno, data, tipo (biscoito/esmalte)
3. Informe consumo em kWh
4. Salve

### 8.2 Manutenção

1. Vá em "Manutenção"
2. Registre: forno, data, tipo de serviço

---

## 9. Clientes e Fornecedores

### 9.1 Cadastrar Cliente

1. Acesse **"Clientes"**
2. Clique em **"➕ Novo Cliente"**
3. Preencha: nome, telefone, e-mail
4. Salve

### 9.2 Cadastrar Fornecedor

1. Acesse **"Administração > Fornecedores"**
2. Clique em **"➕ Novo Fornecedor"**
3. Preencha e salve

---

## 10. Vendas

Funciona como Ponto de Venda.

### 10.1 Realizar Venda

1. Clique em **"🛒 Nova Venda"**
2. Selecione produtos e quantidades
3. Escolha cliente (opcional)
4. Selecione forma de pagamento
5. Aplique desconto se necessário
6. Finalize

### 10.2 Recibo

Após a venda, você pode gerar recibo em PDF.

### 10.3 Histórico

Consulte vendas anteriores com filtros por período, cliente ou produto.

---

## 11. Encomendas

Pedidos de produtos sob demanda.

### 11.1 Criar Encomenda

1. Clique em **"➕ Nova Encomenda"**
2. Selecione cliente
3. Adicione produtos e quantidades
4. Defina prazo de entrega
5. Registre sinal (se houver)
6. Confirme

### 11.2 Status

| Status | Significado |
|--------|-------------|
| Pendente | Aguardando produção |
| Em Produção | Fabricando |
| Concluída | Pronto |
| Entregue | Cliente recebeu |

### 11.3 Finalizar

1. Altere para "Concluída" quando pronto
2. Altere para "Entregue" quando cliente retirar

---

## 12. Relatórios

16 tipos de análises disponíveis.

### 12.1 Como Gerar

1. Acesse **"Relatórios"**
2. Selecione o tipo
3. Configure filtros
4. Clique em **"🔄 Gerar"**

### 12.2 Exportação

- PDF (com gráficos)
- Excel (planilha)

### 12.3 Tipos Disponíveis

**Estoque:**
- Estoque Atual
- Itens sem Movimentação
- Previsão de Estoque

**Vendas:**
- Vendas por Período
- Top Produtos Vendidos
- Análise de Vendas Anual
- Lucratividade por Produto
- Análise de Sazonalidade

**Clientes:**
- Histórico de Compras
- Encomendas Pendentes

**Financeiro:**
- Despesas por Categoria
- Fluxo de Caixa
- Fornecedores - Compras

**Produção:**
- Histórico de Produção
- Consumo de Insumos
- Custo de Produção

---

## 13. Administração

Acessível apenas para administradores.

### 13.1 Usuários

**Criar:**
1. Acesse "Administração > Usuários"
2. Clique em "➕ Novo Usuário"
3. Preencha dados e perfil
4. Salve

**Alterar senha:**
1. Localize o usuário
2. Clique em "🔑 Alterar Senha"

### 13.2 Backup

**Criar:**
1. Acesse "Administração > Backup"
2. Clique em "📥 Baixar Backup"
3. Salve o arquivo em local seguro

**Restaurar:**
1. Clique em "📤 Restaurar"
2. Selecione o arquivo
3. Confirme

> ⚠️ A restauração substitui todos os dados atuais.

### 13.3 Auditoria

Registra todas as ações: quem fez, o quê e quando.

### 13.4 Importação

Importe dados via Excel:
1. Baixe o modelo
2. Preencha
3. Faça upload
4. Confirme

---

## 14. Dicas e Melhores Práticas

### 14.1 Organização

- Verifique vendas e despesas diariamente
- Analise relatórios semanalmente
- Atenda os alertas de estoque

### 14.2 Segurança

- Troque senhas regularmente
- Cada usuário com conta própria
- Faça backup semanal

### 14.3 Eficiência

- Adicione fotos aos produtos
- Use o campo de observações
- Categorize corretamente

### 14.4 Problemas Comuns

| Problema | Solução |
|----------|---------|
| Sistema lento | Limpe cache do navegador |
| Erro ao salvar | Verifique campos obrigatórios |
| Dados incorretos | Consulte auditoria |
| Esqueceu senha | Peça ao administrador |


---

*Manual do Sistema Amicando v2.0*  
*Atualização: Fevereiro 2026*
