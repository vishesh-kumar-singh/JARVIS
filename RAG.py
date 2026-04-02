
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    # Try default initialization (will use CUDA/MPS if available)
    embed_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
except Exception as e:
    print(f"GPU initialization failed for embeddings ({e}). Falling back to CPU...")
    embed_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'}
    )

def RAG(docs, query, embed_model=embed_model, results=5):

    print("Encoding text...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    all_splits = text_splitter.split_documents(docs)
    texts = [doc.page_content for doc in all_splits]
    vectorstore = FAISS.from_texts(texts, embed_model)

    print("Retrieving Relevant Information...")
    retriever = vectorstore.as_retriever(search_kwargs={"k": results})
    
    relevant_docs = retriever.invoke(query)
    context = "\n\n".join([doc.page_content for doc in relevant_docs])

    return context