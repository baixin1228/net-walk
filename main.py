import os
import sys
import re
import gc
import signal
import time
import sqlite3
import argparse
import shutil
import multiprocessing
from importlib import import_module
from ctypes import c_char_p
from ctypes import c_bool
from queue import Empty
import requests_html
import my_global as g
import util
from AppParent import AppParent

GC_STEP = 100

class FileDownLoad(AppParent):
	url_exp = re.compile(r"^file_download$")
	def __init__(self):
		self.name = "file_download"
		pass

	def work(self, url, session, data):
		if not self.params_check(data, "path"):
			return False
		retry = self._msg["retry"]
		while retry > 0:
			try:
				response = session.get(url, stream = True)
				if response.status_code == 200:
					filesize = int(response.headers["Content-Length"])
					downloaded = 0;
					file_name = url.split("/")[-1]
					path = g.get_value("setting").SAVE_PATH + data["path"]
					util.create_dir(path)
					with open(path + "/" + file_name, "wb") as f:
						for chunk in response.iter_content(chunk_size = 8192):
							f.write(chunk)
							downloaded = downloaded + len(chunk)
							self.update_progress(int(downloaded * 100 / filesize))
				response.close()
				del(response)
				retry = 0
			except Exception as e:
				util.print_err("file_download retry:", e)
				retry = retry - 1;
				time.sleep(0.2)
		return True, []

apps = []
def _init_apps(app_name):
	apps.append(FileDownLoad())
	_setting = None
	_login = None
	for file_path in util.get_all_files("apps/" + app_name):
		py_module_path = file_path.replace(".py", "").replace("/", ".")
		if "setting.py" in file_path:
			_setting = import_module(py_module_path)
			continue
		if "login.py" in file_path:
			_login = import_module(py_module_path)
			continue
		if ".py" in file_path:
			module_name = py_module_path.split(".")[-1]
			apps.append(getattr(import_module(py_module_path), module_name)())
			print("add app obj:", module_name)
	if _setting == None:
		util.print_err("can not find setting.py in app:", app_name)
		sys.exit(-1)
	return _setting, _login

def _downloader(session, url, func = "get", data = None, retry = 3):
	if url.startswith("http"):
		for x in range(retry):
			try:
				if func == "get":
					response = session.get(url)
				if func == "post":
					response = session.post(url, data = data)

				if response.status_code == 200:
					return response
				else:
					del(response)
			except KeyboardInterrupt as e:
				return None
			except Exception as e:
				util.print_err(e)
		util.print_err("core download fail, url:", url)

	return None

def update_progress(idx, url, progress):
	g.get_value("worker_msg").put({
		"type" : "progress",
		"url" : url, 
		"idx" : idx,
		"progress" : progress,
	})

def __process_work(pipe_channel, process_info):
	print("process start.")
	for _app in apps:
		_app.process_info = process_info

	update_progress(process_info["idx"], "", 0)
	i = 0
	while True:
		i = i + 1
		try:
			msg = pipe_channel.recv()
		except KeyboardInterrupt:
			break

		try:
			if "exit" in msg.keys() and msg["exit"]:
				print("stop process.")
				return

			if msg["url"]:
				success = False
				tasks = None
				skip = False
				update_progress(process_info["idx"], msg["url"], 0)
				if util.sql_get(process_info["app"], msg["url"]) == None:
					if msg["target_module"]:

						for _app in apps:
							if _app.url_exp.match(msg["target_module"]):
								_app._clear()
								_app._msg = msg
								success, tasks = _app.work(msg["url"], msg["session"], msg["params"])
								break
					else:

						for _app in apps:
							if _app.url_exp.match(msg["url"]):
								response = _downloader(msg["session"], msg["url"], msg["func"], msg["data"], msg["retry"])
								if response:
									_app._clear()
									_app._msg = msg
									success, tasks = _app.work(msg["url"], response, msg["params"])
									response.close()
									del(response)
								break

					if success:
						util.sql_store(process_info["app"], msg["url"], 1)
				else:
					success = True
					skip = True

				if tasks and len(tasks) > 0:
					g.get_value("jobs").put(tasks)

				update_progress(process_info["idx"], msg["url"], 100)
				#广播消息
				g.get_value("worker_msg").put({
					"type" : "broadcast",
					"url" : msg["url"], 
					"ret" : success,
					"skip" : skip
					})
				process_info["working"].value = False
			del(tasks)
			del(msg)
		except Exception as e:
			util.print_err("__process_work error:", e)
		else:
			pass
		finally:
			if i % GC_STEP == 0:
				gc.collect()
	print("stop process.")

def _add_job(session, url_info):
	setting = g.get_value("setting")
	setting_retry = 3
	if hasattr(setting, "RETRY"):
		setting_retry = setting.RETRY

	_process = g.get_value("process")
	while True:
		for x in range(g.get_value("PROCESS_COUNT")):
			if not _process[x]["working"].value:
				_process[x]["working"].value = True
				url = url_info["url"]
				target_module = util.get_dic_value_safe(url_info, "target_module")
				func = util.get_dic_value_safe(url_info, "func", "get")
				data = util.get_dic_value_safe(url_info, "data", {})
				params = util.get_dic_value_safe(url_info, "params", {})
				retry = util.get_dic_value_safe(url_info, "retry", setting_retry)
				_process[x]["pipe"].send({
					"session": session, 
					"url" : url, 
					"target_module" : target_module, 
					"func" : func, 
					"data" : data, 
					"retry" : retry, 
					"params" : params})
				return
		time.sleep(0.003)

