import time
import util
import my_global as g

class AppParent():
	__tasks = []
	def __init__(self):
		pass

	def work(self, url, response, data):
		pass
	
	def params_check(self, data, key):
		if key not in data:
			util.print_err("[" + util.get_attr_safe(self, "name", ""), "]not find params:", key)
			return False
		return True
			
	def update_progress(self, progress):
		g.get_value("worker_msg").put({
			"type" : "progress",
			"url" : self._msg["url"], 
			"idx" : self.process_info["idx"],
			"progress" : progress,
			})

	def _clear(self):
		self.__tasks = []

	def begin_listen(self):
		self.process_info["listening"].value = True

	def stop_listen(self):
		self.process_info["listening"].value = False

	def try_remove_task(self, tasks, url):
		i = len(tasks) - 1
		while i >=0:
			if tasks[i]["url"] == url:
				tasks.pop(i)
			i = i - 1

	def sub_task(self, tasks):
		g.get_value("jobs").put(tasks)

	def try_to_add_task(self, task, max_count):
		ret = False
		msg = util.queue_try_get(self.process_info["msg_q"], False)
		if msg is not None:
			self.try_remove_task(self.__tasks, msg["url"])

		if len(self.__tasks) < max_count:
			g.get_value("jobs").put([task])
			self.__tasks.append(task)
			ret = True
		time.sleep(0.001)
		return ret

	def get_self_task_count(self):
		return len(self.__tasks)

	def sub_task_block(self, tasks):
		self.process_info["listening"].value = True
		g.get_value("jobs").put(tasks)
		ret = True
		#waiting for complete
		while len(tasks) > 0:
			msg = util.queue_try_get(self.process_info["msg_q"])
			self.try_remove_task(tasks, msg["url"])
			if not msg["ret"]:
				ret = False
			time.sleep(0.001)
		self.process_info["listening"].value = False
		return ret

	def file_download_block(self, tasks, save_path):
		for item in tasks:
			item["target_module"] = "file_download"
			if "params" not in item.keys():
				item["params"] = {}
			item["params"]["path"] = save_path
		self.sub_task_block(tasks)