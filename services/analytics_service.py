import pandas as pd
import sqlite3
from datetime import date, datetime
from typing import Optional, List, Dict, Any

def get_sales_data(conn: sqlite3.Connection, start_date: date, end_date: date, seller_filter: str = "Todos") -> pd.DataFrame:
    """Fetches sales data for reports."""
    query = """
        SELECT s.date as 'Data', p.name as 'Produto', s.quantity as 'Qtd',
               s.total_price as 'Valor', s.discount as 'Desconto',
               s.payment_method as 'Pagamento', s.salesperson as 'Vendedor',
               COALESCE(c.name, 'Consumidor Final') as 'Cliente'
        FROM sales s
        LEFT JOIN products p ON s.product_id = p.id
        LEFT JOIN clients c ON s.client_id = c.id
        WHERE s.date BETWEEN ? AND ?
    """
    params = [start_date, end_date]
    
    if seller_filter != "Todos":
        query += " AND s.salesperson = ?"
        params.append(seller_filter)
    
    query += " ORDER BY s.date DESC"
    
    return pd.read_sql(query, conn, params=params)

def get_sales_total_period(conn: sqlite3.Connection, start_date: date, end_date: date, seller_filter: str = "Todos") -> float:
    """Fetches total sales value for a specific period for comparison."""
    query = "SELECT SUM(total_price) as total FROM sales WHERE date BETWEEN ? AND ?"
    params = [start_date, end_date]
    if seller_filter != "Todos":
        query += " AND salesperson = ?"
        params.append(seller_filter)
    
    df = pd.read_sql(query, conn, params=params)
    return df.iloc[0]['total'] if not df.empty and df.iloc[0]['total'] else 0.0

def get_top_products(conn: sqlite3.Connection, start_date: date, end_date: date, top_limit: int, order_by: str) -> pd.DataFrame:
    """Fetches top items for report."""
    order_col = "total_qty" if order_by == "Quantidade" else "total_value"
    
    query = f"""
        SELECT p.name as 'Produto', p.category as 'Categoria',
               SUM(s.quantity) as total_qty,
               SUM(s.total_price) as total_value,
               COUNT(*) as num_sales
        FROM sales s
        JOIN products p ON s.product_id = p.id
        WHERE s.date BETWEEN ? AND ?
        GROUP BY p.id
        ORDER BY {order_col} DESC
        LIMIT ?
    """
    return pd.read_sql(query, conn, params=[start_date, end_date, top_limit])

def get_expenses_data(conn: sqlite3.Connection, start_date: date, end_date: date, cat_filter: str = "Todas") -> pd.DataFrame:
    """Fetches expenses for report."""
    query = """
        SELECT e.date as 'Data', e.description as 'Descrição', e.category as 'Categoria',
               COALESCE(s.name, '-') as 'Fornecedor', e.amount as 'Valor'
        FROM expenses e
        LEFT JOIN suppliers s ON e.supplier_id = s.id
        WHERE e.date BETWEEN ? AND ?
    """
    params = [start_date, end_date]
    if cat_filter != "Todas":
        query += " AND e.category = ?"
        params.append(cat_filter)
    
    query += " ORDER BY e.date DESC"
    return pd.read_sql(query, conn, params=params)

def get_expenses_total_period(conn: sqlite3.Connection, start_date: date, end_date: date, cat_filter: str = "Todas") -> float:
    """Fetches total expenses for comparison."""
    query = "SELECT SUM(amount) as total FROM expenses WHERE date BETWEEN ? AND ?"
    params = [start_date, end_date]
    if cat_filter != "Todas":
        query += " AND category = ?"
        params.append(cat_filter)
    
    df = pd.read_sql(query, conn, params=params)
    return df.iloc[0]['total'] if not df.empty and df.iloc[0]['total'] else 0.0

