For reference always into  and supermemory folder before doing thing then give me a comparison of methods they followed and ask me to pick one.

These are my outcomes:
- this will be exposed as FASTAPI so that dashboard can interact with it. SAAS product
- these will be used for pip installation. SDK
- This will also be used for Model Context Protocol MCP where the function will be utilized from SDK
- in future this will be extended to support more advanced features like npm install.

Upto my knowledge we have 
we will have vector database inherite from base.py
we will have embedding inherite from base.py

so our plan is when user types a text input it will converted into embeddings and stored in the vector database. inbetween after converting into embeddings it will be english text will be encrypted and store in the vector database. Embeddings will be not be encrypted.

inmemory folder will be used primarily for SDK - We will support this SDK from python3.10
server folder will be used for hosting the FastAPI application and handling incoming requests.

we are having one vector database collection and all user data will be stored in it and filtered based on the user_id.

so this project will run both 8080 and 8081 port. but there is a another repo called proxy which will act as reverse proxy and route the request to 8080 or 8081 based on the endpoint which is running on 8000 port. My server can only expose 8000 port to public.

Please dont Change the API contract without asking me.