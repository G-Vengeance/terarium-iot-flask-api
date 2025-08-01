# init_db.py
import os
from app import app, db # Import 'app' dan 'db' dari aplikasi Flask Anda

# Konfigurasi database untuk memastikan Railway_db.create_all() menggunakan DATABASE_URL
# Ini penting karena script ini akan dijalankan di lingkungan Railway
uri = os.getenv("DATABASE_URL", "sqlite:///terarium_data.db")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print("Attempting to create database tables...")
with app.app_context():
    db.create_all()
    print("Database tables created or already exist.")