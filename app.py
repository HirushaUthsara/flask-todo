from flask import Flask, jsonify, request
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential, CredentialUnavailableError
from flask_cors import CORS
import uuid
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Define the Cosmos DB endpoint and database name
endpoint = "https://cosmos-ad-test.documents.azure.com:443/"
DATABASE_NAME = "todo-db"
CONTAINER_NAME = "todo-container"

try:
    # Initialize the AzureCliCredential
    default_credential = DefaultAzureCredential()
    # Create the Cosmos client
    client = CosmosClient(url=endpoint, credential=default_credential)
    print("CosmosClient created")

except CredentialUnavailableError:
    print("Azure CLI is not installed or logged in.")
    exit()

try:
    database = client.get_database_client(DATABASE_NAME)
    container = database.get_container_client(CONTAINER_NAME)
except exceptions.CosmosResourceNotFoundError:
    print(f"Database '{DATABASE_NAME}' or container '{CONTAINER_NAME}' not found.")
    exit()
except exceptions.CosmosHttpResponseError as e:
    print(f"An error occurred: {e.message}")
    exit()


@app.route("/")
def home():
    try:
        query = "SELECT * FROM c"
        items = list(
            container.query_items(query=query, enable_cross_partition_query=True)
        )
        # Transform the items to match the frontend's expected format
        todos = [
            {"id": item["id"], "title": item["title"], "complete": item["complete"]}
            for item in items
        ]
        return jsonify(todos)
    except Exception as e:
        print(f"Error fetching todos: {str(e)}")
        return jsonify({"error": "Failed to fetch todos"}), 500


@app.route("/add", methods=["POST"])
def add():
    title = request.form.get("title")
    if not title:
        return jsonify({"error": "Title is required"}), 400

    try:
        new_todo = {"id": str(uuid.uuid4()), "title": title, "complete": False}
        container.create_item(body=new_todo)
        return jsonify({"message": "Todo created successfully"}), 201
    except Exception as e:
        print(f"Error creating todo: {str(e)}")
        return jsonify({"error": "Failed to create todo"}), 500


@app.route("/update/<string:todo_id>", methods=["POST"])
def update(todo_id):
    try:
        # Retrieve the existing item from the database
        existing_item = container.read_item(item=todo_id, partition_key=todo_id)

        # Update the item's fields based on form data
        if "title" in request.form:
            existing_item["title"] = request.form["title"]
        existing_item["complete"] = "complete" in request.form

        # Replace the item in the database
        container.replace_item(item=todo_id, body=existing_item)
        return jsonify({"message": "Todo updated successfully"}), 200
    except exceptions.CosmosResourceNotFoundError:
        return jsonify({"error": "Todo not found"}), 404
    except Exception as e:
        print(f"Error updating todo: {str(e)}")
        return jsonify({"error": "Failed to update todo"}), 500


@app.route("/delete/<string:todo_id>", methods=["POST"])
def delete(todo_id):
    try:
        container.delete_item(item=todo_id, partition_key=todo_id)
        return jsonify({"message": "Todo deleted successfully"}), 200
    except exceptions.CosmosResourceNotFoundError:
        return jsonify({"error": "Todo not found"}), 404
    except Exception as e:
        print(f"Error deleting todo: {str(e)}")
        return jsonify({"error": "Failed to delete todo"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
