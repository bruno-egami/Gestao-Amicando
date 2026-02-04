import database

if __name__ == "__main__":
    print("Running DB migration update...")
    database.init_db()
    print("Done. Check for product_variants table.")
