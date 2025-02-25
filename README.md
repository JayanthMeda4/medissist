
# **Tech Stack for Medissist**  

## **1. Transcription Module**  
- **Functionality:** Converts doctor-patient conversations into structured text data.  
- **Technology Used:**  
  - **Service:** Deepgram  
  - **Model:** `nova-3`  
  - **Package:** `deepgram-sdk==3.10.0`  

## **2. Medical Assistant Module**  
- **Functionality:** Handles indexing of transcribed files, linking them to unique patient IDs for retrieval.  
- **Technology Used:**  
  - **Indexing Framework:** LlamaIndex (`llama-index==0.12.14`)  
  - **Embedding Model:** OpenAI Embeddings  
    - **Model:** `text-embedding-3-small`  
    - **Dimensions:** `1536`  
  - **Vector Storage:** Qdrant (`qdrant-client==1.13.2`)  
    - **Text Splitting Strategy:** `SentenceSplitter`  
    - **Chunk Size:** `500`  
    - **Chunk Overlap:** `100`  

## **3. Patient Module**  
- **Functionality:** Enables patients to retrieve insights and interact with their past visit data.  
- **Technology Used:**  
  - **Retrieval:** LlamaIndex  
  - **Query Engine:** OpenAI  
    - **Model:** `o1-mini`  
  - **Retrieval Strategy:**  
    - **Vector Store:** `QdrantVectorStore`  
    - **Similarity Top-K:** `3`  
    - **Response Mode:** `compact`  
  - **Custom Prompting:** Uses a predefined `QA_PROMPT` template to ensure responses remain within medical context.  

## **4. Doctor Module**  
- **Functionality:** Generates SOAP (Subjective, Objective, Assessment, Plan) notes summarizing a patient's past visits.  
- **Technology Used:**  
  - **Summarization Framework:** LlamaIndex  
  - **Summarization Model:** OpenAI  
    - **Model:** `gpt-4o`  
  - **Data Processing:**  
    - Aggregates all patient visits into a **single document** before summarization.  
  - **Indexing Strategy:**  
    - **Summary Index:** `SummaryIndex.from_documents`  
  - **Query Engine:**  
    - Uses a **SOAP-specific prompt** for structured note generation.  

## **5. User Interface (UI) Module**  
- **Functionality:** Provides an interactive web-based interface for both doctors and patients.  
- **Technology Used:**  
  - **Framework:** Streamlit (`streamlit==1.41.1`)  

---

### **Tech Stack**
| Component  | Technology Used |
|------------|----------------|
| **Transcription** | Deepgram (`nova-3`) |
| **Indexing** | LlamaIndex (`llama-index==0.12.14`) |
| **Embedding Model** | OpenAI (`text-embedding-3-small`, 1536D) |
| **Vector Storage** | Qdrant (`qdrant-client==1.13.2`, `SentenceSplitter`) |
| **Retrieval** | LlamaIndex (`similarity_top_k=3`) |
| **Query Model (Patient)** | OpenAI (`o1-mini`) |
| **Summarization Model (Doctor)** | OpenAI (`gpt-4o`) |
| **SOAP Note Indexing** | `SummaryIndex.from_documents` |
| **Response Mode** | `compact` |
| **User Interface** | Streamlit (`streamlit==1.41.1`) |

---



