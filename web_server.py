#!/usr/bin/env python3
"""
Simple web server for hosting the hockey stats dashboard and serving scraped data files.
Runs 24/7 on Render to provide access to dashboard and latest data.
"""

import os
from flask import Flask, send_from_directory, jsonify, send_file
from flask_cors import CORS
import json
from datetime import datetime
import glob

app = Flask(__name__)
CORS(app)

# Data directory (mounted from Render persistent disk)
DATA_DIR = os.environ.get('DATA_DIR', '/data')
DASHBOARD_FILE = 'enhanced_dashboard.html'

@app.route('/')
def serve_dashboard():
    """Serve the main dashboard"""
    return send_from_directory('.', DASHBOARD_FILE)

@app.route('/api/latest-data')
def get_latest_data():
    """Get the most recent scraped data as JSON"""
    try:
        # Find most recent data file
        data_files = glob.glob(os.path.join(DATA_DIR, 'scraped_data_*.json'))
        if not data_files:
            return jsonify({'error': 'No data available yet'}), 404
        
        latest_file = max(data_files, key=os.path.getctime)
        
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data-info')
def get_data_info():
    """Get information about available data files"""
    try:
        data_files = glob.glob(os.path.join(DATA_DIR, 'scraped_data_*.json'))
        excel_files = glob.glob(os.path.join(DATA_DIR, '*.xlsx'))
        
        files_info = []
        
        for file in sorted(data_files + excel_files, key=os.path.getctime, reverse=True):
            stat = os.stat(file)
            files_info.append({
                'filename': os.path.basename(file),
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'type': 'excel' if file.endswith('.xlsx') else 'json'
            })
        
        return jsonify({
            'files': files_info,
            'total_files': len(files_info)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    """Download a specific data file"""
    try:
        file_path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/latest-excel')
def download_latest_excel():
    """Download the most recent Excel file"""
    try:
        excel_files = glob.glob(os.path.join(DATA_DIR, '*.xlsx'))
        if not excel_files:
            return jsonify({'error': 'No Excel files available yet'}), 404
        
        latest_file = max(excel_files, key=os.path.getctime)
        return send_file(latest_file, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    print(f"\n{'='*70}")
    print(f"🏒 Hockey Stats Dashboard Server")
    print(f"{'='*70}")
    print(f"\n✅ Server starting on port {port}")
    print(f"✅ Data directory: {DATA_DIR}")
    print(f"✅ Dashboard: /")
    print(f"✅ Latest data API: /api/latest-data")
    print(f"✅ Data info API: /api/data-info")
    print(f"✅ Download Excel: /api/latest-excel")
    print(f"\n{'='*70}\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)
