import os
import logging
import json
import time
import traceback
from typing import List, Dict, Any, Tuple, Optional
import re
import asyncio
import threading
import azure.cognitiveservices.speech as speechsdk
from tenacity import retry, stop_after_attempt, wait_exponential

# Set up logging with more detailed configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ai_telecaller.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AzureServices:
    """
    Enhanced integration with Azure OpenAI for real estate AI assistant.
    Provides improved speech recognition handling and comprehensive real estate knowledge.
    """
    
    def __init__(self):
        """Initialize Azure OpenAI integration with proper error handling and expanded capabilities"""
        try:
            # Import Azure OpenAI SDK
            import openai
            from azure.identity import DefaultAzureCredential
            
            # Get Azure OpenAI settings from environment variables
            self.api_key = os.environ.get('AZURE_OPENAI_API_KEY')
            self.endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
            self.deployment_name = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')
            
            # Speech configuration
            self.speech_key = os.environ.get('AZURE_SPEECH_KEY')
            self.speech_region = os.environ.get('AZURE_SPEECH_REGION', 'eastus')
            
            # Set up OpenAI client for Azure
            if self.api_key and self.endpoint:
                openai.api_type = "azure"
                openai.api_base = self.endpoint
                openai.api_version = "2023-07-01-preview"  # Updated API version
                openai.api_key = self.api_key
                self.client = openai
                logger.info("Azure OpenAI client initialized successfully with API key")
            elif self.endpoint:
                # Use Azure managed identity if available but no API key
                self.credential = DefaultAzureCredential()
                openai.api_type = "azure"
                openai.api_base = self.endpoint
                openai.api_version = "2023-07-01-preview"  # Updated API version
                token = self.credential.get_token("https://cognitiveservices.azure.com/.default")
                openai.api_key = token.token
                self.client = openai
                logger.info("Azure OpenAI client initialized with managed identity")
            else:
                logger.error("Missing Azure OpenAI credentials")
                self.client = None
            
            # Initialize enhanced speech services
            self._init_speech_services()
                
            # Initialize conversation context management
            self._init_conversation_context()
            
            # Initialize advanced speech processing for better recognition
            self._init_advanced_speech_processing()
            
            logger.info("Azure services initialization completed")
        except ImportError as e:
            logger.error(f"Required Azure packages not found: {str(e)}")
            logger.error("Install required packages with: pip install openai azure-identity azure-cognitiveservices-speech tenacity")
            self.client = None
        except Exception as e:
            logger.error(f"Error initializing Azure services: {str(e)}")
            logger.error(traceback.format_exc())
            self.client = None
    
    def _init_speech_services(self):
        """Initialize enhanced speech services with custom acoustic model"""
        try:
            if self.speech_key:
                # Create speech config with custom acoustic model for real estate terminology
                self.speech_config = speechsdk.SpeechConfig(
                    subscription=self.speech_key, 
                    region=self.speech_region
                )
                
                # Enhanced speech configuration
                self.speech_config.speech_recognition_language = "en-US"
                self.speech_config.enable_dictation()  # Enable dictation mode for better recognition
                self.speech_config.request_word_level_timestamps()  # Get word timing for better analysis
                self.speech_config.set_property(
                    speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "500"
                )  # Reduced silence timeout for more responsive experience
                
                # Set up custom pronunciation for real estate terms (if available)
                # self.speech_config.endpoint_id = "YOUR_CUSTOM_PRONUNCIATION_ENDPOINT"
                
                # Create speech recognizer
                self.speech_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=self.speech_config
                )
                
                # Configure continuous recognition settings for better performance
                self.speech_recognizer.recognized.connect(self._process_recognized_speech)
                
                logger.info("Speech services initialized successfully")
            else:
                logger.warning("Speech services not initialized - missing speech key")
                self.speech_config = None
                self.speech_recognizer = None
        except Exception as e:
            logger.error(f"Error initializing speech services: {str(e)}")
            logger.error(traceback.format_exc())
            self.speech_config = None
            self.speech_recognizer = None
    
    def _init_conversation_context(self):
        """Initialize conversation context management for better continuity"""
        # Store conversation history for context
        self.conversation_history = []
        self.max_history_length = 10  # Keep last 10 exchanges for context
        
        # Common real estate intents for faster response mapping
        self.real_estate_intents = {
            "buying": ["looking to buy", "interested in purchasing", "want to buy", "buying a home"],
            "selling": ["want to sell", "selling my house", "list my property", "selling process"],
            "investing": ["investment property", "rental income", "flip houses", "real estate investing"],
            "financing": ["mortgage", "loan options", "interest rates", "down payment", "pre-approval"],
            "market": ["market conditions", "housing prices", "appreciation", "market trends"],
            "property": ["square footage", "bedrooms", "bathrooms", "features", "amenities"],
            "process": ["closing costs", "inspection", "appraisal", "escrow", "contingencies"],
            "location": ["neighborhood", "school district", "community", "location"]
        }
        
        # Response templates for quicker generation
        self.response_templates = {
            "greeting": "Hello! I'm your real estate assistant. How can I help you today with your real estate questions?",
            "clarification": "I'm not quite sure I understood that. Could you rephrase your question about {topic}?",
            "transition": "Is there anything else you'd like to know about {topic}?",
            "closing": "Thank you for chatting about real estate today. Is there anything else I can help with?",
            "handoff": "That's a great question that might need personalized advice. Would you like me to connect you with a human agent to discuss {topic} in more detail?"
        }
    
    def _init_advanced_speech_processing(self):
        """Initialize advanced speech processing for better recognition"""
        # Common speech recognition errors in real estate context
        self.speech_corrections = {
            # Addresses and locations
            "addresses": "addresses",
            "zip code": "zip code",
            "street address": "street address",
            "nearby": "nearby",
            "neighborhood": "neighborhood",
            "school district": "school district",
            
            # Real estate terms
            "pre approval": "pre-approval",
            "preapproval": "pre-approval",
            "pre qualify": "pre-qualify",
            "prequalify": "pre-qualify",
            "f h a": "FHA",
            "fha": "FHA",
            "v a": "VA",
            "va loan": "VA loan",
            "h o a": "HOA",
            "hoa fees": "HOA fees",
            "homeowners association": "homeowners association",
            "condo": "condo",
            "condominium": "condominium",
            "townhouse": "townhouse",
            "town home": "townhome",
            "duplex": "duplex",
            "triplex": "triplex",
            "single family": "single-family",
            "multi family": "multi-family",
            "multifamily": "multi-family",
            
            # Financial terms
            "down payment": "down payment",
            "closing costs": "closing costs",
            "escrow": "escrow",
            "earnest money": "earnest money",
            "interest rate": "interest rate",
            "adjustable rate": "adjustable rate",
            "fixed rate": "fixed rate",
            "mortgage": "mortgage",
            "loan": "loan",
            "refinance": "refinance",
            "refinancing": "refinancing",
            "cash flow": "cash flow",
            "net operating income": "net operating income",
            "noi": "NOI",
            "cap rate": "cap rate",
            "capitalization rate": "capitalization rate",
            "roi": "ROI",
            "return on investment": "return on investment",
            "cash on cash": "cash-on-cash",
            "appreciation": "appreciation",
            "equity": "equity",
            "leverage": "leverage",
        }
        
        # Phonetic alternatives for commonly misheard real estate terms
        self.phonetic_alternatives = {
            "reeltor": "realtor",
            "reel estate": "real estate",
            "reel a state": "real estate",
            "morgage": "mortgage",
            "morgidge": "mortgage",
            "escroh": "escrow",
            "iscrow": "escrow",
            "contingensee": "contingency",
            "preapruval": "pre-approval",
            "howa": "HOA",
            "h o way": "HOA",
            "capperate": "cap rate",
            "cash on cash": "cash-on-cash",
            "eckwity": "equity",
            "square foot-age": "square footage",
            "square feet-age": "square footage"
        }
        
        # Create custom speech config with contextual phrases
        self._create_custom_speech_config()
        
        # Initialize noise reduction and voice enhancement
        self._init_noise_reduction()
    
    def _create_custom_speech_config(self):
        """Create custom speech config with contextual phrases for better recognition"""
        try:
            if self.speech_config:
                # Add phrases to speech recognition to improve accuracy
                phrase_list = speechsdk.PhraseListGrammar.from_recognizer(self.speech_recognizer)
                
                # Add common real estate terms to improve recognition
                real_estate_terms = [
                    "real estate", "realtor", "property", "mortgage", "interest rate",
                    "down payment", "pre-approval", "escrow", "closing costs", "appraisal",
                    "inspection", "contingencies", "HOA", "buyer's agent", "listing agent",
                    "equity", "appreciation", "amortization", "capitalization rate",
                    "cash flow", "investment property", "rental income", "fix and flip",
                    "cash-on-cash return", "ROI", "property management", "refinance",
                    "conventional loan", "FHA loan", "VA loan", "USDA loan", "jumbo loan",
                    "seller's market", "buyer's market", "multiple listing service",
                    "comparables", "days on market", "inventory", "pending sale"
                ]
                
                # Add phrases to recognition context
                for term in real_estate_terms:
                    phrase_list.addPhrase(term)
                
                logger.info("Custom speech configuration created with real estate phrases")
        except Exception as e:
            logger.error(f"Error creating custom speech config: {str(e)}")
    
    def _init_noise_reduction(self):
        """Initialize noise reduction and voice enhancement for better speech recognition"""
        # This would typically involve setting up audio processing configurations
        # For demonstration, we'll just track the settings we'd use in a production system
        self.noise_reduction_settings = {
            "noise_suppression_level": "high",
            "echo_cancellation": True,
            "auto_gain_control": True,
            "voice_activity_detection": True,
            "ambient_noise_adaptation": True
        }
        
        logger.info("Noise reduction initialized with high suppression level")
    
    def _process_recognized_speech(self, evt):
        """Process recognized speech with context awareness and error correction"""
        try:
            # Get the recognized text
            recognized_text = evt.result.text
            
            # Apply real estate terminology corrections
            corrected_text = self._apply_terminology_corrections(recognized_text)
            
            # Add to conversation history for context
            self.conversation_history.append({
                "role": "user",
                "content": corrected_text
            })
            
            # Trim history if needed
            if len(self.conversation_history) > self.max_history_length * 2:  # *2 because each exchange has two entries
                self.conversation_history = self.conversation_history[-self.max_history_length * 2:]
            
            logger.debug(f"Processed speech: '{recognized_text}' -> '{corrected_text}'")
            return corrected_text
        except Exception as e:
            logger.error(f"Error processing recognized speech: {str(e)}")
            return evt.result.text if evt and hasattr(evt, 'result') and hasattr(evt.result, 'text') else ""
    
    def _apply_terminology_corrections(self, text):
        """Apply corrections to commonly misrecognized real estate terminology"""
        if not text:
            return text
        
        # First correct phonetic alternatives
        for wrong, correct in self.phonetic_alternatives.items():
            text = re.sub(r'\b' + re.escape(wrong) + r'\b', correct, text, flags=re.IGNORECASE)
        
        # Then correct other common issues
        for wrong, correct in self.speech_corrections.items():
            text = re.sub(r'\b' + re.escape(wrong) + r'\b', correct, text, flags=re.IGNORECASE)
        
        return text
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def process_query(self, query: str) -> str:
        """
        Process a real estate query with retry logic and enhanced context awareness
        
        Args:
            query: The user's real estate query
            
        Returns:
            A relevant response to the real estate query
        """
        try:
            if not self.client:
                logger.error("OpenAI client not initialized")
                return "I'm sorry, but I'm having trouble connecting to my knowledge base. Please try again later."
            
            # Clean and standardize the query
            processed_query = self._apply_terminology_corrections(query)
            
            # Detect intent for better response targeting
            intent = self._detect_intent(processed_query)
            
            # Build conversation context
            messages = [
                {"role": "system", "content": self._get_system_prompt(intent)},
            ]
            
            # Add conversation history for context
            for message in self.conversation_history[-6:]:  # Last 3 exchanges (6 messages)
                messages.append(message)
            
            # Add the current query
            messages.append({"role": "user", "content": processed_query})
            
            # Get response from Azure OpenAI
            response = await self._get_openai_response(messages)
            
            # Add response to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            return response
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            logger.error(traceback.format_exc())
            return "I apologize, but I'm having trouble processing your question. Could you rephrase it or try asking something else about real estate?"
    
    async def _get_openai_response(self, messages: List[Dict[str, str]]) -> str:
        """Get response from OpenAI with proper async handling"""
        try:
            # Create a response with the OpenAI API
            response = await asyncio.to_thread(
                self.client.ChatCompletion.create,
                engine=self.deployment_name,
                messages=messages,
                temperature=0.7,
                max_tokens=300,  # Keep responses concise for better conversation flow
                top_p=0.95,
                frequency_penalty=0.5,  # Reduce repetition
                presence_penalty=0.2,
                stop=None
            )
            
            # Extract and return the response text
            return response.choices[0].message['content'].strip()
        except Exception as e:
            logger.error(f"Error getting OpenAI response: {str(e)}")
            raise
    
    def _detect_intent(self, query: str) -> str:
        """Detect the intent of a real estate query for better response targeting"""
        query_lower = query.lower()
        
        # Check each intent category
        for intent, keywords in self.real_estate_intents.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    logger.debug(f"Detected intent: {intent} from query: {query}")
                    return intent
        
        # Default to general if no specific intent is found
        return "general"
    
    def _get_system_prompt(self, intent: str) -> str:
        """Get a tailored system prompt based on detected intent"""
        base_prompt = """
        You are a highly knowledgeable real estate assistant working for Premier Real Estate Services.
        Your role is to provide accurate, helpful information about all aspects of real estate.
        
        When responding to queries:
        1. ALWAYS provide specific, actionable information rather than vague statements
        2. Use natural conversational language suitable for a phone call (use contractions, avoid overly formal language)
        3. Break information into concise, digestible chunks
        4. Limit responses to under 100 words when possible to maintain engagement
        5. When discussing financial information, provide specific ranges and percentages when appropriate
        6. Always acknowledge the question first before answering
        7. End your response with a natural conversational transition or brief follow-up question
        """
        
        # Add intent-specific guidance
        intent_guidance = {
            "buying": """
            Focus on buyer-specific information. Emphasize the buying process, making offers,
            negotiation strategies, financing options, and first-time homebuyer considerations.
            Mention typical timelines (30-45 days for closing) and buyer closing costs (2-5%).
            """,
            
            "selling": """
            Focus on seller-specific information. Emphasize pricing strategies, marketing properties,
            staging, negotiating offers, seller closing costs (6-10%), and typical timelines (60-90 days).
            Discuss market conditions relevant to sellers and preparation for selling.
            """,
            
            "investing": """
            Focus on investment property information. Emphasize ROI calculations, cap rates (good range is 4-10%),
            cash flow analysis, rental property management (costs typically 8-12% of rent),
            and investment strategies (fix-and-flip, buy-and-hold, etc.).
            """,
            
            "financing": """
            Focus on mortgage and financing information. Emphasize loan types, down payment requirements,
            interest rates, pre-approval process, closing costs, debt-to-income ratios (typically 43% max),
            and credit score impacts (620+ for conventional, 580+ for FHA).
            """,
            
            "market": """
            Focus on market condition information. Emphasize current trends, supply and demand dynamics,
            appreciation factors, seasonality impacts, inventory levels, and neighborhood analysis factors.
            Discuss indicators of buyer's vs seller's markets.
            """,
            
            "property": """
            Focus on property-specific information. Emphasize property types, construction, home systems,
            condition assessments, square footage considerations, lot size importance, and feature valuations.
            Discuss how various features impact property value.
            """,
            
            "process": """
            Focus on real estate process information. Emphasize purchase contracts, contingencies,
            escrow, closing process, title insurance, property disclosures, and real estate regulations.
            Explain typical timelines and what to expect at each stage.
            """,
            
            "location": """
            Focus on location-specific information. Emphasize neighborhood evaluation, school districts
            (10-20% premium for top districts), crime considerations, proximity to amenities,
            transportation factors, future development impacts, and property tax variations.
            """
        }
        
        # Add intent-specific guidance if available
        if intent in intent_guidance:
            return base_prompt + "\n" + intent_guidance[intent]
        else:
            return base_prompt
    
    async def recognize_speech(self, audio_stream=None):
        """
        Enhanced speech recognition with advanced processing
        
        Args:
            audio_stream: Optional audio stream for processing
            
        Returns:
            The recognized text with real estate terminology corrections
        """
        try:
            if not self.speech_recognizer:
                logger.error("Speech recognizer not initialized")
                return "Speech recognition not available"
            
            # Start speech recognition
            if audio_stream:
                # Use provided audio stream
                result = await asyncio.to_thread(
                    self.speech_recognizer.recognize_once_async().get
                )
            else:
                # Use microphone
                result = await asyncio.to_thread(
                    self.speech_recognizer.recognize_once_async().get
                )
            
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                # Process and correct the recognized text
                processed_text = self._process_recognized_speech(result)
                return processed_text
            elif result.reason == speechsdk.ResultReason.NoMatch:
                logger.warning("No speech could be recognized")
                return "I didn't hear that clearly. Could you repeat your question about real estate?"
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = speechsdk.CancellationDetails.from_result(result)
                if cancellation.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"Speech recognition error: {cancellation.error_details}")
                return "I'm having trouble understanding you right now. Could you try again or maybe phrase your question differently?"
            else:
                return "I didn't quite catch that. Could you repeat your question about real estate?"
        except Exception as e:
            logger.error(f"Error in speech recognition: {str(e)}")
            logger.error(traceback.format_exc())
            return "I'm having technical difficulties understanding you. Please try again shortly."
    
    def start_continuous_recognition(self, callback):
        """
        Start continuous speech recognition for more natural conversation
        
        Args:
            callback: Function to call with recognized speech results
        """
        try:
            if not self.speech_recognizer:
                logger.error("Speech recognizer not initialized")
                return False
            
            # Set up callback for recognized speech
            self.speech_recognizer.recognized.connect(
                lambda evt: self._handle_continuous_recognition(evt, callback)
            )
            
            # Set up callback for session stopped
            self.speech_recognizer.session_stopped.connect(
                lambda evt: logger.info("Speech recognition session stopped")
            )
            
            # Set up callback for canceled recognition
            self.speech_recognizer.canceled.connect(
                lambda evt: logger.warning(f"Speech recognition canceled: {evt}")
            )
            
            # Start continuous recognition
            self.speech_recognizer.start_continuous_recognition_async()
            logger.info("Continuous speech recognition started")
            return True
        except Exception as e:
            logger.error(f"Error starting continuous recognition: {str(e)}")
            return False
    
    def _handle_continuous_recognition(self, evt, callback):
        """Handle recognized speech in continuous recognition mode"""
        try:
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                # Process recognized text
                processed_text = self._process_recognized_speech(evt)
                
                # Call the callback with processed text
                if callback and callable(callback):
                    callback(processed_text)
            elif evt.result.reason == speechsdk.ResultReason.NoMatch:
                logger.debug("No speech could be recognized in continuous mode")
            # Other reasons handled by the canceled callback
        except Exception as e:
            logger.error(f"Error handling continuous recognition: {str(e)}")
    
    def stop_continuous_recognition(self):
        """Stop continuous speech recognition"""
        try:
            if self.speech_recognizer:
                self.speech_recognizer.stop_continuous_recognition_async()
                logger.info("Continuous speech recognition stopped")
                return True
            return False
        except Exception as e:
            logger.error(f"Error stopping continuous recognition: {str(e)}")
            return False
    
    def enhance_audio_quality(self, audio_data):
        """
        Enhance audio quality for better speech recognition
        
        Args:
            audio_data: Raw audio data to enhance
            
        Returns:
            Enhanced audio data
        """
        # This is a placeholder for audio enhancement functionality
        # In a real implementation, this would apply noise reduction, normalization, etc.
        logger.info("Audio enhancement applied")
        return audio_data
    
    def get_real_estate_topics(self):
        """Get the list of real estate topics for knowledge base reference"""
        return list(self.real_estate_intents.keys())
    
    async def get_answer_from_knowledge_base(self, query):
        """
        Get answer from knowledge base with expanded context
        
        Args:
            query: The user's query
            
        Returns:
            Response from knowledge base
        """
        # This function would integrate with your existing knowledge base
        # We'll implement a simplified version that forwards to the OpenAI processing
        return await self.process_query(query)

    def shutdown(self):
        """Clean shutdown of services"""
        try:
            # Stop any ongoing recognition
            if hasattr(self, 'speech_recognizer') and self.speech_recognizer:
                self.stop_continuous_recognition()
            
            logger.info("Azure services shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")