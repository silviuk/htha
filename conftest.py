import sys
import socket

try:
    import custom_components
    print("DEBUG: conftest custom_components path:", custom_components.__path__, flush=True)
except Exception as e:
    print("DEBUG: conftest custom_components import failed:", e, flush=True)

# On Windows, asyncio's ProactorEventLoop uses socket.socketpair() to set up its self-pipe.
# Since pytest-homeassistant-custom-component disables AF_INET sockets, this fails on Windows.
# We patch socket.socketpair to temporarily bypass the socket guard.
if sys.platform == "win32":
    try:
        import pytest_socket
        
        _real_socketpair = socket.socketpair

        def patched_socketpair(*args, **kwargs):
            pytest_socket.enable_socket()
            try:
                return _real_socketpair(*args, **kwargs)
            finally:
                pytest_socket.disable_socket(allow_unix_socket=True)

        socket.socketpair = patched_socketpair
    except ImportError:
        pass



import pytest

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable custom integrations for all tests in this directory."""
    pass


