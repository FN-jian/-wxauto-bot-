# -wxauto-bot-
wxauto bot是一款基于wxauto库开发的自动化脚本
# 1.知识库服务api
基础URL: http://localhost:6000
 
# 2.添加知识条目
添加新的知识到数据库
端点 ：POST /db/add

#请求json参数

{
    "key": "知识关键词",
    "content": "知识内容"
}


# 3.搜索知识条目
根据查询检索相关知识
端点 ：POST /db/search
#请求json参数

{
    "query": "搜索查询"
}

# 4.deepseek大模型调用
处理用户问题并返回回答
端点 ：POST /ai/ask

#请求json参数

{
    "question": "你的问题"
}

响应字段说明
• reply: AI生成的回答内容


• used_knowledge: 使用的知识库内容（数组）


• keywords_used: 

#常见错误码
状态码      含义            可能原因
400        请求参数错误     缺少必要参数或参数格式不正确


500        服务器内部错误   服务端处理异常


503        服务不可用       依赖服务（如DeepSeek API）不可用


#环境要求
• Python 3.8+

• Flask

• SQLite3

自行安装所需要的库

启动 数据库.py

将 服务器端中的DEEPSEEK_API_KEY =    加上自己的deepseek api秘钥  ，编辑ai人格
启动 服务器端.py

使用python代码：

print(requests.post('http://localhost:5000/ai/ask', json={'question': '你的问题'}).json()['reply'])

来提问，随后控制台会print返回的回答


以下代码可以增加知识条目

import requests

# 添加知识
requests.post('http://localhost:6000/db/add', json={
    'key': '关键提示词',
    'content': '内容'
})

# 查看关键词

keywords = requests.get('http://localhost:6000/db/keywords').json()
print("关键词列表:", keywords['keywords'])

以下代码可以提问

# 包含关键词的问题

response = requests.post('http://localhost:5000/ai/ask', json={
    'question': '关键词问题'
})


print("回复:", response.json()['reply'])

# 不包含关键词的问题
response = requests.post('http://localhost:5000/ai/ask', json={
    'question': '问题'
})

print("回复:", response.json()['reply'])

print("是否使用关键词:", response.json()['keywords_used'])



#5. 最佳实践

知识添加：
使用简洁明确的关键词

内容长度建议在50-500字符之间

避免添加重复知识

提问技巧：

问题应包含知识库中的关键词

避免过于模糊的问题

复杂问题可拆分为多个简单问题

错误处理：

客户端应处理400和500错误

重试机制建议间隔2秒

监控API响应时间


#8. 限制说明

知识库服务：

最大知识条目数：10,000

单条内容最大长度：2,000字符

AI服务：

最大问题长度：500字符

最大回复长度：1,000字符

请求频率限制：60次/分钟（按IP）

#最重要的！！！
监听端使用方法：

输入了自己的微信名称后，当有人@自己时，就会唤起ai

/api chat 使用普通api回复

/local chat 使用本地服务器回复（需要数据库端和服务器端启动）

/help 查看指令








