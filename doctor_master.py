from dateutil import parser
from datetime import datetime, timedelta
from pymongo import MongoClient
from openai import OpenAI
import json 
import panel as pn
import os
from dotenv import load_dotenv

mongo_client = MongoClient("mongodb://localhost:27017/")
db = mongo_client["doctor_appointments"]
appointments_collection = db["appointments"]
load_dotenv()
client = OpenAI(
    api_key = os.environ['OPENAI_API_KEY'] #Setup your OpenAI API Key in environment variables. This will be loaded from there.
)
doctor_data = {}

def get_doctor_data():
    with open('doctor_list.json', 'r') as file:
        global doctor_data
        doctor_data = json.load(file)
        return doctor_data

def get_doctors_list():
    get_doctor_data()
    doctors = []
    for doctor in doctor_data['doctor_list']:
        doctors.append(doctor)
    return doctors

def get_doctor_details(attribute):
    doctors = get_doctors_list()
    for doctor in doctors:
        print(doctor[attribute])


def get_list_of_doctors():
    doctors = get_doctors_list()
    doctor_list = []
    for i, doctor in enumerate(doctors, start=1):
        doctor_list.append(f"{i}. {doctor['name']} - {doctor['department']}")
    doctor_list_str = "\n".join(doctor_list)
    return doctor_list_str

def generate_time_slots(start_time, end_time, interval_minutes=30):
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
     
    time_slots = []
    
    current_time = start
    while current_time < end:
        time_slots.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=int(interval_minutes))
    
    return time_slots

def calculate_available_slots(date, doctor, booked_slots=[]):
    available_slots = []
    date_obj = parser.parse(date)
    day = date_obj.strftime('%A') 
    if day in doctor['availableDays']:
        available_slots = generate_time_slots(doctor['checkinTime'], doctor['checkoutTime'], doctor['appointmentSlotInMin'])
        available_slots = set(available_slots) - set(booked_slots)
   
    return list(sorted(available_slots))


def get_available_slots(doctor_name, date):
    doctors = get_doctors_list()
    slots = []
    booked_slots=[]
    for doctor in doctors:
        if doctor['name'] == doctor_name:
            booked_slots= get_doctor_appointments(doctor_name, date)
            slots = calculate_available_slots(date, doctor, booked_slots)
    if len(slots) == 0:
        slots_str = f"No slots available for {doctor_name} on {date}. Please choose another date."
    else:
        slots_str = f"Available slots for {doctor_name} on {date} are: {slots}"
    return slots_str

def save_appointment(doctor_name, patient_name, appointment_date, appointment_time):
    
    appointment_record = {
        "doctor_name": doctor_name,
        "patient_name": patient_name,
        "appointment_date": appointment_date,  
        "appointment_time": appointment_time,
        "created_at": datetime.now()  
    }

    result = appointments_collection.insert_one(appointment_record)

    print(f"Appointment saved with ID: {result.inserted_id}")

def get_doctor_appointments(doctor_name, appointment_date):

    result = appointments_collection.find({
        "doctor_name": doctor_name, 
        "appointment_date": appointment_date
        })

    booked_slots = []
    for appointment in result: 
        booked_slots.append(appointment['appointment_time'])
    return list(sorted(booked_slots))

functions = [
    {
        "name": "get_list_of_doctors",
        "description": "Get the doctor names and their departments",
        "parameters": {}
    },
    {
        "name": "get_available_slots",
        "description": "Get the available slots for the doctor on the given date",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {
                    "type": "string",
                    "description": "Name of the doctor. Use get_list_of_doctors to get the list of doctors. Send the name of the doctor from the list along with proper case."
                },
                "date": {
                    "type": "string",
                    "description": "Date of the appointment. convert it to the format 'dd/mm/yyyy'"
                }
            },
            "required": ["doctor_name", "date"]
        }
    },
    {
        "name": "save_appointment",
        "description": "Save the appointment details",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {
                    "type": "string",
                    "description": "Name of the doctor. Use get_list_of_doctors to get the list of doctors. Send the name of the doctor from the list along with proper case."
                },
                "patient_name": {
                    "type": "string",
                    "description": "Name of the patient."
                },
                "appointment_date": {
                    "type": "string",
                    "description": "Date of the appointment. convert it to the format 'dd/mm/yyyy'"
                },
                "appointment_time": {
                    "type": "string",
                    "description": "Provide the slot time in 'hh:mm' format. Use get_available_slots to get the available slots. slot time to be available in available slots else reject."
                }
            },
            "required": ["doctor_name", "patient_name", "appointment_date", "appointment_time"]
        }
    }
]

context = [{"role": "system", "content": """
             You are an helpful AI assistance to book an appointment with a doctor.
             Where ever required call the respective functions provided to get the data. 
             Ensure you collect the following details before booking an appointment
                - patient name
                - doctor name
                - appointment date
                - appointment time
             Once appointment details are gathered, save the appointment details. Confirm appointment only after Saving the appointment in DB.
             Be clear and precise in your responses."""}]

def get_completion_from_messages(context):

    class Response:
        def __init__(self, content):
            self.content = content

    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=context,
        functions=functions,
        function_call="auto",
        temperature=0
    )

    print(completion)

    if completion.choices[0].message.function_call is not None:
        function_name = completion.choices[0].message.function_call.name
        arguments_str  = completion.choices[0].message.function_call.arguments

        arguments = json.loads(arguments_str)

        if function_name == "get_list_of_doctors":
            response_content = get_list_of_doctors()
        elif function_name == "get_available_slots":
            response_content = get_available_slots(arguments['doctor_name'], arguments['date'])
        elif function_name == "save_appointment":
            save_appointment(arguments['doctor_name'], arguments['patient_name'], arguments['appointment_date'], arguments['appointment_time'])
            response_content = "Appointment saved successfully!"
        else:
            response_content = "I am not sure how to help you with that."

        response = Response(response_content)
        return response

    return completion.choices[0].message


def collect_messages(_):
    prompt = inp.value_input
    inp.value = ''
    context.append({'role':'user', 'content':f"{prompt}"})
    response = get_completion_from_messages(context)
    context.append({'role':'assistant', 'content':f"{response.content}"})
    panels.append(
        pn.Row('User:', pn.pane.Markdown(prompt, width=600)))
    panels.append(
        pn.Row('Assistant:', pn.pane.Markdown(response.content, width=6000)))

    return pn.Column(*panels)

pn.extension()

panels = []
inp = pn.widgets.TextInput(value="Hi", placeholder='Enter text here…')
button_conversation = pn.widgets.Button(name="Chat!")
interactive_conversation = pn.bind(collect_messages, button_conversation)

dashboard = pn.Column(
    inp,
    pn.Row(button_conversation),
    pn.panel(interactive_conversation, loading_indicator=True, height=300),
)

dashboard.servable()