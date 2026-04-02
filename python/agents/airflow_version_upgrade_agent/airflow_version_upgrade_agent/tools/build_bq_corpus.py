import json
import logging
from datetime import datetime, timezone
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from google import genai
from google.genai import types

import os
from pathlib import Path

from dotenv import load_dotenv

# Define the path to the .env file
env_file_path = Path(__file__).parent.parent / ".env"
print(env_file_path)

# Load environment variables from the specified .env file
load_dotenv(dotenv_path=env_file_path)

PROJECT_ID = os.getenv("PROJECT_ID")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET")
BIGQUERY_TABLE = os.getenv("BIGQUERY_TABLE")
BIGQUERY_TABLE_ID = f"{PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"

output_schema = {
    "operator_path": "string", 
    "source_version": "string", 
    "target_version": "string",
    "is_deprecated": "boolean",
    "new_operator_path": "string",
    "parameter_changes": "string",
    "summary": "string",
    "code_example_before": "string",
    "code_example_after": "string",
    "source_urls": ["string"],
    "created_at": "timestamp",
}

bq_client = bigquery.Client(project=PROJECT_ID)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_BQ_TABLE_VERIFIED = False


def ensure_bq_table_exists():
    """
    Checks if the BigQuery table exists and creates it if it does not.
    """
    try:
        bq_client.get_table(BIGQUERY_TABLE_ID)
        logging.info(f"Table {BIGQUERY_TABLE_ID} already exists. No action taken.")
    except NotFound:
        logging.warning(f"Table {BIGQUERY_TABLE_ID} not found. Proceeding to create it.")
        try:
            # Create the dataset if it doesn't exist.
            dataset = bigquery.Dataset(f"{PROJECT_ID}.{BIGQUERY_DATASET}")
            dataset.location = "US" # Or your preferred location
            bq_client.create_dataset(dataset, exists_ok=True)
            logging.info(f"Dataset {BIGQUERY_DATASET} ensured.")

            # Define the schema and create the table
            schema = [
                bigquery.SchemaField("operator_path", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("source_version", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("target_version", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("is_deprecated", "BOOLEAN"),
                bigquery.SchemaField("new_operator_path", "STRING"),
                bigquery.SchemaField("parameter_changes", "JSON"),
                bigquery.SchemaField("summary", "STRING"),
                bigquery.SchemaField("code_example_before", "STRING"),
                bigquery.SchemaField("code_example_after", "STRING"),
                bigquery.SchemaField("source_urls", "STRING", mode="REPEATED"),
                bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            ]
            table = bigquery.Table(BIGQUERY_TABLE_ID, schema=schema)
            bq_client.create_table(table)
            logging.info(f"Successfully created table {BIGQUERY_TABLE_ID}.")
        except Exception as e:
            logging.error(f"Error creating BigQuery dataset or table: {e}")
            raise
    except Exception as e:
        logging.error(f"An unexpected error occurred while checking for table {BIGQUERY_TABLE_ID}: {e}")
        raise


def generate_and_store_knowledge(
    research_results: list[dict], source_version: str, target_version: str
) -> str:
    """
    Processes scraped text with an LLM and stores it in BigQuery as a data corpus.

    Args:
        research_results : List of results from web scrapper
        source_version (str): The source Airflow version for documentation research.
        target_version (str): The target Airflow version for documentation research.

    Returns:
        str: A message indicating the completion of the knowledge base update.
    """
    global _BQ_TABLE_VERIFIED
    
    if not _BQ_TABLE_VERIFIED:
        ensure_bq_table_exists()
        _BQ_TABLE_VERIFIED = True

    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    for result in research_results:
        operator = result["operator"]
        scraped_text = result["content"]
        source_urls = result["urls"]
        
        prompt = f"""
        You are an expert Airflow migration engineer. Your task is to analyze the provided text & URLs 
        and extract specific migration information for an Airflow operator.
        **Context:**
        - Operator to analyze: `{operator}`
        - Migrating from Airflow version: `{source_version}`
        - Migrating to Airflow version: `{target_version}`
        **Source Text & URLs to Analyze:**
        ```
        {scraped_text}
        ```
        **Instructions:**
        Respond ONLY with a single, valid JSON structure adhere to the following schema:
        ```json\n{json.dumps(output_schema, indent=2)}\n```
        """
        try:
            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=prompt
            )
            json_str = response.text.strip().replace("```json", "").replace("```", "")
            structured_data = json.loads(json_str)

            row_to_insert = {
                "operator_path": operator, 
                "source_version": source_version, 
                "target_version": target_version,
                "is_deprecated": structured_data.get("is_deprecated"),
                "new_operator_path": structured_data.get("new_operator_path"),
                "parameter_changes": json.dumps(structured_data.get("parameter_changes", {})),
                "summary": structured_data.get("summary"),
                "code_example_before": structured_data.get("code_example_before"),
                "code_example_after": structured_data.get("code_example_after"),
                "source_urls": source_urls,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            errors = bq_client.insert_rows_json(BIGQUERY_TABLE_ID, [row_to_insert]) 
            if errors:
                raise Exception(f"BigQuery insertion errors: {errors}")
            logging.info(f"Successfully stored knowledge for {operator}")

        except Exception as e:
            logging.error(f"Failed to process and store knowledge for {operator}: {e}")
    
    return "Knowledge base update complete."


# if __name__ == '__main__':
#     from web_scrapper import research_operator_documentation
#     project_id = "<project-id>"

#     # Example usage
#     operator_path = ["airflow.contrib.operators.bigquery_operator.BigQueryOperator",
#         "airflow.operators.bash_operator.BashOperator",
#         "airflow.operators.data_plugins.DataprocsK8sOperator",
#         "airflow.operators.dummy_operator.DummyOperator",
#         "airflow.operators.python_operator.PythonOperator",
#         "airflow.operators.python_operator.PythonVirtualenvOperator",
#         "airflow.operators.slack_operator.SlackAPIPostOperator"]
#     source_version = '1.10'
#     target_version = '2.10.5'
#     scraped_content_dict = research_operator_documentation(operator_path, source_version, target_version, project_id)
#     return_msg = generate_and_store_knowledge(scraped_content_dict, source_version, target_version)
#     print(return_msg)

    