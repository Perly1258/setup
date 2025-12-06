import requests
import json
from pydantic import BaseModel, Field

class Tools:
    # Valves allow you to configure these settings in the Open WebUI interface
    # This means you can change the URL or Timeout later without editing this file!
    class Valves(BaseModel):
        rag_api_url: str = Field(
            default="http://localhost:9000/query", 
            description="The full URL endpoint of the custom RAG API."
        )
        timeout: int = Field(
            default=60, 
            description="Timeout in seconds for the API request."
        )

    def __init__(self):
        self.valves = self.Valves()

    def query_rag_api(self, query: str) -> str:
        """
        Ask the custom RAG server to find an answer in the uploaded documents.
        :param query: The question to ask the documents.
        :return: The answer from the RAG system.
        """
        url = self.valves.rag_api_url
        
        try:
            # Send the question to the configured RAG API (Port 9000)
            response = requests.post(
                url, 
                json={"query": query}, 
                timeout=self.valves.timeout
            )
            response.raise_for_status()
            
            # Get the answer back from the API's JSON response
            data = response.json()
            return data.get("response", "No answer found in API response.")
            
        except Exception as e:
            return f"Error connecting to RAG API at {url}: {e}"