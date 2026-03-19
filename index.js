require('dotenv').config();
const express = require('express');
const cors = require('cors');
const admin = require('firebase-admin');
const axios = require('axios');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5001;

// Firebase configuration (from Python backend)
const firebaseConfig = {
  apiKey: process.env.FIREBASE_API_KEY || "AIzaSyDFXKnP194gyar2DwnI0EIvizFAS-cRdQA",
  projectId: process.env.FIREBASE_PROJECT_ID || "vit-web-app-e5cd5",
};

// Initialize Firebase Admin using Environment Variables
try {
  let privateKey = process.env.FIREBASE_PRIVATE_KEY;
  
  if (privateKey) {
    // Remove potential surrounding quotes and handle escaped newlines
    privateKey = privateKey.replace(/^"(.*)"$/, '$1').replace(/\\n/g, '\n');
  }

  if (process.env.FIREBASE_CLIENT_EMAIL && privateKey) {
    admin.initializeApp({
      credential: admin.credential.cert({
        projectId: process.env.FIREBASE_PROJECT_ID,
        clientEmail: process.env.FIREBASE_CLIENT_EMAIL,
        privateKey: privateKey,
      })
    });
    console.log("Firebase Admin initialized from environment variables.");
  } else {
    // Fallback for local development if file exists
    const SERVICE_ACCOUNT_PATH = path.join(__dirname, 'serviceAccountKey.json');
    const serviceAccount = require(SERVICE_ACCOUNT_PATH);
    admin.initializeApp({
      credential: admin.credential.cert(serviceAccount)
    });
    console.log("Firebase Admin initialized from serviceAccountKey.json.");
  }
} catch (err) {
  console.error("Firebase initialization failed:", err.message);
}

const db = admin.firestore();

// Middleware
app.use(cors({ origin: true, credentials: true }));
app.use(express.json());

// Token Verification Middleware
const tokenRequired = async (req, res, next) => {
  const authHeader = req.headers.authorization;
  const token = authHeader && authHeader.replace('Bearer ', '');

  if (!token) {
    return res.status(401).json({ error: 'Token is missing' });
  }

  try {
    const decodedToken = await admin.auth().verifyIdToken(token);
    req.patient_id = decodedToken.uid;
    next();
  } catch (err) {
    return res.status(401).json({ error: 'Invalid or expired token', details: err.message });
  }
};

