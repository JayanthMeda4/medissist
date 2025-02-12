import time
import streamlit as st
from db_utils import *
import os
from pathlib import Path
from lc_rag_llama import MedQueryRag

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


def radio_on_change():
    print("inside user")
    st.session_state.is_doctor = False
    st.session_state.is_patient = False
    st.session_state.soap_engine = None
    st.session_state.chat_engine = None
    st.session_state.messages = []
    # st.session_state.current_choice = choice


st.set_page_config(page_title="MEDISSIST", layout="wide", initial_sidebar_state="expanded")
st.title("MEDISSIST: *Delivering Answers from Patient-Doctor Conversations*")

with st.sidebar:
    choice = st.radio("User Type", ["Medical Assistant", "Patient", "Doctor"], on_change=radio_on_change)
    if choice == "Medical Assistant":
        option = st.selectbox("Patient Type", ["New Patient", "Old Patient"], placeholder="Select Patient Type")
        if option == "Old Patient":
            upid = st.text_input(label="**Patient ID**")
            if upid:
                conn = db_connect()
                data = db_fetch(tablename="userdata", fetch_list_ids="*", where={"pid": upid}, db=conn,
                                output_as_dict=True)
                if data:
                    fdata = st.file_uploader(label="**Upload Conversation Text File**")
                    if fdata and fdata.size > 10:
                        st.session_state.user_verified = True
                        file_name = f"visit_{data[0].get('visit_count') + 1}.txt"
                        with open(os.path.join(f"data_storage/{data[0].get('pname')}", str(file_name)), "wb") as file:
                            file.write(fdata.getvalue())
                            file.close()
                        with st.spinner("Data is being Indexed..."):
                            med_obj = MedQueryRag(
                                pid=upid,
                                file_name=f"data_storage/{data[0].get('pname')}/{file_name}",
                                visit_number=data[0].get('visit_count') + 1,
                                return_only_boolean=True,
                                doctor_name=data[0].get('doctor_name'),
                                patient_name=data[0].get('pname')
                            )
                            index_status = med_obj.return_vector_store()
                            if index_status:
                                is_inserted = db_update("userdata",
                                                        column_dict={"visit_count": data[0].get('visit_count') + 1},
                                                        db=db_connect(), where={"pid": upid})
                                if is_inserted == 1:
                                    st.session_state.chat_input = True
                                    st.success("Data Indexed Successfully")
                else:
                    st.session_state.user_verified = False
                    st.error("Patient ID does not exist")
        else:
            new_upid = st.text_input(label="**Patient ID**")
            if new_upid:
                conn = db_connect()
                new_data = db_fetch("userdata", fetch_list_ids="*", where={"pid": new_upid}, db=conn,
                                    output_as_dict=True)
                if new_data:
                    st.error("Patient with same ID already Exists")
                else:
                    patient_name = st.text_input(label="**Patient Name**")
                    doctor_name = st.text_input(label="**Doctor Name**")
                    doctor_id = st.text_input(label="**Doctor ID**")
                    if doctor_id and doctor_name and patient_name:
                        doctor_exist = db_fetch("userdata", fetch_list_ids="*",
                                                where={"doctor_id": doctor_id},
                                                db=db_connect(), output_as_dict=True)
                        if doctor_exist:
                            doctor_uploaded_data = st.file_uploader(label="**Upload Conversation Text File**",
                                                                    type=[".txt"], accept_multiple_files=False,
                                                                    help="Upload Only Text files", )
                            if doctor_uploaded_data and doctor_uploaded_data.size > 10:
                                st.session_state.user_verified = True
                                if not os.path.exists(f"data_storage/"):
                                    os.mkdir(f"data_storage/")
                                if not os.path.exists(f"data_storage/{patient_name}"):
                                    os.mkdir(f"data_storage/{patient_name}")
                                file_name = f"visit_1.txt"
                                with open(os.path.join(f"data_storage/{patient_name}", str(file_name)), "wb") as file:
                                    file.write(doctor_uploaded_data.getvalue())
                                    file.close()
                                    with st.spinner("Data is being Indexed..."):
                                        med_obj = MedQueryRag(
                                            pid=new_upid,
                                            file_name=f"data_storage/{patient_name}/{file_name}",
                                            visit_number=1,
                                            return_only_boolean=True,
                                            new_convo=True,
                                            doctor_name=doctor_name,
                                            patient_name=patient_name
                                        )
                                        index_status = med_obj.return_vector_store()
                                        if index_status:
                                            is_inserted = db_insert("userdata",
                                                                    column_dict={"pid": new_upid,
                                                                                 "pname": patient_name,
                                                                                 "file_name": f"{str(new_upid)}_{file_name}",
                                                                                 "doctor_name": doctor_name,
                                                                                 "doctor_id": doctor_id,
                                                                                 "visit_count": 1}, db=db_connect())
                                            if is_inserted == 1:
                                                st.success("Data Indexed Successfully")
                                                st.session_state.chat_input = True
                        else:
                            st.session_state.user_verified = False
                            st.error(f"Doctor with ID {doctor_id} Does not exist")
                    else:
                        st.warning("Fill all the Columns")
    elif choice == "Patient":
        st.session_state.current_choice = choice
        patient_id = st.text_input("Patient ID")
        if patient_id:
            conn = db_connect()
            new_data = db_fetch("userdata", fetch_list_ids="*", where={"pid": patient_id}, db=conn,
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
        doctor_id = st.text_input("Doctor ID")
        if dpatient_id and doctor_id:
            new_data = db_fetch("userdata", fetch_list_ids="*",
                                where={"pid": dpatient_id, "doctor_id": doctor_id},
                                db=db_connect(),
                                output_as_dict=True, close_conn=True)
            if new_data:
                st.session_state.patient_directory = f"data_storage/{new_data[0].get('pname')}"
                st.session_state.user_verified = True
                st.session_state.chat_input = True
                st.session_state.is_doctor = True
                st.success("Preparing SOAP notes...")
            else:
                st.session_state.user_verified = False
                st.error(f"User with PID:{dpatient_id} Does not Exist")

print(st.session_state.current_choice, choice, st.session_state.is_doctor, st.session_state.user_verified,
      st.session_state.soap_engine, st.session_state.chat_engine)
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
    print("Inside doc")
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
    print("inside else")
    prompt = st.chat_input("Say Something", disabled=st.session_state.chat_input)
    st.warning("Patient ID not verified, Please verify Patient ID")
