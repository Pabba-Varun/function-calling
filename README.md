# function-calling

 #Pre-requisites
-Install required packages
-Install MongoDB 
-Configure OPENAI_API_KEY in environment variables


#Steps
1. Loading the Doctor list from the doctor_list.json file
2. Writing the required functions to handle the necessary functions 
3. Integrate with OpenAI chat completion
4. Handle the response from OpenAI
5. Save appointments in to DB - MongoDB



#Command to start the program
panel serve doctor_master.py

Open the browser and enter the url - http://localhost:5006/doctor_master it will load the chat dialog 