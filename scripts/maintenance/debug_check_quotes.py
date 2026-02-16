import database
import pandas as pd

conn = database.get_connection()
try:
    print("--- QUOTES TABLE ---")
    df = pd.read_sql("SELECT * FROM quotes", conn)
    print(df)
    
    print("\n--- CLIENTS TABLE ---")
    df_c = pd.read_sql("SELECT id, name FROM clients", conn)
    print(df_c)

    print("\n--- JOIN TEST ---")
    df_join = pd.read_sql("""
        SELECT q.id, c.name as client, q.date_created, q.status 
        FROM quotes q 
        LEFT JOIN clients c ON q.client_id = c.id
    """, conn)
    print(df_join)

except Exception as e:
    print(f"ERROR: {e}")
finally:
    conn.close()