def get_material_consumption(conn: sqlite3.Connection, start_date: date, end_date: date, cat_filter: str = "Todas") -> pd.DataFrame:
    """Fetches material consumption."""
    query = """
        SELECT m.name as 'Insumo', 
               COALESCE(mc.name, 'Geral') as 'Categoria',
               SUM(it.quantity) as 'Consumido',
               m.unit as 'Unidade',
               m.price_per_unit as 'Custo Unit.',
               SUM(it.quantity) * m.price_per_unit as 'Custo Total'
        FROM inventory_transactions it
        JOIN materials m ON it.material_id = m.id
        LEFT JOIN material_categories mc ON m.category_id = mc.id
        WHERE DATE(it.date) BETWEEN ? AND ?
          AND it.type = 'SAIDA'
    """
    params = [start_date, end_date]
    
    if cat_filter != "Todas":
        query += " AND mc.name = ?"
        params.append(cat_filter)
    
    query += """
        GROUP BY m.id
        HAVING SUM(it.quantity) > 0
        ORDER BY SUM(it.quantity) DESC
    """
    return pd.read_sql(query, conn, params=params)

def get_product_profitability(conn: sqlite3.Connection, cat_filter: str = "Todas") -> pd.DataFrame:
    """Fetches product profitability data."""
    query = (
        "SELECT p.id, p.name as 'Produto', p.category as 'Categoria', p.base_price as 'Preço Venda', "
        "COALESCE((SELECT SUM(pr.quantity * m.price_per_unit) FROM product_recipes pr JOIN materials m ON pr.material_id = m.id WHERE pr.product_id = p.id), 0) as 'Custo Produção', "
        "p.stock_quantity as 'Estoque' FROM products p WHERE 1=1"
    )
    params = []
    
    if cat_filter != "Todas":
        query += " AND p.category = ?"
        params.append(cat_filter)
    
    query += " ORDER BY p.name"
    
    return pd.read_sql(query, conn, params=params)

def get_sales_trend(conn: sqlite3.Connection, year: int) -> pd.DataFrame:
    """Fetches monthly sales data for a specific year."""
    query = (
        "SELECT p.name as Produto, strftime('%m', s.date) as Mes, SUM(s.quantity) as Quantidade, SUM(s.total_price) as Valor "
        "FROM sales s JOIN products p ON s.product_id = p.id "
        "WHERE strftime('%Y', s.date) = ? GROUP BY p.id, strftime('%m', s.date) ORDER BY p.name, Mes"
    )
    return pd.read_sql(query, conn, params=[str(year)])

def get_realized_profitability(conn: sqlite3.Connection, start_date: date, end_date: date, top_limit: int) -> pd.DataFrame:
    """Fetches realized profitability based on sales and product base cost."""
    query = (
        "SELECT p.name as Produto, p.category as Categoria, SUM(s.quantity) as QtdVendida, SUM(s.total_price) as Receita, "
        "p.base_price as CustoBase, SUM(s.quantity) * p.base_price as CustoTotal "
        "FROM sales s JOIN products p ON s.product_id = p.id "
        "WHERE s.date BETWEEN ? AND ? GROUP BY p.id ORDER BY Receita DESC LIMIT ?"
    )
    return pd.read_sql(query, conn, params=[start_date, end_date, top_limit])

def get_customer_history(conn: sqlite3.Connection, start_date: date, end_date: date) -> pd.DataFrame:
    """Fetches customer purchase history."""
    query = (
        "SELECT COALESCE(c.name, 'Consumidor Final') as Cliente, COUNT(s.id) as NumCompras, SUM(s.quantity) as QtdItens, "
        "SUM(s.total_price) as ValorTotal, AVG(s.total_price) as TicketMedio, MAX(s.date) as UltimaCompra "
        "FROM sales s LEFT JOIN clients c ON s.client_id = c.id "
        "WHERE s.date BETWEEN ? AND ? GROUP BY COALESCE(c.id, 0) ORDER BY ValorTotal DESC"
    )
    return pd.read_sql(query, conn, params=[start_date, end_date])

def get_cash_flow_data(conn: sqlite3.Connection, start_date: date, end_date: date, date_format: str) -> Dict[str, pd.DataFrame]:
    """Fetches sales and expenses grouped by period."""
    # Sales
    sales_query = (
        f"SELECT strftime('{date_format}', date) as Periodo, SUM(total_price) as Entradas "
        f"FROM sales WHERE date BETWEEN ? AND ? GROUP BY strftime('{date_format}', date)"
    )
    sales_df = pd.read_sql(sales_query, conn, params=[start_date, end_date])
    
    # Expenses
    expenses_query = (
        f"SELECT strftime('{date_format}', date) as Periodo, SUM(amount) as Saidas "
        f"FROM expenses WHERE date BETWEEN ? AND ? GROUP BY strftime('{date_format}', date)"
    )
    expenses_df = pd.read_sql(expenses_query, conn, params=[start_date, end_date])
    
    return {'sales': sales_df, 'expenses': expenses_df}

