from flask import Flask, render_template, request, redirect, url_for
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential, CredentialUnavailableError, ManagedIdentityCredential
import uuid
import os

app = Flask(__name__)

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


class Todo:
    def __init__(self, id, title, complete):
        self.id = id
        self.title = title
        self.complete = complete

    @staticmethod
    def from_dict(item_dict):
        return Todo(
            id=item_dict['id'],
            title=item_dict['title'],
            complete=item_dict['complete']
        )

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'complete': self.complete
        }


@app.route("/")
def home():
    query = "SELECT * FROM c"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    todo_list = [Todo.from_dict(item) for item in items]
    return render_template("base.html", todo_list=todo_list)


@app.route("/add", methods=["POST"])
def add():
    title = request.form.get("title")
    if not title:
        return redirect(url_for("home"))
    new_todo = Todo(id=str(uuid.uuid4()), title=title, complete=False)
    container.create_item(body=new_todo.to_dict())
    return redirect(url_for("home"))


@app.route("/update/<string:todo_id>", methods=["POST"])
def update(todo_id):
    print(todo_id, request.form)
    try:
        # Retrieve the existing item from the database
        existing_item = container.read_item(item=todo_id, partition_key=todo_id)
        
        # Update the item's fields based on form data
        existing_item['title'] = request.form.get('title', existing_item['title'])
        existing_item['complete'] = 'complete' in request.form

        # Replace the item in the database
        container.replace_item(item=todo_id, body=existing_item)
    except exceptions.CosmosHttpResponseError as e:
        print(f"An error occurred: {e.message}")
    return redirect(url_for("home"))

@app.route("/delete/<string:todo_id>", methods=["POST"])
def delete(todo_id):
    container.delete_item(item=todo_id, partition_key=todo_id)
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)