stop_flag = multiprocessing.Manager().Value(c_char_p, False)
def _start_walk(setting, login):
	if hasattr(setting, "LOGIN_URL"):
		if login:
			session = login.login(setting.LOGIN_URL)
		else:
			util.print_err("login.py not find.")
	else:
		session = requests_html.HTMLSession()
		if hasattr(setting, "HEADERS"):
			session.headers.update(setting.HEADERS)

	i = 0
	while True:
		i = i + 1
		try:
			_job = g.get_value("jobs").get(block = True, timeout = 1)
			for url_info in _job:
				_add_job(session, url_info)
			del(_job)
		except Empty as e:
			pass
		finally:
			if i % GC_STEP == 0:
				gc.collect()

		if stop_flag.value:
			break

def try_send_broadcast(msg):
	_process = g.get_value("process")
	if msg["type"] == "broadcast":
		for x in range(g.get_value("PROCESS_COUNT")):
			if _process[x]["listening"].value:
				_process[x]["msg_q"].put(msg)

def try_print_progress(msg):
	setting = g.get_value("setting")
	_process = g.get_value("process")
	if msg["type"] == "progress" and util.get_attr_safe(setting, "SHOW_PROGRESS"):
		_process[msg["idx"]]["other"]["progress"] = msg["progress"]
		_process[msg["idx"]]["other"]["progress_str"] = \
			"idx:" + str(msg["idx"]) + " progress:" + str(msg["progress"]) + "%" + " url:" + msg["url"]
		util.cursor_back(g.get_value("PROCESS_COUNT"))
		for x in range(g.get_value("PROCESS_COUNT")):
			util.print_progress(_process[x]["other"]["progress_str"], _process[x]["other"]["progress"])
		return True
	return False

def _mesg_center_process():
	print("work_mesg start.")
	setting = g.get_value("setting")
	_process = g.get_value("process")
	i = 0
	while True:
		i = i + 1
		try:
			msg = g.get_value("worker_msg").get(block = True)
			try_send_broadcast(msg)
			try_print_progress(msg)

			if not util.get_attr_safe(setting, "SHOW_PROGRESS") and \
				util.get_attr_safe(setting, "DEBUG") and \
				msg["type"] == "broadcast":
				print(msg)

			if msg["type"] == "broadcast" and \
				msg["url"] == util.get_attr_safe(setting, "ROOT_URL"):
				for x in range(g.get_value("PROCESS_COUNT")):
					if not _process[x]["working"].value:
						_process[x]["working"].value = True
						_process[x]["pipe"].send({"exit": True})
				print("work_mesg stop.")
				stop_flag.value = True
			del(msg)
		except KeyboardInterrupt:
			break
		finally:
			if i % GC_STEP == 0:
				gc.collect()
	print("work_mesg stop.")

def main(args):
	print('this message is from main function')
	app_path = os.path.abspath("./apps/" + args.app)
	if not os.path.exists(app_path):
		util.print_err("not find app:", args.app)
		sys.exit(-1)
	database_path = app_path + "/data.db"
	setting, login = _init_apps(args.app)
	if args.clear:
		input("del all data?")
		if os.path.exists(database_path):
			os.remove(database_path)
			print("del database:", database_path)
		if hasattr(setting, "SAVE_PATH") and os.path.exists(setting.SAVE_PATH):
			shutil.rmtree(setting.SAVE_PATH)
			print("del floder:", setting.SAVE_PATH)

	g._init()
	g.set_value("process", [])
	g.set_value("jobs", multiprocessing.Queue())
	g.set_value("worker_msg", multiprocessing.Queue())
	g.set_value("sql_conn", sqlite3.connect(database_path))
	_process = g.get_value("process")
	g.set_value("setting", setting)
	g.set_value("PROCESS_COUNT", setting.PROCESS)

	for x in range(g.get_value("PROCESS_COUNT")):
		process_info = {}
		conn_a,conn_b=multiprocessing.Pipe()
		process_info["app"] = args.app
		process_info["idx"] = x
		process_info["pipe"] = conn_a
		process_info["other"] = {"progress" : 0, "progress_str" : ""}
		process_info["working"] = multiprocessing.Manager().Value(c_char_p, False)
		process_info["listening"] = multiprocessing.Manager().Value(c_char_p, False)
		process_info["msg_q"] = multiprocessing.Queue()
		process_info["process"] = multiprocessing.Process(target=__process_work, args=(conn_b, process_info))
		process_info["process"].daemon = True
		process_info["process"].start()
		_process.append(process_info)

	mesg_process = multiprocessing.Process(target=_mesg_center_process, args=())
	mesg_process.daemon = True
	mesg_process.start()

	try:
		g.get_value("jobs").put([{"url" : setting.ROOT_URL}])
		_start_walk(setting, login)
		for x in range(g.get_value("PROCESS_COUNT")):
			_process[x]["process"].join()
	except KeyboardInterrupt:
		pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(usage="it's usage tip.", description="help info.")
    parser.add_argument("--address", default=80, help="the port number.", dest="code_address")
    parser.add_argument("--flag", choices=['.txt', '.jpg', '.xml', '.png'], default=".txt", help="the file type")
    # parser.add_argument("--port", type=int, required=True, help="the port number.")
    parser.add_argument("--app", type=str, required=True, help="the app.")
    parser.add_argument("-c", "--clear", default=False, action="store_true", help="clear database.")

    args = parser.parse_args()
    main(args)