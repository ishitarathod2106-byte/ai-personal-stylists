# Use a lightweight Python Linux environment
FROM python:3.10-slim

# Set the working directory inside the server
WORKDIR /app

# Copy the requirements file and install the libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your website files into the server
COPY . .

# Create the uploads folder so it doesn't crash when saving images
RUN mkdir -p static/uploads

# Hugging Face Spaces require web apps to run on port 7860
EXPOSE 7860

# Start the application using Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]