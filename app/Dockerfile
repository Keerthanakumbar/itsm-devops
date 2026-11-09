# Start from the building stage full Python image, which has all the tools needed to install packages
FROM python:3.12 AS build

# Seting the working directory inside the container
WORKDIR /app

# Copy only the list of packages first, so Docker can reuse this step if the list does not change
COPY requirements.txt .

# Install the packages into a separate folder, so we can copy just that folder later
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

#  Run stage: start again from the slim Python image, which is smaller and has fewer security risks
FROM python:3.12-slim
WORKDIR /app

# Show Python print messages in the logs right away
ENV PYTHONUNBUFFERED=1

#  Take the installed packages from the build stage and put them where Python looks for them
COPY --from=build /install /usr/local

#  Copy the app code (the .dockerignore file keeps out things like venv)
COPY . .

#  Create a normal user and switch to it, so the app does not run as root (admin)
RUN useradd --system app
USER app

# The app listens on port 5000
EXPOSE 5000

#  Start the app with gunicorn, a production server, using 2 workers to handle requests at the same time
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]