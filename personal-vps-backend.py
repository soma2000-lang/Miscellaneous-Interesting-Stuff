# app.py
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)
CORS(app)

class VPS(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    ip_address = db.Column(db.String(15), nullable=True)

@app.route('/vps', methods=['GET'])
def get_all_vps():
    vps_list = VPS.query.all()
    return jsonify([{'id': vps.id, 'name': vps.name, 'status': vps.status, 'ip_address': vps.ip_address} for vps in vps_list])

@app.route('/vps', methods=['POST'])
def create_vps():
    data = request.json
    new_vps = VPS(name=data['name'], status='stopped', ip_address=None)
    db.session.add(new_vps)
    db.session.commit()
    return jsonify({'id': new_vps.id, 'name': new_vps.name, 'status': new_vps.status, 'ip_address': new_vps.ip_address}), 201

@app.route('/vps/<int:vps_id>', methods=['PUT'])
def update_vps(vps_id):
    vps = VPS.query.get_or_404(vps_id)
    data = request.json
    vps.status = data['status']
    if data['status'] == 'running':
        vps.ip_address = '192.168.1.' + str(vps_id)  # Simplified IP assignment
    else:
        vps.ip_address = None
    db.session.commit()
    return jsonify({'id': vps.id, 'name': vps.name, 'status': vps.status, 'ip_address': vps.ip_address})

@app.route('/vps/<int:vps_id>', methods=['DELETE'])
def delete_vps(vps_id):
    vps = VPS.query.get_or_404(vps_id)
    db.session.delete(vps)
    db.session.commit()
    return '', 204

if __name__ == '__main__':
    app.run(debug=True)
