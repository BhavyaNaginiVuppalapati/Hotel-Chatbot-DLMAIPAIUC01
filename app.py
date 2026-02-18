from flask import Flask, render_template, request, jsonify, session
import requests
import json
import random
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this to a secure random key

# Rasa server URL
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"

@app.route('/')
def index():
    # Always create a fresh session ID for new page loads
    session['user_id'] = f"user_{uuid.uuid4().hex[:8]}"
    print(f"DEBUG WEB: New page load, created user ID: {session['user_id']}")
    
    # Clear any existing Rasa conversation for this new session
    clear_rasa_conversation(session['user_id'])
    
    return render_template('index.html')

def clear_rasa_conversation(user_id):
    """Clear Rasa conversation state for a user"""
    try:
        # Send a restart event to Rasa to clear conversation state
        rasa_payload = {
            "sender": user_id,
            "message": "/restart"
        }
        
        response = requests.post(RASA_URL, json=rasa_payload, timeout=5)
        print(f"DEBUG WEB: Cleared Rasa state for {user_id}, status: {response.status_code}")
        
    except Exception as e:
        print(f"DEBUG WEB: Failed to clear Rasa state: {e}")

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message', '')
        
        # Use consistent user ID from session
        if 'user_id' not in session:
            session['user_id'] = f"user_{uuid.uuid4().hex[:8]}"
        
        user_id = session['user_id']
        
        print(f"DEBUG WEB: User {user_id} sent: '{user_message}'")
        
        # Send message to Rasa
        rasa_payload = {
            "sender": user_id,
            "message": user_message
        }
        
        response = requests.post(RASA_URL, json=rasa_payload, timeout=10)
        
        if response.status_code == 200:
            rasa_responses = response.json()
            print(f"DEBUG WEB: Rasa responded with: {rasa_responses}")
            
            if rasa_responses:
                # Check ALL messages for booking confirmation, not just the first one
                all_messages = []
                booking_message = None
                
                for msg in rasa_responses:
                    message_text = msg.get('text', '')
                    all_messages.append(message_text)
                    
                    # Check if this message contains booking confirmation
                    if (('Booking Confirmed' in message_text or 
                         'booking confirmed' in message_text.lower() or 
                         '🎉' in message_text) and 'Booking ID:' in message_text) or \
                       ('Booking ID:' in message_text and 'Guest:' in message_text):
                        booking_message = message_text
                        break
                
                # Combine all messages for display
                combined_message = '\n'.join(all_messages)
                
                # Check if any message contains room options
                has_room_options = any('Standard Room' in msg or 'Deluxe Room' in msg for msg in all_messages)
                
                if booking_message:
                    print("DEBUG WEB: Detected booking confirmation!")
                    # Parse the booking details from the booking message
                    booking_data = parse_booking_details(booking_message)
                    print(f"DEBUG WEB: Parsed booking data: {booking_data}")
                    
                    return jsonify({
                        'response': combined_message,  # Send all messages combined
                        'sender': 'bot',
                        'type': 'booking_confirmation',
                        'booking_data': booking_data
                    })
                elif has_room_options:
                    print("DEBUG WEB: Detected room options message!")
                    return jsonify({
                        'response': combined_message,  # Send all room messages combined
                        'sender': 'bot',
                        'type': 'room_options'
                    })
                else:
                    # Get the first message for regular responses
                    bot_message = rasa_responses[0].get('text', 'Sorry, I did not understand.')
                    print(f"DEBUG WEB: Bot message: '{bot_message[:100]}...'")
                    print(f"DEBUG WEB: Regular message - Total messages: {len(rasa_responses)}")
                    
                    return jsonify({
                        'response': bot_message,
                        'sender': 'bot',
                        'type': 'text'
                    })
            else:
                bot_message = 'Sorry, I did not understand.'
        else:
            print(f"DEBUG WEB: Rasa error - Status: {response.status_code}")
            bot_message = 'Sorry, there was an issue connecting to the chatbot.'
        
        return jsonify({
            'response': bot_message,
            'sender': 'bot',
            'type': 'text'
        })
        
    except Exception as e:
        print(f"DEBUG WEB: Exception: {e}")
        return jsonify({
            'response': 'Sorry, there was an error processing your request.',
            'sender': 'bot',
            'type': 'text'
        })

@app.route('/reset', methods=['POST'])
def reset_conversation():
    """Reset the conversation for debugging"""
    try:
        old_user_id = session.get('user_id', 'unknown')
        session['user_id'] = f"user_{uuid.uuid4().hex[:8]}"
        
        # Clear Rasa conversation state
        clear_rasa_conversation(session['user_id'])
        
        print(f"DEBUG WEB: Reset conversation from {old_user_id} to {session['user_id']}")
        
        return jsonify({
            'status': 'success',
            'message': 'Conversation reset'
        })
    except Exception as e:
        print(f"DEBUG WEB: Reset error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to reset conversation'
        })

def parse_booking_details(message):
    """Extract booking details from the message"""
    try:
        lines = message.split('\n')
        booking_data = {}
        
        for line in lines:
            line = line.strip()
            if 'Booking ID:' in line:
                booking_data['booking_id'] = line.split('Booking ID:')[1].strip()
            elif 'Guest:' in line:
                booking_data['guest_name'] = line.split('Guest:')[1].strip()
            elif 'Room:' in line:  # Add room type parsing
                booking_data['room_type'] = line.split('Room:')[1].strip()
            elif 'Check-in:' in line:
                booking_data['checkin_date'] = line.split('Check-in:')[1].strip()
            elif 'Check-out:' in line:
                booking_data['checkout_date'] = line.split('Check-out:')[1].strip()
            elif 'Nights:' in line:
                booking_data['nights'] = line.split('Nights:')[1].strip()
            elif 'Guests:' in line:
                booking_data['guests'] = line.split('Guests:')[1].strip()
        
        print(f"DEBUG WEB: Raw message parsing result: {booking_data}")
        return booking_data
    except Exception as e:
        print(f"DEBUG WEB: Parsing error: {e}")
        return {}

if __name__ == '__main__':
    app.run(debug=True, port=3000)