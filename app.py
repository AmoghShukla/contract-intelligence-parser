import os
import threading
import time
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId

# Initialize the Flask application
app = Flask(__name__)
CORS(app)

# --- MongoDB Configuration and Client ---
# Use the Docker service name 'mongo' for the hostname
# The port is the default MongoDB port, and the database name is 'contracts_db'
MONGO_URI = 'mongodb://mongo:27017/'
DATABASE_NAME = 'contracts_db'

try:
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    contracts_collection = db['contracts']
    print("Successfully connected to MongoDB.")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    # In a production app, you would handle this more gracefully,
    # perhaps by exiting or retrying the connection.

# --- Helper Functions ---

def simulate_data_extraction(contract_id_str):
    """
    Simulates the long-running, asynchronous process of extracting data from a contract.
    This function runs in a separate thread and updates the contracts in MongoDB.
    """
    print(f"[{datetime.now()}] Starting extraction for contract ID: {contract_id_str}")
    
    contract_id = ObjectId(contract_id_str)
    
    # Simulate a long-running process with a progress bar
    total_steps = 10
    for i in range(1, total_steps + 1):
        progress_percentage = (i / total_steps) * 100
        # Update the status and progress in the database
        contracts_collection.update_one(
            {'_id': contract_id},
            {'$set': {'status': 'processing', 'progress': int(progress_percentage)}}
        )
        print(f"[{datetime.now()}] Contract {contract_id_str}: {int(progress_percentage)}% complete.")
        time.sleep(1)
    
    # Simulate the extracted data and a confidence score
    extracted_data = {
        "party_identification": {
            "parties": ["Acme Corp.", "Global Solutions Inc."],
            "signatories": ["John Doe", "Jane Smith"]
        },
        "financial_details": {
            "total_contract_value": 50000.00,
            "currency": "USD"
        },
        "payment_structure": {
            "payment_terms": "Net 30"
        }
    }
    
    # Simulate the scoring algorithm based on the presence of key fields
    score = 0
    if extracted_data['financial_details']['total_contract_value']:
        score += 30
    if extracted_data['party_identification']['parties']:
        score += 25
    if extracted_data['payment_structure']['payment_terms']:
        score += 20
    
    # Finalize the status as 'completed'
    contracts_collection.update_one(
        {'_id': contract_id},
        {'$set': {
            'status': 'completed',
            'progress': 100,
            'extracted_data': extracted_data,
            'confidence_score': score
        }}
    )
    print(f"[{datetime.now()}] Extraction completed for contract ID: {contract_id_str}")

# --- API Endpoints ---

@app.route('/contracts/upload', methods=['POST'])
def upload_contract():
    """
    Handles contract file uploads and stores metadata in MongoDB.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    
    if file.filename == '' or not file.filename.endswith('.pdf'):
        return jsonify({"error": "No selected file or file is not a PDF"}), 400
    
    try:
        # In a real app, you would save the file to a secure location (e.g., S3).
        # For now, we'll just get the filename.
        filename = file.filename
        
        # Store initial contract metadata in MongoDB
        initial_data = {
            'filename': filename,
            'status': 'pending',
            'progress': 0,
            'upload_time': datetime.now().isoformat(),
            'extracted_data': None,
            'confidence_score': 0
        }
        
        result = contracts_collection.insert_one(initial_data)
        contract_id_str = str(result.inserted_id)
        
        # Start the asynchronous processing in a separate thread
        processing_thread = threading.Thread(
            target=simulate_data_extraction,
            args=(contract_id_str,)
        )
        processing_thread.start()
        
        return jsonify({
            "message": "Contract upload successful, processing initiated.",
            "contract_id": contract_id_str
        }), 202
        
    except Exception as e:
        print(f"An error occurred during upload: {e}")
        return jsonify({"error": "An unexpected error occurred."}), 500

@app.route('/contracts/<string:contract_id_str>/status', methods=['GET'])
def get_processing_status(contract_id_str):
    """
    Checks the parsing status of a contract using the MongoDB database.
    """
    try:
        contract_id = ObjectId(contract_id_str)
    except:
        abort(404, description="Invalid contract ID format.")
        
    contract_data = contracts_collection.find_one({'_id': contract_id}, {'status': 1, 'progress': 1})
    
    if not contract_data:
        abort(404, description="Contract not found.")
        
    return jsonify({
        "contract_id": contract_id_str,
        "status": contract_data['status'],
        "progress": contract_data['progress']
    })

@app.route('/contracts/<string:contract_id_str>', methods=['GET'])
def get_contract_data(contract_id_str):
    """
    Retrieves the parsed contract data from the MongoDB database.
    """
    try:
        contract_id = ObjectId(contract_id_str)
    except:
        abort(404, description="Invalid contract ID format.")
        
    contract_data = contracts_collection.find_one({'_id': contract_id})
    
    if not contract_data:
        abort(404, description="Contract not found.")
        
    if contract_data['status'] != 'completed':
        return jsonify({
            "message": "Contract processing is not yet complete.",
            "status": contract_data['status'],
            "progress": contract_data['progress']
        }), 409
        
    # The ObjectId needs to be converted to a string for JSON serialization
    contract_data['_id'] = str(contract_data['_id'])
        
    return jsonify(contract_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
