import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session(user_agent: str = None, retries: int = 3, backoff_factor: float = 0.1):
	"""
	Create a requests session with custom user agent and retry strategy
	
	Args:
		user_agent (str): Custom user agent string
		retries (int): Number of retry attempts
		backoff_factor (float): Backoff factor for retries
	
	Returns:
		requests.Session: Configured session object
	"""
	session = requests.Session()
	
	# Set default user agent if none provided
	if user_agent is None:
		user_agent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36"
	
	session.headers.update({
		"User-Agent": user_agent,
		"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
		"Accept-Language": "en-US,en;q=0.5",
		"Connection": "keep-alive",
	})
	
	# Configure retry strategy
	retry_strategy = Retry(
		total=retries,
		backoff_factor=backoff_factor,
		status_forcelist=[429, 500, 502, 503, 504],
	)
	
	adapter = HTTPAdapter(max_retries=retry_strategy)
	session.mount("http://", adapter)
	session.mount("https://", adapter)
	
	return session
