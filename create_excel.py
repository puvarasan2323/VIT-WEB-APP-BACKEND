import pandas as pd
from openpyxl import Workbook

patients_data = {
    'PatientID': ['P001', 'P002', 'P003', 'P004', 'P005'],
    'Password': ['pass123', 'pass456', 'pass789', 'pass101', 'pass202'],
    'Name': ['John Smith', 'Sarah Johnson', 'Michael Brown', 'Emily Davis', 'Robert Wilson'],
    'Age': [35, 28, 45, 52, 31],
    'Gender': ['Male', 'Female', 'Male', 'Female', 'Male']
}

vitamin_data = {
    'VitaminName': [
        'Vitamin D',
        'Vitamin B12',
        'Vitamin C',
        'Iron',
        'Vitamin A',
        'Vitamin E',
        'Calcium',
        'Vitamin K',
        'Zinc',
        'Folate'
    ],
    'Symptoms': [
        'fatigue,bone pain,muscle weakness,depression,hair loss',
        'numbness,tingling,fatigue,weakness,pale skin,shortness of breath',
        'bleeding gums,bruising,dry skin,slow healing,joint pain',
        'fatigue,weakness,pale skin,headache,dizziness,cold hands',
        'night blindness,dry eyes,skin problems,frequent infections',
        'muscle weakness,vision problems,numbness,immune weakness',
        'muscle cramps,numbness,fatigue,brittle nails,poor appetite',
        'easy bruising,bleeding,weak bones,blood clotting issues',
        'hair loss,slow healing,loss of taste,frequent infections,diarrhea',
        'fatigue,mouth sores,gray hair,tongue swelling,growth problems'
    ],
    'RiskLevel': [
        'High', 'High', 'Medium', 'High', 'Medium',
        'Low', 'Medium', 'Low', 'Medium', 'Medium'
    ],
    'DietSuggestions': [
        'Fatty fish,Egg yolks,Fortified milk,Sunlight exposure,Mushrooms',
        'Meat,Fish,Eggs,Dairy products,Fortified cereals',
        'Citrus fruits,Strawberries,Bell peppers,Broccoli,Tomatoes',
        'Red meat,Spinach,Lentils,Beans,Fortified cereals',
        'Carrots,Sweet potatoes,Spinach,Mangoes,Liver',
        'Nuts,Seeds,Spinach,Avocado,Olive oil',
        'Milk,Cheese,Yogurt,Broccoli,Almonds',
        'Leafy greens,Broccoli,Brussels sprouts,Fish,Meat',
        'Oysters,Beef,Pumpkin seeds,Lentils,Chickpeas',
        'Leafy greens,Citrus fruits,Beans,Peas,Fortified grains'
    ]
}

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.xlsx')

with pd.ExcelWriter(DATA_FILE, engine='openpyxl') as writer:
    pd.DataFrame(patients_data).to_excel(writer, sheet_name='Patients', index=False)
    pd.DataFrame(vitamin_data).to_excel(writer, sheet_name='VitaminData', index=False)

print("Excel file created successfully!")
