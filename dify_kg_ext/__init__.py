import os

import dotenv

dotenv.load_dotenv()

APP_NAME = os.getenv("APP_NAME", "dify_kg_ext")