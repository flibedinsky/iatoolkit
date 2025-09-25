# Quickstart Guide: Creating a New Company Implementation

This guide will show you how to create a new company-specific implementation 
for IAToolkit, using `sample_fintech` as a template.

## Step 1: Copy and Rename the Example Module

The first step is to duplicate the example implementation.

1.  Navigate to the `companies/` folder.
2.  Copy the entire `sample_fintech` folder.
3.  Rename the copy with your company's name. For this guide, we'll use `my_company`.
4.  Adapt my_company.py to your needs.
5. **Important:** Don't forget to also rename the file `sample_fintech.py` to `my_company.py`. And the class name to `MyCompany`.

You should now have a structure like this:

companies/ ├── my_company/ │ ├── context/ │ ├── prompts/ │ ├── schema/ │ ├── **init**.py │ ├── configuration.py │ └── my_company.py (formerly sample_fintech.py) └── sample_fintech/


## Step 2: Update Internal References

Inside your new `companies/my_company/` folder, you need to replace all 
mentions of the old name (`sample_fintech`) with the new one (`my_company`).

Use your code editor's "Find and Replace" feature across the `companies/my_company` folder to change:

*   Every occurrence of the string `sample_fintech` to `my_company`.
*   The main class name, for example, from `SampleFintech` to `MyCompany`.

This is crucial in files like `my_company.py` and `configuration.py`.

## Step 3: Register the New Company in the Application

For IAToolkit to recognize your new implementation, you must register it in the main application.

1.  Open the `app.py` file (or wherever you manage company initialization).
2.  Look for the section where `sample_fintech` is imported and registered.
3.  Add the import for your new company and register it in the same way.
4. Create the api-key for your new company.
5. set-up the LLM API-key for your new company
6. IATOOLKIT_BASE_URL

## Step 4: Customize the Implementation

Your "Hello World" implementation is now registered! You can now begin to customize it. The key directories to modify are:

*   `prompts/`: Modify the text files here to give your chatbot its personality, instructions, and specific knowledge.
*   `context/`: Add the documents (PDF, text, etc.) that will serve as context for the LLM's responses.
*   `my_company.py`: This is where you can define **custom tools** and business logic specific to your company.
*   `configuration.py`: Adjust settings, such as the language models to use, and other specific parameters.

## Step 5: Test!

Start the application as you normally would. Your new company implementation should now be loaded and ready to be used through the API or the corresponding interface.

Congratulations, you have extended IAToolkit with your own business logic!

