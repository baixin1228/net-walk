import os
import sys
import time
from queue import Empty
from urllib.parse import urljoin,urlunparse,urlparse
import my_global as g

def print_err(*strs):
	strings = ""
	for string in strs:
		strings = strings + str(string) + " "
	print("\033[1;31m" + strings + "\033[0m")

def print_progress(string, progress = 0):
	ts = os.get_terminal_size()
	columns = ts.columns
	string = string.replace("\n", " ")
	string = string[:columns]
	string = string.ljust(columns)
	unshow_count = int(columns * progress / 100)
	print_str = "\033[7m" + string[:unshow_count] + "\033[0m" + string[unshow_count:]
	print('\x1b[2K', end = '')
	print(print_str)
	del(string)
	del(print_str)

def cursor_back(count):
	print("\33[%dA" % count, end = "")

def get_attr_safe(obj, key, default = None):
	if hasattr(obj, key):
		return getattr(obj, key)
	else:
		return default

def get_dic_value_safe(dic, key, default = None):
	try:
		return dic[key]
	except KeyError:
		return default

def create_dir(file_dir):
	if not os.path.exists(file_dir):
		os.makedirs(file_dir)

def save_data(path, data):
	file_dir = path[:path.rfind("/")]
	create_dir(file_dir)

	with open(path, "wb") as f:
		f.write(data)
		f.close()

def url_join(base_url, path):
	if path.startswith("/"):
		return urljoin(base_url, path)
	else:
		return base_url[:base_url.rfind("/") + 1] + path

def queue_try_get(q, p_block = True):
	try:
		return q.get(block = p_block)
	except Empty as e:
		pass
	except KeyboardInterrupt:
		sys.exit()

def pipe_try_recv(pipe):
	try:
		return pipe.recv()
	except KeyboardInterrupt:
		sys.exit()

def get_all_files(rootdir, loop = False, abspath = False):
	_files = []
	if not os.path.exists(rootdir):
		return _files

	if abspath:
		rootdir = os.path.abspath(rootdir)

	list_file = os.listdir(rootdir)
	for i in range(0,len(list_file)):
		path = os.path.join(rootdir,list_file[i])

		if os.path.isdir(path) and loop:
			_files.extend(get_all_files(path, loop))
		if os.path.isfile(path):
			 _files.append(path)
	return _files

def sql_try_create_table(table):
	try:
		create_tb_cmd="CREATE TABLE IF NOT EXISTS " + table + "\
		(key TEXT PRIMARY KEY NOT NULL,\
		value INT NOT NULL);"
		g.get_value("sql_conn").execute(create_tb_cmd)
		g.get_value("sql_conn").commit()
		return True
	except Exception as e:
		print("Create table failed:", e)
		return False

def has_table(table):
	ret = g.get_value(table)
	if ret == None:
		if sql_try_create_table(table):
			g.set_value(table, True)
			ret = True
	return ret

def sql_store(table, key, value):
	if has_table(table) and sql_get(table, key) == None:
		g.get_value("sql_conn").execute("INSERT INTO " + table + " (key, value) \
			  VALUES (\"" + key + "\"," + str(int(value)) + ")")
		g.get_value("sql_conn").commit()

def sql_get(table, key):
	if has_table(table):
		cursor = g.get_value("sql_conn").cursor().execute("select value  from " + table + " where key=\"" + key + "\";")
		for row in cursor:
			return row[0]
	return None