def get_stock_forecast_products(conn: sqlite3.Connection, period_days: int, cutoff_date: str) -> pd.DataFrame:
    """Fetches product stock forecast data."""
    query = (
        "SELECT p.name as Nome, p.category as Categoria, p.stock_quantity as EstoqueAtual, "
        "COALESCE(SUM(s.quantity), 0) as VendidoPeriodo, COALESCE(SUM(s.quantity) / ?, 0) as MediaDiaria "
        "FROM products p LEFT JOIN sales s ON p.id = s.product_id AND s.date >= ? "
        "GROUP BY p.id HAVING p.stock_quantity > 0 ORDER BY MediaDiaria DESC"
    )
    return pd.read_sql(query, conn, params=[period_days, cutoff_date])

def get_stock_forecast_materials(conn: sqlite3.Connection, period_days: int, cutoff_date: str) -> pd.DataFrame:
    """Fetches material stock forecast data."""
    query = (
        "SELECT m.name as Nome, COALESCE(mc.name, 'Geral') as Categoria, m.stock_level as EstoqueAtual, m.unit as Unidade, "
        "COALESCE(SUM(it.quantity), 0) as ConsumidoPeriodo, COALESCE(SUM(it.quantity) / ?, 0) as MediaDiaria "
        "FROM materials m LEFT JOIN material_categories mc ON m.category_id = mc.id "
        "LEFT JOIN inventory_transactions it ON m.id = it.material_id AND it.type = 'SAIDA' AND it.date >= ? "
        "WHERE m.type = 'Material' GROUP BY m.id HAVING m.stock_level > 0 ORDER BY MediaDiaria DESC"
    )
    return pd.read_sql(query, conn, params=[period_days, cutoff_date])

def get_dead_stock_products(conn: sqlite3.Connection, cutoff_date: str) -> pd.DataFrame:
    """Fetches products with no sales since cutoff date."""
    query = (
        "SELECT p.name as 'Nome', p.category as 'Categoria', p.stock_quantity as 'Estoque', p.base_price as 'Preço', "
        "(p.stock_quantity * p.base_price) as 'Valor Parado', MAX(s.date) as 'Última Venda' "
        "FROM products p LEFT JOIN sales s ON p.id = s.product_id "
        "GROUP BY p.id HAVING MAX(s.date) IS NULL OR MAX(s.date) < ? ORDER BY 'Valor Parado' DESC"
    )
    return pd.read_sql(query, conn, params=[cutoff_date])

def get_dead_stock_materials(conn: sqlite3.Connection, cutoff_date: str) -> pd.DataFrame:
    """Fetches materials with no consumption since cutoff date."""
    query = (
        "SELECT m.name as 'Nome', COALESCE(mc.name, 'Geral') as 'Categoria', m.stock_level as 'Estoque', m.price_per_unit as 'Preço', "
        "(m.stock_level * m.price_per_unit) as 'Valor Parado', MAX(it.date) as 'Último Consumo' "
        "FROM materials m LEFT JOIN material_categories mc ON m.category_id = mc.id "
        "LEFT JOIN inventory_transactions it ON m.id = it.material_id AND it.type = 'SAIDA' "
        "WHERE m.type = 'Material' GROUP BY m.id HAVING MAX(it.date) IS NULL OR MAX(it.date) < ? ORDER BY 'Valor Parado' DESC"
    )
    return pd.read_sql(query, conn, params=[cutoff_date])

