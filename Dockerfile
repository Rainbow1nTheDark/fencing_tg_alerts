FROM python:3.10-slim

# 2. Set environment variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing pyc files to disc
# PYTHONUNBUFFERED: Ensures logs are flushed immediately to the stream (crucial for Docker logs)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Set the working directory inside the container
# All future commands will run from here.
WORKDIR /app

# 4. Install dependencies.
# We copy JUST requirements.txt first. This leverages Docker's caching mechanism.
# If requirements haven't changed, it skips the 'pip install' step on rebuilds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the application code into the container.
COPY . .

# 6. Define the command that runs when the container starts.
CMD ["python", "bot.py"]


