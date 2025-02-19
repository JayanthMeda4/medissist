import time
import streamlit as st
from db_utils import *
import os
import re
from pathlib import Path
from lc_rag_llama import MedQueryRag

from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource,
)
import httpx

# Initialize session state variables
if "user_verified" not in st.session_state:
    st.session_state.user_verified = False
if "chat_input" not in st.session_state:
    st.session_state.chat_input = True
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_engine" not in st.session_state:
    st.session_state.chat_engine = None
if "pid" not in st.session_state:
    st.session_state.pid = None
if "is_doctor" not in st.session_state:
    st.session_state.is_doctor = False
if "is_patient" not in st.session_state:
    st.session_state.is_patient = False
if "soap_engine" not in st.session_state:
    st.session_state.soap_engine = None
if "patient_directory" not in st.session_state:
    st.session_state.patient_directory = None
if "current_choice" not in st.session_state:
    st.session_state.current_choice = None
if "mabutton" not in st.session_state:
    st.session_state.mabutton = False


def radio_on_change():
    st.session_state.is_doctor = False
    st.session_state.is_patient = False
    st.session_state.soap_engine = None
    st.session_state.chat_engine = None
    st.session_state.messages = []


def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email)


st.set_page_config(page_title="MEDISSIST", layout="wide", initial_sidebar_state="expanded")
st.title("MEDISSIST: *Delivering Answers from Patient-Doctor Conversations*")

with st.sidebar:
    choice = st.radio("User Type", ["Medical Assistant", "Patient", "Doctor", "Transcribe"], on_change=radio_on_change)
    if choice == "Medical Assistant":
        medical_assistant_id = st.text_input(label="**ID**")
        password = st.text_input(label="**Password**", type="password")
        button = st.button(label="**Login**", type="primary")
        if button:
            st.session_state.mabutton = True
        if st.session_state.mabutton and medical_assistant_id and password:
            data = db_fetch(tablename="medical_assistant", fetch_list_ids="*",
                            where={"medical_assistant_id": medical_assistant_id, "password": password},
                            db=db_connect(),
                            output_as_dict=True,
                            close_conn=True)
            if data:
                st.session_state.pid = data[0].get('pid')
                pdata = db_fetch("medissist", fetch_list_ids="*",
                                 where={"pid": st.session_state.pid},
                                 db=db_connect(), output_as_dict=True, close_conn=True)
                st.write(f"**PatientID: {st.session_state.pid}**")

                patient_name = st.text_input(label="Patient Name", value=pdata[0].get('pname'))
                if patient_name != pdata[0].get('pname'):
                    num_affected = db_update("medissist", column_dict={"pname": patient_name},
                              where={"pid": pdata[0].get('pid')}, db=db_connect(),close_conn=True)
                    if num_affected == 1:
                        st.success("Updated Name Successfully")
                uploaded_data = st.file_uploader(label="**Upload Conversation Text File**",
                                                 type=[".txt"], accept_multiple_files=False,
                                                 help="Upload Only Text files")
                if uploaded_data and uploaded_data.size > 10:
                    if not os.path.exists(f"data_storage/"):
                        os.mkdir(f"data_storage/")
                    if not os.path.exists(f"data_storage/{st.session_state.pid}"):
                        os.mkdir(f"data_storage/{st.session_state.pid}")
                    file_name = f"visit_{pdata[0].get('visit_count') + 1}.txt"
                    with open(os.path.join(f"data_storage/{st.session_state.pid}", str(file_name)), "wb") as file:
                        file.write(uploaded_data.getvalue())
                        file.close()
                    with st.spinner("Data is being Indexed..."):
                        med_obj = MedQueryRag(
                            pid=str(st.session_state.pid),
                            file_name=f"data_storage/{st.session_state.pid}/{file_name}",
                            visit_number=pdata[0].get('visit_count') + 1,
                            return_only_boolean=True
                        )
                        index_status = med_obj.return_vector_store()
                        if index_status:
                            is_inserted = db_update("medissist",
                                                    column_dict={"visit_count": pdata[0].get('visit_count') + 1},
                                                    db=db_connect(), where={"pid": st.session_state.pid})
                            if is_inserted == 1:
                                st.session_state.chat_input = True
                                st.success("Data Indexed Successfully")
            else:
                st.error("Invalid Credentials")
    elif choice == "Patient":
        st.session_state.current_choice = choice
        patient_id = st.text_input("Patient ID")
        if patient_id:
            conn = db_connect()
            new_data = db_fetch("medissist", fetch_list_ids="*", where={"pid": patient_id}, db=conn,
                                output_as_dict=True)
            if new_data:
                if st.session_state.pid != patient_id:
                    st.session_state.messages = []
                st.session_state.user_verified = True
                st.session_state.chat_input = False
                st.session_state.pid = patient_id
                st.session_state.is_patient = True
                st.success("Proceed to Chat")
            else:
                st.session_state.user_verified = False
                st.error(f"User with PID:{patient_id} Does not Exist")
    elif choice == "Doctor":
        st.session_state.current_choice = choice
        dpatient_id = st.text_input("Patient ID")
        if dpatient_id:
            new_data = db_fetch("medissist", fetch_list_ids="*",
                                where={"pid": dpatient_id},
                                db=db_connect(),
                                output_as_dict=True, close_conn=True)
            if new_data:
                st.session_state.patient_directory = f"data_storage/{new_data[0].get('pid')}"
                st.session_state.user_verified = True
                st.session_state.chat_input = True
                st.session_state.is_doctor = True
                st.success("Preparing SOAP notes...")
            else:
                st.session_state.user_verified = False
                st.error(f"Invalid Patient ID")
    elif choice == "Transcribe":
        medical_assistant_id = st.text_input("Medical Assistant ID")

        file_name = st.text_input("File Name")
        st.caption("Enter a name for your transcription file. "
                   "Your transcribed text will be saved with this name as a .txt file.")
        print(medical_assistant_id, file_name)
        if medical_assistant_id and file_name:
            print("inside")
            new_data = db_fetch("medical_assistant", fetch_list_ids="*",
                                where={"medical_assistant_id": medical_assistant_id},
                                db=db_connect(),
                                output_as_dict=True, close_conn=True)
            print(new_data)

            if new_data:
                uploaded_data = st.file_uploader(label="**Upload Conversation Text File**",
                                                 type=["mp3", "wav", "aac", "flac", "m4a", "ogg"],
                                                 accept_multiple_files=False,
                                                 help="Upload Only Text files")

                if uploaded_data:
                    with st.spinner("Transcribing your Audio..."):
                        buffer_data = uploaded_data.read()
                        try:
                            deepgram: DeepgramClient = DeepgramClient(api_key=os.getenv('DEEPGRAM_API_KEY'))

                            payload: FileSource = {
                                "buffer": buffer_data,
                            }

                            options: PrerecordedOptions = PrerecordedOptions(
                                model="nova-3",
                                diarize=True,
                            )

                            response = deepgram.listen.rest.v("1").transcribe_file(
                                payload, options, timeout=httpx.Timeout(300.0, connect=10.0)
                            )

                            words = response['results']['channels'][0]['alternatives'][0]['words']

                            # Initialize variables to store the transcription
                            transcription = []
                            current_speaker = None
                            current_line = []

                            # Iterate through the words and group them by speaker
                            for word_info in words:
                                word = word_info['word']
                                speaker = word_info['speaker']

                                # If the speaker changes, append the previous line to the transcription
                                if speaker != current_speaker:
                                    if current_line:
                                        transcription.append(f"Speaker {current_speaker}: {' '.join(current_line)}")
                                        current_line = []
                                    current_speaker = speaker

                                # Add the word to the current line
                                current_line.append(word)

                            # Append the last line if there's any remaining content
                            if current_line:
                                transcription.append(f"Speaker {current_speaker}: {' '.join(current_line)}")

                            # Join the transcription into a single string with newlines
                            final_transcription = "\n\n".join(transcription)
                            st.download_button(label="Download Transcription", data=str(final_transcription),
                                               file_name=file_name)
                        except Exception as e:
                            print(f"Exception: {e}")
            else:
                st.error("Invalid Credentials")



