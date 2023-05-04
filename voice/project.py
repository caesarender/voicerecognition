import sys
import json
import asyncio
import websockets
from PyQt5 import uic
from PyQt5.Qt import *
import pyaudio
import numpy as np
from paddlespeech.cli.log import logger
from paddlespeech.server.bin.paddlespeech_server import ServerExecutor
import pyperclip
import win32api
import win32con
import threading
import gui
import logging
from PyQt5.Qt import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
sample_rate = 16000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载ui文件
ui_file = "./gui.ui"
ui_main_window, _ = uic.loadUiType(ui_file)
class Thread(QThread):
    text_signal = pyqtSignal(str)
    voice_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()

    async def asr(self):
        while 1:
            num_sen = 0
            async with websockets.connect('ws://127.0.0.1:8090/paddlespeech/asr/streaming') as ws:
                audio_info = json.dumps(
                    {"name": "test.wav", "signal": "start", "nbest": 1},
                    sort_keys=True, indent=4, separators=(',', ': '))
                await ws.send(audio_info)
                msg = await ws.recv()
                while 1:
                    b = self.stream.read(85 * 16)
                    numpy_b = np.frombuffer(b, dtype=np.int16)
                    self.voice_signal.emit(int(np.absolute(numpy_b).mean() / 10))
                    await ws.send(b)
                    msg = await ws.recv()
                    msg = json.loads(msg)
                    text = msg['result']
                    if len(text) > num_sen:
                        _t = text[num_sen:len(text)]
                        self.text_signal.emit(_t)
                        if self.paste:
                            pyperclip.copy(_t)
                            win32api.keybd_event(17, 0, 0, 0)
                            win32api.keybd_event(86, 0, 0, 0)
                            win32api.keybd_event(86, 0, win32con.KEYEVENTF_KEYUP, 0)
                            win32api.keybd_event(17, 0, win32con.KEYEVENTF_KEYUP, 0)
                        num_sen = len(text)

                    if len(text) == 0:
                        num_sen = 0
                    if 'signal' in msg.keys():
                        # audio_info = json.dumps(
                        #     {"name": "test.wav", "signal": "end", "nbest": 1},
                        #     sort_keys=True, indent=4, separators=(',', ': '))
                        # await ws.send(audio_info)
                        # msg = await ws.recv()
                        break

    def run(self):
        p = pyaudio.PyAudio()
        self.stream = p.open(format=pyaudio.paInt16, channels=1,
                             rate=sample_rate, input=True,
                             frames_per_buffer=int(85 * 16))

        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.asr())


class Main(QMainWindow, gui.Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.pushButton.setText('启用粘贴')
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.thread = Thread()
        self.thread.start()
        self.thread.voice_signal.connect(self.display_voice)
        self.thread.text_signal.connect(self.display_text)
        self.paste = False
        self.thread.paste = False
        self.pushButton.clicked.connect(self.paste_text)

    def display_text(self, text):
        self.label.setText(text)

    def display_voice(self, db):
        self.progressBar.setValue(db)

    def paste_text(self):
        if self.paste:
            self.paste = False
            self.thread.paste = False
            self.pushButton.setText('启用粘贴')
        else:
            self.paste = True
            self.thread.paste = True
            self.pushButton.setText('禁用粘贴')

    def closeEvent(self, event):
        # 创建一个QMessageBox对象，设置标题、文本、图标和按钮
        reply = QMessageBox()
        reply.setWindowTitle("退出")
        reply.setText("你确定要退出吗？")
        reply.setIcon(QMessageBox.Question)
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

        # 显示对话框，并获取用户的选择
        choice = reply.exec_()

        # 如果用户选择是，就接受关闭事件，否则就忽略关闭事件
        if choice == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
def start_streaming_asr_server():
    # 调用logger对象的info方法，输出日志信息
    logger.info("start to launch the streaming asr server")
    # 创建一个ServerExecutor对象，赋值给streaming_asr_server变量
    streaming_asr_server = ServerExecutor()
    # 调用streaming_asr_server对象的__call__方法，传入配置文件和日志文件参数
    streaming_asr_server(config_file="./conf/ws_conformer_wenetspeech_application_faster.yaml",
                         log_file="./log/paddlespeech.log")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = Main()
    ui.show()
    t = threading.Thread(target=start_streaming_asr_server)
    t.start()
    sys.exit(app.exec_())