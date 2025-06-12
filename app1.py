from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename
import pytesseract
import cv2
import re
import os
import tempfile
import io
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import re
import spacy
from flask import Flask, request, jsonify, send_file
import numpy as np
import pandas as pd
import tensorflow.compat.v1 as tf
import pickle
import os
tf.disable_v2_behavior()
from flask_cors import CORS     
import tempfile

from textwrap import wrap
from flask import Flask, request, render_template, send_file
from werkzeug.utils import secure_filename

from flask_cors import CORS
from flask import Flask, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFilter

app = Flask(__name__)
CORS(app,origins=["http://localhost:3000"])  # Enable CORS to allow communication with the React frontend

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'

# Ensure upload and processed directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# Allowed file extensions for validation
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Define regex patterns for sensitive information
sensitive_patterns = {
    'Aadhaar Number': r'\b\d{4}\s\d{4}\s\d{4}\b',  # Matches Aadhaar number (12 digits grouped by spaces)
    'PAN Card Number': r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b',  # Matches Indian PAN number format (e.g., HCJPD1913B)
    'Date of Birth': r'\b\d{2}/\d{2}/\d{4}\b',  # Matches DOB in DD/MM/YYYY format (e.g., 28/10/1990)
    'Name': r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b',  # Matches names with first and last name (e.g., Kumar Mahesh)
    'Address': r'(Road|Street|St|Rd|Avenue|Pashan|Block|Hotel|Residency|House|Row|Near|Pune)',  # Matches address keywords
}

nlp = spacy.load("en_core_web_sm")

def extract_text_from_pdf(input_pdf_file):
    """Extract text from a PDF file using pdfplumber."""
    text_by_page = []
    with pdfplumber.open(input_pdf_file) as pdf:
        for page in pdf.pages:
            text_by_page.append(page.extract_text())
    return text_by_page

def redact_with_regex(text, redacted_entities=None):
    """Redact sensitive words based on regular expressions."""
    if redacted_entities is None:
        redacted_entities = {}

    # Define patterns for sensitive data
    patterns = {
        "names": r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b",  # Matches names like "John Doe"
        "age": r"\b\d{1,3}-?year-old\b",  # Matches age descriptions like "45-year-old"
        "locations": r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b(Village|City|Clinic|Center)",  # Matches locations
        "emails": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",  # Matches email addresses
        "phone_numbers": r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",  # Matches phone numbers
    }

    # Track and redact entities consistently
    def replace_with_redacted(match):
        entity = match.group(0)
        if entity not in redacted_entities:
            redacted_entities[entity] = "****"
        return redacted_entities[entity]

    # Apply patterns to redact sensitive data
    for pattern in patterns.values():
        text = re.sub(pattern, replace_with_redacted, text)

    return text, redacted_entities

def redact_with_ner(text, redacted_entities=None):
    """Redact sensitive named entities using NER."""
    if redacted_entities is None:
        redacted_entities = {}

    # Use SpaCy NER to identify entities like persons, organizations, and locations
    doc = nlp(text)

    for ent in doc.ents:
        if ent.label_ in ["PERSON", "ORG", "GPE"]:  # Redact persons, organizations, and places
            if ent.text not in redacted_entities:
                redacted_entities[ent.text] = "****"
            text = text.replace(ent.text, redacted_entities[ent.text])

    return text, redacted_entities

def write_redacted_text_to_pdf(text_by_page):
    """Write redacted text to a new PDF with proper text wrapping."""
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)

    page_width, page_height = letter
    margin = 30
    line_height = 14  # Slightly reduced line height
    max_width = page_width - 2 * margin
    y_position = page_height - margin  # Start writing near the top

    for page_number, page_text in enumerate(text_by_page):
        lines = page_text.split("\n")

        for line in lines:
            # Wrap text to fit within the page width
            wrapped_lines = wrap(line, width=int(max_width / 7))  # Approx 7 chars per cm
            for wrapped_line in wrapped_lines:
                if y_position < margin + line_height:  # New page if text goes below margin
                    c.showPage()
                    y_position = page_height - margin
                c.drawString(margin, y_position, wrapped_line)
                y_position -= line_height

        c.showPage()  # Ensure a new page starts after each text page

    c.save()

    # Return the redacted PDF as a byte stream
    return packet.getvalue()

def redact_pdf(input_pdf_file):
    """Redact sensitive information from a PDF."""
    # Extract text from the PDF
    text_by_page = extract_text_from_pdf(input_pdf_file)

    # Redact sensitive information
    redacted_entities = {}
    redacted_pages = []
    for page_text in text_by_page:
        # First, redact using regex
        redacted_page, redacted_entities = redact_with_regex(page_text, redacted_entities)
        
        # Then, apply NER-based redaction
        redacted_page, redacted_entities = redact_with_ner(redacted_page, redacted_entities)
        redacted_pages.append(redacted_page)

    # Create a redacted PDF from the redacted text
    return write_redacted_text_to_pdf(redacted_pages)

app = Flask(__name__)
CORS(app)


BEST_GENERATOR_FILE = r"C:\Users\parva\OneDrive\Documents\Automated Redaction\best_generator_perf_79.pkl"

