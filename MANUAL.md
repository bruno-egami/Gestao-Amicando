# 📖 Manual do Usuário - Sistema Amicando

**Versão:** 2.1  
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
12. [Gestão de Aulas](#12-gestão-de-aulas)
13. [Relatórios](#13-relatórios)
14. [Administração](#14-administração)
15. [Testes e Verificação](#15-testes-e-verificação)
16. [Dicas e Melhores Práticas](#16-dicas-e-melhores-práticas)

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

### 1.6 Facilitar o Acesso (Atalhos)

O sistema já vem com arquivos prontos para facilitar o seu dia a dia:

1. **Arquivo Principal**: Localize o arquivo `Abrir_Amicando.bat`. Você pode clicar duas vezes nele para iniciar o sistema.
2. **Criar Atalho na Área de Trabalho**: 
   - Clique duas vezes em `Configurar_Atalho.bat`.
   - O sistema criará automaticamente um atalho chamado **"Amicando"** na sua Área de Trabalho com o logo oficial.
   - Siga as instruções na tela e pronto!

> 💡 Se você mover a pasta do sistema para outro lugar, basta rodar o `Configurar_Atalho.bat` novamente para atualizar o link.

### 1.7 Solução de Problemas na Instalação

| Problema | Solução |
|----------|---------|
| "python não é reconhecido" | Reinstale o Python marcando "Add to PATH" |
| "pip não é reconhecido" | Use `python -m pip install` em vez de `pip install` |
| "Porta 8501 em uso" | Feche outras janelas do sistema ou reinicie o computador |
| Página não abre | Acesse manualmente http://localhost:8501 |

---

## 2. Introdução

O **Sistema Amicando** foi desenvolvido para auxiliar na gestão de ateliês de cerâmica artesanal. Ele permite controlar o ciclo de produção, desde a compra de insumos até a venda ao cliente. A versão 2.1 traz melhorias significativas de performance e confiabilidade através de otimizações de banco de dados e testes automatizados.

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
4. Informe quantidade e confirme. O sistema agora utiliza precisão de 4 casas decimais para evitar erros de arredondamento.

---

## 6. Produtos

Gerencia itens para venda.

### 6.1 Cadastrar
1. Clique em **"➕ Novo Produto"**
2. Preencha: nome, categoria, preço base, estoque
3. Adicione foto (opcional)
4. Salve

### 6.1a Variações (Esmaltes/Cores)
Após cadastrar o produto:
1. Localize o produto na lista
2. Clique em **"🎨 Variações"**
3. Adicione o nome da variação (ex: "Esmalte Azul") 
4. Defina o acréscimo de preço (se houver) e o estoque específico daquela variação
5. Salve. Agora esta opção aparecerá nas vendas e encomendas!

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

## 10. Vendas e Orçamentos

Funciona como Ponto de Venda e Gerenciador de Cotações.

### 10.1 Realizar Venda
1. Clique em **"🛒 Nova Venda"**
2. Selecione produtos (e variações, se houver) e quantidades
3. Escolha o cliente
4. Selecione forma de pagamento
5. Clique em **"✅ Finalizar Venda"**

### 10.2 Criar Orçamento
1. Adicione os itens no carrinho normalmente
2. Em vez de finalizar, clique em **"📄 Criar Orçamento"**
3. Preencha a validade, prazo e observações
4. O orçamento ficará salvo na aba **"Orçamentos Salvos"**
5. Você pode gerar PDF, Aprovar (vira encomenda) ou Recusar/Excluir

### 10.3 Histórico
Consulte vendas e orçamentos anteriores com filtros por período, cliente ou produto.

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

| Status | Cor | Significado |
|--------|-----|-------------|
| :orange[Pendente] | Laranja | Aguardando início da produção |
| :blue[Em Produção] | Azul | Itens sendo fabricados |
| :green[Concluída] | Verde | Tudo pronto, aguardando retirada |
| :red[Atrasado] | Vermelho | Prazo vencido e não entregue |
| :grey[Entregue] | Cinza | Pedido entregue ao cliente |

### 11.3 Finalizar/Produzir

1. Acompanhe a produção item a item clicando em "Lançar Produção"
2. **Automação**: Quando o último item for produzido, o status muda automaticamente para **"Concluída"**
3. **Manual**: Se precisar, use o botão **"🏁 Marcar como Pronto"**
4. Quando o cliente retirar, clique em **"📦 Realizar Entrega"** para finalizar e baixar do estoque temporário se necessário.

---

---

## 12. Gestão de Aulas

Módulo completo para gestão de alunos, turmas e mensalidades.

### 12.1 Turmas e Alunos
1. **Turmas**: Crie turmas definindo horários (ex: "Terça Manhã").
2. **Alunos**: Cadastre alunos e vincule-os a uma turma.
   - O sistema controla a presença e saldo de massas/queimas individualmente.

### 12.2 Painel Financeiro (Unificado)
A aba **"💰 Gestão Financeira"** centraliza tudo:
1. **Lançar Consumo**: Registre o uso de materiais (argila) ou queimas para uma lista de alunos.
2. **Gerar Mensalidades**: Ferramenta em lote para criar cobranças para todos os alunos ativos.
3. **Controle de Pagamento**:
   - Marque mensalidades como PAGAS.
   - O sistema realiza alocação inteligente de pagamentos parciais, quitando as dívidas mais antigas primeiro.
   - Envie comprovantes via WhatsApp (abertura automática).
   - Visualize alunos com 3+ mensalidades em atraso (destaque em vermelho).

---

## 13. Relatórios

18 tipos de análises disponíveis.

### 13.1 Como Gerar

1. Acesse **"Relatórios"**
2. Selecione o tipo
3. Configure filtros
4. Clique em **"🔄 Gerar"**

### 13.2 Tipos Disponíveis

**Estoque:**
- Estoque Atual (+ Valuation WIP)
- Itens sem Movimentação
- Previsão de Estoque

**Vendas:**
- Vendas por Período
- Top Produtos Vendidos
- Análise de Vendas Anual
- Lucratividade por Produto
- Análise de Sazonalidade

**Produção e Qualidade:**
- **Gargalos de Produção**: Descubra onde suas peças ficam paradas (Lead Time).
- **Controle de Qualidade**: Monitore perdas e motivos (ex: trincas na queima).
- **Histórico de Produção**: Registro temporal.
- **Tendência de Produtividade**: Gráficos de evolução.

**Financeiro e Outros:**
- Despesas, Fluxo de Caixa, Fornecedores e Clientes.

---

## 14. Administração

Acessível apenas para administradores.

### 14.1 Usuários

**Criar:**
1. Acesse "Administração > Usuários"
2. Clique em "➕ Novo Usuário"
3. Preencha dados e perfil
4. Salve

**Alterar senha:**
1. Localize o usuário
2. Clique em "🔑 Alterar Senha"

### 14.2 Backup (Automático e Manual)

O sistema realiza **backups automáticos** periodicamente (configurável).

**Configurar Frequência:**
1. Acesse a aba "Configurações" na Administração.
2. Escolha: Diário, Semanal, Mensal ou Manual.

**Backup Manual:**
1. Acesse "Administração > Backup"
2. Clique em "📥 Baixar Backup" para salvar no seu computador.
3. Ou use "Fazer Backup Local" para salvar na pasta do sistema.

**Restaurar:**
1. Clique em "📤 Restaurar"
2. Selecione o arquivo `.db`
3. Confirme

> ⚠️ A restauração substitui todos os dados atuais.

### 14.3 Auditoria

Registra todas as ações: quem fez, o quê e quando.

### 14.4 Importação

Importe dados via Excel:
1. Baixe o modelo
2. Preencha
3. Faça upload
4. Confirme
    
### 14.5 Performance
O sistema foi otimizado para lidar com grandes volumes de dados. Filtros e buscas agora são processados diretamente no banco de dados, resultando em respostas mais rápidas e menor consumo de memória no computador.

---

## 15. Testes e Verificação

Para garantir que o sistema continue funcionando corretamente após atualizações, foi implementada uma infraestrutura de testes automatizados.

### 15.1 Como Rodar os Testes (Desenvolvedor)
Se você deseja validar o código após fazer alterações:
1. Abra o terminal na pasta do sistema.
2. Execute o comando: `pytest tests/`
3. O sistema validará automaticamente 17 fluxos críticos, incluindo cálculos financeiros e estoque.

---

## 16. Dicas e Melhores Práticas

### 15.1 Organização

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

*Manual do Sistema Amicando v2.1*  
*Atualização: Fevereiro 2026*
