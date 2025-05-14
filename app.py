from flask import Flask, request
from dotenv import load_dotenv
import os
from call_handler_org import CallHandler

# Load environment variables
load_dotenv()

app = Flask(__name__)
call_handler = CallHandler()

@app.route('/call', methods=['POST'])
def initiate_call():
    """Endpoint to initiate a call to a target number"""
    data = request.get_json()
    # Fixed this line - it was using incorrect syntax for accessing the JSON data
    to_number = data.get('to_number')
    if not to_number:
        return {'error': 'Please provide a target phone number'}, 400
        
    result = call_handler.initiate_call(to_number)
    return result

@app.route('/webhook/voice', methods=['POST'])
def handle_incoming_call():
    """Webhook for handling incoming Twilio call"""
    return call_handler.handle_incoming_call(request.form)

@app.route('/webhook/status', methods=['POST'])
def handle_call_status():
    """Webhook for handling call status updates"""
    return call_handler.handle_call_status(request.form)

@app.route('/webhook/speech', methods=['POST'])
def handle_speech_input():
    """Webhook for handling speech input during the call"""
    return call_handler.handle_speech_input(request.form)

@app.route('/', methods=['GET'])
def index():
    """Root endpoint to confirm the server is running"""
    return {
        'status': 'online',
        'message': 'Real Estate Telecaller System is running',
        'endpoints': {
            'initiate_call': '/call',
            'twilio_webhooks': ['/webhook/voice', '/webhook/status', '/webhook/speech']
        }
    }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
    print(f"Server running on port {port}")
    print("Real Estate Telecaller System is ready to make calls")