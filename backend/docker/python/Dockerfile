FROM python:3.11-slim

# Create a non-root sandbox user
RUN useradd -m -u 1000 sandboxuser

WORKDIR /sandbox

# Give ownership of /sandbox to non-root user
RUN chown -R sandboxuser:sandboxuser /sandbox

USER sandboxuser

CMD ["python3"]
