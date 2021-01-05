import random
import time
import requests
import functools
import json
import os
import pickle
import asyncio
from lxml import etree
from util import (parse_json, get_random_useragent, send_mail,
                        response_status, save_image, open_image, add_bg_for_qr)

class SpiderSession:
    """
    Session相关操作
    """
    def __init__(self):
        self.cookies_dir_path = "./cookies/"
        self.user_agent = "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36"

        self.session = self._init_session()

    def _init_session(self):
        session = requests.session()
        session.headers = self.get_headers()
        return session

    def get_headers(self):
        return {"User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;"
                          "q=0.9,image/webp,image/apng,*/*;"
                          "q=0.8,application/signed-exchange;"
                          "v=b3",
                "Connection": "keep-alive"}

    def get_user_agent(self):
        return self.user_agent

    def get_session(self):
        """
        获取当前Session
        :return:
        """
        return self.session

    def get_cookies(self):
        """
        获取当前Cookies
        :return:
        """
        return self.get_session().cookies

    def set_cookies(self, cookies):
        self.session.cookies.update(cookies)

    def load_cookies_from_local(self):
        """
        从本地加载Cookie
        :return:
        """
        cookies_file = ''
        if not os.path.exists(self.cookies_dir_path):
            return False
        for name in os.listdir(self.cookies_dir_path):
            if name.endswith(".cookies"):
                cookies_file = '{}{}'.format(self.cookies_dir_path, name)
                break
        if cookies_file == '':
            return False
        with open(cookies_file, 'rb') as f:
            local_cookies = pickle.load(f)
        self.set_cookies(local_cookies)

    def save_cookies_to_local(self, cookie_file_name):
        """
        保存Cookie到本地
        :param cookie_file_name: 存放Cookie的文件名称
        :return:
        """
        cookies_file = '{}{}.cookies'.format(self.cookies_dir_path, cookie_file_name)
        directory = os.path.dirname(cookies_file)
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(cookies_file, 'wb') as f:
            pickle.dump(self.get_cookies(), f)

class QrLogin:
    """
    扫码登录
    """
    def __init__(self, spider_session: SpiderSession):
        """
        初始化扫码登录
        大致流程：
            1、访问登录二维码页面，获取Token
            2、使用Token获取票据
            3、校验票据
        :param spider_session:
        """
        self.qrcode_img_file = 'qr_code.png'

        self.spider_session = spider_session
        self.session = self.spider_session.get_session()

        self.is_login = False
        self.refresh_login_status()

    def refresh_login_status(self):
        """
        刷新是否登录状态
        :return:
        """
        self.is_login = self._validate_cookies()

    def _validate_cookies(self):
        """
        验证cookies是否有效（是否登陆）
        通过访问用户订单列表页进行判断：若未登录，将会重定向到登陆页面。
        :return: cookies是否有效 True/False
        """
        url = 'https://order.jd.com/center/list.action'
        payload = {
            'rid': str(int(time.time() * 1000)),
        }
        try:
            resp = self.session.get(url=url, params=payload, allow_redirects=False)
            if resp.status_code == requests.codes.OK:
                return True
        except Exception as e:
            logger.error("验证cookies是否有效发生异常", e)
        return False

    def _get_login_page(self):
        """
        获取PC端登录页面
        :return:
        """
        url = "https://passport.jd.com/new/login.aspx"
        page = self.session.get(url, headers=self.spider_session.get_headers())
        return page

    def _get_qrcode(self):
        """
        缓存并展示登录二维码
        :return:
        """
        url = 'https://qr.m.jd.com/show'
        payload = {
            'appid': 133,
            'size': 300,
            't': str(int(time.time() * 1000)),
        }
        headers = {
            'User-Agent': self.spider_session.get_user_agent(),
            'Referer': 'https://passport.jd.com/new/login.aspx',
        }
        resp = self.session.get(url=url, headers=headers, params=payload)

        if not response_status(resp):
            logger.info('获取二维码失败')
            return False

        save_image(resp, self.qrcode_img_file)
        logger.info('二维码获取成功，请打开京东APP扫描')

        open_image(add_bg_for_qr(self.qrcode_img_file))
        return True

    def _get_qrcode_ticket(self):
        """
        通过 token 获取票据
        :return:
        """
        url = 'https://qr.m.jd.com/check'
        payload = {
            'appid': '133',
            'callback': 'jQuery{}'.format(random.randint(1000000, 9999999)),
            'token': self.session.cookies.get('wlfstk_smdl'),
            '_': str(int(time.time() * 1000)),
        }
        headers = {
            'User-Agent': self.spider_session.get_user_agent(),
            'Referer': 'https://passport.jd.com/new/login.aspx',
        }
        resp = self.session.get(url=url, headers=headers, params=payload)

        if not response_status(resp):
            logger.error('获取二维码扫描结果异常')
            return False

        resp_json = parse_json(resp.text)
        if resp_json['code'] != 200:
            logger.info('Code: %s, Message: %s', resp_json['code'], resp_json['msg'])
            return None
        else:
            logger.info('已完成手机客户端确认')
            return resp_json['ticket']

    def _validate_qrcode_ticket(self, ticket):
        """
        通过已获取的票据进行校验
        :param ticket: 已获取的票据
        :return:
        """
        url = 'https://passport.jd.com/uc/qrCodeTicketValidation'
        headers = {
            'User-Agent': self.spider_session.get_user_agent(),
            'Referer': 'https://passport.jd.com/uc/login?ltype=logout',
        }

        resp = self.session.get(url=url, headers=headers, params={'t': ticket})
        if not response_status(resp):
            return False

        resp_json = json.loads(resp.text)
        if resp_json['returnCode'] == 0:
            return True
        else:
            logger.info(resp_json)
            return False

    def login_by_qrcode(self):
        """
        二维码登陆
        :return:
        """
        self._get_login_page()

        # download QR code
        if not self._get_qrcode():
            print('二维码下载失败')

        # get QR code ticket
        ticket = None
        retry_times = 17
        for _ in range(retry_times):
            ticket = self._get_qrcode_ticket()
            if ticket:
                break
            else:
                time.sleep(10)
        else:
            print('二维码过期，请重新获取扫描')

        # validate QR code ticket
        if not self._validate_qrcode_ticket(ticket):
            print('二维码信息校验失败')

        self.refresh_login_status()

        print('二维码登录成功')