for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
if st.session_state.user_verified and st.session_state.is_patient:
    prompt = st.chat_input("Say Something", disabled=st.session_state.chat_input)
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.spinner("Generating Response"):
            st.session_state.chat_engine = MedQueryRag.get_query_engine(pid=st.session_state.pid)
            st.session_state.messages.append({"role": "user", "content": prompt})
            response = st.session_state.chat_engine.query(prompt)
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
        # Stream the response
        for chunk in response.response_gen:
            full_response += chunk
            time.sleep(0.1)
            response_placeholder.markdown(full_response + "▌")
        response_placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})
elif st.session_state.is_doctor and st.session_state.user_verified:
    with st.spinner("Generating Response"):
        st.session_state.soap_engine = MedQueryRag.create_soap_query_engine(
            patient_dir=st.session_state.patient_directory
        )
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
    # Query the engine with streaming
    streaming_response = st.session_state.soap_engine.query(
        f"Generate SOAP notes for patient {Path(st.session_state.patient_directory).name} combining all visits"
    )
    # Stream the response chunk by chunk
    for chunk in streaming_response.response_gen:
        full_response += chunk
        time.sleep(0.1)  # Simulate a slight delay for streaming effect
        response_placeholder.markdown(full_response + "▌")  # Add a typing cursor effect
    # Finalize the response (remove the cursor)
    response_placeholder.markdown(full_response)
    st.session_state.is_doctor = False
else:
    prompt = st.chat_input("Say Something", disabled=st.session_state.chat_input)
    st.warning("Patient ID not verified, Please verify Patient ID")
