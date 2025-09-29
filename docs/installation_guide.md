# IAToolkit Installation and Onboarding Guide

Welcome to IAToolkit! 
This guide provides a comprehensive walkthrough for setting up the IAToolkit framework, 
creating your first "company" module, and understanding its core configuration concepts.

## Understanding the "Company" Concept

IAToolkit is a multi-tenant framework designed to serve multiple, isolated companies (or projects) from a single core application. 
A Company is not just a user or a profile; it is a self-contained Python module that encapsulates 
all the specific data, logic, and context required for 
the AI to operate within a particular business domain.

### Anatomy of a Company Module

Every Company resides in its own directory within the `companies/` folder. 
An an example, `companies/sample_company/` provides a complete implementation forr sample_company. 
Here is the breakdown of its essential components:

*   **`sample_company.py`**: This is the heart of your module. It contains a primary class (e.g., `SampleCompany`) that inherits from `iatoolkit.base_company.BaseCompany`. This class is where you define:
    *   **Custom Tools**: Python functions that the AI can execute. This is how you connect the AI to your existing databases, internal APIs, or any other data source. For example, a tool to `get_sales_data(region, date_range)`.
    *   **Business Logic**: Methods to handle specific data lookups, like `get_user_info()` or `handle_request()`.
    *   **CLI Commands**: Custom Flask CLI commands for administrative tasks, such as populating a database.

*   **`context/`**: This directory contains `.md` (Markdown) files. Any text you place here—business rules, operational procedures, product descriptions, FAQs—is automatically loaded into the AI's system prompt. This is the primary way to provide the AI with the static, domain-specific knowledge it needs to answer questions accurately.

*   **`schema/`**: This directory holds `.yaml` files that define data structures. These can be database table schemas, API response structures, or any other structured data. By providing these schemas, you enable the AI to understand your data models, allowing it to generate precise SQL queries or correctly interpret API responses.

*   **`prompts/`**: This directory is for `.prompt` files, which are Jinja2 templates. They are used for complex, multi-step tasks or for generating structured outputs. You can instruct the AI to use a specific prompt to perform a task, guiding its reasoning process.

By leveraging this structure, you can build a powerful, context-aware AI agent that is deeply integrated with your unique business environment.

---

## Step-by-Step Installation Guide

### Step 1: Project Setup

First, set up your local environment and install the necessary dependencies.

1.  **Clone the Repository**:
    ```bash
    git clone <your-repository-url>
    cd iatoolkit-core
    ```

2.  **Create and Activate a Virtual Environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

### Step 2: Environment Configuration

Configure the core settings of the application by creating a `.env` file.

1.  **Create the `.env` file** in the project's root directory. You can copy the provided `.env.example` if it exists.

2.  **Edit the `.env` file** with your specific configuration. 

### Step 3: Initialize the IAToolkit Database

Run the following command to create the necessary tables for the IAToolkit core system in the database specified by `DATABASE_URI`.

```bash
flask setup-all-companies
```

This command initializes system prompts and functions, and it ensures that any companies already registered in the code are synced with the database.

### Step 4: Create Your First Company Module

Now, let's create a new Company by scaffolding it from the sample_company.
1. Duplicate the Folder: In the companies/ directory, copy sample_company and rename the copy to my_company.
2. Rename the Core File: Inside companies/my_company/, rename sample_company.py to my_company.py.
3. Update the Class Name: Open my_company.py and change the class name from SampleCompany to MyCompany.
4. Register the New Company: open app.py and add the following lines:
```
from .my_company import MyCompany
from iatoolkit.company_registry import register_company

# The first argument is the unique short_name, the second is the class
register_company("my_company", MyCompany)
```

### Step 5: Setup the New Company and Generate an API Key
Run the built-in setup command for register your new company in the database and generate a secure API key for it.
```
flask setup-company my_company
```

The command will output a new `IATOOLKIT_API_KEY`. 
**Action Required**: Copy this IATOOLKIT_API_KEY and add it to your .env file. 
This key is used by frontends to authenticate with the IAToolkit backend.

### Step 6: Populate Your Company's Database (Optional)
Most companies need access to their own data. IAToolkit allows you to define custom CLI commands for this purpose. 
The sample_company provides a powerful example of how to do this.
To populate the sample database, first ensure SAMPLE_DATABASE_URI is set in your .env file, and then run:
```
flask populate-sample-db
```

this command create tables for customers, products, order and order_items with dummy data.
You can use is as an example of sql access to your own data

### Step 7: Run the Application
You are now ready to start the IAToolkit web server.
```
flask run
```

The application will be available at `http://127.0.0.1:5000` (or the port specified in your Flask configuration). 
You can now navigate to the web interface, register a user, and start chatting with your newly configured AI!

