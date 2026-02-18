from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from datetime import datetime, date
import random
import re

class ActionCollectBookingInfo(Action):
    def name(self) -> Text:
        return "action_collect_booking_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get current slot values
        name = tracker.get_slot("guest_name")
        checkin = tracker.get_slot("checkin_date")
        checkout = tracker.get_slot("checkout_date")
        guests = tracker.get_slot("number_of_guests")
        room_type = tracker.get_slot("room_type")  # Add room type slot
        
        user_input = tracker.latest_message.get('text', '').strip()
        
        # Debug prints
        print(f"DEBUG: User input: '{user_input}'")
        print(f"DEBUG: Name slot: '{name}'")
        print(f"DEBUG: Checkin slot: '{checkin}'")
        print(f"DEBUG: Checkout slot: '{checkout}'")
        print(f"DEBUG: Guests slot: '{guests}'")
        print(f"DEBUG: Room type slot: '{room_type}'")  # Add debug for room type
        
        # Step 1: Get name
        if not name:
            print("DEBUG: Asking for name")
            # More flexible name detection
            cleaned_input = user_input.lower().strip()
            
            # Skip greetings and common non-name words
            skip_words = ['hello', 'hi', 'hey', 'start', 'book', 'room', 'thanks', 'thank', 'you', 'bye', 'goodbye']
            
            if (len(user_input) > 1 and 
                cleaned_input not in skip_words and 
                not user_input.isdigit() and
                not re.search(r'\d{1,2}[/-]\d{1,2}', user_input)):  # Not a date
                
                print(f"DEBUG: Setting name to '{user_input}'")
                dispatcher.utter_message(text=f"Hi {user_input}! When would you like to check in? (e.g., '20/9/2025', 'September 20')")
                return [SlotSet("guest_name", user_input)]
            else:
                dispatcher.utter_message(text="What's your name for the booking?")
                return []
        
        # Step 2: Get check-in date
        if not checkin:
            print("DEBUG: Processing checkin date")
            parsed_date = self._parse_date(user_input)
            if not parsed_date:
                dispatcher.utter_message(text="I couldn't understand that date. Please try '20/9/2025', 'September 20', or 'sep 20'.")
                return []
            
            cutoff = date.today();
            if parsed_date <= cutoff:
                dispatcher.utter_message(text=f"Please enter a check-in date after {cutoff.strftime('%B %d, %Y')}.")
                return []
            
            print(f"DEBUG: Setting checkin to '{parsed_date.strftime('%Y-%m-%d')}'")
            dispatcher.utter_message(text=f"Check-in: {parsed_date.strftime('%B %d, %Y')}. When would you like to check out?")
            return [SlotSet("checkin_date", parsed_date.strftime("%Y-%m-%d"))]
        
        # Step 3: Get check-out date
        if not checkout:
            print("DEBUG: Processing checkout date")
            parsed_date = self._parse_date(user_input)
            if not parsed_date:
                dispatcher.utter_message(text="I couldn't understand that date. Please try '23/9/2025', 'September 23', or 'sep 23'.")
                return []
            
            try:
                checkin_obj = datetime.strptime(checkin, "%Y-%m-%d").date()
                if parsed_date <= checkin_obj:
                    dispatcher.utter_message(text=f"Check-out must be after check-in ({checkin_obj.strftime('%B %d, %Y')}). Please try again.")
                    return []
            except Exception as e:
                print(f"DEBUG: Error parsing checkin date: {e}")
                dispatcher.utter_message(text="Error with dates. Let's start over. What's your name?")
                return [SlotSet("guest_name", None), SlotSet("checkin_date", None)]
            
            nights = (parsed_date - checkin_obj).days
            print(f"DEBUG: Setting checkout to '{parsed_date.strftime('%Y-%m-%d')}'")
            dispatcher.utter_message(text=f"Check-out: {parsed_date.strftime('%B %d, %Y')} ({nights} nights). How many guests?")
            return [SlotSet("checkout_date", parsed_date.strftime("%Y-%m-%d"))]
        
        # Step 4: Get number of guests
        if not guests:
            print("DEBUG: Processing guest count")
            # Try to extract number from input
            numbers = re.findall(r'\d+', user_input)
            if numbers:
                guest_count = numbers[0]
                print(f"DEBUG: Setting guests to '{guest_count}'")
                
                # Send room options as ONE complete message
                complete_message = f"""Perfect! Booking for {guest_count} guest(s). Which room would you like?

1. Standard Room - $100/night
   WiFi, TV, AC

2. Deluxe Room - $150/night
   WiFi, TV, AC, Mini-bar

3. Family Room - $180/night
   WiFi, TV, AC, Extra bed

4. Suite - $250/night
   WiFi, TV, AC, Living area, Balcony

Please choose: Standard, Deluxe, Family, or Suite."""
                
                dispatcher.utter_message(text=complete_message)
                return [SlotSet("number_of_guests", guest_count)]
            else:
                dispatcher.utter_message(text="How many guests will be staying? Please enter a number.")
                return []
        
        # Step 5: Get room type selection
        if not room_type:
            print("DEBUG: Processing room type selection")
            selected_room = self._parse_room_selection(user_input)
            if selected_room:
                print(f"DEBUG: Setting room type to '{selected_room}'")
                dispatcher.utter_message(text=f"Excellent choice! You've selected the {selected_room}.")
                self._show_booking_summary(dispatcher, name, checkin, checkout, guests, selected_room)
                return [SlotSet("room_type", selected_room)]
            else:
                dispatcher.utter_message(text="Please select a room type: Standard, Deluxe, Family, or Suite.")
                return []
        
        # If we get here, all info is collected - this shouldn't happen
        print("DEBUG: All slots filled, showing summary")
        self._show_booking_summary(dispatcher, name, checkin, checkout, guests, room_type)
        return []
    
    def _parse_date(self, text: str):
        """Parse date from text"""
        try:
            text = text.lower().strip()
            print(f"DEBUG: Trying to parse date: '{text}'")
            
            # DD/MM/YYYY or DD-MM-YYYY
            match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
            if match:
                result = datetime.strptime(f"{match[1]}/{match[2]}/{match[3]}", "%d/%m/%Y").date()
                print(f"DEBUG: Parsed as DD/MM/YYYY: {result}")
                return result
            
            # DD/MM or DD-MM (assume 2025)
            match = re.search(r'(\d{1,2})[/-](\d{1,2})\b', text)
            if match:
                result = datetime.strptime(f"{match[1]}/{match[2]}/2025", "%d/%m/%Y").date()
                print(f"DEBUG: Parsed as DD/MM: {result}")
                return result
            
            # Month names
            months = {
                'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
                'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
                'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
                'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
            }
            
            for month_name, month_num in months.items():
                # Month Day
                pattern = rf'{month_name}\s+(\d{{1,2}})'
                match = re.search(pattern, text)
                if match:
                    result = date(2025, month_num, int(match[1]))
                    print(f"DEBUG: Parsed as month day: {result}")
                    return result
                
                # Day Month  
                pattern = rf'(\d{{1,2}})\s+{month_name}'
                match = re.search(pattern, text)
                if match:
                    result = date(2025, month_num, int(match[1]))
                    print(f"DEBUG: Parsed as day month: {result}")
                    return result
            
            print("DEBUG: Could not parse date")
            return None
            
        except Exception as e:
            print(f"DEBUG: Date parsing exception: {e}")
            return None
    
    def _show_room_options(self, dispatcher):
        """Display available room options with prices"""
        room_message = """Here are our available rooms:

1. **Standard Room** - $100/night
   WiFi, TV, AC

2. **Deluxe Room** - $150/night  
   WiFi, TV, AC, Mini-bar

3. **Family Room** - $180/night
   WiFi, TV, AC, Extra bed

4. **Suite** - $250/night
   WiFi, TV, AC, Living area, Balcony

Which room would you like to book? Please choose: Standard, Deluxe, Family, or Suite."""
        
        # Send as ONE message instead of multiple
        dispatcher.utter_message(text=room_message)
    
    def _parse_room_selection(self, user_input):
        """Parse room type from user input"""
        user_input_lower = user_input.lower().strip()
        
        # Map various ways users might say room types
        room_mappings = {
            'standard': 'Standard Room',
            'standard room': 'Standard Room', 
            '1': 'Standard Room',
            'basic': 'Standard Room',
            
            'deluxe': 'Deluxe Room',
            'deluxe room': 'Deluxe Room',
            '2': 'Deluxe Room',
            'luxury': 'Deluxe Room',
            
            'family': 'Family Room',
            'family room': 'Family Room',
            '3': 'Family Room',
            'large': 'Family Room',
            
            'suite': 'Suite',
            'presidential': 'Suite',
            '4': 'Suite',
            'premium': 'Suite'
        }
        
        for key, room_type in room_mappings.items():
            if key in user_input_lower:
                print(f"DEBUG: Matched '{user_input}' to '{room_type}'")
                return room_type
        
        print(f"DEBUG: Could not match '{user_input}' to any room type")
        return None
    
    def _show_booking_summary(self, dispatcher, name, checkin_str, checkout_str, guests, room_type):
        """Show final booking summary with room type"""
        try:
            print(f"DEBUG: Showing summary - name:{name}, checkin:{checkin_str}, checkout:{checkout_str}, guests:{guests}, room:{room_type}")
            checkin_obj = datetime.strptime(checkin_str, "%Y-%m-%d").date()
            checkout_obj = datetime.strptime(checkout_str, "%Y-%m-%d").date()
            nights = (checkout_obj - checkin_obj).days
            booking_id = f"GH{random.randint(1000, 9999)}"
            
            # Send the exact format that the Flask app expects
            summary = f"""🎉 Booking Confirmed! 🎉

Booking ID: {booking_id}
Guest: {name}
Room: {room_type}
Check-in: {checkin_obj.strftime('%B %d, %Y')}
Check-out: {checkout_obj.strftime('%B %d, %Y')}
Nights: {nights}
Guests: {guests}

Thank you for choosing Grand Hotel!"""
            
            print(f"DEBUG: Sending booking summary: {summary}")
            dispatcher.utter_message(text=summary)
            
        except Exception as e:
            print(f"DEBUG: Summary exception: {e}")
            dispatcher.utter_message(text="There was an error processing your booking. Let's start over. What's your name?")