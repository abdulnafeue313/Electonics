import os
import sqlite3
from werkzeug.security import generate_password_hash

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(BASE_DIR,"website.db")

def get_db():
    db=sqlite3.connect(DB_PATH)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db

def _cols(db,table):
    return {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}

def _ensure(db,table,defs):
    existing=_cols(db,table)
    for name,definition in defs.items():
        if name not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

def init_db():
    db=get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,password_hash TEXT,role TEXT DEFAULT 'customer',email_verified INTEGER DEFAULT 0,google_id TEXT,facebook_id TEXT,phone TEXT,address TEXT,city TEXT,province TEXT,postal_code TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("""CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,category TEXT,description TEXT,price REAL DEFAULT 0,image TEXT,active INTEGER DEFAULT 1,stock INTEGER DEFAULT 100,created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("""CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT,order_number TEXT UNIQUE,user_id INTEGER,customer_name TEXT NOT NULL,customer_email TEXT NOT NULL,phone TEXT NOT NULL,alternate_phone TEXT,country TEXT,province TEXT,city TEXT,area TEXT,address TEXT NOT NULL,house_number TEXT,postal_code TEXT,delivery_instructions TEXT,payment_method TEXT DEFAULT 'Cash on Delivery',payment_status TEXT DEFAULT 'Pending',transaction_id TEXT,subtotal REAL DEFAULT 0,discount REAL DEFAULT 0,delivery_fee REAL DEFAULT 0,tax REAL DEFAULT 0,total REAL DEFAULT 0,status TEXT DEFAULT 'Pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("""CREATE TABLE IF NOT EXISTS order_items (id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER NOT NULL,product_id INTEGER,product_name TEXT NOT NULL,product_image TEXT,quantity INTEGER DEFAULT 1,price REAL DEFAULT 0,line_total REAL DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS service_requests (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,customer_name TEXT NOT NULL,email TEXT NOT NULL,phone TEXT NOT NULL,service_name TEXT NOT NULL,address TEXT,city TEXT,preferred_date TEXT,preferred_time TEXT,description TEXT,status TEXT DEFAULT 'Pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("""CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,name TEXT NOT NULL,email TEXT NOT NULL,phone TEXT,subject TEXT,message TEXT NOT NULL,status TEXT DEFAULT 'New',created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("""CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER NOT NULL,user_id INTEGER NOT NULL,rating INTEGER NOT NULL,comment TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    db.execute("""CREATE TABLE IF NOT EXISTS email_verifications (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,token TEXT UNIQUE,expires_at TEXT,used INTEGER DEFAULT 0)""")
    _ensure(db,"products",{"description":"TEXT","price":"REAL DEFAULT 0","image":"TEXT","active":"INTEGER DEFAULT 1","stock":"INTEGER DEFAULT 100","category":"TEXT"})
    _ensure(db,"users",{"email_verified":"INTEGER DEFAULT 0","google_id":"TEXT","facebook_id":"TEXT","phone":"TEXT","address":"TEXT","city":"TEXT","province":"TEXT","postal_code":"TEXT"})
    _ensure(db,"orders",{"alternate_phone":"TEXT","country":"TEXT","province":"TEXT","city":"TEXT","area":"TEXT","house_number":"TEXT","postal_code":"TEXT","delivery_instructions":"TEXT","payment_method":"TEXT DEFAULT 'Cash on Delivery'","payment_status":"TEXT DEFAULT 'Pending'","transaction_id":"TEXT","subtotal":"REAL DEFAULT 0","discount":"REAL DEFAULT 0","delivery_fee":"REAL DEFAULT 0","tax":"REAL DEFAULT 0","total":"REAL DEFAULT 0","status":"TEXT DEFAULT 'Pending'"})
    admin=db.execute("SELECT id FROM users WHERE email=?",("admin@example.com",)).fetchone()
    if not admin:
        db.execute("INSERT INTO users(name,email,password_hash,role,email_verified) VALUES(?,?,?,?,?)",("Website Admin","admin@example.com",generate_password_hash("admin123"),"admin",1))
    if db.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]==0:
        db.executemany("INSERT INTO products(name,category,description,price,image,active,stock) VALUES(?,?,?,?,?,1,100)",[
        ('Premium Product', 'Featured', 'High-quality featured product.', 2500.00, 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80'),
        ('Popular Product', 'Popular', 'One of our popular products.', 3500.00, 'https://images.unsplash.com/photo-1491553895911-0055eca6402d?auto=format&fit=crop&w=900&q=80'),
        ('New Arrival', 'New', 'A fresh new arrival.', 4200.00, 'https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?auto=format&fit=crop&w=900&q=80'),
        ('Best Seller', 'Best Seller', 'A customer favorite.', 5500.00, 'https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&w=900&q=80')
        ])
    db.commit(); db.close()

if __name__=="__main__": init_db()
