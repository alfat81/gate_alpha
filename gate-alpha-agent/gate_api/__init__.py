# Local gate_api package for testnet client
# Re-export from installed gate-api package using absolute import
import sys

# Remove local path temporarily to import system package
_local_path = None
for path in sys.path[:]:
    if 'gate-alpha-agent' in path:
        _local_path = path
        sys.path.remove(path)

try:
    from gate_api import ApiClient, Configuration, ApiException, SpotApi
    __all__ = ["ApiClient", "Configuration", "ApiException", "SpotApi"]
finally:
    # Restore local path
    if _local_path:
        sys.path.insert(0, _local_path)
