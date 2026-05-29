import os
from typing import List, Dict, Any, Tuple, Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import logging
import json
import certifi

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(".env.example")

class RAGService:
    def __init__(self):
        """Initialize the RAG service with necessary configurations."""
        self.mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
        self.pinecone_api_key = os.getenv('PINECONE_API_KEY')
        self.groq_api_key = os.getenv('GROQ_API_KEY')
        
        # Initialize components
        self.mongo_client = None
        self.db = None
        self.terms_collection = None
        self.vector_store = None
        self.retriever = None
        self.llm = None
        self.qa_chain = None
        
        # Initialize connections
        self._connect_mongodb()
        self._initialize_llm()
    
    def _connect_mongodb(self):
        """Establish connection to MongoDB with error handling."""
        try:
            self.mongo_client = MongoClient(self.mongo_uri, tlsCAFile=certifi.where())
            self.mongo_client.admin.command('ping')  # Test connection
            self.db = self.mongo_client.get_database('revenueLensdb')
            self.terms_collection = self.db.terms_and_conditions
            logger.info("✅ Successfully connected to MongoDB")
        except ConnectionFailure as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            # Continue without MongoDB connection for now
            self.mongo_client = None
    
    def _initialize_llm(self):
        """Initialize the language model with fallback to a simple echo model."""
        try:
            if self.groq_api_key:
                from langchain_groq import ChatGroq
                self.llm = ChatGroq(
                    api_key=self.groq_api_key,
                    model_name='llama-3.3-70b-versatile',
                    temperature=0.1
                )
                logger.info("✅ Initialized ChatGroq LLM")
            else:
                from langchain.schema import HumanMessage
                from langchain.chat_models.base import BaseChatModel
                
                class EchoChatModel(BaseChatModel):
                    """Echo chat model for testing purposes."""
                    def _generate(self, messages, **kwargs):
                        last_message = messages[-1].content
                        return [HumanMessage(content=f"Echo: {last_message}")]
                    
                    def _llm_type(self):
                        return "echo"
                
                self.llm = EchoChatModel()
                logger.warning("⚠️ Using echo model - set GROQ_API_KEY for full functionality")
                
        except ImportError as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise RuntimeError("Failed to initialize language model. Please check your dependencies and API keys.")

    def initialize_rag(self) -> Tuple[bool, str]:
        """Initialize the RAG system with fallbacks."""
        try:
            logger.info("Initializing RAG system...")
            
            # Try to initialize Pinecone if API key is available
            if self.pinecone_api_key:
                try:
                    self._initialize_pinecone()
                    self._create_qa_chain()
                    logger.info("✅ RAG system initialized successfully")
                    return True, "RAG system initialized successfully"
                except Exception as e:
                    logger.error(f"Failed to initialize Pinecone: {e}")
                    return False, f"Failed to initialize RAG system: {e}"
            else:
                logger.warning("⚠️ PINECONE_API_KEY not set. RAG system will run in limited mode.")
                return False, "RAG system not fully initialized - missing Pinecone API key"
                
        except Exception as e:
            error_msg = f"Failed to initialize RAG system: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _initialize_pinecone(self):
        """Initialize Pinecone vector store with error handling."""
        if not self.pinecone_api_key:
            raise ValueError("PINECONE_API_KEY is not set in environment variables")
        
        try:
            from pinecone import Pinecone as PineconeClient, ServerlessSpec
            from langchain.vectorstores import Pinecone
            from langchain.embeddings import HuggingFaceEmbeddings
            
            # Initialize Pinecone client
            pc = PineconeClient(api_key=self.pinecone_api_key)
            index_name = 'revenuelens-terms-qa'
            
            # Check if index exists, create if not
            if index_name not in pc.list_indexes().names():
                logger.info(f"Creating new Pinecone index: {index_name}")
                pc.create_index(
                    name=index_name,
                    dimension=384,  # Dimension for all-MiniLM-L6-v2
                    metric="cosine",
                    spec=ServerlessSpec(cloud='aws', region='us-west-2')
                )
            
            # Initialize embeddings
            embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')
            
            # Initialize Pinecone vector store
            self.vector_store = Pinecone.from_existing_index(
                index_name=index_name,
                embedding=embeddings
            )
            
            # Initialize retriever
            self.retriever = self.vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 3}
            )
            
        except ImportError as e:
            logger.error(f"Failed to import Pinecone dependencies: {e}")
            raise ImportError("Please install required packages: pip install pinecone-client langchain-pinecone")
    
    def _create_qa_chain(self):
        """Create the QA chain for question answering."""
        if not hasattr(self, 'llm') or not self.llm:
            raise RuntimeError("Language model not initialized")
        
        try:
            from langchain.chains import RetrievalQA
            from langchain.prompts import PromptTemplate
            
            # Define prompt template
            template = """You are a helpful AI assistant for RevenueLens. 
            Use the following pieces of context to answer the question at the end. 
            If you don't know the answer, just say that you don't know, don't try to make up an answer.
            
            Context: {context}
            
            Question: {question}
            
            Answer in a clear and concise manner:"""
            
            prompt = PromptTemplate(
                template=template,
                input_variables=["context", "question"]
            )
            
            # Create QA chain
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.retriever,
                return_source_documents=True,
                chain_type_kwargs={"prompt": prompt}
            )
            
        except ImportError as e:
            logger.error(f"Failed to create QA chain: {e}")
            raise
    
    def query(self, question: str) -> Dict[str, Any]:
        """Query the RAG system with a question."""
        if not question or not question.strip():
            return {
                "error": "Question cannot be empty",
                "answer": "Please provide a valid question."
            }
        
        try:
            if not hasattr(self, 'qa_chain') or not self.qa_chain:
                # Fallback to simple LLM response if RAG is not initialized
                if hasattr(self, 'llm') and self.llm:
                    response = self.llm.invoke(question)
                    return {
                        "answer": response.content if hasattr(response, 'content') else str(response),
                        "sources": [],
                        "warning": "RAG system not fully initialized - using basic response"
                    }
                else:
                    return {
                        "error": "RAG system not initialized",
                        "answer": "I'm sorry, but the RAG system is not properly initialized. Please check your configuration and try again later."
                    }
            
            # Get response from QA chain
            result = self.qa_chain({"query": question})
            
            # Extract source documents
            sources = []
            for doc in result.get('source_documents', []):
                sources.append({
                    "content": doc.page_content,
                    "metadata": getattr(doc, 'metadata', {})
                })
            
            return {
                "answer": result.get('result', 'No answer generated'),
                "sources": sources
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "error": str(e),
                "answer": "I encountered an error while processing your request. Please try again later."
            }

# Create a singleton instance of the RAG service
rag_service = RAGService()