class JdTdudfp(object):
    def __init__(self, sp: SpiderSession):
        self.cookies = sp.get_cookies()
        self.user_agent = sp.get_user_agent()

        self.is_init = False
        self.jd_tdudfp = None

    def init_jd_tdudfp(self):
        self.is_init = True

        loop = asyncio.get_event_loop()
        get_future = asyncio.ensure_future(self._get())
        loop.run_until_complete(get_future)
        self.jd_tdudfp = get_future.result()

    def get(self, key):
        return self.jd_tdudfp.get(key) if self.jd_tdudfp else None

    async def _get(self):
        jd_tdudfp = None
        try:
            from pyppeteer import launch
            url = "https://www.jd.com/"
            browser = await launch(userDataDir=".user_data", autoClose=True,
                                   args=['--start-maximized', '--no-sandbox', '--disable-setuid-sandbox'])
            page = await browser.newPage()
            # 有些页面打开慢，这里设置时间长一点，360秒
            page.setDefaultNavigationTimeout(360 * 1000)
            await page.setViewport({"width": 1920, "height": 1080})
            await page.setUserAgent(self.user_agent)
            for key, value in self.cookies.items():
                await page.setCookie({"domain": ".jd.com", "name": key, "value": value})
            await page.goto(url)
            await page.waitFor(".nickname")
            print("page_title:【%s】, page_url【%s】" % (await page.title(), page.url))

            nick_name = await page.querySelectorEval(".nickname", "(element) => element.textContent")
            if not nick_name:
                # 如果未获取到用户昵称，说明可能登陆失败，放弃获取 _JdTdudfp
                return jd_tdudfp

            await page.waitFor(".cate_menu_lk")
            # .cate_menu_lk是一个a标签，理论上可以直接触发click事件
            # 点击事件会打开一个新的tab页，但是browser.pages()无法获取新打开的tab页，导致无法引用新打开的page对象
            # 所以获取href，使用goto跳转的方式
            # 下面类似goto写法都是这个原因
            a_href = await page.querySelectorAllEval(".cate_menu_lk", "(elements) => elements[0].href")
            await page.goto(a_href)
            await page.waitFor(".goods_item_link")
            print("page_title：【%s】, page_url：【%s】" % (await page.title(), page.url))
            a_href = await page.querySelectorAllEval(".goods_item_link", "(elements) => elements[{}].href".format(
                str(random.randint(1, 20))))
            await page.goto(a_href)
            await page.waitFor("#InitCartUrl")
            print("page_title：【%s】, page_url：【%s】" % (await page.title(), page.url))
            a_href = await page.querySelectorAllEval("#InitCartUrl", "(elements) => elements[0].href")
            await page.goto(a_href)
            await page.waitFor(".btn-addtocart")
            print("page_title：【%s】, page_url：【%s】" % (await page.title(), page.url))
            a_href = await page.querySelectorAllEval(".btn-addtocart", "(elements) => elements[0].href")
            await page.goto(a_href)
            await page.waitFor(".common-submit-btn")
            print("page_title：【%s】, page_url：【%s】" % (await page.title(), page.url))

            await page.click(".common-submit-btn")
            await page.waitFor("#sumPayPriceId")
            print("page_title：【%s】, page_url：【%s】" % (await page.title(), page.url))

            for _ in range(30):
                jd_tdudfp = await page.evaluate("() => {try{return _JdTdudfp}catch(e){}}")
                if jd_tdudfp and len(jd_tdudfp) > 0:
                    print("jd_tdudfp：【%s】" % jd_tdudfp)
                    break
                else:
                    await asyncio.sleep(1)

            await page.close()
        except Exception as e:
            print("自动获取JdTdudfp发生异常，将从配置文件读取！")
        return jd_tdudfp

if __name__ == '__main__':
    spider_session = SpiderSession()
    spider_session.load_cookies_from_local()
    qrlogin = QrLogin(spider_session)
    session = spider_session.get_session()
    fp = JdTdudfp(spider_session)
    fp.init_jd_tdudfp()
    eid = fp.get("eid")
    fp = fp.get("fp")
    print(eid)
    print(fp)
