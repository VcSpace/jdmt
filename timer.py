# -*- coding:utf-8 -*-
import time
from datetime import datetime
from jd_logger import logger
from config import global_config

class Timer(object):
    def __init__(self, sleep_interval=0.2):
        # '2018-09-28 22:45:50.000'
        self.start_time = datetime.strptime(global_config.getRaw('config','buy_time'), "%Y-%m-%d %H:%M:%S.%f")
        self.ready_time = datetime.strptime(global_config.getRaw('config','ready_time'), "%Y-%m-%d %H:%M:%S.%f")
        self.end_time = datetime.strptime(global_config.getRaw('config','end_time'), "%Y-%m-%d %H:%M:%S.%f")
        self.sleep_interval = sleep_interval

    def ready(self):
        logger.info('正在等待到达设定时间:%s' % self.ready_time)
        now_time = datetime.now
        while True:
            if now_time() >= self.ready_time:
                logger.info('准备开始执行……')
                break
            else:
                time.sleep(self.sleep_interval)

    def start(self):
        now_time = datetime.now
        while True:
            if now_time() >= self.start_time:
                logger.info('时间到达，开始执行……')
                break
            else:
                time.sleep(self.sleep_interval)

    def end(self):
        now_time = datetime.now
        while True:
            if now_time() < self.end_time:
                return True
            else:
                break
        return False


