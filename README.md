# Year 4 Dissertation Project Extension
This is the repository where I have uploaded my final dissertation project.

Download the custom Llama 3.2 model I trained specifically for this project extension from:
https://huggingface.co/DanielFHugging/Finetuned-Model-For-a-Tutor-LLM/tree/main

# User Guide (how to setup the program)
The first step is for the user to download the aiCodingAssistant.py, the config.py, the questions.txt, and the sessions.txt. They should put all these files in one directory.
The second step is for the user to download Ollama from ollama.com and set it up so the operating system has a path set to it. The user should use the Ollama documentation at docs.ollama.com/api/introduction, if they have any trouble with the setup.
The third step for the user is to download the 3 billion parameter model at a Q4_KM quant of llama 3.2. The user can do this using this command when typed into a command prompt: Ollama pull llama3.2:3b
The fourth step is to make sure that the user has the model running using the command in the command prompt: Ollama run llama3.2:3b
The final setup step is to run the aiCodingAssistant.py python program using the command prompt and while the user is in the correct directory. The user can also use IDLE to run the program, as that was the main editor that was tested.

