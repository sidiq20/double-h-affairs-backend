from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
import uuid
import qrcode
from io import BytesIO
import base64
import os
from datetime import datetime
import json

app = Flask(__name__)
CORS(app,
        resources={r"/*": {
        "origins": [
            'http://localhost:5173',
            'http://127.0.0.1:5173',
         'https://doublehaffairs.vercel.app',
         'https://*.vercel.app'
        ]
    }},
    supports_credentials=True,
)

# MongoDB configuration
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb+srv://sidiqolasode_db_user:sEAD4FnMnaz1QlVl@double-h.dqoemjz.mongodb.net/?retryWrites=true&w=majority&appName=double-h')
client = MongoClient(MONGO_URI)
db = client['wedding_verification']
qr_codes_collection = db['qr_codes']

class QRCodeManager:
    def __init__(self):
        self.base_url = os.environ.get('BASE_URL', 'https://doublehaffairs.vercel.app')
    
    def generate_bulk_qr_codes(self, count=200):
        """Generate bulk QR codes with unique IDs"""
        codes = []
        
        for i in range(1, count + 1):
            code_id = str(uuid.uuid4())
            
            # Create QR code document
            qr_doc = {
                "code_id": code_id,
                "qr_number": i,
                "name": None,
                "scan_count": 0,
                "max_scans": 2,
                "created_at": datetime.utcnow(),
                "initialized_at": None
            }
            
            # Insert into MongoDB
            result = qr_codes_collection.insert_one(qr_doc)
            
            # Generate QR code image
            qr_url = f"{self.base_url}/init?code={code_id}"
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # Convert to base64 for easy storage/transmission
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            codes.append({
                "code_id": code_id,
                "qr_number": i,
                "qr_url": qr_url,
                "qr_image_base64": img_base64,
                "_id": str(result.inserted_id)
            })
        
        return codes
    
    def get_qr_code(self, code_id):
        """Get QR code document by code_id"""
        return qr_codes_collection.find_one({"code_id": code_id})
    
    def initialize_qr_code(self, code_id, name):
        """Initialize QR code with guest name"""
        qr_doc = self.get_qr_code(code_id)
        
        if not qr_doc:
            return {"error": "Invalid QR code"}
        
        if qr_doc.get("name"):
            return {"error": "QR code already initialized"}
        
        # Update with name and initialization timestamp
        result = qr_codes_collection.update_one(
            {"code_id": code_id},
            {
                "$set": {
                    "name": name.strip(),
                    "initialized_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            return {"success": True, "message": "QR initialized successfully", "name": name}
        else:
            return {"error": "Failed to initialize QR code"}
    
    def scan_qr_code(self, code_id):
        """Process QR code scan at event"""
        qr_doc = self.get_qr_code(code_id)
        
        if not qr_doc:
            return {"status": "invalid", "reason": "QR code not found"}
        
        if not qr_doc.get("name"):
            return {"status": "invalid", "reason": "QR code not initialized"}
        
        if qr_doc.get("scan_count", 0) >= qr_doc.get("max_scans", 2):
            return {
                "status": "invalid", 
                "reason": f"Maximum scans ({qr_doc.get('max_scans', 2)}) already used"
            }
        
        # Increment scan count
        new_scan_count = qr_doc.get("scan_count", 0) + 1
        qr_codes_collection.update_one(
            {"code_id": code_id},
            {
                "$set": {"scan_count": new_scan_count},
                "$push": {"scan_history": datetime.utcnow()}
            }
        )
        
        scans_left = qr_doc.get("max_scans", 2) - new_scan_count
        
        return {
            "status": "valid",
            "name": qr_doc.get("name"),
            "scans_left": scans_left,
            "qr_number": qr_doc.get("qr_number")
        }

# Initialize QR manager
qr_manager = QRCodeManager()

# API Routes
@app.route('/api/generate', methods=['POST'])
def generate_qr_codes():
    """Generate bulk QR codes"""
    data = request.get_json() or {}
    count = data.get('count', 200)
    
    try:
        codes = qr_manager.generate_bulk_qr_codes(count)
        return jsonify({
            "success": True,
            "message": f"Generated {len(codes)} QR codes",
            "codes": codes
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/codes', methods=['GET'])
def get_all_codes():
    """List all QR codes for admin"""
    try:
        codes = list(qr_codes_collection.find({}, {
            "_id": 0,
            "code_id": 1,
            "qr_number": 1,
            "name": 1,
            "scan_count": 1,
            "max_scans": 1,
            "created_at": 1,
            "initialized_at": 1
        }).sort("qr_number", 1))
        
        return jsonify({
            "success": True,
            "codes": codes,
            "total": len(codes)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/init', methods=['POST'])
def initialize_qr():
    """Initialize QR code with guest name"""
    data = request.get_json()
    
    if not data or not data.get('code_id') or not data.get('name'):
        return jsonify({"error": "Missing code_id or name"}), 400
    
    code_id = data.get('code_id')
    name = data.get('name')
    
    if not name.strip():
        return jsonify({"error": "Name cannot be empty"}), 400
    
    result = qr_manager.initialize_qr_code(code_id, name)
    
    if "error" in result:
        return jsonify(result), 400
    
    return jsonify(result)

@app.route('/api/scan', methods=['POST'])
def scan_qr():
    """Scan QR code at event"""
    data = request.get_json()
    
    if not data or not data.get('code_id'):
        return jsonify({"error": "Missing code_id"}), 400
    
    code_id = data.get('code_id')
    result = qr_manager.scan_qr_code(code_id)
    
    return jsonify(result)

@app.route('/api/code/<code_id>', methods=['GET'])
def get_code_info(code_id):
    """Get specific QR code information"""
    try:
        qr_doc = qr_manager.get_qr_code(code_id)
        
        if not qr_doc:
            return jsonify({"error": "QR code not found"}), 404
        
        # Remove sensitive MongoDB _id
        qr_doc.pop('_id', None)
        
        return jsonify({
            "success": True,
            "code": qr_doc
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        total_codes = qr_codes_collection.count_documents({})
        initialized_codes = qr_codes_collection.count_documents({"name": {"$ne": None}})
        used_codes = qr_codes_collection.count_documents({"scan_count": {"$gt": 0}})
        max_used_codes = qr_codes_collection.count_documents({"scan_count": {"$gte": 2}})
        
        return jsonify({
            "success": True,
            "stats": {
                "total_codes": total_codes,
                "initialized_codes": initialized_codes,
                "used_codes": used_codes,
                "max_used_codes": max_used_codes,
                "unused_codes": total_codes - used_codes
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/attendees', methods=['GET'])
def get_attendees():
    """Get list of all attendees who have initialized QR codes"""
    try:
        # Get all QR codes that have been initialized with names
        attendees = list(qr_codes_collection.find(
            {"name": {"$ne": None}},  # Only codes with names
            {
                "_id": 0,
                "name": 1,
                "qr_number": 1,
                "initialized_at": 1,
                "scan_count": 1,
                "max_scans": 1
            }
        ).sort("initialized_at", 1))  # Sort by initialization time
        
        return jsonify({
            "success": True,
            "attendees": attendees,
            "total": len(attendees)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test MongoDB connection
        db.command('ping')
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)