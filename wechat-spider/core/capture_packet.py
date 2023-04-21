# -*- coding: utf-8 -*-
'''
Created on 2019/5/8 10:59 PM
---------
@summary:
---------
@author:
'''
import re

import mitmproxy
from mitmproxy import ctx

from core.deal_data import deal_data


class WechatCapture():

    def response(self, flow: mitmproxy.http.HTTPFlow):
        url = flow.request.url

        next_page = None
        try:
            if 'mp/profile_ext?action=home' in url or 'mp/profile_ext?action=getmsg' in url:  # 文章列表 包括html格式和json格式

                ctx.log.info('此功能已经删除')
                # next_page = deal_data.deal_article_list(url, flow.response.text)

                # flow.response.text = re.sub('<img.*?>', '', flow.response.text)

            elif 'startscan' in url: # 开始扫描
                ctx.log.info('检查全部任务列表，跳转微信首页')
                next_page = deal_data.deal_article_list_by_wechat()


            elif 'waittask' in url or 'cgi-bin/home' in url:
                ctx.log.info('抽取公众号列表内容')
                next_page = deal_data.deal_article_list_by_wechat_sec()


            elif '/s?__biz=' in url or '/mp/appmsg/show?__biz=' in url or '/mp/rumor' in url:  
                # 文章内容；mp/appmsg/show?_biz 为2014年老版链接;  mp/rumor 是不详实的文章
                ctx.log.info('检查账户信息有效性')
                deal_data.parse_account_info(flow.response.text, url)

                ctx.log.info('抽取文章内容')
                next_page = deal_data.deal_article(url, flow.response.text)

                # 修改文章内容的响应头，去掉安全协议，否则注入的 < script > setTimeout(function() {window.location.href = 'url';}, sleep_time); < / script > js脚本不执行
                flow.response.headers.pop('Content-Security-Policy', None)
                flow.response.headers.pop('content-security-policy-report-only', None)
                flow.response.headers.pop('Strict-Transport-Security', None)

                #  不缓存
                flow.response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'

                # 去掉图片
                flow.response.text = re.sub('<img.*?>', '', flow.response.text)

            elif 'cgi-bin/appmsg' in url:
                if "invalid referrer" in flow.response.text:
                    ctx.log.info('页面来源检查出错')
                    next_page = deal_data.deal_article_list_by_wechat()

                next_page = deal_data.deal_wechat_list(url, flow.response.text)

        except Exception as e:
            # log.exception(e)
            next_page = "Exception: {}".format(e)

        if next_page:
            # 修改返回求头 json 为text
            flow.response.headers['content-type'] = 'text/html; charset=UTF-8'
            if 'window.location.reload()' in next_page:
                flow.response.set_text(next_page)
            else:
                flow.response.set_text(next_page + flow.response.text)


addons = [
    WechatCapture(),
]

# 运行  mitmdump -s capture_packet.py -p 8080
