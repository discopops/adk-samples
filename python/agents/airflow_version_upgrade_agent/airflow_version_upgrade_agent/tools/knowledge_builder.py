from . import dag_parser
from . import web_scrapper
from . import build_bq_corpus
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Define the path to the .env file
env_file_path = Path(__file__).parent.parent / ".env"
print(env_file_path)

# Load environment variables from the specified .env file
load_dotenv(dotenv_path=env_file_path)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_pipeline(gcs_folder_uri: str, source_version: str, target_version: str, project_id: str) -> str:
    """
    Executes a sequential data pipeline to build a knowledge base from Airflow DAGs.

    This function performs the following steps:
    1. Extracts unique Airflow operators from Python files in a GCS folder.
    2. Researches documentation for each operator using a web scraper.
    3. Processes the scraped content with an LLM and stores it in BigQuery.

    Args:
        gcs_folder_uri (str): The GCS URI of the folder containing Airflow DAG files.
        source_version (str): The source Airflow version for documentation research.
        target_version (str): The target Airflow version for documentation research.
        project_id (str): The Google Cloud project ID.

    Returns:
        str: A message indicating the completion of the knowledge base update.
    """
    print("Step 1: Extracting operators from GCS...")
    operators = dag_parser.extract_operators_from_gcs(gcs_folder_uri)
    print(f"Found {operators} unique operators.")
    if not operators:
        return "No operators found to process."

    print("Step 2: Researching operator documentation...")
    research_results = web_scrapper.research_operator_documentation(
        operators=operators,
        source_version=source_version,
        target_version=target_version,
        project_id=project_id
    )
    print(f"Scraped documentation for {len(research_results)} operators.")

    if not research_results:
        return "No documentation found for the operators."

    print("Step 3: Generating and storing knowledge in BigQuery...")
    completion_message = build_bq_corpus.generate_and_store_knowledge(
        research_results=research_results,
        source_version=source_version,
        target_version=target_version
    )
    
    print(f"Pipeline completed successfully, your knowledege base has been updated in {os.getenv('BIGQUERY_TABLE')}")
    return completion_message

# if __name__ == '__main__':
#     # Example usage of the pipeline function
#     gcs_uri = "gs://<bucket-name>/dags"
#     src_ver = "1.10.12"
#     tgt_ver = "2.10.5"
#     project_id = "<project-id>"
    
#     final_status = run_pipeline(gcs_uri, src_ver, tgt_ver, project_id)
#     print(final_status)