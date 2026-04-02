import logging
from google.cloud import storage
from google import genai
from google.genai.types import (
    GenerateContentConfig,
    HttpOptions,
    Retrieval,
    Tool,
    VertexAISearch,
)

import os
from pathlib import Path

from dotenv import load_dotenv

# Define the path to the .env file
env_file_path = Path(__file__).parent.parent / ".env"
print(env_file_path)

# Load environment variables from the specified .env file
load_dotenv(dotenv_path=env_file_path)

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("VERTEX_SEARCH_LOCATION", "global")

def convert_dags(
    source_gcs_uri: str,
    destination_gcs_uri: str,
    source_version: str,
    target_version: str,
    project_id: str,
    bq_collection_id: str,
    bq_data_store_id: str
) -> str:
    """
    Uses Gemini with RAG to convert Airflow DAGs from a source to a destination GCS folder,
    grounded with a Vertex AI Search data store.

    Args:
        source_gcs_uri (str): The GCS URI of the folder containing Airflow DAG files.
        destination_gcs_uri (str): The GCS URI of the folder where converted DAGs will be saved.
        source_version (str): The source Airflow version.
        target_version (str): The target Airflow version.   
        bq_collection_id (str): The ID of the Vertex AI Search collection for BigQuery.
        bq_data_store_id (str): The ID of the Vertex AI Search datastore for BigQuery.

    Returns:
        str: A message indicating the completion of the DAG conversion.
    """
    if not PROJECT_ID or not LOCATION:
        logging.error("Environment variables 'PROJECT_ID' and 'VERTEX_SEARCH_LOCATION' must be set in your .env file.")
        return "DAG conversion failed: Missing environment configuration."
    try:
        storage_client = storage.Client()
        vertex_ai_search_data_store_path = f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/{bq_collection_id}/dataStores/{bq_data_store_id}"
        client = genai.Client(vertexai=True, project=project_id, location="global")

        logging.info(f"Starting DAG conversion from {source_gcs_uri} to {destination_gcs_uri}")

        # 1. List files in the source bucket
        source_bucket_name, source_prefix = source_gcs_uri.replace("gs://", "").split("/", 1)
        dest_bucket_name, dest_prefix = destination_gcs_uri.replace("gs://", "").split("/", 1)
        
        source_blobs = storage_client.list_blobs(source_bucket_name, prefix=source_prefix)
        
        # 2. Iterate and convert each DAG file
        for blob in source_blobs:
            if not blob.name.endswith(".py"):
                continue

            logging.info(f"Converting DAG: {blob.name}")
            original_dag_code = blob.download_as_text()
            
            prompt = f"""
            You are an expert Airflow migration engineer.
            Your task is to convert the following Airflow DAG from version {source_version} to {target_version}.
            Focus on updating operator paths, parameters, and fixing breaking changes.
            Maintain the original structure and logic of the DAG.

            Original DAG Code:
            ```python
            {original_dag_code}
            ```

            Respond ONLY with the complete, converted Python code for the new DAG.
            """

            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash', # Change if needed
                    contents=prompt,
                    config=GenerateContentConfig(
                    tools=[
                        Tool(
                            retrieval=Retrieval(
                                vertex_ai_search=VertexAISearch(datastore=vertex_ai_search_data_store_path)
                            )
                        )
                    ],
                    ),
                )
                converted_dag_code = response.text.strip().replace("```python", "").replace("```", "")

                relative_path = blob.name[len(source_prefix):]
                destination_blob_name = f"{dest_prefix}{relative_path}"

                dest_bucket = storage_client.bucket(dest_bucket_name)
                destination_blob = dest_bucket.blob(destination_blob_name)
                destination_blob.upload_from_string(converted_dag_code, content_type="text/python")
                
                logging.info(f"Successfully converted and saved to gs://{dest_bucket_name}/{destination_blob_name}")

            except Exception as e:
                logging.error(f"Failed to convert DAG {blob.name}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    return "DAG conversion process complete."