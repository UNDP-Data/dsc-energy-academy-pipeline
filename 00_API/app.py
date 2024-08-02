from flask import Flask, jsonify, request
import pandas as pd

app = Flask(__name__)

# Load your data
df = pd.read_csv('../04_Outputs/Modules/parsed_data.csv')
import os
# print(os.path.abspath('../04_Outputs/Modules/parsed_data.csv'))



@app.route('/')
def index():
    return "Welcome to the Academy Data Pipeline API!"

@app.route('/data', methods=['GET'])
def get_data():
    data = df.to_dict(orient='records')  # Convert DataFrame to a list of dictionaries
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
