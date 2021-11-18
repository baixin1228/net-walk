import sys
import re
from urllib.parse import urljoin
sys.path.append("../..")
import util
from AppParent import AppParent

class MainPages(AppParent):
	url_exp = re.compile(r"https://gitee\.com/$")
	def __init__(self):
		pass

	def work(self, url, response, data):
		print(url)
		return False, []