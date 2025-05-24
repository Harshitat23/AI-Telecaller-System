import os
import logging
import json
import time
import threading
from typing import List, Dict, Any, Optional, Callable
import re
from concurrent.futures import ThreadPoolExecutor

class EnhancedConversationManager:
    """
    Advanced conversation management for AI telecaller system
    Provides enhanced context tracking, follow-up handling, and conversation state management
    """
    def __init__(self, max_history_length: int = 10):
        """
        Initialize enhanced conversation manager
        
        Args:
            max_history_length: Maximum number of exchanges to keep in conversation history
        """
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Conversation tracking
        self.conversations: Dict[str, Dict[str, Any]] = {}
        self.max_history_length = max_history_length
        
        # Conversation state management
        self.conversation_lock = threading.RLock()  # Using RLock to prevent deadlocks
        
        # Active responses tracking
        self.active_responses: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("EnhancedConversationManager initialized")
    
    def initialize_conversation(self, call_sid: str, initial_context: Dict[str, Any] = None) -> bool:
        """
        Initialize a new conversation for a specific call with enhanced tracking
        
        Args:
            call_sid: Unique identifier for the call
            initial_context: Optional initial context for the conversation
            
        Returns:
            True if a new conversation was created, False if it already existed
        """
        if not call_sid:
            self.logger.error("Cannot initialize conversation with empty call SID")
            return False
            
        try:
            with self.conversation_lock:
                if call_sid not in self.conversations:
                    self.conversations[call_sid] = {
                        'history': [],
                        'state': {
                            'current_topic': None,
                            'intent': None,
                            'context': initial_context or {},
                            'last_interaction_time': time.time(),
                            'total_interactions': 0,
                            'conversation_type': 'initial'
                        },
                        'follow_up_context': {
                            'expected_topics': [],
                            'related_questions': [],
                            'context_keywords': []
                        },
                        'interruption_management': {
                            'active_response_token': None,
                            'can_interrupt': True,
                            'interrupt_threshold': 3  # Number of times user can interrupt
                        }
                    }
                    
                    self.logger.info(f"Initialized enhanced conversation for call SID: {call_sid}")
                    return True
                return False
        except Exception as e:
            self.logger.error(f"Error initializing conversation for call SID {call_sid}: {str(e)}")
            # Create a basic conversation structure to prevent further errors
            with self.conversation_lock:
                if call_sid not in self.conversations:
                    self.conversations[call_sid] = {
                        'history': [],
                        'state': {'last_interaction_time': time.time()},
                        'follow_up_context': {},
                        'interruption_management': {'can_interrupt': True}
                    }
            return False
    
    def add_follow_up_context(
        self, 
        call_sid: str, 
        expected_topics: List[str] = None, 
        related_questions: List[str] = None, 
        context_keywords: List[str] = None
    ) -> bool:
        """
        Add enhanced follow-up context for more intelligent conversation tracking
        
        Args:
            call_sid: Unique identifier for the call
            expected_topics: List of topics expected to be discussed
            related_questions: List of related questions that might come up
            context_keywords: Keywords to help identify context
            
        Returns:
            True if context was added successfully, False otherwise
        """
        if not call_sid:
            self.logger.error("Cannot add follow-up context with empty call SID")
            return False
            
        try:
            with self.conversation_lock:
                if call_sid not in self.conversations:
                    if not self.initialize_conversation(call_sid):
                        self.logger.error(f"Failed to initialize conversation for call SID: {call_sid}")
                        return False
                
                # Update follow-up context
                follow_up_context = self.conversations[call_sid]['follow_up_context']
                
                if expected_topics:
                    follow_up_context['expected_topics'] = expected_topics
                
                if related_questions:
                    follow_up_context['related_questions'] = related_questions
                
                if context_keywords:
                    follow_up_context['context_keywords'] = context_keywords
                
                self.logger.debug(f"Updated follow-up context for call SID: {call_sid}")
                return True
        except Exception as e:
            self.logger.error(f"Error adding follow-up context for call SID {call_sid}: {str(e)}")
            return False
    
    def evaluate_follow_up_relevance(self, call_sid: str, new_query: str) -> Dict[str, Any]:
        """
        Evaluate the relevance of a follow-up query with advanced matching
        
        Args:
            call_sid: Unique identifier for the call
            new_query: New user query
        
        Returns:
            Detailed follow-up relevance assessment
        """
        if not call_sid or not new_query:
            self.logger.error("Cannot evaluate follow-up relevance with empty call SID or query")
            return {'is_follow_up': False, 'confidence': 0.0, 'error': 'Empty call SID or query'}
            
        try:
            with self.conversation_lock:
                if call_sid not in self.conversations:
                    self.logger.warning(f"Call SID {call_sid} not found in existing conversations")
                    return {'is_follow_up': False, 'confidence': 0.0, 'matched_context': []}
                
                follow_up_context = self.conversations[call_sid]['follow_up_context']
                query_lower = new_query.lower()
                
                # Initialize match tracking
                matched_context = {
                    'expected_topics': [],
                    'related_questions': [],
                    'context_keywords': []
                }
                confidence = 0.0
                
                # Check expected topics
                for topic in follow_up_context.get('expected_topics', []):
                    if topic.lower() in query_lower:
                        matched_context['expected_topics'].append(topic)
                        confidence += 0.4
                
                # Check related questions
                for question in follow_up_context.get('related_questions', []):
                    if question.lower() in query_lower:
                        matched_context['related_questions'].append(question)
                        confidence += 0.3
                
                # Check context keywords
                for keyword in follow_up_context.get('context_keywords', []):
                    if keyword.lower() in query_lower:
                        matched_context['context_keywords'].append(keyword)
                        confidence += 0.2
                
                # Apply semantic understanding rules
                if re.search(r'\b(more|further|additional|again)\b', query_lower):
                    confidence += 0.1
                
                return {
                    'is_follow_up': confidence > 0.5,
                    'confidence': min(confidence, 1.0),
                    'matched_context': matched_context
                }
        except Exception as e:
            self.logger.error(f"Error evaluating follow-up relevance: {str(e)}")
            return {'is_follow_up': False, 'confidence': 0.0, 'error': str(e)}
    
    def track_active_response(
        self, 
        call_sid: str, 
        response_token: str, 
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Track an active response generation with enhanced interruption management
        
        Args:
            call_sid: Unique identifier for the call
            response_token: Unique token for the response
            metadata: Optional metadata about the response
            
        Returns:
            True if response was tracked successfully, False otherwise
        """
        if not call_sid or not response_token:
            self.logger.error("Cannot track active response with empty call SID or response token")
            return False
            
        try:
            with self.conversation_lock:
                if call_sid not in self.conversations:
                    if not self.initialize_conversation(call_sid):
                        self.logger.error(f"Failed to initialize conversation for call SID: {call_sid}")
                        return False
                
                # Track active response
                self.active_responses[response_token] = {
                    'call_sid': call_sid,
                    'start_time': time.time(),
                    'metadata': metadata or {},
                    'status': 'active',
                    'interruption_count': 0
                }
                
                # Update conversation's active response
                conversation = self.conversations[call_sid]
                if 'interruption_management' in conversation:
                    conversation['interruption_management']['active_response_token'] = response_token
                    conversation['interruption_management']['can_interrupt'] = True
                else:
                    # Ensure interruption_management exists
                    conversation['interruption_management'] = {
                        'active_response_token': response_token,
                        'can_interrupt': True,
                        'interrupt_threshold': 3
                    }
                
                self.logger.debug(f"Tracking active response: {response_token}")
                return True
        except Exception as e:
            self.logger.error(f"Error tracking active response for call SID {call_sid}: {str(e)}")
            return False
    
    def handle_response_interruption(
        self, 
        response_token: str, 
        interrupt_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle interruption of an active response
        
        Args:
            response_token: Unique token for the response being interrupted
            interrupt_reason: Optional reason for interruption
        
        Returns:
            Interruption handling result
        """
        if not response_token:
            self.logger.error("Cannot handle response interruption with empty response token")
            return {'success': False, 'message': 'Empty response token'}
            
        try:
            with self.conversation_lock:
                if response_token not in self.active_responses:
                    self.logger.warning(f"Response token {response_token} not found in active responses")
                    return {'success': False, 'message': 'Response not found'}
                
                response_info = self.active_responses[response_token]
                call_sid = response_info['call_sid']
                
                # Mark response as interrupted
                response_info['status'] = 'interrupted'
                response_info['interrupt_reason'] = interrupt_reason
                response_info['interruption_count'] += 1
                
                # Check if conversation exists
                if call_sid not in self.conversations:
                    self.logger.warning(f"Call SID {call_sid} not found during interruption handling")
                    return {'success': True, 'message': 'Response interrupted but conversation not found'}
                    
                conversation = self.conversations[call_sid]
                
                # Check if interruption_management exists, create if not
                if 'interruption_management' not in conversation:
                    conversation['interruption_management'] = {
                        'active_response_token': None,
                        'can_interrupt': True,
                        'interrupt_threshold': 3
                    }
                
                # Check interruption threshold
                interrupt_mgmt = conversation['interruption_management']
                if response_info['interruption_count'] > interrupt_mgmt.get('interrupt_threshold', 3):
                    interrupt_mgmt['can_interrupt'] = False
                    return {
                        'success': False, 
                        'message': 'Maximum interruptions reached'
                    }
                
                # Reset active response token
                interrupt_mgmt['active_response_token'] = None
                
                self.logger.info(f"Interrupted response: {response_token}")
                
                return {
                    'success': True, 
                    'message': 'Response interrupted successfully',
                    'interruption_count': response_info['interruption_count']
                }
        except Exception as e:
            self.logger.error(f"Error handling response interruption: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def add_conversation_message(
        self, 
        call_sid: str, 
        role: str, 
        content: str, 
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Add a message to the conversation history with enhanced tracking
        
        Args:
            call_sid: Unique identifier for the call
            role: Role of the message sender (user/assistant)
            content: Message content
            metadata: Optional metadata about the message
            
        Returns:
            True if message was added successfully, False otherwise
        """
        if not call_sid or not role or content is None:
            self.logger.error("Cannot add conversation message with empty call SID, role, or content")
            return False
            
        try:
            with self.conversation_lock:
                if call_sid not in self.conversations:
                    if not self.initialize_conversation(call_sid):
                        self.logger.error(f"Failed to initialize conversation for call SID: {call_sid}")
                        return False
                
                conversation = self.conversations[call_sid]
                
                # Prepare message
                message = {
                    'role': role,
                    'content': content,
                    'timestamp': time.time(),
                    'metadata': metadata or {},
                    'message_id': f"{call_sid}_{len(conversation['history']) + 1}"
                }
                
                # Add message to history
                conversation['history'].append(message)
                
                # Trim history if it exceeds max length
                if len(conversation['history']) > self.max_history_length * 2:
                    conversation['history'] = conversation['history'][-self.max_history_length * 2:]
                
                # Ensure state exists
                if 'state' not in conversation:
                    conversation['state'] = {
                        'last_interaction_time': time.time(),
                        'total_interactions': 0
                    }
                
                # Update conversation state
                conversation['state']['last_interaction_time'] = time.time()
                conversation['state']['total_interactions'] = conversation['state'].get('total_interactions', 0) + 1
                
                # Update intent tracking if it's a user message
                if role == 'user':
                    self._update_conversation_intent(call_sid, content)
                
                self.logger.debug(f"Added message to conversation history for call SID: {call_sid}")
                return True
        except Exception as e:
            self.logger.error(f"Error adding conversation message for call SID {call_sid}: {str(e)}")
            return False
    
    def get_conversation_context(self, call_sid: str, max_messages: int = None) -> Dict[str, Any]:
        """
        Get the current conversation context for improved response generation
        
        Args:
            call_sid: Unique identifier for the call
            max_messages: Optional maximum number of messages to include
        
        Returns:
            Current conversation context
        """
        if not call_sid:
            self.logger.error("Cannot get conversation context with empty call SID")
            return {'history': [], 'state': {}, 'context': {}, 'error': 'Empty call SID'}
            
        try:
            with self.conversation_lock:
                if call_sid not in self.conversations:
                    self.logger.warning(f"Call SID {call_sid} not found when getting conversation context")
                    return {'history': [], 'state': {}, 'context': {}}
                
                conversation = self.conversations[call_sid]
                
                # Get history with optional limit
                history = conversation.get('history', [])
                if max_messages and len(history) > max_messages:
                    history = history[-max_messages:]
                
                # Ensure all required fields exist
                if 'state' not in conversation:
                    conversation['state'] = {}
                    
                if 'follow_up_context' not in conversation:
                    conversation['follow_up_context'] = {}
                    
                if 'interruption_management' not in conversation:
                    conversation['interruption_management'] = {}
                
                return {
                    'history': history,
                    'state': conversation.get('state', {}),
                    'follow_up_context': conversation.get('follow_up_context', {}),
                    'interruption_management': conversation.get('interruption_management', {})
                }
        except Exception as e:
            self.logger.error(f"Error getting conversation context for call SID {call_sid}: {str(e)}")
            return {'history': [], 'state': {}, 'context': {}, 'error': str(e)}
    
    def _update_conversation_intent(self, call_sid: str, user_content: str):
        """
        Update conversation intent based on user message
        
        Args:
            call_sid: Unique identifier for the call
            user_content: User's message content
        """
        if not call_sid or not user_content:
            self.logger.error("Cannot update conversation intent with empty call SID or user content")
            return
            
        try:
            # Basic intent recognition for real estate topics
            intent_keywords = {
                'buying': ['buy', 'purchase', 'home', 'property', 'real estate'],
                'selling': ['sell', 'listing', 'market', 'price', 'value'],
                'mortgage': ['loan', 'finance', 'interest', 'rate', 'mortgage'],
                'investment': ['invest', 'rental', 'income', 'property management'],
                'market_info': ['market', 'trend', 'prices', 'appreciation']
            }
            
            # Convert to lowercase for case-insensitive matching
            content_lower = user_content.lower()
            
            # Find the most likely intent
            with self.conversation_lock:
                if call_sid not in self.conversations:
                    self.logger.warning(f"Call SID {call_sid} not found when updating conversation intent")
                    return
                    
                conversation = self.conversations[call_sid]
                
                # Ensure state exists
                if 'state' not in conversation:
                    conversation['state'] = {
                        'intent': None,
                        'last_interaction_time': time.time(),
                        'total_interactions': 0
                    }
                
                for intent, keywords in intent_keywords.items():
                    if any(keyword in content_lower for keyword in keywords):
                        conversation['state']['intent'] = intent
                        self.logger.debug(f"Detected intent: {intent}")
                        break
        except Exception as e:
            self.logger.error(f"Error updating conversation intent for call SID {call_sid}: {str(e)}")

    def cleanup_stale_conversations(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up stale conversations
        
        Args:
            max_age_seconds: Maximum age for conversations in seconds
            
        Returns:
            Number of conversations removed
        """
        if max_age_seconds <= 0:
            self.logger.error("Invalid max_age_seconds parameter for cleanup")
            return 0
            
        try:
            removed_count = 0
            current_time = time.time()
            
            with self.conversation_lock:
                # Find stale conversations
                stale_conversations = []
                for call_sid, conv in list(self.conversations.items()):
                    # Ensure 'state' exists with 'last_interaction_time'
                    if 'state' not in conv or 'last_interaction_time' not in conv['state']:
                        # If state is missing, consider it stale
                        stale_conversations.append(call_sid)
                    elif current_time - conv['state']['last_interaction_time'] > max_age_seconds:
                        stale_conversations.append(call_sid)
                
                # Remove stale conversations
                for call_sid in stale_conversations:
                    del self.conversations[call_sid]
                    removed_count += 1
                
                # Clean up related data structures
                stale_responses = [
                    response_token for response_token, response_info in list(self.active_responses.items())
                    if response_info['call_sid'] in stale_conversations
                ]
                
                for response_token in stale_responses:
                    del self.active_responses[response_token]
                
                self.logger.info(f"Removed {removed_count} stale conversations")
                return removed_count
        except Exception as e:
            self.logger.error(f"Error cleaning up stale conversations: {str(e)}")
            return 0
            
    def cleanup_conversation(self, call_sid: str) -> bool:
        """
        Clean up a specific conversation by call SID
        
        Args:
            call_sid: Unique identifier for the call to clean up
            
        Returns:
            True if conversation was removed, False otherwise
        """
        if not call_sid:
            self.logger.error("Cannot cleanup conversation with empty call SID")
            return False
            
        try:
            with self.conversation_lock:
                if call_sid not in self.conversations:
                    self.logger.warning(f"Call SID {call_sid} not found when cleaning up conversation")
                    return False
                
                # Remove the conversation
                del self.conversations[call_sid]
                
                # Clean up related active responses
                response_tokens_to_remove = [
                    response_token for response_token, response_info in list(self.active_responses.items())
                    if response_info['call_sid'] == call_sid
                ]
                
                for response_token in response_tokens_to_remove:
                    del self.active_responses[response_token]
                
                self.logger.info(f"Cleaned up conversation for call SID: {call_sid}")
                return True
        except Exception as e:
            self.logger.error(f"Error cleaning up conversation for call SID {call_sid}: {str(e)}")
            return False

# Initialize a global enhanced conversation manager
global_enhanced_conversation_manager = EnhancedConversationManager()

def start_conversation_cleanup(conversation_manager, interval=3600):
    """
    Start a background thread to periodically clean up stale conversations
    
    Args:
        conversation_manager: ConversationManager instance
        interval: Time between cleanup runs (in seconds)
    """
    if interval <= 0:
        conversation_manager.logger.error(f"Invalid cleanup interval: {interval}")
        interval = 3600  # Use default if invalid
        
    def cleanup_worker():
        while True:
            try:
                # Use the conversation manager's cleanup method
                removed = conversation_manager.cleanup_stale_conversations(interval)
                conversation_manager.logger.info(f"Periodic cleanup removed {removed} stale conversations")
                
                # Sleep between cleanup runs
                time.sleep(interval)
            except Exception as e:
                conversation_manager.logger.error(f"Error in conversation cleanup thread: {e}")
                # Don't crash the thread, just retry after a delay
                time.sleep(60)
    
    # Start as a daemon thread
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    return cleanup_thread

# Start the cleanup thread
cleanup_thread = start_conversation_cleanup(global_enhanced_conversation_manager)