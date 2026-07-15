import requests
import os

# ============ 环境变量读取密钥（不要直接写死代码） ============
ALAPI_TOKEN = os.getenv("ALAPI_TOKEN")
WX_APPID = os.getenv("WX_APPID")
WX_APPSECRET = os.getenv("WX_APPSECRET")
WX_OPENID = os.getenv("WX_OPENID")
WX_TEMPLATE_ID = os.getenv("WX_TEMPLATE_ID")

def get_daily_news():
    """调用ALAPI 获取每日早报"""
    url = f"https://v3.alapi.cn/api/zaobao?token={ALAPI_TOKEN}&format=json"
    resp = requests.get(url, timeout=20)
    res = resp.json()
    if res.get("code") != 200:
        raise Exception(f"新闻接口异常：{res}")
    return res["data"]

def get_wechat_access_token():
    """获取公众号access_token"""
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={WX_APPID}&secret={WX_APPSECRET}"
    resp = requests.get(url, timeout=20)
    data = resp.json()
    if "access_token" not in data:
        raise Exception(f"获取微信token失败 {data}")
    return data["access_token"]

def send_wx_template(news_data):
    """发送模板消息到微信"""
    access_token = get_wechat_access_token()
    send_url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}"

    post_body = {
        "touser": WX_OPENID,
        "template_id": WX_TEMPLATE_ID,
        "data": {
            "date": {"value": news_data["date"]},
            "summary": {"value": news_data["summary"]},
            "news": {"value": news_data["news"]},
            "tip": {"value": news_data["tip"]}
        }
    }
    resp = requests.post(send_url, json=post_body, timeout=20)
    result = resp.json()
    print("推送返回结果：", result)
    if result["errcode"] != 0:
        raise Exception(f"消息推送失败：{result}")

if __name__ == "__main__":
    news_info = get_daily_news()
    send_wx_template(news_info)
    print("✅任务执行完毕，消息已发起推送")