# Load the generator's weights
def load_generator(weights_file, z_dim, dim):
    # Placeholder for random input
    Z = tf.placeholder(tf.float32, shape=[None, z_dim])

    # Define generator architecture
    def generator(z):
        G_W1 = tf.Variable(tf.zeros([z_dim, 4 * dim]), name='G_W1')
        G_b1 = tf.Variable(tf.zeros([4 * dim]), name='G_b1')
        G_W2 = tf.Variable(tf.zeros([4 * dim, 4 * dim]), name='G_W2')
        G_b2 = tf.Variable(tf.zeros([4 * dim]), name='G_b2')
        G_W3 = tf.Variable(tf.zeros([4 * dim, dim]), name='G_W3')
        G_b3 = tf.Variable(tf.zeros([dim]), name='G_b3')

        G_h1 = tf.nn.tanh(tf.matmul(z, G_W1) + G_b1)
        G_h2 = tf.nn.tanh(tf.matmul(G_h1, G_W2) + G_b2)
        G_out = tf.nn.sigmoid(tf.matmul(G_h2, G_W3) + G_b3)

        return G_out

    # Initialize session
    G_sample = generator(Z)
    sess = tf.compat.v1.Session()
    sess.run(tf.global_variables_initializer())

    # Restore weights
    with open(weights_file, "rb") as f:
        best_generator_weights = pickle.load(f)
    print("Variables in the model:")
    for var in tf.global_variables():
        print(f"{var.name} (initial value): {sess.run(var)}")

    print("Keys in the pickle file:")
    for key in best_generator_weights.keys():
        print(key)
    
    for var in tf.global_variables():
        var_name = var.name.split(":")[0] 
        if var_name in best_generator_weights:
            weight_shape = best_generator_weights[var_name].shape
            if var.shape == weight_shape:
                print(f"Assigning weight to {var_name}")
                sess.run(var.assign(best_generator_weights[var_name]))
            else:
                print(f"Skipping {var_name} due to shape mismatch: {var.shape} vs {weight_shape}")
        else:
            print(f"WARNING: No weight found for {var.name}")

    return sess, G_sample, Z

# Initialize generator
z_dim = 27 # Define this based on your model
dim = 27    # Define this based on your model
sess, G_sample, Z = load_generator(BEST_GENERATOR_FILE, z_dim, dim)



@app.route('/redact_pdf', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)

        # Redact PDF in memory
        redacted_pdf = redact_pdf(file)

        # Send the redacted PDF back to the user for download
        return send_file(io.BytesIO(redacted_pdf), as_attachment=True, download_name=f"redacted_{filename}", mimetype="application/pdf")

    return "Invalid file format. Only PDFs are allowed.", 400

def allowed_file(filename):
    """Check if the uploaded file is a valid PDF."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf'}

@app.route("/generate_synthetic", methods=["POST"])
def generate_synthetic():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    if "columns" not in request.form:
        return jsonify({"error": "No columns specified for synthetic data generation"}), 400

    # Get uploaded file
    file = request.files["file"]
    input_data = pd.read_csv(file)

    # Get columns for synthetic data generation
    columns_to_generate = request.form["columns"].split(",")
    columns_to_generate = [col.strip() for col in columns_to_generate]

    # Validate columns
    missing_columns = [col for col in columns_to_generate if col not in input_data.columns]
    if missing_columns:
        return jsonify({"error": f"Columns not found in input data: {missing_columns}"}), 400

    # Pass entire dataset to the model for synthetic data generation
    no, dim = input_data.shape
    random_input = np.random.uniform(-1., 1., size=[no, z_dim])
    synthetic_data = sess.run(G_sample, feed_dict={Z: random_input})

    # Adjust synthetic data columns to match the input data
    if synthetic_data.shape[1] != dim:
        if synthetic_data.shape[1] > dim:  # Extra columns
            synthetic_data = synthetic_data[:, :dim]
        else:  # Missing columns
            missing_cols = dim - synthetic_data.shape[1]
            additional_data = np.zeros((synthetic_data.shape[0], missing_cols))
            synthetic_data = np.hstack((synthetic_data, additional_data))

    # Create a synthetic DataFrame
    synthetic_df = pd.DataFrame(synthetic_data, columns=input_data.columns)

    # Replace non-specified columns with original data
    output_data = synthetic_df.copy()
    for col in input_data.columns:
        if col not in columns_to_generate:
            output_data[col] = input_data[col]

    # Save to CSV
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
        tmp_file_path = tmp_file.name
        output_data.to_csv(tmp_file_path, index=False)

    # Return the file to the user
    return send_file(tmp_file_path, as_attachment=True, download_name="synthetic_data.csv", mimetype="text/csv")

def process_file(file_type, input_path):
    """
    Simulates file processing based on the file type.
    For actual implementation, replace this function with redaction logic.
    """
    output_path = os.path.join(app.config['PROCESSED_FOLDER'], f"processed_{os.path.basename(input_path)}")

    # Example logic for different file types
    try:
        if file_type == 'image':
            # Dummy image processing logic
            with open(output_path, 'wb') as f_out:
                f_out.write(b"This is a placeholder for processed image data.")
        elif file_type == 'pdf':
            # Dummy PDF processing logic
            with open(output_path, 'wb') as f_out:
                f_out.write(b"This is a placeholder for processed PDF data.")
        elif file_type == 'csv':
            # Dummy synthetic data generation logic
            with open(output_path, 'w') as f_out:
                f_out.write("ID,Name,Age\n1,John Doe,30\n2,Jane Smith,25\n")
        else:
            return None
    except Exception as e:
        print(f"Error processing file: {e}")
        return None

    return output_path

if __name__ == '__main__':
    app.run(debug=True)
 