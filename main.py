from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import pika
import json
import traceback
from typing import Optional
from fastapi.responses import JSONResponse
import requests

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

# Define the data model for incoming volunteer data with default values for required fields
class Volunteer(BaseModel):
    user_id: int
    username: str
    email: EmailStr  # Mandatory and validated as an email
    first_name: Optional[str] = "FirstName"  # Default value if not provided
    last_name: Optional[str] = "LastName"    # Default value if not provided
    phone: Optional[str] = "0000000000"      # Default value if not provided
    city: Optional[str] = "Unknown"
    state: Optional[str] = "Unknown"
    country: Optional[str] = "Unknown"
    gender: Optional[str] = "Male"  # Default value if not provided
    dob: Optional[str] = "2000-01-01"        # Default date if not provided
    qualification: Optional[str] = "Graduate"
    current_job: Optional[str] = "Unemployed"
    employment_status: Optional[str] = "Others"
    work_exp: Optional[str] = "0"
    languages_known: Optional[str] = "English"
    pref_days: Optional[str] = ""
    pref_slots: Optional[str] = ""

# Function to publish data to RabbitMQ
def publish_to_rabbitmq(message: dict):
    try:
        print('In rabbit mq method')
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        
        # Declare the queue
        channel.queue_declare(queue='volunteer_data_queue', durable=True)
        
        # Publish the message to the queue
        channel.basic_publish(
            exchange='',
            routing_key='volunteer_data_queue',
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)  # Make the message persistent
        )
        
        connection.close()
    except Exception as e:
        error_traceback = traceback.format_exc()
        print('Traceback = ', error_traceback)
        raise HTTPException(status_code=500, detail=f"Error sending data to RabbitMQ: {str(e)}")

@app.post("/submit-volunteer/")
async def submit_volunteer(volunteer: Volunteer):
    try:
        # Display the volunteer data with defaults if necessary
        print('Volunteer = ', volunteer.dict())
        # Publish volunteer data to RabbitMQ
        publish_to_rabbitmq(volunteer.dict())
        return {"message": "Volunteer data sent to consumer application"}
    except Exception as e:
        print('Exception = ', e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def read_root():
    return {"message": "Provider application is running"}


@app.post("/trigger-serve-nominated")
def trigger_serve_nominated():
    try:
        # Fetch data from Serve API
        response = requests.get("https://serve-v1.evean.net/api/v1/serve-need/need/?page=0&status=Nominated")
        response.raise_for_status()
        serve_data = response.json().get("content", [])

        # Connect to RabbitMQ and publish data
        connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        channel = connection.channel()
        channel.queue_declare(queue="serve_data_queue", durable=True)

        for item in serve_data:
            channel.basic_publish(
                exchange="",
                routing_key="serve_data_queue",
                body=json.dumps(item),
                properties=pika.BasicProperties(delivery_mode=2),
            )
        connection.close()

        return {"message": "Data fetched and sent to RabbitMQ"}
    except Exception as e:
        return {"error": str(e)}
    
