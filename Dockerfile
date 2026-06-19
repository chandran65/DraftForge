FROM ubuntu:22.04

# Avoid prompts during apt installations
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies, FreeCAD, pip, and Xvfb virtual framebuffer
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    freecad \
    python3-freecad \
    xvfb \
    x11-apps \
    && rm -rf /var/lib/apt/lists/*

# Set up work directory
WORKDIR /app

# Copy dependency specifications and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose Streamlit default port
EXPOSE 8501

# Run under xvfb-run to provide virtual GUI context for TechDraw
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