def get_pending_orders(conn: sqlite3.Connection, status_filter: str, order_by_clause: str) -> pd.DataFrame:
    """Fetches pending commission orders."""
    query = (
        "SELECT co.id as 'Nº Pedido', COALESCE(c.name, 'Sem Cliente') as 'Cliente', co.status as 'Status', DATE(co.date_created) as 'Dt Criação', "
        "DATE(co.date_due) as 'Prazo', co.total_price as 'Valor Total', co.deposit_amount as 'Sinal', "
        "(co.total_price - COALESCE(co.deposit_amount, 0) - COALESCE(co.manual_discount, 0)) as 'Saldo', "
        "(SELECT COUNT(*) FROM commission_items ci WHERE ci.order_id = co.id) as 'Itens', co.notes as 'Observações' "
        "FROM commission_orders co LEFT JOIN clients c ON co.client_id = c.id "
        f"WHERE co.status NOT IN ('Entregue', 'Concluída') {status_filter} ORDER BY {order_by_clause}"
    )
    return pd.read_sql(query, conn)

def get_production_cost_data(conn: sqlite3.Connection, start_date: date, end_date: date) -> pd.DataFrame:
    """Fetches production data for cost analysis."""
    query = (
        "SELECT p.name as Produto, p.category as Categoria, SUM(ph.quantity) as QtdProduzida, p.base_price as PrecoVenda, "
        "SUM(ph.quantity) * p.base_price as ReceitaPotencial "
        "FROM production_history ph JOIN products p ON ph.product_id = p.id "
        "WHERE DATE(ph.timestamp) BETWEEN ? AND ? GROUP BY p.id ORDER BY QtdProduzida DESC"
    )
    return pd.read_sql(query, conn, params=[start_date, end_date])

def get_period_material_cost(conn: sqlite3.Connection, start_date: date, end_date: date) -> float:
    """Fetches total material cost for a period."""
    query = (
        "SELECT SUM(it.quantity * m.price_per_unit) as CustoInsumos "
        "FROM inventory_transactions it JOIN materials m ON it.material_id = m.id "
        "WHERE it.type = 'SAIDA' AND DATE(it.date) BETWEEN ? AND ?"
    )
    df = pd.read_sql(query, conn, params=[start_date, end_date])
    return df.iloc[0]['CustoInsumos'] or 0.0

def get_seasonality_data(conn: sqlite3.Connection, month_num: int, years: List[str]) -> pd.DataFrame:
    """Fetches seasonality comparison data."""
    years_str = "', '".join(years)
    query = (
        "SELECT strftime('%Y', date) as Ano, COUNT(*) as NumVendas, SUM(quantity) as QtdVendida, "
        "SUM(total_price) as ValorTotal, AVG(total_price) as TicketMedio "
        "FROM sales WHERE strftime('%m', date) = ? AND strftime('%Y', date) IN ('{years_str}') "
        "GROUP BY strftime('%Y', date) ORDER BY Ano"
    ).format(years_str=years_str)
    
    return pd.read_sql(query, conn, params=[f"{month_num:02d}"])

def get_supplier_purchases(conn: sqlite3.Connection, start_date: date, end_date: date) -> pd.DataFrame:
    """Fetches purchases by supplier."""
    query = (
        "SELECT COALESCE(s.name, 'Sem Fornecedor') as Fornecedor, COUNT(e.id) as NumCompras, "
        "SUM(e.amount) as ValorTotal, AVG(e.amount) as MediaCompra, MAX(e.date) as UltimaCompra "
        "FROM expenses e LEFT JOIN suppliers s ON e.supplier_id = s.id "
        "WHERE e.date BETWEEN ? AND ? AND e.category LIKE '%Compra%' "
        "GROUP BY COALESCE(s.id, 0) ORDER BY ValorTotal DESC"
    )
    return pd.read_sql(query, conn, params=[start_date, end_date])

def get_supplier_purchases_all(conn: sqlite3.Connection, start_date: date, end_date: date) -> pd.DataFrame:
    """Fetches purchases by supplier (all categories with supplier)."""
    query = (
        "SELECT COALESCE(s.name, 'Sem Fornecedor') as Fornecedor, COUNT(e.id) as NumCompras, "
        "SUM(e.amount) as ValorTotal, AVG(e.amount) as MediaCompra, MAX(e.date) as UltimaCompra "
        "FROM expenses e LEFT JOIN suppliers s ON e.supplier_id = s.id "
        "WHERE e.date BETWEEN ? AND ? AND e.supplier_id IS NOT NULL "
        "GROUP BY s.id ORDER BY ValorTotal DESC"
    )
    return pd.read_sql(query, conn, params=[start_date, end_date])
