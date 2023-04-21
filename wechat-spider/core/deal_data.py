# -*- coding: utf-8 -*-
"""
Created on 2019/5/11 6:37 PM
---------
@summary: 处理数据
---------
@author:
"""
from utils.selector import Selector
import utils.tools as tools
from utils.log import log
from core import data_pipeline
from core.task_manager import TaskManager
from config import config
import requests
import time
import json
from datetime import datetime
import urllib.parse
from urllib.parse import urlparse, parse_qs


class DealData:
    def __init__(self):
        self._task_manager = TaskManager()
        self._task_manager.reset_task()

    def parse_account_info(self, data, req_url):
        """
        @summary:
        ---------
        @param data:
        ---------
        @result:
        """
        __biz = tools.get_param(req_url, "__biz")

        regex = 'class="profile_nickname">(.*?)</strong>'
        account = tools.get_info(data, regex, fetch_one=True).strip()

        regex = 'profile_avatar">.*?<img src="(.*?)"'
        head_url = tools.get_info(data, regex, fetch_one=True)

        regex = 'class="profile_meta_value">(.*?)</span>'
        summary = tools.get_info(data, regex, fetch_one=True).strip()

        # 认证信息（关注的账号直接点击查看历史消息，无认证信息）
        regex = '<i class="icon_verify success">.*?</i>(.*?)</span>'
        verify = tools.get_info(data, regex, fetch_one=True)
        verify = verify.strip() if verify else ""

        # 二维码
        regex = 'var username = "" \|\| "(.*?)";'  # ||  需要转译
        qr_code = tools.get_info(data, regex, fetch_one=True)
        qr_code = "http://open.weixin.qq.com/qr/code?username=" + qr_code

        account_data = {
            "__biz": __biz,
            "account": account,
            "head_url": head_url,
            "summary": summary,
            "qr_code": qr_code,
            "verify": verify,
            "spider_time": tools.get_current_date(),
        }

        if account_data:
            data_pipeline.save_account(account_data)

    def __parse_article_list(self, article_list, __biz, is_first_page=False):
        """
        @summary: 解析文章列表
        ---------
        @param article_list: 文章列表信息 str
        ---------
        @result: True / None (True: 继续向下抓取； None: 停止向下抓取）
        """

        # log.debug(tools.dumps_json(article_list))

        # 解析json内容里文章信息
        def parse_article_info(article_info, comm_msg_info):
            if not article_info:
                return

            # log.debug(tools.dumps_json(article_info))

            title = article_info.get("title")
            digest = article_info.get("digest")
            url = article_info.get("content_url").replace("\\", "").replace("amp;", "")
            source_url = article_info.get("source_url").replace("\\", "")  # 引用的文章链接
            cover = article_info.get("cover").replace("\\", "")
            subtype = article_info.get("subtype")
            is_multi = article_info.get("is_multi")
            author = article_info.get("author")
            copyright_stat = article_info.get("copyright_stat")
            duration = article_info.get("duration")
            del_flag = article_info.get("del_flag")
            type = comm_msg_info.get("type")
            publish_time = tools.timestamp_to_date(comm_msg_info.get("datetime"))
            sn = tools.get_param(url, "sn")

            if sn:
                # 缓存文章信息
                article_data = {
                    "title": title,
                    "digest": digest,
                    "url": url,
                    "source_url": source_url,
                    "cover": cover,
                    "subtype": subtype,
                    "is_multi": is_multi,
                    "author": author,
                    "copyright_stat": copyright_stat,
                    "duration": duration,
                    "del_flag": del_flag,
                    "type": type,
                    "publish_time": publish_time,
                    "sn": sn,
                    "__biz": __biz,
                    "spider_time": tools.get_current_date(),
                }

                return article_data

        # log.debug(tools.dumps_json(article_list))
        article_list = tools.get_json(article_list)

        article_list_data = []
        publish_time = None
        is_need_get_more = True
        article_list = article_list.get("list", [])
        is_first_article = True
        for article in article_list:
            comm_msg_info = article.get("comm_msg_info", {})

            publish_timestamp = comm_msg_info.get("datetime")
            publish_time = tools.timestamp_to_date(publish_timestamp)

            # 记录最新发布时间
            if is_first_page and is_first_article:
                self._task_manager.record_new_last_article_publish_time(
                    __biz, publish_time
                )
                is_first_article = False

                if publish_timestamp and self._task_manager.is_zombie_account(
                    publish_timestamp
                ):  # 首页检测是否为最新发布的文章 若最近未发布 则为僵尸账号
                    log.info("公众号 {} 为僵尸账号 不再监控".format(__biz))
                    self._task_manager.sign_account_is_zombie(__biz, publish_time)
                    is_need_get_more = False
                    break

            # 对比时间 若采集到上次时间，则跳出
            is_reach = self._task_manager.is_reach_last_article_publish_time(
                __biz, publish_time
            )
            if is_reach:
                log.info("采集到上次发布时间 公众号 {} 采集完成".format(__biz))
                new_last_publish_time = self._task_manager.get_new_last_article_publish_time(
                    __biz
                )
                self._task_manager.update_account_last_publish_time(
                    __biz, new_last_publish_time
                )
                is_need_get_more = False
                break

            elif is_reach is None:
                log.info("公众号 {} 为爬虫启动时的手点公众号。不遍历历史消息，即将抓取监控池里的公众号".format(__biz))
                return

            article_type = comm_msg_info.get("type")
            if article_type != 49:  # 49为常见的图文消息、其他消息有文本、语音、视频，此处不采集，格式不统一
                continue

            # 看是否在抓取时间范围
            publish_time_status = self._task_manager.is_in_crawl_time_range(
                publish_time
            )
            if publish_time_status == TaskManager.OVER_MIN_TIME_RANGE:
                log.info("公众号 {} 超过采集时间范围 采集完成".format(__biz))
                new_last_publish_time = self._task_manager.get_new_last_article_publish_time(
                    __biz
                )
                self._task_manager.update_account_last_publish_time(
                    __biz, new_last_publish_time
                )
                is_need_get_more = False
                break
            elif publish_time_status == TaskManager.NOT_REACH_TIME_RANGE:
                log.info("公众号 {} 当前采集到的时间 {} 未到采集时间范围 不采集".format(__biz, publish_time))
                continue

            # 在时间范围

            # 微信公众号每次可以发多个图文消息
            # 第一个图文消息
            app_msg_ext_info = article.get("app_msg_ext_info", {})
            article_data = parse_article_info(app_msg_ext_info, comm_msg_info)
            if article_data:
                article_list_data.append(article_data)

            # 同一天附带的图文消息
            multi_app_msg_item_list = app_msg_ext_info.get("multi_app_msg_item_list")
            for multi_app_msg_item in multi_app_msg_item_list:
                article_data = parse_article_info(multi_app_msg_item, comm_msg_info)
                if article_data:
                    article_list_data.append(article_data)

        if article_list_data:
            data_pipeline.save_article_list(article_list_data)

        if is_need_get_more:
            return publish_time

    def deal_article_list(self, req_url, text):
        """
        @summary: 获取文章列表
        分为两种
            1、第一次查看历史消息 返回的是html格式 包含公众号信息
            2、下拉显示更多时 返回json格式
        但是文章列表都是json格式 且合适相同
        抓取思路：
        1、如果是第一种格式，直接解析文章内容，拼接下一页json格式的地址
        2、如果是第二种格式，
        ---------
        @param data:
        ---------
        @result:
        """
        try:
            # 判断是否为被封的账号， 被封账号没有文章列表
            __biz = tools.get_param(req_url, "__biz")

            if "list" in text:
                # 取html格式里的文章列表
                if "action=home" in req_url:
                    # 解析公众号信息
                    self.parse_account_info(text, req_url)

                    # 解析文章列表
                    regex = "msgList = '(.*?})';"
                    article_list = tools.get_info(text, regex, fetch_one=True)
                    article_list = article_list.replace("&quot;", '"')
                    publish_time = self.__parse_article_list(
                        article_list, __biz, is_first_page=True
                    )

                    # 判断是否还有更多文章 没有跳转到下个公众号，有则下拉显示更多
                    regex = "can_msg_continue = '(\d)'"
                    can_msg_continue = tools.get_info(text, regex, fetch_one=True)
                    if can_msg_continue == "0":  # 无更多文章
                        log.info("抓取到列表底部 无更多文章，公众号 {} 抓取完毕".format(__biz))
                        new_last_publish_time = self._task_manager.get_new_last_article_publish_time(
                            __biz
                        )
                        if not new_last_publish_time:
                            # 标记成僵尸号
                            log.info("公众号 {} 为僵尸账号 不再监控".format(__biz))
                            self._task_manager.sign_account_is_zombie(__biz)
                        else:
                            self._task_manager.update_account_last_publish_time(
                                __biz, new_last_publish_time
                            )

                    elif publish_time:
                        # 以下是拼接下拉显示更多的历史文章 跳转
                        # 取appmsg_token 在html中
                        regex = 'appmsg_token = "(.*?)";'
                        appmsg_token = tools.get_info(text, regex, fetch_one=True)

                        # 取其他参数  在url中
                        __biz = tools.get_param(req_url, "__biz")
                        pass_ticket = tools.get_param(req_url, "pass_ticket")

                        next_page_url = "https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz={__biz}&f=json&offset={offset}&count=10&is_ok=1&scene=124&uin=777&key=777&pass_ticket={pass_ticket}&wxtoken=&appmsg_token={appmsg_token}&x5=0&f=json".format(
                            __biz=__biz,
                            offset=10,
                            pass_ticket=pass_ticket,
                            appmsg_token=appmsg_token,
                        )
                        return self._task_manager.get_task(
                            next_page_url,
                            tip="正在抓取列表 next_offset {} 抓取到 {}".format(10, publish_time),
                        )

                else:  # json格式
                    text = tools.get_json(text)
                    article_list = text.get("general_msg_list", {})
                    publish_time = self.__parse_article_list(article_list, __biz)

                    # 判断是否还有更多文章 没有跳转到下个公众号，有则下拉显示更多
                    can_msg_continue = text.get("can_msg_continue")
                    if not can_msg_continue:  # 无更多文章
                        log.info("抓取到列表底部 无更多文章，公众号 {} 抓取完毕".format(__biz))
                        new_last_publish_time = self._task_manager.get_new_last_article_publish_time(
                            __biz
                        )
                        self._task_manager.update_account_last_publish_time(
                            __biz, new_last_publish_time
                        )
                        pass

                    elif publish_time:
                        # 以下是拼接下拉显示更多的历史文章 跳转
                        # 取参数  在url中
                        __biz = tools.get_param(req_url, "__biz")
                        pass_ticket = tools.get_param(req_url, "pass_ticket")
                        appmsg_token = tools.get_param(req_url, "appmsg_token")

                        # 取offset 在json中
                        offset = text.get("next_offset", 0)

                        next_page_url = "https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz={__biz}&f=json&offset={offset}&count=10&is_ok=1&scene=124&uin=777&key=777&pass_ticket={pass_ticket}&wxtoken=&appmsg_token={appmsg_token}&x5=0&f=json".format(
                            __biz=__biz,
                            offset=offset,
                            pass_ticket=pass_ticket,
                            appmsg_token=appmsg_token,
                        )
                        return self._task_manager.get_task(
                            next_page_url,
                            tip="正在抓取列表 next_offset {} 抓取到 {}".format(
                                offset, publish_time
                            ),
                        )

            else:  # 该__biz 账号已被封
                # self._task_manager.sign_account_is_zombie(__biz)
                log.info("账号被封了，g")
                pass

        except Exception as e:
            log.exception(e)

        return self._task_manager.get_task()

    def deal_article_list_by_wechat(self):
        # 目标url
        url = "https://mp.weixin.qq.com/cgi-bin/appmsg"
        s1 = "select * from `wechat_profile`"
        results = self._task_manager._mysqldb.find(s1)
        is_scan = 0
        cookie = ""
        token = ""
        count = ""

        for result in results:
            if result[1] == "WECHAT_COOKIE":
                cookie = result[2] 
            elif result[1]  == "WECHAT_TOKEN":
                token = result[2] 
            elif result[1]  == "WECHAT_COUNT":
                count = result[2] 
            elif result[1] == "IS_SCAN":
                is_scan = int(result[2])

        if is_scan:
            log.info("当前已经有线程正在扫描中")
            return

        s2 = "update `wechat_profile` SET `value`='1' where `profile_name`='IS_SCAN'"
        self._task_manager._mysqldb.update(s2)

        # 使用Cookie，跳过登陆操作
        # headers = {
        #   "Cookie": cookie,
        #   "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.116 Safari/537.36 QBCore/3.53.1159.400 QQBrowser/9.0.2524.400 Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 MicroMessenger/6.5.2.501 NetType/WIFI WindowsWechat",
        # }

        # 获取所有的任务
        sql = "SELECT * FROM `wechat_account_task` where is_zombie = 0 and last_publish_time < '{today}'".format(today=tools.get_current_date(date_format='%Y-%m-%d' + ' 00:00:00'))
        tasks = self._task_manager._mysqldb.find(sql, to_json=True)

        for task in tasks:
            # 如果有任务，那么跳转到微信首页
            next_url = "https://mp.weixin.qq.com/?status=waittask"

            return self._task_manager.get_task(
                next_url,
                tip="跳转至微信公众号首页，设置cookie",
                cookie=cookie
            )

        # 没有任务直接返回
        s4 = "update `wechat_profile` SET `value`='0' where `profile_name`='IS_SCAN'"
        self._task_manager._mysqldb.update(s4)

        return self._task_manager.get_task()


    def deal_article_list_by_wechat_sec(self):
        # 目标url
        url = "https://mp.weixin.qq.com/cgi-bin/appmsg"
        s1 = "select * from `wechat_profile`"
        results = self._task_manager._mysqldb.find(s1)
        is_scan = 0
        cookie = ""
        token = ""
        count = ""

        for result in results:
            if result[1] == "WECHAT_COOKIE":
                cookie = result[2] 
            elif result[1]  == "WECHAT_TOKEN":
                token = result[2] 
            elif result[1]  == "WECHAT_COUNT":
                count = result[2] 
            elif result[1] == "IS_SCAN":
                is_scan = int(result[2])


        # 获取所有的任务
        sql = "SELECT * FROM `wechat_account_task` where is_zombie = 0 and last_spider_time < '{today}'".format(today=tools.get_current_date(date_format='%Y-%m-%d' + ' 00:00:00'))
        
        tasks = self._task_manager._mysqldb.find(sql, to_json=True)

        for task in tasks:
            biz = task['__biz']

            """
            需要提交的data
            以下个别字段是否一定需要还未验证。
            注意修改yourtoken,number
            number表示从第number页开始爬取，为5的倍数，从0开始。如0、5、10……
            token可以使用Chrome自带的工具进行获取
            fakeid是公众号独一无二的一个id，等同于后面的__biz
            """

            data = {
                "token": token,
                "lang": "zh_CN",
                "f": "json",
                "ajax": "1",
                "action": "list_ex",
                "begin": "0",
                "count": count,
                "query": "",
                "fakeid": biz,
                "type": "9",
            }

            # 使用get方法进行提交
            log.info("对{}的公众号进行扫描".format(biz))

            # request方案有概率失败，还是通过代理方案实现
            params_str = urllib.parse.urlencode(data)
            next_url = url + '?' + params_str

            return self._task_manager.get_task(
                next_url,
                tip="正在抓取{}公众号的列表,抓取完成后休眠120秒".format(biz),
                cookie=cookie,
                sleep_time=200
            )

        # 结束公众号扫描
        s4 = "update `wechat_profile` SET `value`='0' where `profile_name`='IS_SCAN'"
        self._task_manager._mysqldb.update(s4)

        return self._task_manager.get_task()



    def deal_wechat_list(self, req_url, text):
        # parse biz
        parsed_url = urlparse(req_url)
        query_params = parse_qs(parsed_url.query)
        biz = query_params.get('fakeid')[0]

        result = json.loads(text)
        article_task = []

        # 检查登录状态
        if "invalid session" in str(text):
            log.info("当前登录状态失效")
            sql = "update `wechat_profile` SET `value`='0' where `profile_name`='IS_LOGIN'"
            self._task_manager._mysqldb.update(sql)

            s4 = "update `wechat_profile` SET `value`='0' where `profile_name`='IS_SCAN'"
            self._task_manager._mysqldb.update(s4)
            return False
        else:
            sql = "update `wechat_profile` SET `value`='1' where `profile_name`='IS_LOGIN'"
            self._task_manager._mysqldb.update(sql)

        # 存文章任务
        for article in result["app_msg_list"]:
            link = article["link"]
            parsed_url = urlparse(link)
            query_params = parse_qs(parsed_url.query)
            sn = query_params.get('sn')[0]


            article_task.append(
                {
                    "article_url": link,
                    "__biz": biz,
                    "sn": sn,
                }
            )

        sql, article_task = tools.make_batch_sql('wechat_article_task', article_task, update_columns=("article_url",))
        self._task_manager._mysqldb.add_batch(sql, article_task)

        # 扫描完成，更新publish time
        s5 = "UPDATE `wechat_account_task` SET last_spider_time = '{}' where __biz ='{}'".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), biz)
        self._task_manager._mysqldb.update(s5)

        # 读取一次列表完成，继续读取列表中下一次结果
        self.deal_article_list_by_wechat_sec()


    def deal_article(self, req_url, text):
        """
        解析文章
        :param req_url:
        :param text:
        :return:
        """
        sn = tools.get_param(req_url, "sn")

        if not text:
            self._task_manager.update_article_task_state(sn, -1)
            return None

        selector = Selector(text)

        content = selector.xpath(
            '//div[@id="js_content"]|//div[@class="rich_media_content"]|//div[@class="share_media"]'
        )
        title = (
            selector.xpath('//h1[@id="activity-name"]/text()')
            .extract_first(default="")
            .strip()
        )
        account = (
            selector.xpath('//a[@id="js_name"]/text()')
            .extract_first(default="")
            .strip()
        )
        author = (
            selector.xpath(
                '//span[@class="rich_media_meta rich_media_meta_text"]/text()'
            )
            .extract_first(default="")
            .strip()
        )

        publish_timestamp = selector.re_first('create_time = "(\d{10})"')
        publish_timestamp = int(publish_timestamp) if publish_timestamp else None
        publish_time = (
            tools.timestamp_to_date(publish_timestamp) if publish_timestamp else None
        )

        pics_url = content.xpath(".//img/@src|.//img/@data-src").extract()
        biz = tools.get_param(req_url, "__biz")

        digest = selector.re_first('var msg_desc = "(.*?)"')
        cover = selector.re_first('var cover = "(.*?)";') or selector.re_first(
            'msg_cdn_url = "(.*?)"'
        )
        source_url = selector.re_first("var msg_source_url = '(.*?)';")

        content_html = content.extract_first(default="")
        comment_id = selector.re_first('var comment_id = "(\d+)"')

        article_data = {
            "account": account,
            "title": title,
            "url": req_url,
            "author": author,
            "publish_time": publish_time,
            "__biz": biz,
            "digest": digest,
            "cover": cover,
            "pics_url": pics_url,
            "content_html": content_html,
            "source_url": source_url,
            "comment_id": comment_id,
            "sn": sn,
            "spider_time": tools.get_current_date(),
        }

        # 入库
        if article_data and data_pipeline.save_article(article_data) is not None:
            self._task_manager.update_article_task_state(sn, 1)

        return self._task_manager.get_task()

    def deal_article_dynamic_info(self, req_data, text):
        """
        取文章动态信息 阅读 点赞 评论
        :param req_data: post 请求的data str格式
        :param text:
        :return:
        """
        data = tools.get_json(text)

        dynamic_data = dict(
            sn=tools.get_param(req_data, "sn"),
            __biz=tools.get_param(req_data, "__biz").replace("%3D", "="),
            read_num=data.get("appmsgstat", {}).get("read_num"),
            like_num=data.get("appmsgstat", {}).get("like_num"),
            comment_count=data.get("comment_count"),
            spider_time=tools.get_current_date(),
        )

        if dynamic_data:
            data_pipeline.save_article_dynamic(dynamic_data)

    def deal_comment(self, req_url, text):
        """
        解析评论
        :param req_url:
        :param text:
        :return:
        """

        data = tools.get_json(text)

        __biz = tools.get_param(req_url, "__biz")

        comment_id = tools.get_param(req_url, "comment_id")  # 与文章关联
        elected_comment = data.get("elected_comment", [])

        comment_datas = [
            dict(
                __biz=__biz,
                comment_id=comment_id,
                nick_name=comment.get("nick_name"),
                logo_url=comment.get("logo_url"),
                content=comment.get("content"),
                create_time=tools.timestamp_to_date(comment.get("create_time")),
                content_id=comment.get("content_id"),
                like_num=comment.get("like_num"),
                is_top=comment.get("is_top"),
                spider_time=tools.get_current_date(),
            )
            for comment in elected_comment
        ]

        if comment_datas:
            data_pipeline.save_article_commnet(comment_datas)

    def get_task(self):
        return self._task_manager.get_task()


deal_data = DealData()