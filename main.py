import requests
import os

# ============ 环境变量密钥 ============
ALAPI_TOKEN = os.getenv("ALAPI_TOKEN")
WX_APPID = os.getenv("WX_APPID")
WX_APPSECRET = os.getenv("WX_APPSECRET")
WX_OPENID = os.getenv("WX_OPENID")
WX_TEMPLATE_ID = os.getenv("WX_TEMPLATE_ID")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")


def get_daily_news():
    """获取ALAPI完整原始早报数据"""
    url = f"https://v3.alapi.cn/api/zaobao?token={ALAPI_TOKEN}&format=json"
    resp = requests.get(url, timeout=30)
    res = resp.json()
    print("ALAPI原始返回：", res)
    if res.get("code") != 200:
        raise Exception(f"早报接口异常 {res}")
    return res["data"]


def ai_sort_news(raw_news_list):
    """调用智谱 glm-4-flash 永久免费模型整理新闻"""
    raw_text = "\n".join(raw_news_list)

    prompt = f"""
【角色】
专业资讯编辑，仅负责新闻的格式优化与语句润色。

【必须遵守的规则】
1. 完整保留全部新闻条目，不得删减任何一条，不得修改新闻事实
2. 去除每条新闻首尾多余的标点、符号、无效空格，使语句通顺自然
3. 严格使用「1. 2. 3.」有序列表输出，每条新闻单独占一行，序号连续
4. 禁止输出任何额外内容：不得加开场白、结束语、总结、评论、补充说明
5. 不添加主观解读，不扩展信息，只做格式和表达优化

【原始早报内容】
{raw_text}
"""

    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "glm-4-flash",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2000
    }

    try:
        resp = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers=headers,
            json=payload,
            timeout=90
        )
        result = resp.json()
        print("智谱AI返回结果：", result)

        if "choices" not in result:
            raise Exception(f"智谱接口返回异常：{result}")

        content = result["choices"][0]["message"]["content"].strip()
        return content

    except Exception as e:
        print(f"AI整理失败，降级使用原始内容：{e}")
        return "\n".join(raw_news_list)


def get_wechat_access_token():
    """获取公众号access_token"""
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={WX_APPID}&secret={WX_APPSECRET}"
    resp = requests.get(url, timeout=20)
    data = resp.json()
    if "access_token" not in data:
        raise Exception(f"获取微信Token失败 {data}")
    return data["access_token"]


def send_wx_template(date_str, ai_content, weiyu):
    """推送模板消息到微信"""
    access_token = get_wechat_access_token()
    send_url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}"
    post_body = {
        "touser": WX_OPENID,
        "template_id": WX_TEMPLATE_ID,
        "data": {
            "date": {"value": date_str},
            "summary": {"value": "📰AI整理今日完整热点资讯"},
            "news": {"value": ai_content},
            "tip": {"value": weiyu}
        }
    }
    resp = requests.post(send_url, json=post_body, timeout=30)
    result = resp.json()
    print("微信推送结果：", result)
    if result["errcode"] != 0:
        raise Exception(f"推送失败 {result}")


if __name__ == "__main__":
    news_data = get_daily_news()
    raw_news = news_data["news"]
    tidy_news = ai_sort_news(raw_news)
    send_wx_template(
        date_str=news_data["date"],
        ai_content=tidy_news,
        weiyu=news_data["weiyu"]
    )
    print("✅全部流程执行完成！")
