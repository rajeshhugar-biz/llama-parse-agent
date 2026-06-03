# pip install llama-index-workflows[client] llama-cloud>=1.0.0
# Docs: https://developers.llamaindex.ai/python/llamaagents/workflows/deployment/#using-workflowclient-to-interact-with-servers

import asyncio
import httpx
from llama_cloud import LlamaCloud
from workflows.client import WorkflowClient
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
WORKFLOW_NAME = os.getenv("WORKFLOW_NAME", "invoice-data-extraction-tool") 



async def main():
    # Step 1: Upload a file to LlamaCloud (if your workflow requires a file)
    llama_cloud = LlamaCloud(api_key=API_KEY)
    with open("document.pdf", "rb") as f:
        file = llama_cloud.files.create(file=f, purpose="user_data")
    file_id = file.id
    print(f"Uploaded file: {file_id}")

    # Step 2: Connect to the workflow API
    httpx_client = httpx.AsyncClient(
        base_url="https://api.cloud.llamaindex.ai/deployments/invoice-data-extraction-tool",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    client = WorkflowClient(httpx_client=httpx_client)

    # List available workflows
    print(await client.list_workflows())

    # Step 3: Run workflow with file_id in start_event
    handler = await client.run_workflow_nowait(
        WORKFLOW_NAME,
        start_event={"file_id": file_id} 
    )

    # Stream events
    async for event in client.get_workflow_events(handler.handler_id):
        print(event.type, event.value)

    # Get final result
    result = await client.get_handler(handler.handler_id)
    print(result.result)

    await httpx_client.aclose()

asyncio.run(main())