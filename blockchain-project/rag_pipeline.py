import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from blockchain import verify_hash_on_chain, calculate_sha256

OFF_CHAIN_DIR = "./off_chain_storage"
os.makedirs(OFF_CHAIN_DIR, exist_ok=True)

embeddings = OpenAIEmbeddings()
vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

def ingest_document(doc_id: str, title: str, text: str, raw_bytes: bytes, access_level: str):
    """Մասնատում է տեքստը chunks-ի, պահպանում off-chain և ինդեքսավորում վեկտորային բազայում"""
    file_path = os.path.join(OFF_CHAIN_DIR, f"{doc_id}.bin")
    with open(file_path, "wb") as f:
        f.write(raw_bytes)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=100
    )
    chunks = splitter.split_text(text)
    metadatas = [
        {
            "doc_id": doc_id,
            "title": title,
            "chunk_index": i,
            "access_level": access_level
        }
        for i in range(len(chunks))
    ]

    vector_db.add_texts(texts=chunks, metadatas=metadatas)

def semantic_search_and_generate(query: str, user_role: str):
    """Կատարում է RBAC զտմամբ որոնում, բլոկչեյն ստուգում և LLM պատասխանի գեներացում"""
    allowed_levels = ["public"]
    if user_role in ["content_manager", "admin"]:
        allowed_levels.extend(["internal", "confidential"])
    elif user_role == "user":
        allowed_levels.append("internal")
    results = vector_db.similarity_search(
        query,
        k=4,
        filter={"access_level": {"$in": allowed_levels}}
    )

    verified_chunks = []
    citations = []
    for doc in results:
        doc_id = doc.metadata["doc_id"]
        file_path = os.path.join(OFF_CHAIN_DIR, f"{doc_id}.bin")
        
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                current_hash = calculate_sha256(f.read())

            if verify_hash_on_chain(doc_id, current_hash):
                verified_chunks.append(doc.page_content)
                citations.append(f"{doc.metadata['title']} (ID: {doc_id}, Հատված #{doc.metadata['chunk_index']})")
            else:
                print(f"[ԱՆՎՏԱՆԳՈՒԹՅԱՆ ԱՀԱԶԱՆԳ] {doc_id} փաստաթուղթը փոփոխվել է off-chain բազայում!")

    if not verified_chunks:
        return {
            "answer": "Տրամադրված և բլոկչեյնով հաստատված փաստաթղթերում հարցմանը վերաբերող բավարար տեղեկատվություն չգտնվեց։",
            "citations": [],
            "blockchain_verified": False
        }

    context_text = "\n\n---\n\n".join(verified_chunks)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Դու կորպորատիվ գիտելիքների օգնական ես։ Պատասխանիր հարցին ԲԱՑԱՌԱՊԵՍ ստորև տրված համատեքստի հիման վրա։ Մի օգտագործիր արտաքին գիտելիքներ և մի հորինիր փաստեր։ Եթե պատասխանը համատեքստում չկա, ազնվորեն հայտնիր այդ մասին։"),
        ("human", "Համատեքստ:\n{context}\n\nՀարց: {question}")
    ])

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    chain = prompt | llm
    response = chain.invoke({"context": context_text, "question": query})

    return {
        "answer": response.content,
        "citations": list(set(citations)),
        "blockchain_verified": True
    }