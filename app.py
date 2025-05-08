import os
from flask import Flask, render_template, request, jsonify
from openai import AzureOpenAI
from dotenv import load_dotenv
import pandas as pd
import io # For string buffer for df.info()

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Initialize Azure OpenAI client (same as before)
try:
    endpoint = os.getenv("ENDPOINT_URL")
    subscription_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("DEPLOYMENT_NAME")

    if not all([endpoint, subscription_key, deployment]):
        raise ValueError("Missing one or more environment variables: ENDPOINT_URL, AZURE_OPENAI_API_KEY, DEPLOYMENT_NAME")

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=subscription_key,
        api_version="2025-01-01-preview",
    )
except Exception as e:
    print(f"Error initializing Azure OpenAI client: {e}")
    client = None

conversation_history = []

# --- Constants for data summarization ---
MAX_DATA_TABLE_CHARS = 60000  # Target character limit for the df.head().to_string() part
INITIAL_ROWS_TO_TRY = 75     # Start by trying to get this many rows
MIN_ROWS_TO_SHOW = 10        # Show at least this many rows if possible
ROW_DECREMENT_STEP = 10      # Reduce row count by this step if too large

def get_base_system_prompt():
    return (
        "You are an AI assistant specializing in data analysis. Your responses should be clear, concise, and well-formatted using Markdown.\n\n"
        "**Formatting Guidelines:**\n"
        "- Use **bold** (`**text**`) for emphasis, especially for key findings, monetary values, and important column names.\n"
        "- Use *italics* (`*text*` or `_text_`) for mild emphasis or when defining terms.\n"
        "- Use bullet points (`* ` or `- `) for lists of items or multiple findings.\n"
        "- When referring to specific column names from the dataset, enclose them in backticks (e.g., `Column Name`) or bold them.\n"
        "- For code snippets or data representations if necessary (though detailed data is already provided), use triple backticks (```text```).\n"
        "- Present numerical results clearly. For example: \"The total `Sales Volume` is **1,234,567 units**.\"\n"
        "- Structure longer answers with headings (e.g., `## Key Observations`) if it improves readability.\n\n"
        "**Task Context:**\n"
        "The user will provide a file (Excel or CSV). A detailed summary of this file, "
        "including data types, statistical overview, and a data snippet (a variable number of initial rows), will be provided to you by the 'assistant' role after file processing. "
        "Use ALL this information to understand the data's structure and content. "
        "The backend holds the full dataset. If the user's query requires analysis beyond the provided summary "
        "(e.g., calculations on the entire dataset, specific filtering, aggregations), "
        "clearly state what computation is needed on the full data. "
        "Answer user questions based on the provided data summary. If the summary is insufficient, "
        "explain what additional information or computation on the full dataset is required."
    )

def initialize_conversation_history():
    global conversation_history
    conversation_history = [
        {
            "role": "system",
            "content": [{"type": "text", "text": get_base_system_prompt()}]
        }
    ]

