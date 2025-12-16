import os
from pymongo import MongoClient
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

def check_stats():
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/algoclash')
    try:
        client = MongoClient(mongo_uri)
        db = client.get_default_database()
        
        agents = list(db.agents.find({}, {'_id': 0}))
        
        if not agents:
            print("No agents found in database.")
            return

        data = []
        for a in agents:
            data.append({
                'Name': a.get('name'),
                'Equity ($)': f"{a.get('equity', 0):.2f}",
                'Cash ($)': f"{a.get('cash', 0):.2f}",
                'ROI (%)': f"{a.get('roi', 0):.2f}%",
                'Holdings': str(a.get('portfolio', {}))
            })
            
        df = pd.DataFrame(data)
        print("\n=== AGENT STATISTICS (LIVE FROM DB) ===")
        print(df.to_string(index=False))
        print("=======================================\n")
        
    except Exception as e:
        print(f"Error connecting to DB: {e}")

if __name__ == "__main__":
    check_stats()
