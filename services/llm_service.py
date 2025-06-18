import google.generativeai as genai
import os
import gc
import time
import shutil
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.document_loaders import PyPDFLoader, TextLoader

load_dotenv()

class LLMAgentService:
    def __init__(self, api_key: str):
        # Make sure api_key is not None or empty
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment variables.")
        self.embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        self.llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.2, google_api_key=api_key)
        self.base_vector_store_path = os.path.join("data", "chroma_db") # Base dir for all agent DBs
        os.makedirs(self.base_vector_store_path, exist_ok=True) # Ensure it exists

    def _get_agent_chroma_path(self, agent_id: int):
        return os.path.join(self.base_vector_store_path, str(agent_id))

    def _escape_braces(self, text):
        if not isinstance(text, str):
            return text
        return text.replace("{", "{{").replace("}", "}}")

    async def process_knowledge_base(self, agent_id: int, file_path: str):
        # Load documents
        if file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        elif file_path.endswith(".txt"):
            loader = TextLoader(file_path)
        # Add more loaders for .csv, .docx etc. using appropriate LangChain loaders
        else:
            raise ValueError("Unsupported file type for knowledge base.")
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(documents)

        # Delete existing vector store for this agent before creating a new one
        agent_chroma_path = self._get_agent_chroma_path(agent_id)
        if os.path.exists(agent_chroma_path):
            try:
                # Try to load and delete any existing Chroma instance
                tmp_vs = Chroma(
                    persist_directory=agent_chroma_path,
                    embedding_function=self.embeddings_model
                )
                del tmp_vs
            except Exception:
                pass
            gc.collect()
            time.sleep(1)  # Give the OS a moment to release handles
            shutil.rmtree(agent_chroma_path) # Clean up old data

        vector_store = await Chroma.afrom_documents(
            chunks,
            self.embeddings_model,
            persist_directory=agent_chroma_path
        )
        vector_store.persist()
        vector_store = None
        gc.collect()
        return agent_chroma_path

    async def get_agent_response(self, agent_id: int, agent_config: dict, user_query: str):
        agent_chroma_path = self._get_agent_chroma_path(agent_id)

        if not os.path.exists(agent_chroma_path) or not os.listdir(agent_chroma_path):
            return agent_config.get("fallback_message", "I'm sorry, I don't have a knowledge base configured yet for this agent.")

        vector_store = Chroma(
            persist_directory=agent_chroma_path,
            embedding_function=self.embeddings_model
        )
        retriever = vector_store.as_retriever()

        # Retrieve relevant documents for context
        docs = await retriever.aget_relevant_documents(user_query)
        context = "\n".join([doc.page_content for doc in docs]) if docs else ""

        system_prompt_template = (
            "You are a helpful AI assistant for the brand \"{brand_name}\".\n"
            "Your purpose is: {purpose}.\n"
            "Maintain a {tone} tone in all your responses.\n"
            "Answer questions based ONLY on the provided context. If you cannot find the answer in the context,\n"
            "politely state that you don't have enough information and provide the fallback message: \"{fallback_message}\".\n\n"
            "Context:\n"
            "{context}"
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_template),
            ("human", "{input}"),
        ])

        # Prepare all variables for the prompt
        prompt_vars = {
            "brand_name": self._escape_braces(agent_config.get("name", "your brand")),
            "purpose": self._escape_braces(agent_config.get("purpose", "answer questions")),
            "tone": self._escape_braces(agent_config.get("tone", "neutral")),
            "fallback_message": self._escape_braces(agent_config.get("fallback_message", "I'm sorry, I cannot answer that based on my current knowledge.")),
            "context": context,
            "input": user_query
        }

        # Generate response
        chain = prompt | self.llm
        response = await chain.ainvoke(prompt_vars)
        return response.content if hasattr(response, "content") else str(response)

llm_service = LLMAgentService(os.getenv("GEMINI_API_KEY"))