initialize_conversation_history()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_handler():
    global conversation_history
    if not client:
        return jsonify({"error": "Azure OpenAI client not initialized. Check server logs."}), 500

    user_message_text = request.form.get('message', '')
    file = request.files.get('file')

    file_processed_successfully_flag = False
    # file_summary_for_chat_frontend = None # We'll let AI's response handle this

    if file and file.filename:
        filename = file.filename
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        df = None
        sheet_names = None
        
        initialize_conversation_history() # Reset history for new file context

        try:
            file_stream = io.BytesIO(file.read())
            file_stream.seek(0)

            if file_ext in ['xlsx', 'xls']:
                xls = pd.ExcelFile(file_stream)
                sheet_names = xls.sheet_names
                if sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet_names[0])
                else:
                    raise ValueError("No sheets found in the Excel file.")
            elif file_ext == 'csv':
                df = pd.read_csv(file_stream)
            else:
                raise ValueError(f"Unsupported file type: '{file_ext}'. Please upload .xlsx, .xls, or .csv")

            if df is not None and not df.empty:
                # 1. Get df.info() as string
                info_buffer = io.StringIO()
                df.info(buf=info_buffer)
                df_info_str = info_buffer.getvalue()

                # 2. Get df.describe() as string
                # For mixed-type data, describe() might only show numerical.
                # df.describe(include='all') gives more but can be very wide.
                # Let's get default and if object columns exist, get describe for them too.
                df_describe_numerical_str = df.describe(include='number').to_string()
                df_describe_object_str = ""
                if any(df.select_dtypes(include='object').columns):
                     df_describe_object_str = df.describe(include='object').to_string()


                # 3. Get adaptive data snippet (df.head(N))
                num_rows_for_snippet = INITIAL_ROWS_TO_TRY
                head_data_str = ""
                while num_rows_for_snippet >= MIN_ROWS_TO_SHOW:
                    # Ensure we don't try to get more rows than available
                    actual_rows_to_take = min(num_rows_for_snippet, len(df))
                    if actual_rows_to_take == 0: # Handle empty dataframe after potential filtering etc.
                        head_data_str = "The data frame is empty or has no rows to display."
                        break

                    temp_head_str = df.head(actual_rows_to_take).to_string()
                    if len(temp_head_str) <= MAX_DATA_TABLE_CHARS:
                        head_data_str = temp_head_str
                        num_rows_for_snippet = actual_rows_to_take # Store actual number of rows shown
                        break
                    
                    if num_rows_for_snippet == MIN_ROWS_TO_SHOW: # Last attempt with min_rows
                        head_data_str = temp_head_str[:MAX_DATA_TABLE_CHARS] + "\n... (data truncated to fit limit)"
                        num_rows_for_snippet = actual_rows_to_take
                        break
                    
                    num_rows_for_snippet -= ROW_DECREMENT_STEP
                
                if not head_data_str and len(df) > 0: # Fallback if loop didn't set it (e.g. even MIN_ROWS is too big)
                    actual_rows_to_take = min(MIN_ROWS_TO_SHOW, len(df))
                    head_data_str = df.head(actual_rows_to_take).to_string()[:MAX_DATA_TABLE_CHARS] + "\n... (data truncated to fit limit)"
                    num_rows_for_snippet = actual_rows_to_take


                file_summary_for_ai = (
                    f"The user has provided a file named '{filename}' (Type: {file_ext.upper()}).\n"
                )
                if sheet_names:
                    file_summary_for_ai += f"Processed Sheet: '{sheet_names[0]}' (Available sheets: {', '.join(sheet_names)}).\n"
                
                file_summary_for_ai += "\n--- Data Overview & Types ---\n"
                file_summary_for_ai += f"{df_info_str}\n"
                
                file_summary_for_ai += "\n--- Statistical Summary (Numerical Columns) ---\n"
                file_summary_for_ai += f"{df_describe_numerical_str}\n"

                if df_describe_object_str:
                    file_summary_for_ai += "\n--- Statistical Summary (Categorical/Object Columns) ---\n"
                    file_summary_for_ai += f"{df_describe_object_str}\n"

                file_summary_for_ai += f"\n--- Data Snippet (First {num_rows_for_snippet} Rows) ---\n"
                file_summary_for_ai += f"{head_data_str}\n\n"
                file_summary_for_ai += "Based on this comprehensive summary, please address the user's query. The full dataset is available on the backend for more complex operations if needed."
                
                conversation_history.append({
                    "role": "assistant", # AI acknowledges processing and presents the summary
                    "content": [{"type": "text", "text": f"Okay, I've processed the file '{filename}'. Here's a detailed summary:\n\n{file_summary_for_ai}"}]
                })
                file_processed_successfully_flag = True
            elif df is not None and df.empty: # df is not None but it's empty
                empty_df_message = f"The file '{filename}' (Sheet: '{sheet_names[0]}' if Excel) was processed, but it appears to be empty or contains no data rows."
                conversation_history.append({"role": "assistant", "content": [{"type": "text", "text": empty_df_message}]})
                file_processed_successfully_flag = True # Processed, but it's empty
            else: # df is None
                raise ValueError("Could not read data from the file.")

        except Exception as e:
            print(f"Error processing file {filename if 'filename' in locals() else 'unknown'}: {e}")
            error_message = f"Error processing file '{filename if 'filename' in locals() else 'selected file'}': {str(e)}. Please check the file and try again."
            # Ensure history is initialized before appending error if init failed before this point
            if not conversation_history or conversation_history[0]['role'] != 'system':
                initialize_conversation_history()
            conversation_history.append({"role": "system", "content": [{"type": "text", "text": error_message}]}) # Add error to history
            return jsonify({
                "reply": error_message, # Send error as AI reply so user sees it
                "file_processed_successfully": False
            }), 200 # Return 200 so frontend JS parses it

    # --- End of File Processing Logic ---

    if not user_message_text and file_processed_successfully_flag:
        user_message_text = f"The file '{file.filename}' has been summarized above. What would you like to know or do with this data?"
    elif not user_message_text and not file:
        return jsonify({"reply": "Please type a message or upload a file.", "error": "Empty request"}), 200

    conversation_history.append(
        {"role": "user", "content": [{"type": "text", "text": user_message_text}]}
    )

    try:
        messages_for_api = conversation_history
        # print(f"DEBUG: Prompt to AI will contain {sum(len(m['content'][0]['text']) for m in messages_for_api if m['content'] and m['content'][0]['type']=='text')} characters.")

        completion = client.chat.completions.create(
            model=deployment,
            messages=messages_for_api,
            max_tokens=8000, # Max tokens for the *response*. Can be adjusted.
            temperature=0.7,
            top_p=0.95,
            # frequency_penalty=0, # Keep commented unless specific need
            # presence_penalty=0,  # Keep commented unless specific need
            stop=None,
            stream=False
        )

        ai_response_text = ""
        if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
            ai_response_text = completion.choices[0].message.content
        else:
            ai_response_text = "Sorry, I couldn't get a valid response from the AI at this moment."
        
        # Log token usage from response if available (actual format may vary by API version/SDK)
        # For Azure, usage might be in completion.usage
        if completion.usage:
            print(f"DEBUG: Tokens used: Prompt={completion.usage.prompt_tokens}, Completion={completion.usage.completion_tokens}, Total={completion.usage.total_tokens}")


        conversation_history.append(
            {"role": "assistant", "content": [{"type": "text", "text": ai_response_text}]}
        )
        
        return jsonify({
            "reply": ai_response_text,
            "file_processed_successfully": file_processed_successfully_flag
        })

    except Exception as e:
        error_str = str(e)
        print(f"Error in /chat_handler (API call): {error_str}")
        # Check for specific API errors if possible
        # if "context_length_exceeded" in error_str.lower():
        #     specific_error_msg = "The request was too large and exceeded the model's context limit. Try a smaller file or a more focused query."
        # else:
        #     specific_error_msg = f"An API error occurred: {error_str}"
        return jsonify({"error": f"An API error occurred: {error_str}", "reply": f"Sorry, I encountered an API error: {error_str}"}), 500


if __name__ == '__main__':
    app.run(debug=True)