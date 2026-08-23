import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class TimeoutHTTPAdapter(HTTPAdapter):
	def __init__(self, *args, timeout=30, **kwargs):
		self.timeout = timeout
		super().__init__(*args, **kwargs)

	def send(self, request, **kwargs):
		if kwargs.get("timeout") is None:
			kwargs["timeout"] = self.timeout
		return super().send(request, **kwargs)

def create_session(user_agent: str = None, timeout: int = 30, retries: int = 3, backoff_factor: float = 0.1):
	session = requests.Session()
	
	if user_agent is None:
		user_agent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36"
	
	session.headers.update({
		"User-Agent": user_agent,
		"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
		"Accept-Language": "en-US,en;q=0.5",
		"Connection": "keep-alive",
	})
	
	retry_strategy = Retry(
		total=retries,
		backoff_factor=backoff_factor,
		status_forcelist=[429, 500, 502, 503, 504],
	)
	
	adapter = TimeoutHTTPAdapter(max_retries=retry_strategy, timeout=timeout)
	session.mount("http://", adapter)
	session.mount("https://", adapter)
	
	return session
