# Clinical Trial Enrollment Prediction API
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import pickle
import numpy as np

# Initialize FastAPI
app = FastAPI(
    title="Clinical Trial Enrollment Prediction API",
    description="AI-powered patient enrollment prediction system",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load models at startup
@app.on_event("startup")
async def load_models():
    global model, scaler, label_encoders, feature_columns
    
    print("Loading models...")
    model = pickle.load(open('enrollment_model.pkl', 'rb'))
    scaler = pickle.load(open('scaler.pkl', 'rb'))
    label_encoders = pickle.load(open('label_encoders.pkl', 'rb'))
    feature_columns = pickle.load(open('feature_columns.pkl', 'rb'))
    print("✅ Models loaded successfully!")

# Input schema
class PatientData(BaseModel):
    age: float
    gender: str
    bmi: float
    smoker: int
    chronic_conditions: int
    previous_trials: int
    distance_to_site_miles: float
    insurance_type: str
    education_level: str
    trial_phase: str
    disease_category: str
    site_location: str
    referral_source: str

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Clinical Trial Enrollment Prediction API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "POST /predict": "Predict enrollment for single patient",
            "GET /health": "Check API health"
        }
    }

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "models_loaded": True}

# Prediction endpoint
@app.post("/predict")
async def predict_enrollment(patient: PatientData):
    try:
        # Convert to DataFrame
        patient_dict = patient.dict()
        df = pd.DataFrame([patient_dict])
        
        # Feature engineering
        df['age_group'] = pd.cut(df['age'], bins=[0, 30, 50, 65, 100], 
                                 labels=['Young', 'Middle', 'Senior', 'Elderly'])
        df['bmi_category'] = pd.cut(df['bmi'], bins=[0, 18.5, 25, 30, 100], 
                                    labels=['Underweight', 'Normal', 'Overweight', 'Obese'])
        df['site_nearby'] = (df['distance_to_site_miles'] < 30).astype(int)
        df['high_risk'] = (df['chronic_conditions'] >= 3).astype(int)
        df['trial_experienced'] = (df['previous_trials'] > 0).astype(int)
        df['patient_risk_score'] = (df['chronic_conditions'] * 2 + 
                                    df['age'] / 20 + df['previous_trials'] * 3)
        df['accessibility_score'] = (100 - df['distance_to_site_miles']).clip(0, 100)
        
        # Encode categoricals
        for feature, encoder in label_encoders.items():
            try:
                df[feature + '_encoded'] = encoder.transform(df[feature])
            except:
                df[feature + '_encoded'] = 0
        
        # Predict
        X = df[feature_columns]
        X_scaled = scaler.transform(X)
        
        probability = float(model.predict_proba(X_scaled)[0, 1])
        prediction = "Enrolled" if probability > 0.5 else "Not Enrolled"
        
        # Generate recommendation
        if probability >= 0.7:
            confidence = "HIGH"
            recommendation = "🟢 Prioritize for enrollment - High likelihood!"
            action = "Schedule immediate screening call"
        elif probability >= 0.5:
            confidence = "MEDIUM"
            recommendation = "🟡 Good candidate - Follow up recommended"
            action = "Send informational materials and schedule call"
        else:
            confidence = "LOW"
            recommendation = "🔴 Low likelihood - Consider alternative trials"
            action = "Explore other trial options or address barriers"
        
        return {
            "success": True,
            "patient_id": f"P{hash(str(patient_dict)) % 10000}",
            "enrollment_probability": round(probability * 100, 2),
            "prediction": prediction,
            "confidence": confidence,
            "recommendation": recommendation,
            "next_action": action,
            "key_factors": {
                "age": patient.age,
                "distance": patient.distance_to_site_miles,
                "chronic_conditions": patient.chronic_conditions,
                "previous_trials": patient.previous_trials
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)