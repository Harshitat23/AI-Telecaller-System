from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import os
import logging
import json
import traceback
import re
import time
import threading

# Set up logging with more details for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class CallHandler:
    def __init__(self):
        # Initialize Twilio client with error handling
        try:
            account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
            
            if not account_sid or not auth_token:
                logger.error("Missing Twilio credentials in environment variables")
                self.client = None
            else:
                self.client = Client(account_sid, auth_token)
                logger.info("Twilio client initialized successfully")
                
            self.twilio_phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
            if not self.twilio_phone_number:
                logger.warning("TWILIO_PHONE_NUMBER not set in environment variables")
        except Exception as e:
            logger.error(f"Error initializing Twilio client: {str(e)}")
            logger.error(traceback.format_exc())
            self.client = None
        
        # Initialize Azure Services with retry
        self.initialize_azure_services(max_retries=3)
        
        # Store active calls with their state and conversation history
        self.active_calls = {}
        
        # Add threading lock for thread safety when accessing shared data
        self.calls_lock = threading.Lock()
        
        # Set up periodic cleanup for stale calls
        self._start_cleanup_thread()
        
        logger.info("CallHandler initialization completed")

    def initialize_azure_services(self, max_retries=3):
        """Initialize Azure OpenAI and Speech services with retry mechanism"""
        retries = 0
        while retries < max_retries:
            try:
                # Import here to prevent errors if Azure modules aren't available
                from azure_services import AzureServices
                
                self.azure_services = AzureServices()
                self.use_azure = True
                logger.info("Azure services initialized successfully")
                return True
            except ImportError:
                logger.warning("Azure services module not found. Continuing without Azure.")
                self.use_azure = False
                self.azure_services = None
                return False
            except Exception as e:
                retries += 1
                logger.error(f"Failed to initialize Azure services (attempt {retries}/{max_retries}): {str(e)}")
                logger.error(traceback.format_exc())
                # Exponential backoff
                time.sleep(2 ** retries)
        
        # If we get here, all retries have failed
        self.use_azure = False
        self.azure_services = None
        logger.error("All attempts to initialize Azure services failed")
        return False

    def _start_cleanup_thread(self):
        """Start a background thread to clean up stale calls"""
        def cleanup_worker():
            while True:
                try:
                    # Run every 5 minutes
                    time.sleep(300)
                    self._cleanup_stale_calls()
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {str(e)}")
        
        # Start the thread as daemon so it doesn't block program exit
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("Started cleanup thread for stale calls")

    def _cleanup_stale_calls(self):
        """Remove calls that have been inactive for too long"""
        current_time = time.time()
        calls_to_remove = []
        
        with self.calls_lock:
            for call_sid, call_data in self.active_calls.items():
                # Check if the call has a last_activity timestamp
                if 'last_activity' in call_data:
                    # If the call has been inactive for more than 30 minutes, mark it for removal
                    if current_time - call_data['last_activity'] > 1800:  # 30 minutes
                        calls_to_remove.append(call_sid)
                else:
                    # Add a timestamp if it doesn't exist
                    self.active_calls[call_sid]['last_activity'] = current_time
            
            # Remove stale calls
            for call_sid in calls_to_remove:
                logger.info(f"Removing stale call {call_sid} due to inactivity")
                self.active_calls.pop(call_sid, None)
        
        logger.info(f"Cleanup completed. Removed {len(calls_to_remove)} stale calls.")

    def initiate_call(self, to_number):
        """Initiate a call to the provided phone number"""
        try:
            # Check if Twilio client is available
            if not self.client:
                logger.error("Cannot initiate call: Twilio client not initialized")
                return {
                    'success': False,
                    'error': 'Twilio client not initialized'
                }
                
            # Your server URL where Twilio will send webhook requests
            base_url = os.environ.get('SERVER_URL')
            if not base_url:
                logger.error("Cannot initiate call: SERVER_URL not set in environment variables")
                return {
                    'success': False,
                    'error': 'SERVER_URL not configured'
                }
                
            logger.info(f"Initiating call to {to_number} using base URL: {base_url}")
            
            # Make the call
            call = self.client.calls.create(
                to=to_number,
                from_=self.twilio_phone_number,
                url=f"{base_url}/webhook/voice",
                status_callback=f"{base_url}/webhook/status",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                record=True,  # Enable call recording for quality monitoring
                recording_status_callback=f"{base_url}/webhook/recording"
            )
            
            # Store call information with timestamp
            with self.calls_lock:
                self.active_calls[call.sid] = {
                    'to_number': to_number,
                    'status': 'initiated',
                    'conversation_state': 'greeting',
                    'conversation_history': [],
                    'last_activity': time.time()
                }
            
            logger.info(f"Call initiated successfully with SID: {call.sid}")
            return {
                'success': True,
                'message': 'Call initiated successfully',
                'call_sid': call.sid
            }
            
        except Exception as e:
            logger.error(f"Error initiating call: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }

    def handle_incoming_call(self, form_data):
        """Handle incoming call webhook from Twilio with improved speech recognition settings"""
        try:
            response = VoiceResponse()
            call_sid = form_data.get('CallSid')
            logger.info(f"Handling incoming call with SID: {call_sid}")
            
            # Initialize or get call state
            with self.calls_lock:
                if call_sid not in self.active_calls:
                    logger.info(f"New call detected, initializing state for call SID: {call_sid}")
                    self.active_calls[call_sid] = {
                        'status': 'in-progress',
                        'conversation_state': 'greeting',
                        'conversation_history': [],
                        'last_activity': time.time()
                    }
                else:
                    # Update the last activity timestamp
                    self.active_calls[call_sid]['last_activity'] = time.time()
                
                call_state = self.active_calls[call_sid].copy()  # Copy to avoid concurrent modification
            
            # Initial greeting
            greeting_message = (
                "Hello, I'm calling from Premier Real Estate Services. "
                "I'm an AI assistant here to answer your questions about "
                "buying, selling, mortgages, market trends, or any other real estate topics. "
                "How can I help you today?"
            )
            
            # Add greeting to conversation history if this is a new greeting
            if call_state['conversation_state'] == 'greeting' and not call_state['conversation_history']:
                with self.calls_lock:
                    self.active_calls[call_sid]['conversation_history'].append({
                        "role": "assistant", 
                        "content": greeting_message
                    })
                
                # Speak slowly and clearly for better comprehension
                response.say(
                    greeting_message, 
                    voice='alice',
                    rate="0.9"  # Slightly slower pace for clarity
                )
                logger.info("Delivered greeting message")
            
            # Set up gather for speech input with improved settings
            base_url = os.environ.get('SERVER_URL', 'http://localhost:5000')
            gather = Gather(
                input='speech',
                action=f"{base_url}/webhook/speech",
                timeout=7,  # Increased timeout for user to start speaking
                speechTimeout='auto',
                enhanced=True,
                language='en-US',
                speechModel='phone_call',
                profanityFilter=False,  # Allow natural speech including words AI might flag
            )
            
            # Add prompt based on conversation state
            if call_state['conversation_state'] == 'greeting':
                gather.say("Please go ahead with your question.", voice='alice', rate="0.9")
            else:
                gather.say("Do you have another real estate question I can help with?", voice='alice', rate="0.9")
            
            response.append(gather)
            
            # Add fallback in case no input is received
            response.say(
                "I didn't hear anything. Please speak clearly when you're ready.", 
                voice='alice',
                rate="0.9"
            )
            response.redirect(f"{base_url}/webhook/voice")
            
            logger.debug(f"TwiML response for incoming call: {str(response)}")
            return str(response)
            
        except Exception as e:
            logger.error(f"Error handling incoming call: {str(e)}")
            logger.error(traceback.format_exc())
            # Return a valid TwiML response even in case of error
            error_response = VoiceResponse()
            error_response.say(
                "I'm sorry, we're experiencing technical difficulties. Please try again later.", 
                voice='alice',
                rate="0.9"
            )
            error_response.hangup()
            return str(error_response)

    def handle_call_status(self, form_data):
        """Handle call status updates from Twilio"""
        try:
            call_sid = form_data.get('CallSid')
            call_status = form_data.get('CallStatus')
            logger.info(f"Call status update for SID {call_sid}: {call_status}")
            
            with self.calls_lock:
                if call_sid in self.active_calls:
                    self.active_calls[call_sid]['status'] = call_status
                    self.active_calls[call_sid]['last_activity'] = time.time()
                    
                    # Clean up completed calls
                    if call_status in ['completed', 'failed', 'busy', 'no-answer', 'canceled']:
                        # Log the conversation history before removing it
                        if 'conversation_history' in self.active_calls[call_sid]:
                            try:
                                # Store the conversation history for analytics
                                self._store_conversation_history(call_sid, self.active_calls[call_sid])
                                logger.info(f"Call {call_sid} completed. Conversation history stored.")
                            except Exception as e:
                                logger.error(f"Error storing conversation history: {str(e)}")
                                
                        self.active_calls.pop(call_sid, None)
                    
            return {'success': True}
        except Exception as e:
            logger.error(f"Error handling call status: {str(e)}")
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    def _store_conversation_history(self, call_sid, call_data):
        """Store conversation history for analytics and training"""
        try:
            # In a production system, you would store this in a database
            # For now, we'll just log it
            history_file = f"conversation_history_{call_sid}.json"
            with open(history_file, 'w') as f:
                json.dump(call_data, f, indent=2)
            logger.info(f"Saved conversation history to {history_file}")
            
            # In a real implementation, you would use a database like:
            # - MongoDB for flexible document storage
            # - PostgreSQL with JSONB for structured and queryable storage
            # - Cloud-based solutions like Azure CosmosDB or AWS DynamoDB
            
        except Exception as e:
            logger.error(f"Failed to store conversation history: {str(e)}")
            raise

    def is_end_of_call(self, speech_text):
        """Check if user wants to end the call with improved pattern matching"""
        # Normalized input for better matching
        normalized_text = speech_text.lower().strip()
        
        # Keywords and phrases that indicate the user wants to end the call
        end_call_phrases = [
            'no', 'nope', 'no questions', 'no more questions', 'no other questions',
            'no other question', "don't have any questions", "don't have any other questions",
            "i don't have any questions", 'nothing else', 'that is all', "that's all",
            'goodbye', 'bye', 'thank you goodbye', 'thanks goodbye', 'end call',
            'hang up', 'that will be all', 'i am done', "i'm done", 'no thanks',
            'gotta go', 'have to go', 'we re done', 'thats it', 'end this call',
            'that concludes', 'thanks for your help', 'i am finished', 'i am good',
            'that is enough', 'all set', 'i will let you go', 'good day', 'have a good day'
        ]
        
        # Check if the normalized text matches or contains any end call phrases
        for phrase in end_call_phrases:
            if phrase == normalized_text or phrase in normalized_text:
                return True
            
        # Check for sentences that indicate no further questions
        no_question_patterns = [
            r"no,?\s+(i|I)?\s*(don'?t|do not)?\s*have\s*(any|more|other)?\s*questions",
            r"(i|I)?\s*(don'?t|do not)\s*have\s*(any|more|other)?\s*questions",
            r"that'?s\s+(all|it)",
            r"nothing\s+(else|more)",
            r"(i|I)'?m\s+(good|done|finished|all\s+set)",
            r"(no|nope),?\s+(thank|thanks)\s+(you|ya)"
        ]
        
        for pattern in no_question_patterns:
            if re.search(pattern, normalized_text):
                return True
                
        return False

    def handle_speech_input(self, form_data):
        """Process speech input from the call with improved handling"""
        try:
            response = VoiceResponse()
            call_sid = form_data.get('CallSid')
            speech_result = form_data.get('SpeechResult')
            confidence = form_data.get('Confidence', 0)
            
            # Log incoming speech data
            logger.debug(f"Speech result: '{speech_result}', Confidence: {confidence}")
            logger.debug(f"All form data: {form_data}")
            
            # Make sure we have an active call record
            with self.calls_lock:
                if call_sid not in self.active_calls:
                    logger.warning(f"Received speech for unknown call SID: {call_sid} - initializing new call record")
                    self.active_calls[call_sid] = {
                        'status': 'in-progress',
                        'conversation_state': 'in-progress',
                        'conversation_history': [],
                        'last_activity': time.time()
                    }
                else:
                    # Update activity timestamp
                    self.active_calls[call_sid]['last_activity'] = time.time()
                
                # Get a copy to avoid concurrent modification issues
                call_state = self.active_calls[call_sid].copy()
            
            # Handle low confidence or empty speech
            if not speech_result or float(confidence or 0) < 0.3:
                logger.warning(f"Low confidence speech detected: {confidence}")
                response.say(
                    "I'm sorry, I didn't catch that clearly. Could you please speak a bit louder and more clearly?", 
                    voice='alice',
                    rate="0.9"
                )
                
                # Set up a new gather for retry
                base_url = os.environ.get('SERVER_URL', 'http://localhost:5000')
                gather = Gather(
                    input='speech',
                    action=f"{base_url}/webhook/speech",
                    timeout=7,
                    speechTimeout='auto',
                    enhanced=True,
                    language='en-US',
                    speechModel='phone_call',
                    profanityFilter=False
                )
                gather.say("Please ask your real estate question clearly.", voice='alice', rate="0.9")
                response.append(gather)
                
                # Add fallback if no input received
                response.say("I still didn't hear anything. Let me ask again.", voice='alice', rate="0.9")
                response.redirect(f"{base_url}/webhook/voice")
                
                return str(response)
            
            logger.info(f"Recognized speech: {speech_result}")
            
            # Check if user wants to end the call
            if self.is_end_of_call(speech_result):
                logger.info("User indicated end of call")
                end_message = "Thank you for calling Premier Real Estate Services. If you have more questions in the future, feel free to call us again. Have a great day!"
                response.say(end_message, voice='alice', rate="0.9")
                response.hangup()
                
                # Add the final user and system messages to conversation history
                with self.calls_lock:
                    self.active_calls[call_sid]['conversation_history'].append({
                        "role": "user",
                        "content": speech_result
                    })
                    self.active_calls[call_sid]['conversation_history'].append({
                        "role": "assistant",
                        "content": end_message
                    })
                
                return str(response)
            
            # Add user query to conversation history
            with self.calls_lock:
                self.active_calls[call_sid]['conversation_history'].append({
                    "role": "user",
                    "content": speech_result
                })
            
            # Try to address the query with multiple fallback mechanisms
            ai_response = self._process_user_query(speech_result, call_state.get('conversation_history', []))
            
            logger.info(f"Final AI Response: {ai_response}")
            
            # Add assistant response to conversation history
            with self.calls_lock:
                self.active_calls[call_sid]['conversation_history'].append({
                    "role": "assistant",
                    "content": ai_response
                })
                
            # Check if response is valid before adding to TwiML
            if not ai_response or not isinstance(ai_response, str) or len(ai_response.strip()) == 0:
                ai_response = "I understand you have a question about real estate. I'd be happy to help with information about buying, selling, or investing in properties."
            
            # Respond to the user with the answer - limit to 1000 chars to avoid TwiML issues
            if len(ai_response) > 1000:
                ai_response = ai_response[:997] + "..."
                
            # Break long responses into smaller chunks for better comprehension
            response_chunks = self._chunk_response(ai_response)
            for chunk in response_chunks:
                response.say(chunk, voice='alice', rate="0.9")
            
            # Ask if they have another question with a new Gather
            base_url = os.environ.get('SERVER_URL', 'http://localhost:5000')
            gather = Gather(
                input='speech',
                action=f"{base_url}/webhook/speech",
                timeout=7,
                speechTimeout='auto',
                enhanced=True,
                language='en-US',
                speechModel='phone_call',
                profanityFilter=False
            )
            gather.say("Do you have another real estate question I can help with?", voice='alice', rate="0.9")
            response.append(gather)
            
            # Add a fallback if no response is received
            response.say("I didn't hear anything. Let me ask one more time.", voice='alice', rate="0.9")
            response.redirect(f"{base_url}/webhook/voice")
            
            # Update call state
            with self.calls_lock:
                self.active_calls[call_sid]['conversation_state'] = 'in-progress'
            
            logger.debug(f"TwiML response for speech input: {str(response)}")
            return str(response)
            
        except Exception as e:
            logger.error(f"Error handling speech input: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Return a valid TwiML response even in case of error
            error_response = VoiceResponse()
            error_response.say(
                "I'm sorry, we're experiencing technical difficulties. Please try again.", 
                voice='alice',
                rate="0.9"
            )
            
            # Set up a new gather for retry
            base_url = os.environ.get('SERVER_URL', 'http://localhost:5000')
            gather = Gather(
                input='speech',
                action=f"{base_url}/webhook/speech",
                timeout=7,
                speechTimeout='auto'
            )
            gather.say("Please ask your question again.", voice='alice', rate="0.9")
            error_response.append(gather)
            
            return str(error_response)

    def _chunk_response(self, response_text, max_chunk_length=150):
        """Break long responses into smaller chunks at natural break points"""
        if len(response_text) <= max_chunk_length:
            return [response_text]
            
        # Find natural break points (sentences)
        chunks = []
        current_chunk = ""
        
        # Split by sentences
        sentences = re.split(r'(?<=[.!?])\s+', response_text)
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_chunk_length:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
                
        # Add the last chunk if there's anything left
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

    def _process_user_query(self, query, conversation_history):
        """Process user query with multiple fallback mechanisms"""
        # First try local knowledge base
        try:
            from real_estate_knowledge_base import get_response
            kb_response, found_in_kb = get_response(query)
            
            if found_in_kb and kb_response:
                logger.info("Response found in knowledge base")
                # Enhance the KB response with context awareness if needed
                enhanced_response = self._enhance_kb_response(kb_response, query, conversation_history)
                return enhanced_response
        except ImportError:
            logger.warning("Could not import real_estate_knowledge_base module")
            found_in_kb = False
        except Exception as e:
            logger.error(f"Error using knowledge base: {str(e)}")
            found_in_kb = False
            
        # If not found in knowledge base, try Azure OpenAI
        try:
            if hasattr(self, 'use_azure') and self.use_azure and self.azure_services is not None:
                azure_response = self.azure_services.process_real_estate_query(query, conversation_history)
                
                if azure_response and isinstance(azure_response, str) and len(azure_response.strip()) > 0:
                    logger.info("Successfully got response from Azure OpenAI")
                    return azure_response
        except Exception as e:
            logger.error(f"Error using Azure OpenAI: {str(e)}")
            
        # Final fallback - use comprehensive real estate response
        logger.info("All AI methods failed, using comprehensive fallback")
        return self._generate_comprehensive_fallback(query)
        
    def _enhance_kb_response(self, kb_response, query, conversation_history):
        """Enhance knowledge base response with context awareness"""
        # This method could be expanded to use the conversation history
        # to make the knowledge base responses more contextual
        
        # For now, we'll make simple enhancements
        
        # Add personalization if appropriate
        if len(conversation_history) >= 2:
            # Get the first user message to check if they've mentioned their name
            for message in conversation_history:
                if message.get("role") == "user":
                    user_message = message.get("content", "").lower()
                    name_match = re.search(r"my name is (\w+)", user_message)
                    if name_match:
                        name = name_match.group(1).capitalize()
                        # Add personalization to the response
                        kb_response = f"{name}, {kb_response}"
                        break
        
        return kb_response
        
    def _generate_comprehensive_fallback(self, query):
        """Generate a comprehensive fallback response based on the query"""
        # Extract key topics from the query
        query_lower = query.lower()
        
        # Check for common real estate topics
        if any(word in query_lower for word in ["buy", "buying", "purchase", "purchasing"]):
            return "When buying a property, it's important to consider your budget, desired location, and long-term goals. I recommend getting pre-approved for a mortgage first to understand your budget. Our agents can help guide you through the entire process from property search to closing the deal. Would you like more specific information about any part of the home buying process?"
            
        elif any(word in query_lower for word in ["sell", "selling", "market", "list"]):
            return "Selling a property involves preparing your home, determining the right price, marketing effectively, and negotiating offers. Our team can provide a comprehensive market analysis to determine the optimal listing price for your property. We also offer professional photography and marketing services to showcase your home at its best. Is there a specific aspect of selling you'd like to know more about?"
            
        elif any(word in query_lower for word in ["mortgage", "loan", "finance", "interest", "down payment"]):
            return "Real estate financing options include conventional mortgages, FHA loans, VA loans, and various first-time homebuyer programs. Current interest rates vary based on your credit score, loan amount, and down payment. I recommend speaking with a mortgage specialist to explore options tailored to your financial situation. Would you like me to explain any specific mortgage program in more detail?"
            
        elif any(word in query_lower for word in ["invest", "investment", "rental", "income", "property management"]):
            return "Real estate investing can provide both income and appreciation. Common strategies include buying rental properties, fix-and-flip projects, or REITs for passive investment. The best approach depends on your financial goals, risk tolerance, and how hands-on you want to be. Our team works with many investors and can help you identify opportunities that match your investment criteria. What type of real estate investment are you considering?"
            
        elif any(word in query_lower for word in ["market", "trend", "price", "value", "appreciation"]):
            return "Real estate markets are highly localized, with conditions varying by neighborhood. Generally, we're seeing moderate price growth with inventory levels improving in most areas. Interest rates remain a key factor affecting buyer demand. Our agents can provide you with detailed market analysis for specific areas you're interested in. Which location are you curious about?"
            
        else:
            # General fallback for any real estate query
            return "I understand you have a question about real estate. At Premier Real Estate Services, we specialize in helping clients buy, sell, and invest in properties. Our experienced agents can provide guidance on property values, market trends, mortgage options, and investment strategies. Could you please provide more details about your specific real estate needs so I can give you more targeted information?"

    def get_call_history(self, call_sid):
        """Get conversation history for a specific call"""
        with self.calls_lock:
            if call_sid in self.active_calls and 'conversation_history' in self.active_calls[call_sid]:
                return self.active_calls[call_sid]['conversation_history']
        return []