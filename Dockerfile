FROM apify/actor-python:3.11

# Copy project
COPY . ./

# Install dependencies
RUN pip install -r requirements.txt

# Install Playwright browsers
RUN python -m playwright install --with-deps chromium

# Run Actor
CMD ["python", "-m", "src.main"]
