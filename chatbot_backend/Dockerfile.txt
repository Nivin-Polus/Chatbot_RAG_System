# Use official Python image
FROM python:3.10-slim
 
# Set working directory
WORKDIR /app
 
# Copy requirements file
COPY requirements.txt .
 
# Install dependencies
#RUN pip install --upgrade pip \
#&& pip install --no-cache-dir -r requirements.txt
 
# Copy application code
#COPY app ./app
#COPY start_server.py .
#COPY README.md .
 
# Create necessary directories
RUN mkdir -p storage uploads
 
# Expose port for FastAPI
EXPOSE 8000
 
# Start the server
CMD ["python", "start_server.py"]
