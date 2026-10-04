import os
import tempfile

# sifu modules read Path.home() at import time, so HOME must point at a
# throwaway directory before any test module imports them. Without this the
# suite writes into the user's real ~/.sifu (config.json, capture.db).
os.environ["HOME"] = tempfile.mkdtemp(prefix="sifu-test-home-")
