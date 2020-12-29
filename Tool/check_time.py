import time
import requests
import json
import sys
import platform
import os
from datetime import datetime

if __name__ == '__main__':
    url = 'https://a.jd.com//ajax/queryServerData.html'
    ret = requests.get(url).text
    js = json.loads(ret)
    jd_time = int(js["serverTime"])

    local_time = int(round(time.time() * 1000))

    local_jd_time_diff = local_time - jd_time
    print(local_time)
    print(jd_time)

    print("检测本地时间与京东服务器时间误差为{}毫秒".format(local_jd_time_diff))
    
    print('操作完成')
    sys = platform.system()
    if sys == "Windows":
        os.system('pause')
