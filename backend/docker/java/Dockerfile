FROM eclipse-temurin:17-jdk-alpine

# Create a non-root sandbox user
RUN adduser -D -u 1000 sandboxuser

WORKDIR /sandbox

# Give ownership of /sandbox to non-root user
RUN chown -R sandboxuser:sandboxuser /sandbox

USER sandboxuser

CMD ["java"]
