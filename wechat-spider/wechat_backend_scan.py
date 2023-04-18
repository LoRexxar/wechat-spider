# -*- coding: utf-8 -*-
import requests
import time
import json


# 目标url
url = "https://mp.weixin.qq.com/cgi-bin/appmsg"

# 使用Cookie，跳过登陆操作
headers = {
  "Cookie": "appmsglist_action_3907326541=card; ua_id=O5T6ChVi5qDVnWxwAAAAAI1Jh4KdtKmvb__Bsub_PYw=; mm_lang=zh_CN; _clck=3907326541|1|f6a|0; rewardsn=; wxtokenkey=777; pgv_info=ssid=s3063972355; pgv_pvid=6305076999; eas_sid=xMA7JbFZVanizs8WwLMzSr9YQi; _qpsvr_localtk=0.004155613692446769; RK=3F9wtkmMU6; ptcz=26706f3c9065bf8a18542ea03452db5d08cd661cd9adb9eac58590e6f2b08ec4; lostarkqqcomrouteLine=a20230314index_a20230314index; wwapp.vid=; wwapp.cst=; wwapp.deviceid=; appmsg_token=1211_y3yZFh67JdIH2Ll3B14QEnXTLVPCpmbKjlHbEhW0gkh9hJjIX5t8atb0V7c8E3mvohLVbWGsyEkS2CwN; lang=zh_CN; wxuin=1089095992; devicetype=Windows10; version=62060834; pass_ticket=OYykAz8tz321UO5f6ZJhCZPHBRueNujtUEDwt9L3FWb/N84ieH4J6ngoqbAcH8t2LQNxJfRMtRW20uMeETfILw==; wap_sid2=CLiSqYcEEooBeV9ISENycGxKU0xKckdtTWNLdnVIRWZBSlczSGc0Z2owWDZtQkh3UGhzUlFFMFpIMDFKWjZoTEJzV0FxYTJtejdRV0ZVVUFsYUlZR2tWdktqQnlkMkNwNGtITEJvNGtQLTdYOFRacTNYWlkwMmFUc2c5OTJuUjNlMkpuOGthWXZIeUY1b1NBQUF+MLOL2qEGOAxAlE4=; uuid=ca2d95d3533bdd98d692398a09b03404; rand_info=CAESIEQxp2byMz4oTIXEODL+izQnaPPBE/CnGIv6JP7znxtM; slave_bizuin=3907326541; data_bizuin=3907326541; bizuin=3907326541; data_ticket=mVf5k7LxBB/iW6XQUFd5VBqmLW9TYc8GLAsKf7dGMJrc8V0FzH0k74fcLmtoPaT/; slave_sid=anE3MnY2ZnpKMnZuRzU0OGVrX3hOd1pQSVFCdkI0eEI2QklBTmd0YW1YUHpnc3pFVlAxSUhzZWpDbGwyNUJ2X1Z4ZU85Y29MQnhXU2d2NnNCeUhOR3RBMTZUYXhtMDdHeE9acjVLano5eG1qbFhVU0c5enlEQWNpNnhpTDB5N1NGZGFHMXpISE5OZGI3aTJX; slave_user=gh_8f2c3072b8fa; xid=cd68db73eb8548171025d98618200932",
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.62 Safari/537.36",
}

"""
需要提交的data
以下个别字段是否一定需要还未验证。
注意修改yourtoken,number
number表示从第number页开始爬取，为5的倍数，从0开始。如0、5、10……
token可以使用Chrome自带的工具进行获取
fakeid是公众号独一无二的一个id，等同于后面的__biz
"""
data = {
    "token": "2038225367",
    "lang": "zh_CN",
    "f": "json",
    "ajax": "1",
    "action": "list_ex",
    "begin": "0",
    "count": "5",
    "query": "",
    "fakeid": "MzI2NzI2OTExNA==",
    "type": "9",
}

# 使用get方法进行提交
content_json = requests.get(url, headers=headers, params=data).json()
# 返回了一个json，里面是每一页的数据
for item in content_json["app_msg_list"]:
    # 提取每页文章的标题及对应的url
    print(item)