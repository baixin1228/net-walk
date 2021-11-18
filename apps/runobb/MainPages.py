import sys
import re
from urllib.parse import urljoin
sys.path.append("../..")
import util
from AppParent import AppParent

class MainPages(AppParent):
	url_exp = re.compile(r"https://www\.runoob\.com/python/$")
	def __init__(self):
		pass

	def work(self, url, response, data):
		sel = '//a[@target="_top"]'
		i = 0
		res = response.html.xpath(sel, first=False)
		for a in res:
			new_url = urljoin(url, a.attrs["href"])
			self.file_download_block([{"url" : new_url}], "/test")
			self.update_progress(int(i * 100 / len(res)))
			i = i + 1
		return False, []