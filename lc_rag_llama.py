from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.core import Settings
from dotenv import load_dotenv
from db_utils import *
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, SummaryIndex, DocumentSummaryIndex, \
    get_response_synthesizer
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from datetime import datetime
from qdrant_client.models import Distance, VectorParams
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.chat_engine.types import ChatMode
from llama_index.core import load_index_from_storage, StorageContext
from llama_index.core import PromptTemplate, Response
from pathlib import Path
from llama_index.core import SummaryIndex, Document
from llama_index.core.prompts import PromptTemplate

load_dotenv()
embed_model = OpenAIEmbedding(model="text-embedding-3-small")
llm = OpenAI(model="o1-mini")

QA_PROMPT = PromptTemplate(
    """Context information is below.
    ---------------------
    {context_str}
    ---------------------
    You are a medical assistant that ONLY answers questions about doctor-patient visits from the provided context.
    If a question is unrelated to medical visits, medical history, medications, or patient care documented in the context, 
    respond: "I specialize in analyzing medical visit records. How can I help with this patient's case?"

    Question: {query_str}
    Answer: """
)


class MedQueryRag:
    def __init__(self, pid, file_name, visit_number, return_only_boolean=False,
                 new_convo=False, doctor_name=None, patient_name=None):
        self.pid = pid
        self.new_convo = new_convo
        self.return_only_boolean = return_only_boolean
        self.doctor_name = doctor_name
        self.patient_name = patient_name
        self.filename = file_name
        self.visit_number = visit_number
        self.embed_model = OpenAIEmbedding(model="text-embedding-3-small", dimensions=1536)

    def return_documents(self):
        reader = SimpleDirectoryReader(input_files=[str(self.filename)])
        docs = reader.load_data()
        docs[0].metadata = {"visit_number": self.visit_number, "doctor_name": self.doctor_name,
                            "create_datetime": str(datetime.now()), "patient_name": self.patient_name}
        text_splitter = SentenceSplitter(
            chunk_size=500,
            chunk_overlap=100,
            separator=" ",
            secondary_chunking_regex=r"\n|Doctor: |Patient: |(?<= )"
        )
        return docs, text_splitter

    def return_vector_store(self):
        docs, text_splitter = self.return_documents()
        qc = QdrantClient("http://localhost:6333")
        if not qc.collection_exists(self.pid):
            qc.create_collection(
                collection_name=self.pid,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )
        qdrant_vector_store = QdrantVectorStore(client=qc, collection_name=self.pid)
        print("vector store first index creation")
        storage_context = StorageContext.from_defaults(vector_store=qdrant_vector_store)
        index = VectorStoreIndex.from_documents(documents=docs, transformations=[text_splitter],
                                                storage_context=storage_context)
        return index if not self.return_only_boolean else True

    @classmethod
    def get_existing_vector_store(cls, pid):
        qc = QdrantClient("http://localhost:6333")
        if not qc.collection_exists(pid):
            raise ValueError(f"collection {pid} does not exist")
        qdrant_vector_store = QdrantVectorStore(client=qc, collection_name=pid)
        index = VectorStoreIndex.from_vector_store(qdrant_vector_store)
        return index

    @classmethod
    def return_query_engine(cls, existing_index):
        query_engine = existing_index.as_query_engine(similarity_top_k=3)
        return query_engine

    @classmethod
    def get_metadata(cls, pid):
        data = db_fetch("patient_records", fetch_list_ids="visit_count",
                        where={"pid": pid}, db=db_connect(), output_as_dict=True, close_conn=True)
        return data

    @classmethod
    def get_query_engine(cls, pid):
        query_engine = cls.get_existing_vector_store(pid).as_query_engine(
            llm=llm,
            streaming=True,
            similarity_top_k=3,
            response_mode="compact",
            text_qa_template=QA_PROMPT
        )
        return query_engine

    @classmethod
    def create_soap_query_engine(cls, patient_dir):

        def load_visit_docs(patient_path):
            combined_content = ""
            for visit_file in patient_path.glob("visit_*.txt"):
                with open(visit_file, "r") as f:
                    content = f.read()
                combined_content += f"Visit {visit_file.stem.split('_')[1]}:\n{content}\n\n"

            # Create a single document with all visits combined
            combined_doc = Document(
                text=combined_content,
                metadata={
                    "patient_name": patient_path.name,
                    "category": "medical_visit",
                    "description": "Combined content from all visits"
                }
            )
            return [combined_doc]  # Return a single document  # Return a single document with all visits combined

        # Create custom prompt template
        soap_prompt_template = PromptTemplate(
            "Generate a comprehensive SOAP note for the patient based on ALL their visits. "
            "Combine information from all visits into a single, unified report. "
            "Include details about:\n"
            "- Patient's reported symptoms across all visits (Subjective)\n"
            "- Clinical findings and tests across all visits (Objective)\n"
            "- Diagnoses and progress over time (Assessment)\n"
            "- Treatment plans and medications across all visits (Plan)\n"
            "Maintain a clear and organized structure, grouping related information together. "
            "Do not separate information by visit; instead, synthesize the data into a single, cohesive report.\n"
            "Patient Name: {patient_name}\n\n"
            "Context:\n{context_str}\n\n"
            "SOAP Notes:"
        )

        # Load documents
        patient_path = Path(patient_dir)
        documents = load_visit_docs(patient_path)

        # Create summary index
        index = SummaryIndex.from_documents(documents)

        # Create query engine with custom prompt
        soap_query_engine = index.as_query_engine(
            llm=OpenAI(model="gpt-4o", temperature=0),  # Use GPT-4 or your preferred model
            response_mode="tree_summarize",  # Encourages synthesis of information
            summary_template=soap_prompt_template,
            streaming=True
        )

        return soap_query_engine

    # @classmethod
    # def create_soap_query_engine(cls,patient_dir):
    #     """
    #     Creates a query engine for generating SOAP notes from a patient's visit files.
    #
    #     Args:
    #         patient_dir (str): Path to the patient's directory containing visit files.
    #
    #     Returns:
    #         QueryEngine: A query engine configured to generate SOAP notes.
    #     """
    #
    #     def load_visit_docs(patient_path):
    #         docs = []
    #         for visit_file in patient_path.glob("visit_*.txt"):
    #             # Extract visit number from filename
    #             visit_num = int(visit_file.stem.split("_")[1])
    #
    #             with open(visit_file, "r") as f:
    #                 content = f.read()
    #
    #             # Create document with metadata
    #             metadata = {
    #                 "patient_name": patient_path.name,
    #                 "visit_number": visit_num,
    #                 "category": "medical_visit"
    #             }
    #
    #             docs.append(Document(
    #                 text=content,
    #                 metadata=metadata
    #             ))
    #
    #         return docs
    #
    #     # Create custom prompt template
    #     soap_prompt_template = PromptTemplate(
    #         "Combine all medical visits to create comprehensive SOAP notes. "
    #         "Include details about:\n"
    #         "- Patient's reported symptoms (Subjective)\n"
    #         "- Clinical findings and tests (Objective)\n"
    #         "- Diagnoses and progress (Assessment)\n"
    #         "- Treatment plans and medications (Plan)\n"
    #         "Maintain chronological order of visits where relevant.\n"
    #         "Patient Name: {patient_name}\n\n"
    #         "Context:\n{context_str}\n\n"
    #         "SOAP Notes:"
    #     )
    #
    #     # Load documents
    #     patient_path = Path(patient_dir)
    #     documents = load_visit_docs(patient_path)
    #
    #     # Create summary index
    #     index = SummaryIndex.from_documents(documents)
    #
    #     # Create query engine with custom prompt
    #     soap_query_engine = index.as_query_engine(
    #         llm=OpenAI(model="gpt-4o-mini",temperature=0),
    #         response_mode="tree_summarize",
    #         summary_template=soap_prompt_template,
    #         streaming=True
    #     )
    #
    #     return soap_query_engine


# ce = MedQueryRag.get_query_engine(pid="48001")
# response = ce.query("what is the capital city of US?")
# response.print_response_stream()
