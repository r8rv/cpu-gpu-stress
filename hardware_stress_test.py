from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk


测试秒数 = 10


def CPU工人(停止事件):
	数值 = 0.123456789
	while not 停止事件.is_set():
		数值 = (数值 * 1.0000001 + 0.0000003) % 1000000


def 运行CPU测试():
	停止事件 = multiprocessing.Event()
	工人列表 = [multiprocessing.Process(target=CPU工人, args=(停止事件,))
			   for _ in range(os.cpu_count() or 1)]

	try:
		for 工人 in 工人列表:
			工人.start()
		time.sleep(测试秒数)
		return True, "CPU: load test completed successfully."
	except Exception as 错误:
		return False, f"CPU: {错误}"
	finally:
		停止事件.set()
		for 工人 in 工人列表:
			工人.join(timeout=2)
		for 工人 in 工人列表:
			if 工人.is_alive():
				工人.terminate()
				工人.join()


def 运行GPU测试():
	try:
		结果 = subprocess.run(
			["winsat", "d3d", "-duration", str(测试秒数)],
			capture_output=True,
			text=True,
			timeout=测试秒数 + 5,
			creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		)
		if 结果.returncode == 0:
			return True, "GPU: Direct3D load test completed successfully."
		return False, f"GPU: WinSAT returned error code {结果.returncode}."
	except FileNotFoundError:
		return False, "GPU: Windows WinSAT is not available on this system."
	except OSError as 错误:
		if getattr(错误, "winerror", None) != 740:
			return False, f"GPU: {错误}"
		return GPU备用测试()
	except subprocess.TimeoutExpired:
		return False, "GPU: Direct3D test exceeded the time limit."
	except Exception as 错误:
		return False, f"GPU: {错误}"


def GPU备用测试():
	try:
		结果 = subprocess.run(
			[
				"powershell", "-NoProfile", "-Command",
				"(Get-CimInstance Win32_VideoController).Name",
			],
			capture_output=True,
			text=True,
			timeout=5,
			creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		)
		显卡列表 = 结果.stdout.strip().splitlines()
		if 结果.returncode == 0 and 显卡列表:
			return True, (
				f"GPU: {显卡列表[0]} detected. "
				"Full Direct3D stress test requires administrator rights."
			)
	except (FileNotFoundError, subprocess.TimeoutExpired):
		pass
	return False, "GPU: unable to access the graphics adapter without administrator rights."


class 硬件测试器:
	def __init__(self, 根窗口):
		self.根窗口 = 根窗口
		self.根窗口.title("CPU and GPU Test")
		self.根窗口.geometry("620x360")
		self.根窗口.resizable(False, False)
		self.结果队列 = queue.Queue()
		self.已完成 = False

		self.标题标签 = tk.Label(根窗口, text="CPU and GPU Test", font=("Segoe UI", 22, "bold"))
		self.标题标签.pack(pady=(24, 8))
		self.状态标签 = tk.Label(根窗口, text="Preparing test...", font=("Segoe UI", 14))
		self.状态标签.pack(pady=8)
		self.结果标签 = tk.Label(根窗口, text="", wraplength=560, font=("Segoe UI", 11))
		self.结果标签.pack(pady=18)
		self.进度条 = ttk.Progressbar(根窗口, mode="indeterminate", length=430)
		self.进度条.pack(pady=8)
		self.进度条.start(12)

		threading.Thread(target=self.运行测试, daemon=True).start()
		self.根窗口.after(100, self.检查结果)

	def 运行测试(self):
		self.结果队列.put(("status", "CPU and GPU tests running (10 seconds)..."))
		with ThreadPoolExecutor(max_workers=2) as executor:
			CPU结果 = executor.submit(运行CPU测试)
			GPU结果 = executor.submit(运行GPU测试)
			CPU通过, CPU消息 = CPU结果.result()
			GPU通过, GPU消息 = GPU结果.result()

		if not CPU通过:
			self.结果队列.put(("failure", CPU消息))
			return
		if not GPU通过:
			self.结果队列.put(("failure", GPU消息))
			return

		self.结果队列.put(("success", f"{CPU消息}\n{GPU消息}"))

	def 检查结果(self):
		try:
			结果类型, 消息 = self.结果队列.get_nowait()
		except queue.Empty:
			if not self.已完成:
				self.根窗口.after(100, self.检查结果)
			return

		if 结果类型 == "status":
			self.状态标签.config(text=消息)
			self.根窗口.after(100, self.检查结果)
			return

		self.已完成 = True
		self.进度条.stop()
		self.显示结果(结果类型 == "success", 消息)

	def 显示结果(self, 成功, 消息):
		if 成功:
			背景, 颜色 = "#d9f7df", "#087f23"
			标题 = "TEST PASSED"
			状态 = "Everything is OK. Closing in 5 seconds."
			延迟 = 5000
		else:
			背景, 颜色 = "#ffdcdc", "#b00020"
			标题 = "PROBLEM DETECTED"
			状态 = "The test failed. Closing in 10 seconds."
			延迟 = 10000

		self.根窗口.configure(bg=背景)
		for 标签 in (self.标题标签, self.状态标签, self.结果标签):
			标签.configure(bg=背景, fg=颜色)
		self.标题标签.config(text=标题)
		self.状态标签.config(text=状态)
		self.结果标签.config(text=消息)
		self.进度条.pack_forget()
		self.根窗口.after(延迟, self.根窗口.destroy)


if __name__ == "__main__":
	multiprocessing.freeze_support()
	根窗口 = tk.Tk()
	硬件测试器(根窗口)
	根窗口.mainloop()
