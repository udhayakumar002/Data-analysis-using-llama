from rag_service import rag_service

def main():
    print("Initializing RAG system...")
    success, message = rag_service.initialize_rag()
    if success:
        print("✅ RAG system initialized successfully!")
    else:
        print(f"❌ Failed to initialize RAG: {message}")

if __name__ == "__main__":
    main()