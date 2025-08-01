from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from flask_cors import CORS # Pastikan ini ada dan Flask-Cors sudah diinstal

app = Flask(__name__)

# Konfigurasi CORS: Mengizinkan semua origin untuk semua path.
# Ini penting untuk komunikasi dengan frontend Anda di Vercel.
CORS(app, resources={r"/*": {"origins": "*"}}) 

# Konfigurasi database
# Railway akan secara otomatis menyediakan variabel lingkungan DATABASE_URL
# Jika tidak ada, fallback ke SQLite untuk pengembangan lokal
uri = os.getenv("DATABASE_URL", "sqlite:///terarium_data.db")
# Mengganti skema URL PostgreSQL lama ke yang baru jika diperlukan oleh SQLAlchemy
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Inisialisasi database:
# Panggil db.create_all() HANYA SEKALI, saat aplikasi dijalankan
# Ini akan membuat tabel jika belum ada.
# Untuk deployment di Railway, ini akan dijalankan saat Gunicorn start.
# Untuk lokal, ini akan dijalankan saat __name__ == '__main__'.

# Endpoint root untuk cek status server
@app.route('/')
def home():
    return "Terrarium API is running 🐍", 200

# --- Model database ---
class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(80), nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'temperature': self.temperature,
            'humidity': self.humidity,
            'timestamp': self.timestamp.isoformat() + 'Z'
        }

class DeviceCommand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(80), unique=True, nullable=False)
    command = db.Column(db.String(80), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# --- API untuk menerima data ---
@app.route('/api/v1/data', methods=['POST'])
def receive_sensor_data():
    if request.is_json:
        data = request.get_json()
        device_id = data.get('device_id')
        temperature = data.get('temperature')
        humidity = data.get('humidity')

        if not all([device_id, temperature is not None, humidity is not None]):
            return jsonify({"message": "Invalid data"}), 400

        new_data = SensorData(device_id=device_id, temperature=temperature, humidity=humidity)
        db.session.add(new_data)
        db.session.commit()
        print(f"[{datetime.now()}] Received data from {device_id}: Temp={temperature}, Hum={humidity}")
        return jsonify({"message": "Data received successfully"}), 200
    return jsonify({"message": "Request must be JSON"}), 400

# --- API untuk polling command ---
@app.route('/api/v1/commands', methods=['GET'])
def get_commands():
    device_id = request.args.get('device_id')
    if not device_id:
        return jsonify({"message": "device_id is required"}), 400

    command_entry = DeviceCommand.query.filter_by(device_id=device_id).first()
    if command_entry and command_entry.command:
        # Perintah akan dikirim ke NodeMCU, lalu bisa dihapus dari DB jika hanya sekali pakai
        # Untuk skripsi, bisa dibiarkan agar bisa di-polling berkali-kali sampai diganti
        command_to_send = command_entry.command
        # command_entry.command = None # Opsional: jika command hanya untuk sekali pakai
        # db.session.commit() # Opsional: jika command hanya untuk sekali pakai
        print(f"[{datetime.now()}] Sending command '{command_to_send}' to {device_id}")
        return jsonify({"command": command_to_send}), 200
    return jsonify({"command": None}), 200

# --- API untuk kontrol command dari dashboard ---
@app.route('/api/v1/control', methods=['POST'])
def send_control_command():
    if request.is_json:
        data = request.get_json()
        device_id = data.get('device_id')
        command = data.get('command')

        if not all([device_id, command]):
            return jsonify({"message": "device_id and command are required"}), 400

        command_entry = DeviceCommand.query.filter_by(device_id=device_id).first()
        if command_entry:
            command_entry.command = command
        else:
            command_entry = DeviceCommand(device_id=device_id, command=command)
            db.session.add(command_entry)
        db.session.commit()
        print(f"[{datetime.now()}] Control command '{command}' set for {device_id}")
        return jsonify({"message": "Command set successfully"}), 200
    return jsonify({"message": "Request must be JSON"}), 400

# --- API untuk latest data ---
@app.route('/api/v1/latest_data/<device_id>', methods=['GET'])
def get_latest_data(device_id):
    data = SensorData.query.filter_by(device_id=device_id).order_by(SensorData.timestamp.desc()).first()
    if data:
        return jsonify(data.to_dict()), 200
    return jsonify({"message": "No data found for this device"}), 404

# --- API untuk historical data ---
@app.route('/api/v1/historical_data/<device_id>', methods=['GET'])
def get_historical_data(device_id):
    # Ambil 100 data terakhir sebagai contoh, Anda bisa menambahkan parameter limit/offset
    data = SensorData.query.filter_by(device_id=device_id).order_by(SensorData.timestamp.desc()).limit(100).all()
    return jsonify([d.to_dict() for d in data]), 200

# --- Run aplikasi (Untuk pengembangan lokal) ---
if __name__ == '__main__':
    # Pastikan database dibuat saat aplikasi dijalankan secara lokal
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)