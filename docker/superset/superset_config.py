import os

# --- Production Metadata Repository Database ---
# Superset requires a relational database to store users, configurations, and dashboards.
# We direct it to a secure internal SQLite or PostgreSQL database.
SQLALCHEMY_DATABASE_URI = os.getenv(
    "SUPERSET_METADATA_DB",
    "sqlite:////app/superset_home/superset.db"
)

# Custom secret key configuration for sessions hashing security
SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY", "coindcx_default_production_secure_key_1029384756")

# --- Production Security Policies ---
CSRF_ENABLED = True
WTF_CSRF_ENABLED = True
PREVENT_UNSAFE_DB_CONNECTIONS = True

# Disable loading of demo dashboards to optimize memory footprint
LOAD_EXAMPLES = False

# --- Operational Settings ---
ROW_LIMIT = 5000
SUPERSET_WEBSERVER_PORT = 8088

# Enable Cross-Origin Resource Sharing (CORS) for analytics embeddings
ENABLE_CORS = True
CORS_OPTIONS = {
    "supports_credentials": True,
    "allow_headers": ["Content-Type", "Authorization"],
    "resources": ["/api/v1/*"]
}
