from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)

# Konfigurasi Database untuk Heroku (PostgreSQL) dan Lokal (SQLite)
# Heroku akan menyediakan variabel lingkungan DATABASE_URL
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///terarium_data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Models ---
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
            'timestamp': self.timestamp.isoformat() + 'Z' # Format ISO 8601
        }

class DeviceCommand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(80), unique=True, nullable=False)
    command = db.Column(db.String(80), nullable=True) # e.g., "fan_on", "pump_off"
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Buat tabel database jika belum ada
@app.before_request
def create_tables():
    db.create_all()

# --- API Endpoints ---

# Endpoint untuk NodeMCU mengirim data sensor (HTTP POST)
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

# Endpoint untuk NodeMCU polling perintah (HTTP GET)
@app.route('/api/v1/commands', methods=['GET'])
def get_commands():
    device_id = request.args.get('device_id')
    if not device_id:
        return jsonify({"message": "device_id is required"}), 400

    command_entry = DeviceCommand.query.filter_by(device_id=device_id).first()
    if command_entry and command_entry.command:
        command_to_send = command_entry.command
        # Opsional: setelah perintah diambil, Anda bisa menghapusnya atau mengosongkannya
        # Untuk skripsi, biarkan saja agar bisa terus di-polling sampai diganti manual
        # command_entry.command = None
        # db.session.commit()
        print(f"[{datetime.now()}] Sending command '{command_to_send}' to {device_id}")
        return jsonify({"command": command_to_send}), 200
    return jsonify({"command": None}), 200 # Tidak ada perintah baru

# Endpoint untuk Dashboard Web mengambil data terbaru (HTTP GET)
@app.route('/api/v1/latest_data/<device_id>', methods=['GET'])
def get_latest_data(device_id):
    data = SensorData.query.filter_by(device_id=device_id).order_by(SensorData.timestamp.desc()).first()
    if data:
        return jsonify(data.to_dict()), 200
    return jsonify({"message": "No data found for this device"}), 404

# Endpoint untuk Dashboard Web mengambil data historis (HTTP GET)
@app.route('/api/v1/historical_data/<device_id>', methods=['GET'])
def get_historical_data(device_id):
    # Ambil 100 data terakhir sebagai contoh, Anda bisa menambahkan parameter limit/offset
    data = SensorData.query.filter_by(device_id=device_id).order_by(SensorData.timestamp.desc()).limit(100).all()
    return jsonify([d.to_dict() for d in data]), 200

# Endpoint untuk Dashboard Web mengirim perintah kontrol (HTTP POST)
@app.route('/api/v1/control', methods=['POST'])
def send_control_command():
    if request.is_json:
        data = request.get_json()
        device_id = data.get('device_id')
        command = data.get('command') # e.g., "fan_on", "fan_off", "pump_on", "pump_off"

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

# Untuk menjalankan aplikasi secara lokal
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)