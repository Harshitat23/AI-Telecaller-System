"""
Enhanced interruption handling for real estate AI telecaller system.
This module adds speech interruption detection and handling.
"""
import os
import logging
import time
import threading
import re
from typing import Dict, Any, Optional

from twilio.twiml.voice_response import VoiceResponse, Gather
from flask import request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class InterruptionHandler:
    """
    Handles voice interruptions during AI response playback
    """
    def __init__(self, conversation_manager=None):
        """
        Initialize the interruption handler
        
        Args:
            conversation_manager: Conversation manager instance
        """
        # Import here to avoid circular imports
        if conversation_manager is None:
            from conversation_manager import global_enhanced_conversation_manager
            self.conversation_manager = global_enhanced_conversation_manager
        else:
            self.conversation_manager = conversation_manager
            
        self.active_responses = {}
        self.response_lock = threading.RLock()
        
        logger.info("InterruptionHandler initialized")
    
    def register_response(self, call_sid: str, response_token: str, chunks: list) -> Dict[str, Any]:
        """
        Register a multi-chunk response for interruption handling
        
        Args:
            call_sid: Call SID
            response_token: Unique token for this response
            chunks: List of response chunks
        
        Returns:
            Dict with response_id
        """
        with self.response_lock:
            try:
                response_id = f"{call_sid}_{int(time.time())}"
                self.active_responses[response_id] = {
                    'call_sid': call_sid,
                    'response_token': response_token,
                    'chunks': chunks,
                    'current_chunk': 0,
                    'status': 'pending',
                    'start_time': time.time(),
                    'interrupted': False,
                    'interrupt_data': None
                }
                
                # Also register in conversation manager for cross-reference
                self.conversation_manager.track_active_response(call_sid, response_token, {
                    'response_id': response_id,
                    'chunks_count': len(chunks)
                })
                
                logger.info(f"Registered response {response_id} with {len(chunks)} chunks")
                return {'response_id': response_id}
            except Exception as e:
                logger.error(f"Error registering response: {str(e)}")
                return {'response_id': f"{call_sid}_{int(time.time())}", 'error': str(e)}
    
    def start_response_playback(self, response_id: str) -> str:
        """
        Start playing back a response with interruption detection
        
        Args:
            response_id: ID of the response
        
        Returns:
            TwiML response
        """
        with self.response_lock:
            try:
                if response_id not in self.active_responses:
                    logger.error(f"Response ID {response_id} not found")
                    return self._create_error_response()
                
                response_data = self.active_responses[response_id]
                response_data['status'] = 'active'
                
                # Create TwiML response with interruption detection
                twiml = self._create_chunk_response(response_id)
                return twiml
            except Exception as e:
                logger.error(f"Error starting response playback: {str(e)}")
                return self._create_error_response()
    
    def _create_chunk_response(self, response_id: str) -> str:
        """
        Create TwiML response for current chunk with interruption detection
        
        Args:
            response_id: ID of the response
        
        Returns:
            TwiML response
        """
        try:
            with self.response_lock:
                if response_id not in self.active_responses:
                    logger.error(f"Response ID {response_id} not found in _create_chunk_response")
                    return self._create_error_response()
                    
                response_data = self.active_responses[response_id]
                current_chunk_idx = response_data['current_chunk']
                chunks = response_data['chunks']
                
                # Check if we've played all chunks
                if current_chunk_idx >= len(chunks):
                    return self._create_completion_response(response_id)
                
                # Get current chunk
                current_chunk = chunks[current_chunk_idx]
                
            # Create response outside of lock to avoid deadlocks
            response = VoiceResponse()
            
            # Set up interruption detection using <Gather>
            base_url = os.environ.get('SERVER_URL', 'http://localhost:5000')
            
            # Use Gather with very short timeout and interruptible speech
            gather = Gather(
                input='speech',
                action=f"{base_url}/webhook/interrupt?response_id={response_id}",
                timeout=1,  # Very short timeout
                speechTimeout='auto',
                actionOnEmptyResult=True,
                enhanced=True,  # Enhanced speech recognition
                interruptible='true',  # Allow interruption of TTS
                speechModel='phone_call'
            )
            
            # Say the current chunk
            gather.say(
                current_chunk, 
                voice='alice', 
                rate="0.9"
            )
            
            response.append(gather)
            
            # If not interrupted, proceed to next chunk
            response.redirect(f"{base_url}/webhook/continue_response?response_id={response_id}")
            
            return str(response)
        except Exception as e:
            logger.error(f"Error creating chunk response: {str(e)}")
            return self._create_error_response()
    
    def continue_response(self, response_id: str) -> str:
        """
        Continue to the next chunk of the response
        
        Args:
            response_id: ID of the response
        
        Returns:
            TwiML response
        """
        with self.response_lock:
            try:
                if response_id not in self.active_responses:
                    logger.error(f"Response ID {response_id} not found in continue_response")
                    return self._create_error_response()
                
                response_data = self.active_responses[response_id]
                response_data['current_chunk'] += 1
                
            except Exception as e:
                logger.error(f"Error continuing response: {str(e)}")
                return self._create_error_response()
            
        # Create response outside of lock to avoid potential deadlocks
        return self._create_chunk_response(response_id)
    
    def handle_interruption(self, response_id: str, speech_result: str = None, confidence: float = None) -> str:
        """
        Handle an interruption during response playback
        
        Args:
            response_id: ID of the interrupted response
            speech_result: What user said to interrupt
            confidence: Confidence level of speech recognition
        
        Returns:
            TwiML response
        """
        # Get data from request if not provided
        if speech_result is None:
            speech_result = request.values.get('SpeechResult', '')
        if confidence is None:
            try:
                confidence = float(request.values.get('Confidence', 0))
            except (ValueError, TypeError):
                confidence = 0.0
        
        call_sid = None
        response_token = None
        
        with self.response_lock:
            try:
                if response_id not in self.active_responses:
                    logger.error(f"Response ID {response_id} not found for interruption")
                    return self._create_error_response()
                
                response_data = self.active_responses[response_id]
                call_sid = response_data['call_sid']
                response_token = response_data['response_token']
                
                # Mark as interrupted
                response_data['interrupted'] = True
                response_data['status'] = 'interrupted'
                response_data['interrupt_data'] = {
                    'speech_result': speech_result,
                    'confidence': confidence,
                    'time': time.time()
                }
                
                logger.info(f"Response {response_id} interrupted with: '{speech_result}'")
                
            except Exception as e:
                logger.error(f"Error handling interruption: {str(e)}")
                return self._create_error_response()
        
        # These operations don't need to be in the lock
        if call_sid and response_token:
            # Notify conversation manager
            self.conversation_manager.handle_response_interruption(response_token, 'user_interrupt')
            
            # Track interruption in conversation
            self.conversation_manager.add_conversation_message(
                call_sid,
                role='user',
                content=speech_result,
                metadata={
                    'type': 'interruption',
                    'confidence': confidence,
                    'response_token': response_token
                }
            )
            
        # Process the interruption
        return self._process_interruption(response_id, speech_result, call_sid)
    
    def _process_interruption(self, response_id: str, speech_result: str, call_sid: str) -> str:
        """
        Process an interruption with context continuation
        
        Args:
            response_id: ID of the interrupted response
            speech_result: What user said to interrupt
            call_sid: Call SID
        
        Returns:
            TwiML response with contextual reply
        """
        try:
            # Create TwiML response
            response = VoiceResponse()
            base_url = os.environ.get('SERVER_URL', 'http://localhost:5000')
            
            # Brief acknowledgment of interruption
            response.say(
                "I understand. Let me address that.",
                voice='alice',
                rate="0.9"
            )
            
            # Set up to gather the user's full question after the interruption
            followup_gathering = Gather(
                input='speech',
                action=f"{base_url}/webhook/speech",
                timeout=5,
                speechTimeout='auto',
                enhanced=True,
                language='en-US',
                speechModel='phone_call'
            )
            
            # Prompt for more details
            followup_gathering.say(
                "Please continue with your question.", 
                voice='alice', 
                rate="0.9"
            )
            
            response.append(followup_gathering)
            
            # Fallback in case of no speech detected
            response.say("I didn't hear anything. Please ask your question again.", voice='alice', rate="0.9")
            response.redirect(f"{base_url}/webhook/voice")
            
            return str(response)
        except Exception as e:
            logger.error(f"Error processing interruption: {str(e)}")
            return self._create_error_response()
    
    def _create_completion_response(self, response_id: str) -> str:
        """
        Create TwiML response for when all chunks are complete
        
        Args:
            response_id: ID of the response
        
        Returns:
            TwiML response
        """
        call_sid = None
        
        # Clean up
        with self.response_lock:
            try:
                if response_id not in self.active_responses:
                    logger.error(f"Response ID {response_id} not found in completion")
                    return self._create_error_response()
                    
                response_data = self.active_responses.pop(response_id, None)
                call_sid = response_data['call_sid'] if response_data else None
                
            except Exception as e:
                logger.error(f"Error in completion response: {str(e)}")
                return self._create_error_response()
        
        try:
            # Create response with follow-up question
            response = VoiceResponse()
            
            # Set up next gather
            base_url = os.environ.get('SERVER_URL', 'http://localhost:5000')
            gather = Gather(
                input='speech',
                action=f"{base_url}/webhook/speech",
                timeout=5,
                speechTimeout='auto',
                enhanced=True,
                language='en-US',
                speechModel='phone_call'
            )
            
            gather.say("Is there anything else you'd like to know?", voice='alice', rate="0.9")
            response.append(gather)
            
            # Fallback
            response.say("I didn't hear anything. How else can I help you?", voice='alice', rate="0.9")
            response.redirect(f"{base_url}/webhook/voice")
            
            return str(response)
        except Exception as e:
            logger.error(f"Error creating completion response: {str(e)}")
            return self._create_error_response()
    
    def _create_error_response(self) -> str:
        """
        Create error response TwiML
        
        Returns:
            TwiML error response
        """
        try:
            response = VoiceResponse()
            response.say(
                "I apologize for the technical difficulty. Let's try again.", 
                voice='alice',
                rate="0.9"
            )
            
            base_url = os.environ.get('SERVER_URL', 'http://localhost:5000')
            
            # Set up gathering instead of redirecting immediately
            gather = Gather(
                input='speech',
                action=f"{base_url}/webhook/speech",
                timeout=5,
                speechTimeout='auto',
                enhanced=True,
                language='en-US',
                speechModel='phone_call'
            )
            
            gather.say("How can I help you with your real estate questions?", voice='alice', rate="0.9")
            response.append(gather)
            
            # Only redirect if no input
            response.redirect(f"{base_url}/webhook/voice")
            
            return str(response)
        except Exception as e:
            logger.error(f"Error creating error response: {str(e)}")
            # Fallback to minimal response in case of severe error
            return str(VoiceResponse().say("We're experiencing technical difficulties. Please call again later."))

# Create singleton instance
interruption_handler = None

def get_interruption_handler():
    """Factory function to get or create singleton interruption handler"""
    global interruption_handler
    if interruption_handler is None:
        try:
            from conversation_manager import global_enhanced_conversation_manager
            interruption_handler = InterruptionHandler(global_enhanced_conversation_manager)
        except ImportError:
            # Create without conversation manager, will be set later
            interruption_handler = InterruptionHandler()
    return interruption_handler