// Routes
// 1. Signup
app.post('/api/signup', async (req, res) => {
  const { patient_id, password, name, age, gender } = req.body;

  if (!patient_id || !password || !name || !age || !gender) {
    return res.status(400).json({ error: 'All fields are required' });
  }

  try {
    const email = `${patient_id.trim().toLowerCase()}@vitacheck.com`;
    // 1. Create Auth User
    await admin.auth().createUser({
      uid: patient_id.trim(),
      email: email,
      password: password,
      displayName: name.trim(),
    });

    // 2. Create Firestore Profile
    await db.collection('users').document(patient_id.trim()).set({
      name: name.trim(),
      age: parseInt(age),
      gender: gender.trim(),
      role: 'patient',
      email: email,
      created_at: admin.firestore.FieldValue.serverTimestamp()
    });

    res.status(201).json({ message: 'Account created successfully', patient_id });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

// 2. Login
app.post('/api/login', async (req, res) => {
  const { patient_id, password } = req.body;

  if (!patient_id || !password) {
    return res.status(400).json({ error: 'Patient ID and Password are required' });
  }

  try {
    const email = `${patient_id.trim().toLowerCase()}@vitacheck.com`;
    // Use Firebase REST API for client-side password sign-in (Node Admin SDK doesn't support password auth)
    const response = await axios.post(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${firebaseConfig.apiKey}`, {
      email,
      password,
      returnSecureToken: true
    });

    const token = response.data.idToken;
    const userDoc = await db.collection('users').doc(patient_id.trim()).get();

    if (!userDoc.exists) {
      return res.status(404).json({ error: 'User profile not found in Firestore.' });
    }

    const userData = userDoc.data();
    res.json({
      token,
      patient: {
        id: patient_id.trim(),
        name: userData.name,
        age: String(userData.age),
        gender: userData.gender
      }
    });
  } catch (err) {
    res.status(401).json({ error: 'Invalid Patient ID or Password' });
  }
});

// 3. Select Doctor
app.post('/api/select-doctor', tokenRequired, async (req, res) => {
  const { doctor } = req.body;

  if (!doctor) {
    return res.status(400).json({ error: 'Doctor selection is required' });
  }

  try {
    await db.collection('sessions').doc(req.patient_id).set({
      doctor: doctor.trim(),
      updated_at: admin.firestore.FieldValue.serverTimestamp()
    }, { merge: true });

    res.json({ message: 'Doctor selected successfully', doctor });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// 4. Analyze Symptoms
app.post('/api/analyze-symptoms', tokenRequired, async (req, res) => {
  const { symptoms } = req.body;
  const symptoms_text = (symptoms || '').trim().toLowerCase();

  if (!symptoms_text) {
    return res.status(400).json({ error: 'Symptoms are required' });
  }

  try {
    const vitaminsSnapshot = await db.collection('vitamins').get();
    const input_symptoms = symptoms_text.split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
    const results = [];

    vitaminsSnapshot.forEach(doc => {
      const v_data = doc.data();
      const vitamin_symptoms = (v_data.symptoms || []).map(s => s.toLowerCase());
      
      const matched = input_symptoms.filter(s => 
        vitamin_symptoms.some(vs => vs.includes(s) || s.includes(vs))
      );
      
      const match_count = matched.length;
      const total_symptoms = vitamin_symptoms.length;

      if (match_count > 0) {
        const match_percentage = (match_count / total_symptoms) * 100;
        results.push({
          vitamin: v_data.vitamin_name,
          risk_level: v_data.risk_level,
          diet_suggestions: v_data.diet_suggestions || [],
          matched_symptoms: matched,
          match_percentage: Math.round(Math.min(match_percentage, 100) * 10) / 10
        });
      }
    });

    results.sort((a, b) => b.match_percentage - a.match_percentage);

    let finalResults = results;
    if (results.length === 0) {
      finalResults = [{
        vitamin: 'No specific deficiency detected',
        risk_level: 'Low',
        diet_suggestions: ['Maintain a balanced diet', 'Eat fruits and vegetables', 'Stay hydrated', 'Exercise regularly'],
        matched_symptoms: [],
        match_percentage: 0
      }];
    }

    const top_result = finalResults[0];
    const report = {
      primary_deficiency: top_result.vitamin,
      risk_level: top_result.risk_level,
      risk_percentage: top_result.match_percentage > 0 ? top_result.match_percentage : 15,
      diet_suggestions: top_result.diet_suggestions,
      all_deficiencies: finalResults.slice(0, 5),
      symptoms_entered: symptoms_text,
      timestamp: new Date().toISOString()
    };

    // Store in session and history
    await db.collection('sessions').doc(req.patient_id).set({
      symptoms: symptoms_text,
      report: report,
      updated_at: admin.firestore.FieldValue.serverTimestamp()
    }, { merge: true });

    await db.collection('users').doc(req.patient_id).collection('history').add(report);

    res.json(report);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// 5. Get History
app.get('/api/history', tokenRequired, async (req, res) => {
  try {
    const historySnapshot = await db.collection('users')
      .doc(req.patient_id)
      .collection('history')
      .orderBy('timestamp', 'desc')
      .limit(10)
      .get();

    const history = [];
    historySnapshot.forEach(doc => history.push(doc.data()));
    res.json(history);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// 6. Get Report
app.get('/api/report', tokenRequired, async (req, res) => {
  try {
    const [userDoc, sessionDoc] = await Promise.all([
      db.collection('users').doc(req.patient_id).get(),
      db.collection('sessions').doc(req.patient_id).get()
    ]);

    if (!userDoc.exists) {
      return res.status(404).json({ error: 'User not found' });
    }

    const userData = userDoc.data();
    const sessionData = sessionDoc.exists ? sessionDoc.data() : {};

    res.json({
      patient: {
        id: req.patient_id,
        name: userData.name,
        age: String(userData.age),
        gender: userData.gender
      },
      doctor: sessionData.doctor || null,
      symptoms: sessionData.symptoms || null,
      report: sessionData.report || null
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Node.js Backend running on http://localhost:${PORT}`);
});
