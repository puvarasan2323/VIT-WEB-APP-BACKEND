import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
import pyrebase
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import datetime

# Firebase configuration from user
firebase_config = {
  "apiKey": "AIzaSyDFXKnP194gyar2DwnI0EIvizFAS-cRdQA",
  "authDomain": "vit-web-app-e5cd5.firebaseapp.com",
  "projectId": "vit-web-app-e5cd5",
  "storageBucket": "vit-web-app-e5cd5.firebasestorage.app",
  "messagingSenderId": "1053416298949",
  "appId": "1:1053416298949:web:9977960db4bc53a35c93ac",
  "measurementId": "G-8LYDVE1S82",
  "databaseURL": "https://vit-web-app-e5cd5.firebaseio.com"
}

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Initialize Firebase Admin
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_KEY = os.path.join(BASE_DIR, 'serviceAccountKey.json')

if os.path.exists(SERVICE_ACCOUNT_KEY):
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
    firebase_admin.initialize_app(cred)
else:
    print("\n" + "!"*60)
    print("WARNING: serviceAccountKey.json NOT FOUND in backend/ directory.")
    print("Firestore and Auth verification will FAIL until this file is added.")
    print("!"*60 + "\n")

db = firestore.client()

# Initialize Pyrebase for client-side auth
firebase = pyrebase.initialize_app(firebase_config)
pb_auth = firebase.auth()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        try:
            decoded_token = auth.verify_id_token(token)
            patient_id = decoded_token['uid']
        except Exception as e:
            return jsonify({'error': 'Invalid or expired token', 'details': str(e)}), 401
        
        return f(patient_id, *args, **kwargs)
    return decorated

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    patient_id = data.get('patient_id', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    age = data.get('age')
    gender = data.get('gender', '').strip()

    if not all([patient_id, password, name, age, gender]):
        return jsonify({'error': 'All fields are required'}), 400

    try:
        email = f"{patient_id.lower()}@vitacheck.com"
        # 1. Create Auth User
        user = auth.create_user(
            uid=patient_id,
            email=email,
            password=password,
            display_name=name
        )
        # 2. Create Firestore Profile
        db.collection('users').document(patient_id).set({
            'name': name,
            'age': int(age),
            'gender': gender,
            'role': 'patient',
            'email': email,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        return jsonify({'message': 'Account created successfully', 'patient_id': patient_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    patient_id = data.get('patient_id', '').strip()
    password = data.get('password', '').strip()

    if not patient_id or not password:
        return jsonify({'error': 'Patient ID and Password are required'}), 400

    try:
        email = f"{patient_id.lower()}@vitacheck.com"
        user = pb_auth.sign_in_with_email_and_password(email, password)
        token = user['idToken']
        
        user_doc = db.collection('users').document(patient_id).get()
        if not user_doc.exists:
            return jsonify({'error': 'User profile not found in Firestore.'}), 404
        
        user_data = user_doc.to_dict()
        
        return jsonify({
            'token': token,
            'patient': {
                'id': patient_id,
                'name': user_data.get('name'),
                'age': str(user_data.get('age')),
                'gender': user_data.get('gender')
            }
        })
    except Exception as e:
        return jsonify({'error': 'Invalid Patient ID or Password'}), 401

@app.route('/api/select-doctor', methods=['POST'])
@token_required
def select_doctor(patient_id):
    data = request.get_json()
    doctor = data.get('doctor', '').strip()

    if not doctor:
        return jsonify({'error': 'Doctor selection is required'}), 400

    db.collection('sessions').document(patient_id).set({
        'doctor': doctor,
        'updated_at': firestore.SERVER_TIMESTAMP
    }, merge=True)

    return jsonify({'message': 'Doctor selected successfully', 'doctor': doctor})

@app.route('/api/analyze-symptoms', methods=['POST'])
@token_required
def analyze_symptoms(patient_id):
    data = request.get_json()
    symptoms_text = data.get('symptoms', '').strip().lower()

    if not symptoms_text:
        return jsonify({'error': 'Symptoms are required'}), 400

    vitamins_ref = db.collection('vitamins').get()
    input_symptoms = [s.strip() for s in symptoms_text.replace('\n', ',').split(',') if s.strip()]
    results = []

    for doc in vitamins_ref:
        v_data = doc.to_dict()
        vitamin_symptoms = [s.lower() for s in v_data.get('symptoms', [])]
        matched = [s for s in input_symptoms if any(vs in s or s in vs for vs in vitamin_symptoms)]
        match_count = len(matched)
        total_symptoms = len(vitamin_symptoms)

        if match_count > 0:
            match_percentage = (match_count / total_symptoms) * 100
            results.append({
                'vitamin': v_data.get('vitamin_name'),
                'risk_level': v_data.get('risk_level'),
                'diet_suggestions': v_data.get('diet_suggestions', []),
                'matched_symptoms': matched,
                'match_percentage': round(min(match_percentage, 100), 1)
            })

    results.sort(key=lambda x: x['match_percentage'], reverse=True)

    if not results:
        results = [{
            'vitamin': 'No specific deficiency detected',
            'risk_level': 'Low',
            'diet_suggestions': ['Maintain a balanced diet', 'Eat fruits and vegetables', 'Stay hydrated', 'Exercise regularly'],
            'matched_symptoms': [],
            'match_percentage': 0
        }]

    top_result = results[0]
    report = {
        'primary_deficiency': top_result['vitamin'],
        'risk_level': top_result['risk_level'],
        'risk_percentage': top_result['match_percentage'] if top_result['match_percentage'] > 0 else 15,
        'diet_suggestions': top_result['diet_suggestions'],
        'all_deficiencies': results[:5],
        'symptoms_entered': symptoms_text,
        'timestamp': datetime.datetime.utcnow().isoformat()
    }

    # 1. Store in current session
    db.collection('sessions').document(patient_id).set({
        'symptoms': symptoms_text,
        'report': report,
        'updated_at': firestore.SERVER_TIMESTAMP
    }, merge=True)

    # 2. Add to User History for persistence
    db.collection('users').document(patient_id).collection('history').add(report)

    return jsonify(report)

@app.route('/api/history', methods=['GET'])
@token_required
def get_history(patient_id):
    history_ref = db.collection('users').document(patient_id).collection('history').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).get()
    history = [doc.to_dict() for doc in history_ref]
    return jsonify(history)

@app.route('/api/report', methods=['GET'])
@token_required
def get_report(patient_id):
    user_doc = db.collection('users').document(patient_id).get()
    session_doc = db.collection('sessions').document(patient_id).get()
    
    if not user_doc.exists:
        return jsonify({'error': 'User not found'}), 404

    user_data = user_doc.to_dict()
    session_data = session_doc.to_dict() if session_doc.exists else {}

    return jsonify({
        'patient': {
            'id': patient_id,
            'name': user_data.get('name'),
            'age': str(user_data.get('age')),
            'gender': user_data.get('gender')
        },
        'doctor': session_data.get('doctor'),
        'symptoms': session_data.get('symptoms'),
        'report': session_data.get('report')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
